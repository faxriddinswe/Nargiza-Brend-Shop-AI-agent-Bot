"""Oxirgi router: hech kim ushlamagan tugma bosishlariga javob (tugmadagi "yuklanmoqda" to'xtaydi)."""

from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from bot.db.models import Role, User
from bot.keyboards import common as kb
from bot.texts import uz_latn as t

router = Router(name="fallback")


@router.message()
async def unhandled_message(message: Message, user: User) -> None:
    """Any unrecognized message: re-show the persistent menu so buttons are always visible."""
    if user.phone is None:
        await message.answer(t.PLEASE_START)
        return
    await message.answer(t.UNKNOWN_INPUT, reply_markup=kb.menu_for(Role(user.role)))


@router.callback_query()
async def unhandled_callback(cb: CallbackQuery) -> None:
    await cb.answer()
