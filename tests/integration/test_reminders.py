"""Debt reminders: schedule, no duplicates, one message per customer, unreachable customers → call list."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, Customer, PaymentKind, User
from bot.db.session import read_session, uow
from bot.scheduler import jobs
from bot.services import customers as cust
from bot.services import ledger, reminders
from bot.services.ledger import ItemInput

SM = async_sessionmaker[AsyncSession]
D0 = date(2026, 11, 1)


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


def test_step_schedule() -> None:
    due = date(2026, 11, 10)
    f = reminders.step_for
    assert f(due, date(2026, 11, 7)) is None  # 3 days before: too early
    assert f(due, date(2026, 11, 8)) == ("before", 0)
    assert f(due, date(2026, 11, 10)) == ("due", 0)
    assert f(due, date(2026, 11, 11)) is None  # 1 day after: wait
    assert f(due, date(2026, 11, 13)) == ("overdue", 1)
    assert f(due, date(2026, 11, 25)) == ("overdue", 5)
    assert f(due, date(2026, 11, 28)) is None  # at most 5 overdue reminders


async def _world(sm: SM, *, registered: bool = True) -> tuple[User, Customer, dict[str, int]]:
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=1, role="staff"))
        if registered:
            s.add(User(telegram_id=500, role="customer", phone="+998900000777"))
    async with read_session(sm) as s:
        st = (await s.scalars(select(User).where(User.telegram_id == 1))).one()
        cats = {c.name: c.id for c in await ledger.categories(s)}
    async with uow(sm, actor_id=st.id) as s:
        c = await cust.create(
            s, st, name="Umida", address_form=AddressForm.OPA, raw_phone="+998900000777"
        )
        if registered:
            cu = (await s.scalars(select(User).where(User.telegram_id == 500))).one()
            await s.execute(update(Customer).where(Customer.id == c.id).values(user_id=cu.id))
    return st, c, cats


async def _debt(sm: SM, st: User, c: Customer, cat: int, amount: int, due: date) -> int:
    async with uow(sm, actor_id=st.id) as s:
        [d] = await ledger.create_debts(
            s, st, customer_id=c.id, items=[ItemInput(cat, 1, amount)], due_date=due, today=D0
        )
    return d.debt_id


async def test_one_message_per_customer_with_both_sections_and_no_duplicates(sm: SM) -> None:
    st, c, cats = await _world(sm)
    due = D0 + timedelta(days=9)
    await _debt(sm, st, c, cats["ko'ylak"], 300_000, due)
    await _debt(sm, st, c, cats["ichki kiyim"], 80_000, due)
    bot = FakeBot()
    day = due - timedelta(days=2)
    assert await jobs.send_reminders(bot, sm, today=day) == 1  # ONE message
    assert len(bot.sent) == 1 and "Do'kon" in bot.sent[0][1] and "Ichki kiyim" in bot.sent[0][1]
    assert await jobs.send_reminders(bot, sm, today=day) == 0  # same day again: nothing
    assert await jobs.send_reminders(bot, sm, today=due) == 1  # the due day is a new step
    assert "Bugun" in bot.sent[-1][1]


async def test_paid_debt_gets_no_reminder_and_partial_shows_remaining(sm: SM) -> None:
    st, c, cats = await _world(sm)
    due = D0 + timedelta(days=5)
    await _debt(sm, st, c, cats["ko'ylak"], 300_000, due)
    async with uow(sm, actor_id=st.id) as s:
        sid = (await ledger.section_ids(s))["shop"]
        await ledger.record_payment(
            s,
            st,
            customer_id=c.id,
            section_id=sid,
            amount=100_000,
            kind=PaymentKind.PAYMENT,
            today=D0,
        )
    bot = FakeBot()
    await jobs.send_reminders(bot, sm, today=due)
    assert "200 000" in bot.sent[0][1]
    async with uow(sm, actor_id=st.id) as s:
        await ledger.record_payment(
            s,
            st,
            customer_id=c.id,
            section_id=sid,
            amount=200_000,
            kind=PaymentKind.PAYMENT,
            today=D0,
        )
    assert await jobs.send_reminders(bot, sm, today=due + timedelta(days=3)) == 0


async def test_no_due_date_and_unregistered_customers_get_nothing_but_call_list(sm: SM) -> None:
    st, c, cats = await _world(sm, registered=False)
    due = D0 + timedelta(days=3)
    await _debt(sm, st, c, cats["ko'ylak"], 150_000, due)
    async with uow(sm, actor_id=st.id) as s:  # a debt without a due date
        await ledger.create_debts(
            s,
            st,
            customer_id=c.id,
            items=[ItemInput(cats["shim"], 1, 90_000)],
            due_date=None,
            today=D0,
        )
    bot = FakeBot()
    assert await jobs.send_reminders(bot, sm, today=due) == 0  # not on Telegram → nobody to message
    async with read_session(sm) as s:
        cl = await reminders.call_list(s, due + timedelta(days=4))
    assert [i.amount for i in cl.overdue] == [150_000] and cl.overdue[0].days_overdue == 4
    assert [i.amount for i in cl.no_due] == [90_000]
    assert cl.no_phone == []  # has a phone


async def test_blocked_bot_marks_user_and_is_not_retried(sm: SM) -> None:
    from aiogram.exceptions import TelegramForbiddenError
    from aiogram.methods import SendMessage

    st, c, cats = await _world(sm)
    due = D0 + timedelta(days=2)
    await _debt(sm, st, c, cats["ko'ylak"], 150_000, due)

    class Blocked:
        async def send_message(self, chat_id: int, text: str) -> None:
            raise TelegramForbiddenError(SendMessage(chat_id=chat_id, text=text), "blocked")

    assert await jobs.send_reminders(Blocked(), sm, today=due) == 0
    async with read_session(sm) as s:
        u = (await s.scalars(select(User).where(User.telegram_id == 500))).one()
        assert u.bot_blocked_at is not None
    assert await jobs.send_reminders(FakeBot(), sm, today=due) == 0  # now on the call list instead


async def test_morning_call_list_goes_to_staff_once(sm: SM) -> None:
    st, c, cats = await _world(sm)
    due = D0 + timedelta(days=1)
    await _debt(sm, st, c, cats["ko'ylak"], 150_000, due)
    bot = FakeBot()
    day = due + timedelta(days=2)
    assert await jobs.morning_call_list(bot, sm, today=day) == 1
    assert "Muddati o'tganlar" in bot.sent[0][1]
    assert await jobs.morning_call_list(bot, sm, today=day) == 0
