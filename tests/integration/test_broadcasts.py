"""Announcement audiences: promotions-off respected only for 'everyone'; blocked never; text limit; history row."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, Broadcast, Customer, User
from bot.db.session import read_session, uow
from bot.services import broadcasts, ledger
from bot.services import customers as cust
from bot.services.ledger import ItemInput

SM = async_sessionmaker[AsyncSession]
D0 = date(2026, 11, 1)


async def _world(sm: SM) -> tuple[User, dict[str, Customer]]:
    now = datetime.now(UTC)
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=1, role="staff"))
        for tid, kw in (
            (101, {}),
            (102, {"ads_opt_out": True}),
            (103, {"bot_blocked_at": now}),
            (104, {}),
        ):
            s.add(User(telegram_id=tid, role="customer", consent_at=now, **kw))
    async with read_session(sm) as s:
        st = (await s.scalars(select(User).where(User.telegram_id == 1))).one()
        users = {u.telegram_id: u.id for u in await s.scalars(select(User))}
        cats = {c.name: c.id for c in await ledger.categories(s)}
    out: dict[str, Customer] = {}
    async with uow(sm, actor_id=st.id) as s:
        for key, tid, phone in (
            ("a", 101, "+998900000101"),
            ("b", 102, "+998900000102"),
            ("c", 103, "+998900000103"),
        ):
            c = await cust.create(
                s, st, name=key.upper() * 3, address_form=AddressForm.OPA, raw_phone=phone
            )
            await s.execute(update(Customer).where(Customer.id == c.id).values(user_id=users[tid]))
            out[key] = c
        for key, due in (
            ("a", D0 + timedelta(days=10)),
            ("b", D0 + timedelta(days=1)),
            ("c", D0 + timedelta(days=1)),
        ):
            await ledger.create_debts(
                s,
                st,
                customer_id=out[key].id,
                items=[ItemInput(cats["ko'ylak"], 1, 100_000)],
                due_date=due,
                today=D0,
            )
    return st, out


async def _aud(sm: SM, seg: str, cid: int | None = None) -> set[int]:
    async with read_session(sm) as s:
        return {
            r.chat_id
            for r in await broadcasts.audience(s, seg, D0 + timedelta(days=5), customer_id=cid)
        }


async def test_everyone_skips_promotions_off_and_blocked(sm: SM) -> None:
    await _world(sm)
    assert await _aud(sm, "all") == {101, 104}  # 102 turned ads off, 103 blocked the bot


async def test_debt_segments_ignore_promotions_off_but_not_blocked(sm: SM) -> None:
    _, c = await _world(sm)
    assert await _aud(sm, "debtors") == {101, 102}  # 103 unreachable
    assert await _aud(sm, "overdue") == {102}  # only b is past due on day 6
    assert await _aud(sm, "one", c["b"].id) == {102}  # personal message: ads setting irrelevant
    assert await _aud(sm, "one", c["c"].id) == set()


async def test_text_limit_history_and_unknown_segment(sm: SM) -> None:
    st, _ = await _world(sm)
    with pytest.raises(broadcasts.BroadcastError):
        broadcasts.check_text("x" * 1001)
    assert broadcasts.check_text("  ") is None
    async with uow(sm, actor_id=st.id) as s:
        bid = await broadcasts.start(s, st, segment="all", has_photo=False, recipients=2)
        await broadcasts.finish(s, bid, delivered=1, blocked=1)
    async with read_session(sm) as s:
        row = (await s.scalars(select(Broadcast))).one()
        assert (row.recipients, row.delivered, row.blocked) == (2, 1, 1)
    with pytest.raises(broadcasts.BroadcastError):
        async with read_session(sm) as s:
            await broadcasts.audience(s, "everybody", D0)
