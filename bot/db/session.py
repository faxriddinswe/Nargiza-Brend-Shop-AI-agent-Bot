"""DB ulanishi va "unit of work" (BR-105, BR-106).

Har bir biznes amal:

    async with uow(sessionmaker, actor_id=user.id) as session:
        ...  # yozish
    # chiqishda COMMIT; xato bo'lsa ROLLBACK — hammasi yoki hech narsa

Tranzaksiya boshida `app.actor_id` / `app.actor_kind` o'rnatiladi (`set_config(..., true)` —
faqat shu tranzaksiya uchun, pool'dagi boshqa ulanishlarga o'tmaydi). Audit trigger'i shularni
o'qiydi; aktor berilmagan yozuvni trigger rad etadi.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

ActorKind = Literal["user", "system"]


def make_engine(url: URL | str) -> AsyncEngine:
    # hide_parameters: xato matnlarida (log) SQL parametrlari — telefon, ism — ko'rinmasin
    return create_async_engine(
        url, pool_pre_ping=True, pool_size=5, max_overflow=5, hide_parameters=True
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: commit'dan keyin obyekt maydonlarini o'qish uchun qayta so'rov kerak emas
    return async_sessionmaker(engine, expire_on_commit=False)


async def set_actor(session: AsyncSession, actor_id: int | None, kind: ActorKind) -> None:
    if kind == "user" and actor_id is None:
        raise ValueError("user aktor uchun actor_id kerak")
    await session.execute(
        text(
            "SELECT set_config('app.actor_kind', :kind, true), set_config('app.actor_id', :id, true)"
        ),
        {"kind": kind, "id": "" if actor_id is None else str(actor_id)},
    )


@asynccontextmanager
async def uow(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    actor_id: int | None = None,
    actor_kind: ActorKind = "user",
) -> AsyncIterator[AsyncSession]:
    """Bitta tranzaksiya: muvaffaqiyatda COMMIT, istisno bo'lsa ROLLBACK."""
    async with sessionmaker() as session, session.begin():
        await set_actor(session, actor_id, actor_kind)
        yield session


@asynccontextmanager
async def read_session(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Faqat o'qish uchun (aktor kerak emas, yozishga urinish trigger'da rad etiladi)."""
    async with sessionmaker() as session, session.begin():
        yield session
