"""One handler for every confirmation card (BR-100…BR-103): ✅ runs the action, ❌ cancels it.

The whole action + marking the card `done` is ONE transaction; a double tap or two staff tapping at the
same time still writes once (pending.claim takes a row lock).
"""

from __future__ import annotations

import structlog
from aiogram import Bot, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Role, User
from bot.db.session import uow
from bot.handlers.staff.actions import execute
from bot.keyboards import common as kb
from bot.middlewares.auth import RoleFilter
from bot.services import customers as cust
from bot.services import ledger, pending, returns, sales
from bot.services import staff as staff_svc
from bot.services import users as users_svc
from bot.services.allocation import AllocationError
from bot.services.sale_math import SaleMathError
from bot.texts import uz_latn as t
from bot.utils.guards import required

log = structlog.get_logger(__name__)
router = Router(name="confirm")
router.callback_query.filter(RoleFilter(Role.STAFF, Role.ADMIN))

SM = async_sessionmaker[AsyncSession]

# error type → alert text shown to the user (the card stays open so they can retry or cancel)
_ALERTS: tuple[tuple[type[Exception], str], ...] = (
    (pending.PendingExpiredError, t.CARD_EXPIRED),
    (pending.PendingForbiddenError, t.CARD_NOT_YOURS),
    (staff_svc.StaffExistsError, t.STAFF_EXISTS),
    (cust.PhoneTakenError, t.PHONE_TAKEN),
    (ledger.PlanChangedError, t.PAY_CHANGED),
    (ledger.DueDatePassedError, t.DUE_PASSED),
    (AllocationError, t.PAY_CHANGED),
    (ledger.DebtHasPaymentsError, t.CANCEL_HAS_PAYMENTS),
    (ledger.DebtHasReturnsError, t.CANCEL_HAS_RETURNS),
    (sales.SaleHasReturnsError, t.CANCEL_HAS_RETURNS),
    (returns.ReturnError, t.PAY_CHANGED),
    (SaleMathError, t.PAY_CHANGED),
    (ledger.AlreadyCancelledError, t.CANCEL_ALREADY),
    (cust.CustomerNotFoundError, t.CUSTOMER_NOT_FOUND),
    (cust.NotAllowedError, t.CARD_NOT_YOURS),
    (staff_svc.NotAdminError, t.CARD_NOT_YOURS),
    (staff_svc.StaffError, t.STAFF_NOT_LINKED),
)


@router.callback_query(kb.PendingCb.filter())
async def on_pending(
    cb: CallbackQuery, callback_data: kb.PendingCb, user: User, sm: SM, bot: Bot
) -> None:
    msg = cb.message if isinstance(cb.message, Message) else None
    if not callback_data.ok:
        async with uow(sm, actor_id=user.id) as s:
            await pending.cancel(s, callback_data.key, user_id=user.id)
        await cb.answer()
        if msg:
            await msg.edit_text(t.CANCELLED)
        return

    try:
        async with uow(sm, actor_id=user.id) as s:
            actor = required(await s.get(User, user.id), "user")
            pa = await pending.claim(s, callback_data.key, user_id=user.id)
            if isinstance(pa, pending.AlreadyDone):
                await cb.answer(t.CARD_ALREADY_DONE)
                return
            text, notify = await execute(s, actor, pa.action, pa.payload)
            pending.complete(pa, {"text": text})
    except pending.PendingError as exc:
        if isinstance(exc, pending.PendingExpiredError):
            await cb.answer(t.CARD_EXPIRED, show_alert=True)
        elif isinstance(exc, pending.PendingForbiddenError):
            await cb.answer(t.CARD_NOT_YOURS, show_alert=True)
        else:
            await cb.answer(t.CANCELLED)
        return
    except Exception as exc:
        for etype, alert in _ALERTS:
            if isinstance(exc, etype):
                if isinstance(exc, ledger.PlanChangedError | AllocationError):
                    log.info("confirm_plan_changed")
                await cb.answer(alert, show_alert=True)
                return
        raise
    await cb.answer()
    if msg:
        await msg.edit_text(text)
    for chat_id, note in notify:
        try:
            await bot.send_message(chat_id, note)
        except TelegramForbiddenError:
            async with uow(sm, actor_kind="system") as s:
                await users_svc.mark_bot_blocked(s, chat_id)
        except Exception:
            log.warning("notify_failed")
