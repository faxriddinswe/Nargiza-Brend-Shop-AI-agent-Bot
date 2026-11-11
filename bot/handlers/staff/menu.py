"""Xodim menyusi (master 13). Funksiyalar 2-bosqichdan boshlab qo'shiladi."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Role
from bot.db.session import read_session
from bot.middlewares.auth import RoleFilter
from bot.services import inventory
from bot.texts import uz_latn as t

router = Router(name="staff")
router.message.filter(RoleFilter(Role.STAFF, Role.ADMIN))

_SOON = {t.BTN_STAFF_REPORT, t.BTN_STAFF_BROADCAST}


@router.message(F.text.in_(_SOON))
async def coming_soon(message: Message) -> None:
    await message.answer(t.COMING_SOON)


@router.message(F.text == t.BTN_STAFF_SALE)
async def sale_help(message: Message) -> None:
    await message.answer(t.BTN_SALE_HELP)


@router.message(F.text == t.BTN_STAFF_STOCK)
async def stock_overview(message: Message, sm: async_sessionmaker[AsyncSession]) -> None:
    async with read_session(sm) as s:
        rows = await inventory.levels(s)
    if not any(r.qty for r in rows):
        await message.answer(t.STOCK_EMPTY)
        return
    await message.answer(t.stock_list([(r.section_code, r.name, r.qty, r.threshold) for r in rows]))
