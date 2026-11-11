"""Xodim menyusi (master 13). Funksiyalar 2-bosqichdan boshlab qo'shiladi."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from bot.db.models import Role
from bot.middlewares.auth import RoleFilter
from bot.texts import uz_latn as t

router = Router(name="staff")
router.message.filter(RoleFilter(Role.STAFF, Role.ADMIN))

_SOON = {
    t.BTN_STAFF_DEBT,
    t.BTN_STAFF_SALE,
    t.BTN_STAFF_PAYMENT,
    t.BTN_STAFF_SEARCH,
    t.BTN_STAFF_REPORT,
    t.BTN_STAFF_STOCK,
    t.BTN_STAFF_BROADCAST,
    t.BTN_STAFF_MORE,
}


@router.message(F.text.in_(_SOON))
async def coming_soon(message: Message) -> None:
    await message.answer(t.COMING_SOON)
