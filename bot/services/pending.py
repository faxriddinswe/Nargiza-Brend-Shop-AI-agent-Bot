"""Tasdiqlash kartalari va idempotentlik (BR-100…BR-103).

Oqim:
1. `create()` — karta ko'rsatilganda: kalit + payload bazaga (`open`, 30 daqiqa).
2. Foydalanuvchi ✅ bosadi → `claim()` shu tranzaksiyada `SELECT ... FOR UPDATE` bilan qatorni
   qulflaydi. Ikkinchi parallel bosish birinchisi tugashini kutadi, keyin `done` holatini ko'radi.
3. Biznes amal bajariladi → `complete()` → `done`. Hammasi BITTA tranzaksiyada: amal muvaffaqiyatsiz
   bo'lsa, karta ham `open` bo'lib qoladi.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import PendingAction, PendingStatus

DEFAULT_TTL = timedelta(minutes=30)  # BR-103


class PendingError(Exception):
    """Kartani tasdiqlab bo'lmaydi."""


class PendingNotFoundError(PendingError):
    pass


class PendingForbiddenError(PendingError):
    """Kartani boshqa odam bosdi."""


class PendingExpiredError(PendingError):
    pass


class PendingCancelledError(PendingError):
    pass


@dataclass(frozen=True, slots=True)
class AlreadyDone:
    """Takroriy bosish: amal avval bajarilgan, natija qaytariladi."""

    result: dict[str, Any] | None


def new_key() -> str:
    # 16 bayt → 22 belgi; callback_data 64 bayt chegarasiga bemalol sig'adi
    return secrets.token_urlsafe(16)


async def create(
    session: AsyncSession,
    *,
    user_id: int,
    action: str,
    payload: dict[str, Any],
    ttl: timedelta = DEFAULT_TTL,
    now: datetime | None = None,
) -> str:
    key = new_key()
    session.add(
        PendingAction(
            key=key,
            user_id=user_id,
            action=action,
            payload=payload,
            expires_at=(now or datetime.now(UTC)) + ttl,
        )
    )
    await session.flush()
    return key


async def claim(
    session: AsyncSession,
    key: str,
    *,
    user_id: int,
    action: str | None = None,
    now: datetime | None = None,
) -> PendingAction | AlreadyDone:
    """Kartani qulflab oladi. `AlreadyDone` — takroriy bosish (yozuv qayta yozilmaydi)."""
    pa = await session.scalar(
        select(PendingAction).where(PendingAction.key == key).with_for_update()
    )
    if pa is None or (action is not None and pa.action != action):
        raise PendingNotFoundError(key)
    if pa.user_id != user_id:
        raise PendingForbiddenError(key)
    if pa.status == PendingStatus.DONE:
        return AlreadyDone(pa.result)
    if pa.status == PendingStatus.CANCELLED:
        raise PendingCancelledError(key)
    if pa.status == PendingStatus.EXPIRED or pa.expires_at <= (now or datetime.now(UTC)):
        pa.status = PendingStatus.EXPIRED
        raise PendingExpiredError(key)
    return pa


def complete(pa: PendingAction, result: dict[str, Any] | None = None) -> None:
    pa.status = PendingStatus.DONE
    pa.result = result
    pa.completed_at = datetime.now(UTC)


async def cancel(session: AsyncSession, key: str, *, user_id: int) -> bool:
    """❌ Bekor qilish. Allaqachon bajarilgan kartani bekor qilib bo'lmaydi."""
    pa = await session.scalar(
        select(PendingAction).where(PendingAction.key == key).with_for_update()
    )
    if pa is None or pa.user_id != user_id or pa.status != PendingStatus.OPEN:
        return False
    pa.status = PendingStatus.CANCELLED
    return True
