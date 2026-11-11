"""Free text and voice from staff → AI agent → confirmation cards / questions (master §8.2).

Flow: message → model picks tool(s) → `ai.dispatcher` validates and resolves everything in code →
a confirmation card (writes), an answer (reads) or a clarifying question with buttons. Nothing is saved
without the ✅ on the card. If the model is down, staff keep working with the buttons.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.ai import dispatcher as ai_dispatch
from bot.ai.base import AIProvider, AIResult, AIUnavailableError, AudioInput, ToolCall, Turn, Usage
from bot.ai.prompts import build_system_prompt
from bot.ai.tools import tool_specs
from bot.config import Settings
from bot.db.models import AiCall, Role, User
from bot.db.session import read_session, uow
from bot.handlers.staff.ledger import MENU_TEXTS
from bot.keyboards import common as kb_common
from bot.keyboards import ledger as kb
from bot.logging_setup import safe_frames
from bot.middlewares.auth import RoleFilter
from bot.services import customers as cust
from bot.services import staff as staff_svc
from bot.services import users as users_svc
from bot.texts import uz_latn as t
from bot.utils.dates import TASHKENT, today_tashkent

log = structlog.get_logger(__name__)
router = Router(name="staff_agent")
router.message.filter(RoleFilter(Role.STAFF, Role.ADMIN))
router.callback_query.filter(RoleFilter(Role.STAFF, Role.ADMIN))

SM = async_sessionmaker[AsyncSession]
CONTEXT_TTL = 15 * 60  # BR-111: the "last customer" is forgotten after 15 minutes of silence
HISTORY_TURNS = 3
MAX_TEXT_CHARS = 1000
_SLOTS = asyncio.Semaphore(4)
ALERT_COOLDOWN = 600
_last_alert = 0.0

PLAIN = F.text & ~F.text.in_(MENU_TEXTS) & ~F.text.startswith("/")


# ------------------------------------------------------------------ entry points
@router.message(StateFilter(None), PLAIN)
async def on_text(
    message: Message,
    user: User,
    state: FSMContext,
    sm: SM,
    ai: AIProvider | None,
    settings: Settings,
    bot: Bot,
) -> None:
    await _process(message, user, state, sm, ai, settings, bot, text=message.text, voice=None)


@router.message(StateFilter(None), F.voice)
async def on_voice(
    message: Message,
    user: User,
    state: FSMContext,
    sm: SM,
    ai: AIProvider | None,
    settings: Settings,
    bot: Bot,
) -> None:
    voice = message.voice
    if voice is None or ai is None:
        await message.answer(t.AI_NOT_CONFIGURED)
        return
    if voice.duration > settings.voice_max_seconds or (voice.file_size or 0) > 2_000_000:
        await message.answer(t.AI_VOICE_TOO_LONG)
        return
    buf = await bot.download(voice)
    data = buf.read() if buf is not None else b""
    if not data:
        await message.answer(t.AI_NOT_UNDERSTOOD)
        return
    await _process(
        message, user, state, sm, ai, settings, bot, text=None, voice=AudioInput(data, "audio/ogg")
    )


@router.callback_query(kb.AiChoiceCb.filter())
async def on_choice(
    cb: CallbackQuery,
    callback_data: kb.AiChoiceCb,
    user: User,
    state: FSMContext,
    sm: SM,
    ai: AIProvider | None,
    settings: Settings,
    bot: Bot,
) -> None:
    await cb.answer()
    msg = cb.message if isinstance(cb.message, Message) else None
    if msg is None:
        return
    data = await state.get_data()
    pend = data.get("ai_pending")
    if (
        not pend
        or pend.get("nonce") != callback_data.n  # a button from an older question
        or not (0 <= callback_data.i < len(pend["patches"]))
        or time.time() - pend["at"] > CONTEXT_TTL
    ):
        await msg.answer(t.AI_CHOICE_EXPIRED)
        return
    await state.update_data(ai_pending=None)
    call = ai_dispatch.with_choice(
        ToolCall(pend["name"], pend["args"], pend.get("fix", {})), pend["patches"][callback_data.i]
    )
    await _run_and_reply(msg, user, state, sm, [call], heard=None)


# ------------------------------------------------------------------ core
async def _process(
    message: Message,
    user: User,
    state: FSMContext,
    sm: SM,
    ai: AIProvider | None,
    settings: Settings,
    bot: Bot,
    *,
    text: str | None,
    voice: AudioInput | None,
) -> None:
    if ai is None:
        await message.answer(t.AI_NOT_CONFIGURED)
        return
    if await _rate_limited(sm, settings, user.id):
        await message.answer(t.AI_SLOW_DOWN)
        return
    if text is not None:
        text = text[:MAX_TEXT_CHARS]
    data = await state.get_data()
    fresh = _is_fresh(data)
    last_id = _fresh_last(data)
    history = [Turn(u, a) for u, a in data.get("ai_history", [])][-HISTORY_TURNS:] if fresh else []

    async with read_session(sm) as s:
        hints = await ai_dispatch.load_hints(s)
        db_user = await s.get(User, user.id)
        staff_name = await staff_svc.actor_label(s, db_user) if db_user else "xodim"
        last_name = None
        if last_id:
            try:
                c = await cust.get(s, int(last_id))
                last_name = f"{c.name} {c.address_form}"
            except cust.CustomerNotFoundError:
                last_id = None
    system = build_system_prompt(
        now=datetime.now(TASHKENT), staff_name=staff_name, categories=hints, last_customer=last_name
    )

    status = await message.answer(t.AI_LISTENING) if voice else None
    started = time.monotonic()
    result: AIResult | None = None
    error: str | None = None
    try:
        result = await ai.decide(
            system=system, text=text, audio=voice, history=history, tools=tool_specs()
        )
    except AIUnavailableError as exc:
        error = str(exc) or "AIUnavailable"
    except Exception as exc:  # never let a vendor bug reach the staff member
        error = type(exc).__name__
        log.error("ai_unexpected_error", error_type=error, frames=safe_frames(exc))
    latency = int((time.monotonic() - started) * 1000)
    if status is not None:
        try:
            await status.delete()
        except Exception:
            log.debug("status_delete_failed")

    await _log_call(sm, settings, ai, user.id, "voice" if voice else "text", result, latency, error)
    if result is None:
        await message.answer(t.AI_DOWN)
        await _alert_admins(bot, sm, error or "?")
        return
    calls = result.calls or ([ToolCall("say", {"text": result.text})] if result.text else [])
    if not calls:
        await message.answer(t.AI_NOT_UNDERSTOOD)
        return
    await _run_and_reply(message, user, state, sm, calls, heard=text)


async def _run_and_reply(
    msg: Message,
    user: User,
    state: FSMContext,
    sm: SM,
    calls: list[ToolCall],
    *,
    heard: str | None,
) -> None:
    data = await state.get_data()
    last = _fresh_last(data)  # BR-111: a customer older than 15 minutes is forgotten
    ctx = ai_dispatch.Context(today=today_tashkent(), last_customer_id=last)
    async with uow(sm, actor_id=user.id) as s:
        actor = await s.get(User, user.id)
        if actor is None:
            return
        outcomes = await ai_dispatch.run_calls(s, actor, calls, ctx)

    skipped = len(calls[: ai_dispatch.MAX_CALLS]) - len(outcomes)
    outcomes_note = t.ai_skipped(skipped) if skipped > 0 else None
    summary: list[str] = []
    new_last = last
    for out, _call in zip(outcomes, calls, strict=False):
        if out.customer_id is not None:
            new_last = out.customer_id
        if out.card is not None:
            await msg.answer(out.text or "", reply_markup=kb_common.confirm(out.card.key))
            summary.append("karta ko'rsatildi")
        elif out.question is not None:
            await _ask(msg, state, out)
            summary.append(out.question)
        elif out.text:
            await msg.answer(out.text)
            summary.append(out.text.splitlines()[0])
    if outcomes_note:
        await msg.answer(outcomes_note)
    history = list(data.get("ai_history", []))
    spoken = heard or next((o.heard for o in outcomes if o.heard), None) or "[ovozli xabar]"
    history.append([spoken[:200], " | ".join(summary)[:200]])
    await state.update_data(
        ai_history=history[-HISTORY_TURNS:], ai_last_customer=new_last, ai_at=time.time()
    )


async def _ask(msg: Message, state: FSMContext, out: ai_dispatch.Outcome) -> None:
    if out.choices and out.resume is not None:
        nonce = secrets.randbelow(1_000_000)
        await state.update_data(
            ai_pending={
                "name": out.resume.name,
                "args": out.resume.args,
                "fix": out.resume.fix,
                "nonce": nonce,
                "patches": [c.patch for c in out.choices],
                "at": time.time(),
            }
        )
        await msg.answer(
            out.question or "", reply_markup=kb.ai_choices(nonce, [c.label for c in out.choices])
        )
    else:
        await msg.answer(out.question or "")


# ------------------------------------------------------------------ logging & alerts
async def _log_call(
    sm: SM,
    settings: Settings,
    ai: AIProvider,
    user_id: int,
    kind: str,
    result: AIResult | None,
    latency: int,
    error: str | None,
) -> None:
    """Sizes, timing and estimated cost only — never the text, audio or any customer data."""
    usage = result.usage if result else Usage()
    cost = None
    if usage.prompt_tokens is not None or usage.output_tokens is not None:
        cost = round(
            (usage.prompt_tokens or 0) * settings.ai_input_usd_per_m
            + (usage.output_tokens or 0) * settings.ai_output_usd_per_m
        )
    try:
        async with uow(sm, actor_id=user_id) as s:
            s.add(
                AiCall(
                    user_id=user_id, kind=kind, provider=ai.provider_name, model=ai.model,
                    prompt_tokens=usage.prompt_tokens, output_tokens=usage.output_tokens,
                    total_tokens=usage.total_tokens, cost_micro_usd=cost, latency_ms=latency,
                    tools=",".join(c.name for c in result.calls) if result else None,
                    success=result is not None, error_type=error,
                )
            )  # fmt: skip
    except Exception:
        log.warning("ai_call_log_failed")


async def _alert_admins(bot: Bot, sm: SM, error: str) -> None:
    """Tell the admins the AI is down — at most once per 10 minutes."""
    global _last_alert
    if time.time() - _last_alert < ALERT_COOLDOWN:
        return
    _last_alert = time.time()
    async with read_session(sm) as s:
        admins = await users_svc.admins(s)
    for adm in admins:
        try:
            await bot.send_message(adm.telegram_id, t.ai_down_alert(error[:60]))
        except Exception:
            log.warning("admin_alert_failed")


async def _rate_limited(sm: SM, settings: Settings, user_id: int) -> bool:
    """Per-user ceiling from the call log (`ai_per_minute`, `ai_per_day`) — protects the budget."""
    now = datetime.now(UTC)
    limits = (
        (timedelta(minutes=1), settings.ai_per_minute),
        (timedelta(days=1), settings.ai_per_day),
    )
    async with read_session(sm) as s:
        for window, limit in limits:
            n = await s.scalar(
                select(func.count())
                .select_from(AiCall)
                .where(AiCall.user_id == user_id, AiCall.created_at > now - window)
            )
            if (n or 0) >= limit:
                return True
    return False


def _is_fresh(data: dict[str, Any]) -> bool:
    return time.time() - float(data.get("ai_at", 0)) <= CONTEXT_TTL


def _fresh_last(data: dict[str, Any]) -> int | None:
    """The last discussed customer — only within the 15-minute window (BR-111), else nobody."""
    last = data.get("ai_last_customer")
    return int(last) if last and _is_fresh(data) else None
