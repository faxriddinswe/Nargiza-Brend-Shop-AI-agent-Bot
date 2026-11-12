"""/daftar — enter the old paper notebook by typing (BR-140…144). Preview → fix → one-tap save."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Role, User
from bot.db.session import read_session, uow
from bot.middlewares.auth import RoleFilter
from bot.services import notebook
from bot.texts import uz_latn as t
from bot.utils.dates import today_tashkent

SM = async_sessionmaker[AsyncSession]
router = Router(name="staff_notebook")
router.message.filter(RoleFilter(Role.STAFF, Role.ADMIN))
router.callback_query.filter(RoleFilter(Role.STAFF, Role.ADMIN))


class Nb(StatesGroup):
    collecting = State()
    editing = State()


class NbCb(CallbackData, prefix="nb"):
    action: str  # save | edit | more | cancel


def _kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for label, action in (
        (t.NB_BTN_SAVE, "save"),
        (t.NB_BTN_EDIT, "edit"),
        (t.NB_BTN_MORE, "more"),
        (t.NB_BTN_CANCEL, "cancel"),
    ):
        b.button(text=label, callback_data=NbCb(action=action))
    b.adjust(2)
    return b.as_markup()


async def _show(target: Message, state: FSMContext, sm: SM) -> None:
    lines: list[str] = (await state.get_data()).get("lines", [])
    async with read_session(sm) as s:
        rows = await notebook.plan(s, lines, today_tashkent())
    await target.answer(
        t.nb_preview(list(rows)) if rows else t.NB_ASK, reply_markup=_kb() if rows else None
    )


@router.message(Command("daftar"))
async def begin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Nb.collecting)
    await state.update_data(lines=[])
    await message.answer(t.NB_ASK)


@router.message(Nb.collecting, F.text, ~F.text.startswith("/"))
async def add_lines(message: Message, state: FSMContext, sm: SM) -> None:
    lines: list[str] = (await state.get_data()).get("lines", [])
    new = [x.strip() for x in (message.text or "").splitlines() if x.strip()]
    if len(lines) + len(new) > notebook.MAX_ROWS:
        await message.answer(t.NB_TOO_MANY)
        return
    await state.update_data(lines=[*lines, *new])
    await _show(message, state, sm)


@router.message(Nb.editing, F.text, ~F.text.startswith("/"))
async def edit_line(message: Message, state: FSMContext, sm: SM) -> None:
    head, _, rest = (message.text or "").strip().partition(" ")
    lines: list[str] = (await state.get_data()).get("lines", [])
    if (
        not (head.isascii() and head.isdigit())
        or not 1 <= int(head) <= len(lines)
        or not rest.strip()
    ):
        await message.answer(t.NB_EDIT_BAD)
        return
    i = int(head) - 1
    if rest.strip() == "-":
        lines.pop(i)
    else:
        lines[i] = rest.strip()
    await state.update_data(lines=lines)
    await state.set_state(Nb.collecting)
    await _show(message, state, sm)


@router.callback_query(NbCb.filter(), StateFilter(Nb.collecting, Nb.editing))
async def on_button(
    cb: CallbackQuery, callback_data: NbCb, state: FSMContext, sm: SM, user: User
) -> None:
    if not isinstance(cb.message, Message):
        return
    await cb.answer()
    if callback_data.action == "cancel":
        await state.clear()
        await cb.message.answer(t.NB_CANCELLED)
    elif callback_data.action == "more":
        await state.set_state(Nb.collecting)
        await cb.message.answer(t.NB_MORE_ASK)
    elif callback_data.action == "edit":
        await state.set_state(Nb.editing)
        await cb.message.answer(t.NB_EDIT_ASK)
    elif callback_data.action == "save":
        lines: list[str] = (await state.get_data()).get("lines", [])
        today = today_tashkent()
        async with read_session(sm) as s:
            rows = await notebook.plan(s, lines, today)
        if not any(r.saved for r in rows):
            await cb.message.answer(t.NB_NOTHING)
            return
        async with uow(
            sm, actor_id=user.id
        ) as s:  # saving is serialised and re-checked inside (see notebook.save)
            res = await notebook.save(s, user, rows, today)
        await state.clear()  # only after success: on an error the typed lines are kept
        await cb.message.answer(t.nb_result(res.debts, res.new_customers, res.skipped, res.total))


@router.callback_query(NbCb.filter())
async def stale(cb: CallbackQuery) -> None:
    await cb.answer(t.NB_EXPIRED, show_alert=True)
