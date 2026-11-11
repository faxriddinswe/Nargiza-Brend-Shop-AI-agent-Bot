"""📢 E'lon: text and/or photo → who → preview ("87 kishiga boradi") → send in a rate-limited queue (BR-170…176)."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Customer, Role, User
from bot.db.session import read_session, uow
from bot.middlewares.auth import RoleFilter
from bot.services import broadcasts
from bot.services import customers as cust
from bot.services import users as users_svc
from bot.texts import uz_latn as t
from bot.utils.dates import today_tashkent
from bot.utils.phone import format_phone

log = structlog.get_logger(__name__)
SM = async_sessionmaker[AsyncSession]
PAUSE = 0.05  # ≈20 messages/second: below Telegram's ~30/second broadcast limit (core.telegram.org/bots/faq)

router = Router(name="staff_broadcast")
router.message.filter(RoleFilter(Role.STAFF, Role.ADMIN))
router.callback_query.filter(RoleFilter(Role.STAFF, Role.ADMIN))


class Bc(StatesGroup):
    content = State()
    segment = State()
    one = State()
    confirm = State()


class SegCb(CallbackData, prefix="bs"):
    seg: str


class OneCb(CallbackData, prefix="bo"):
    id: int


class GoCb(CallbackData, prefix="bg"):
    go: int  # 1 = send, 0 = cancel


def _segments() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for seg, label in (
        ("all", t.BC_SEG_ALL),
        ("debtors", t.BC_SEG_DEBTORS),
        ("overdue", t.BC_SEG_OVERDUE),
        ("one", t.BC_SEG_ONE),
    ):
        b.button(text=label, callback_data=SegCb(seg=seg))
    b.adjust(1)
    return b.as_markup()


def _go() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t.BC_SEND, callback_data=GoCb(go=1))
    b.button(text=t.BC_CANCEL, callback_data=GoCb(go=0))
    b.adjust(2)
    return b.as_markup()


@router.message(F.text == t.BTN_STAFF_BROADCAST)
async def begin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Bc.content)
    await message.answer(t.BC_ASK_CONTENT)


@router.message(Bc.content, F.photo | F.text)
async def got_content(message: Message, state: FSMContext) -> None:
    try:
        text = broadcasts.check_text(message.caption if message.photo else message.text)
    except broadcasts.BroadcastError:
        await message.answer(t.BC_TOO_LONG)
        return
    photo = message.photo[-1].file_id if message.photo else None
    if text is None and photo is None:
        await message.answer(t.BC_ASK_CONTENT)
        return
    await state.update_data(text=text, photo=photo)
    await state.set_state(Bc.segment)
    await message.answer(t.BC_ASK_SEGMENT, reply_markup=_segments())


async def _preview(
    target: Message,
    state: FSMContext,
    sm: SM,
    *,
    segment: str,
    customer_id: int | None = None,
    one_name: str | None = None,
) -> None:
    async with read_session(sm) as s:
        people = await broadcasts.audience(s, segment, today_tashkent(), customer_id=customer_id)
    if not people:
        await target.answer(t.BC_NOBODY)
        return
    data = await state.get_data()
    await state.update_data(segment=segment, customer_id=customer_id)
    await state.set_state(Bc.confirm)
    await target.answer(
        t.bc_preview(segment, len(people), data.get("text"), bool(data.get("photo")), one_name),
        reply_markup=_go(),
    )


@router.callback_query(SegCb.filter(), StateFilter(Bc.segment))
async def pick_segment(cb: CallbackQuery, callback_data: SegCb, state: FSMContext, sm: SM) -> None:
    if not isinstance(cb.message, Message):
        return
    await cb.answer()
    if callback_data.seg == "one":
        await state.set_state(Bc.one)
        await cb.message.answer(t.BC_ASK_ONE)
        return
    await _preview(cb.message, state, sm, segment=callback_data.seg)


@router.message(Bc.one, F.text)
async def find_one(message: Message, state: FSMContext, sm: SM) -> None:
    async with read_session(sm) as s:
        found = await cust.search(s, message.text or "", limit=8)
    if not found:
        await message.answer(t.SEARCH_EMPTY)
        return
    b = InlineKeyboardBuilder()
    for c in found:
        b.button(
            text=f"{c.name} {c.address_form}" + (f" · {format_phone(c.phone)}" if c.phone else ""),
            callback_data=OneCb(id=c.id),
        )
    b.adjust(1)
    await message.answer(t.BC_ASK_ONE, reply_markup=b.as_markup())


@router.callback_query(OneCb.filter(), StateFilter(Bc.one))
async def pick_one(cb: CallbackQuery, callback_data: OneCb, state: FSMContext, sm: SM) -> None:
    if not isinstance(cb.message, Message):
        return
    await cb.answer()
    async with read_session(sm) as s:
        c = await s.get(Customer, callback_data.id)
    name = f"{c.name} {c.address_form}" if c else "?"
    await _preview(
        cb.message, state, sm, segment="one", customer_id=callback_data.id, one_name=name
    )


@router.callback_query(GoCb.filter(), StateFilter(Bc.confirm))
async def go(
    cb: CallbackQuery, callback_data: GoCb, state: FSMContext, sm: SM, bot: Bot, user: User
) -> None:
    if not isinstance(cb.message, Message):
        return
    data: dict[str, Any] = await state.get_data()
    await state.clear()  # one tap = one send (a second tap finds no state)
    await cb.answer()
    if not callback_data.go:
        await cb.message.answer(t.BC_CANCELLED)
        return
    async with read_session(sm) as s:
        people = await broadcasts.audience(
            s, data["segment"], today_tashkent(), customer_id=data.get("customer_id")
        )
    async with uow(sm, actor_id=user.id) as s:
        bid = await broadcasts.start(
            s,
            user,
            segment=data["segment"],
            has_photo=bool(data.get("photo")),
            recipients=len(people),
            customer_id=data.get("customer_id"),
        )
    delivered = blocked = failed = 0
    for p in people:
        try:
            await _send(bot, p.chat_id, data.get("text"), data.get("photo"))
            delivered += 1
        except TelegramForbiddenError:
            blocked += 1
            async with uow(sm, actor_kind="system") as s:
                await users_svc.mark_bot_blocked(s, p.chat_id)
        except Exception as e:
            failed += 1
            log.warning("broadcast_send_failed", error=type(e).__name__)
        await asyncio.sleep(PAUSE)
    async with uow(sm, actor_id=user.id) as s:
        await broadcasts.finish(s, bid, delivered=delivered, blocked=blocked)
    await cb.message.answer(t.bc_result(delivered, blocked, failed))


async def _send(bot: Bot, chat_id: int, text: str | None, photo: str | None) -> None:
    for attempt in (0, 1):
        try:
            if photo:
                await bot.send_photo(chat_id, photo, caption=text)
            else:
                await bot.send_message(chat_id, text or "")
            return
        except TelegramRetryAfter as e:
            if attempt:
                raise
            await asyncio.sleep(min(e.retry_after, 30))


@router.callback_query(GoCb.filter())
@router.callback_query(SegCb.filter())
@router.callback_query(OneCb.filter())
async def stale(cb: CallbackQuery) -> None:
    """Old buttons (a newer announcement was started, or it was already sent)."""
    await cb.answer(t.BC_EXPIRED, show_alert=True)
