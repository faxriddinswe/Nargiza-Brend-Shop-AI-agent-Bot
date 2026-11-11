"""Sozlamalar (kalit-qiymat) va do'kon ma'lumoti (BR-001, BR-003)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Setting

# Sukut qiymatlari (master prompt 1-bo'lim). Sozlamada o'zgartirilsa — bazadagi ustun.
DEFAULTS: dict[str, Any] = {
    "shop.name": "Nargiza Brend",
    "shop.address": "Sherbaraka bozori, 82-do'kon",
    "shop.hours": "07:00 – 18:00",
    "shop.phone": "+998 94 511 17 00",
    "shop.instagram": "@nargiza_17_00_",
    "shop.instagram_url": "https://www.instagram.com/nargiza_17_00_/",
    "shop.photo_file_id": None,
    "shop.location": None,  # {"lat": .., "lon": ..}
    "schedule.weekly_day_off": None,  # BR-003: dam olish kuni yo'q
    "pending.ttl_minutes": 30,  # BR-103
}


async def get(session: AsyncSession, key: str) -> Any:
    value = await session.scalar(select(Setting.value).where(Setting.key == key))
    return DEFAULTS.get(key) if value is None else value


async def set_value(session: AsyncSession, key: str, value: Any, *, actor_id: int | None) -> None:
    row = await session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value, updated_by=actor_id))
    else:
        row.value = value
        row.updated_by = actor_id
    await session.flush()


@dataclass(frozen=True, slots=True)
class ShopInfo:
    name: str
    address: str
    hours: str
    phone: str
    instagram: str
    instagram_url: str
    photo_file_id: str | None
    location: dict[str, float] | None


async def shop_info(session: AsyncSession) -> ShopInfo:
    keys = [k for k in DEFAULTS if k.startswith("shop.")]
    rows: dict[str, Any] = dict(
        (
            await session.execute(select(Setting.key, Setting.value).where(Setting.key.in_(keys)))
        ).all()
    )
    v = {k.removeprefix("shop."): rows.get(k, DEFAULTS[k]) for k in keys}
    return ShopInfo(**v)
