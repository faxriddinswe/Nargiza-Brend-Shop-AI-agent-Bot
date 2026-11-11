"""Har bir xabar/tugma uchun foydalanuvchini aniqlash va bloklashni tekshirish (BR-011, BR-015, BR-018).

Rol HAR SAFAR bazadan o'qiladi — keshlanmaydi. Shunda admin xodimni bloklasa yoki xodimlikdan
olsa, bu keyingi xabardanoq kuchga kiradi.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Role, User
from bot.db.session import uow
from bot.services import users as users_svc
from bot.services.settings import DEFAULTS
from bot.texts import uz_latn as t


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return None
        sm: async_sessionmaker[AsyncSession] = data["sm"]
        async with uow(sm, actor_kind="system") as session:
            user = await users_svc.get_or_create_user(session, tg_user.id, tg_user.first_name)

        if user.is_blocked:
            if isinstance(event, Message):
                await event.answer(t.blocked(DEFAULTS["shop.phone"]))
            elif isinstance(event, CallbackQuery):
                await event.answer(t.blocked(DEFAULTS["shop.phone"]), show_alert=True)
            return None

        data["user"] = user
        return await handler(event, data)


class RoleFilter(Filter):
    """Ruxsat kodda tekshiriladi (BR-018). Masalan: RoleFilter(Role.STAFF, Role.ADMIN)."""

    def __init__(self, *roles: Role) -> None:
        self.roles = {r.value for r in roles}

    async def __call__(self, event: TelegramObject, user: User) -> bool:
        return user.role in self.roles


class RegisteredFilter(Filter):
    async def __call__(self, event: TelegramObject, user: User) -> bool:
        return user.phone is not None
