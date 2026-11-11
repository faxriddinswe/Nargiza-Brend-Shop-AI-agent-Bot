"""Tasdiqlash kartalari va idempotentlik (BR-102, BR-103)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Customer, User
from bot.db.session import read_session, uow
from bot.services import pending

SM = async_sessionmaker[AsyncSession]


async def _user(sm: SM, tg: int = 1) -> int:
    async with uow(sm, actor_kind="system") as s:
        u = User(telegram_id=tg, role="staff")
        s.add(u)
        await s.flush()
        return u.id


async def _card(sm: SM, user_id: int, **kw: Any) -> str:
    async with uow(sm, actor_id=user_id) as s:
        return await pending.create(
            s, user_id=user_id, action="create_customer", payload={"name": "Umida"}, **kw
        )


async def _confirm(sm: SM, key: str, user_id: int) -> str:
    """Tasdiqlash: karta qulflanadi, mijoz yoziladi, karta done — bitta tranzaksiyada."""
    async with uow(sm, actor_id=user_id) as s:
        pa = await pending.claim(s, key, user_id=user_id)
        if isinstance(pa, pending.AlreadyDone):
            return "already"
        await asyncio.sleep(0.05)  # parallel bosish bilan to'qnashuvni kuchaytirish
        s.add(Customer(name=pa.payload["name"], search_name="umida", address_form="opa"))
        pending.complete(pa, {"ok": True})
        return "done"


async def _count(sm: SM) -> int:
    async with read_session(sm) as s:
        return int(await s.scalar(select(func.count()).select_from(Customer)) or 0)


async def test_double_click_writes_once(sm: SM) -> None:
    """BR-102: ikki marta bosish — bitta yozuv."""
    uid = await _user(sm)
    key = await _card(sm, uid)
    assert await _confirm(sm, key, uid) == "done"
    assert await _confirm(sm, key, uid) == "already"
    assert await _count(sm) == 1


async def test_concurrent_clicks_write_once(sm: SM) -> None:
    """BR-102: bir vaqtda ikki bosish (FOR UPDATE) — bitta yozuv."""
    uid = await _user(sm)
    key = await _card(sm, uid)
    results = await asyncio.gather(*(_confirm(sm, key, uid) for _ in range(5)))
    assert sorted(results) == ["already"] * 4 + ["done"]
    assert await _count(sm) == 1


async def test_expired_card_rejected(sm: SM) -> None:
    """BR-103"""
    uid = await _user(sm)
    key = await _card(sm, uid, now=datetime.now(UTC) - timedelta(minutes=31))
    with pytest.raises(pending.PendingExpiredError):
        await _confirm(sm, key, uid)
    assert await _count(sm) == 0


async def test_other_user_cannot_confirm(sm: SM) -> None:
    """BR-103: kartani faqat uni olgan xodim tasdiqlaydi."""
    uid = await _user(sm, 1)
    other = await _user(sm, 2)
    key = await _card(sm, uid)
    with pytest.raises(pending.PendingForbiddenError):
        await _confirm(sm, key, other)


async def test_cancelled_card_cannot_be_confirmed(sm: SM) -> None:
    uid = await _user(sm)
    key = await _card(sm, uid)
    async with uow(sm, actor_id=uid) as s:
        assert await pending.cancel(s, key, user_id=uid) is True
    with pytest.raises(pending.PendingCancelledError):
        await _confirm(sm, key, uid)


async def test_failed_action_keeps_card_open(sm: SM) -> None:
    """Amal xato bersa karta `open` qoladi — qayta urinish mumkin."""
    uid = await _user(sm)
    key = await _card(sm, uid)
    with pytest.raises(RuntimeError):
        async with uow(sm, actor_id=uid) as s:
            pa = await pending.claim(s, key, user_id=uid)
            assert not isinstance(pa, pending.AlreadyDone)
            pending.complete(pa)
            raise RuntimeError("biznes xato")
    assert await _confirm(sm, key, uid) == "done"
