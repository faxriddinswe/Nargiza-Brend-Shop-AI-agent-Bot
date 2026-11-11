"""Oxirgi router: hech kim ushlamagan tugma bosishlariga javob (tugmadagi "yuklanmoqda" to'xtaydi)."""

from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery

router = Router(name="fallback")


@router.callback_query()
async def unhandled_callback(cb: CallbackQuery) -> None:
    await cb.answer()
