"""Nightly integrity check: quiet on clean data, loud on impossible data, admins only, once per day."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Category, PaymentKind, User
from bot.db.session import read_session, uow
from bot.scheduler import jobs
from bot.services import customers as cust
from bot.services import integrity, inventory, ledger, notebook

SM = async_sessionmaker[AsyncSession]
TODAY = date(2026, 11, 11)


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


async def _users(sm: SM) -> User:
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=1, role="staff"))
        s.add(User(telegram_id=2, role="admin"))
    async with read_session(sm) as s:
        return (await s.scalars(select(User).where(User.telegram_id == 1))).one()


async def test_clean_data_has_no_problems(sm: SM) -> None:
    st = await _users(sm)
    async with uow(sm, actor_id=st.id) as s:
        rows = await notebook.plan(s, ["Umida opa, 90 123 45 67, 100 ming, 1.10"], TODAY)
        await notebook.save(s, st, rows, TODAY)
    async with read_session(sm) as s:
        c = await cust.find_by_phone(s, "+998901234567")
        assert c is not None
        shop = (await ledger.section_ids(s))["shop"]
    async with uow(sm, actor_id=st.id) as s:
        await ledger.record_payment(
            s, st, customer_id=c.id, section_id=shop, amount=40_000,
            kind=PaymentKind.PAYMENT, today=TODAY,
        )  # fmt: skip
    async with read_session(sm) as s:
        rep = await integrity.run_checks(s)
    assert rep.ok and (rep.debts, rep.payments) == (1, 1)


async def test_negative_stock_and_duplicate_payment_are_found(sm: SM) -> None:
    st = await _users(sm)
    async with uow(sm, actor_id=st.id) as s:
        rows = await notebook.plan(s, ["Umida opa, 90 123 45 67, 100 ming, 1.10"], TODAY)
        await notebook.save(s, st, rows, TODAY)
    async with read_session(sm) as s:
        c = await cust.find_by_phone(s, "+998901234567")
        assert c is not None
        cat = (await s.scalars(select(Category).where(Category.is_active.is_(True)))).first()
        assert cat is not None
        shop = (await ledger.section_ids(s))["shop"]
    async with uow(sm, actor_id=st.id) as s:
        await inventory.add_movement(
            s, category_id=cat.id, quantity=-3, reason="count_adjustment", actor_id=st.id
        )
        for _ in range(2):  # same customer, amount and day within a minute
            await ledger.record_payment(
                s, st, customer_id=c.id, section_id=shop, amount=10_000,
                kind=PaymentKind.PAYMENT, today=TODAY,
            )  # fmt: skip
    async with read_session(sm) as s:
        codes = {p.code for p in (await integrity.run_checks(s)).problems}
    assert codes == {"negative_stock", "possible_duplicate_payment"}


async def test_job_goes_to_admins_only_and_once_a_day(sm: SM) -> None:
    await _users(sm)
    bot = FakeBot()
    assert await jobs.integrity_check(bot, sm, today=TODAY) == 1
    assert await jobs.integrity_check(bot, sm, today=TODAY) == 0
    assert [c for c, _ in bot.sent] == [2]
    assert "muammo yo'q" in bot.sent[0][1]
