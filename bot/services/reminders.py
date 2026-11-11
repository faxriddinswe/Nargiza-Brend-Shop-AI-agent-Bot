"""Debt reminders to customers (BR-161…168) and the 08:00 call list (BR-180).

Schedule (owner decisions, Q-20/Q-21): sent every day at 10:00, no day off; one message per customer
with the sections on separate lines. Per debt that has a due date and is still open:
  - 2 days before (kind `before`), on the due day (`due`), then every 3 days after, at most 5 times (`overdue` seq 1…5).
`reminders_log` has UNIQUE(debt_id, kind, seq): a reminder can never be sent twice. If the bot was down, the
latest missed step is sent once (never a burst of old ones). Debts without a due date get no reminder (BR-052).
Reminders go out even when the customer turned promotions off (BR-164).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import BigInteger, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Customer, Debt, LedgerStatus, ReminderLog, Section, User
from bot.services import ledger

BEFORE_DAYS = 2
OVERDUE_EVERY = 3
OVERDUE_MAX = 5


@dataclass(frozen=True, slots=True)
class Step:
    debt_id: int
    kind: str  # before | due | overdue
    seq: int


@dataclass(slots=True)
class Reminder:
    customer_id: int
    chat_id: int
    name: str
    form: str
    lines: list[tuple[str, int, date, str]] = field(
        default_factory=list
    )  # (section code, remaining, due, kind)
    steps: list[Step] = field(default_factory=list)


def step_for(due: date, today: date) -> tuple[str, int] | None:
    """Which reminder step applies today for a debt due on `due` (None = nothing today)."""
    delta = (due - today).days
    if 0 < delta <= BEFORE_DAYS:
        return ("before", 0)
    if delta == 0:
        return ("due", 0)
    if delta < 0:
        seq = (-delta) // OVERDUE_EVERY
        if 1 <= seq <= OVERDUE_MAX:
            return ("overdue", seq)
    return None


async def due_reminders(session: AsyncSession, today: date) -> list[Reminder]:
    """Reminders to send now: only reachable customers (registered, bot not blocked), grouped one per customer."""
    paid = ledger.paid_subquery()
    remaining = Debt.total_amount - func.coalesce(paid.c.paid, 0)
    horizon = today + timedelta(days=BEFORE_DAYS)
    earliest = today - timedelta(days=OVERDUE_EVERY * (OVERDUE_MAX + 1))
    rows = (
        await session.execute(
            select(Debt.id, Debt.customer_id, Section.code, cast(remaining, BigInteger), Debt.due_date,
                   Customer.name, Customer.address_form, User.telegram_id)
            .join(Customer, Customer.id == Debt.customer_id)
            .join(User, User.id == Customer.user_id)
            .join(Section, Section.id == Debt.section_id)
            .outerjoin(paid, paid.c.debt_id == Debt.id)
            .where(
                Debt.status == LedgerStatus.ACTIVE,
                remaining > 0,
                Debt.due_date.is_not(None),
                Debt.due_date.between(earliest, horizon),
                Customer.deleted_at.is_(None),
                User.is_blocked.is_(False),
                User.bot_blocked_at.is_(None),
            )
            .order_by(Debt.customer_id, Debt.due_date, Debt.id)
        )
    ).all()  # fmt: skip
    candidates: list[tuple[int, int, str, int, date, str, str, int, tuple[str, int]]] = []
    for debt_id, cid, code, rem, due, name, form, chat in rows:
        step = step_for(due, today) if due is not None else None
        if step is not None and due is not None:
            candidates.append((debt_id, cid, code, int(rem), due, name, form, chat, step))
    if not candidates:
        return []
    done = {
        (d, k, s)
        for d, k, s in (
            await session.execute(
                select(ReminderLog.debt_id, ReminderLog.kind, ReminderLog.seq).where(
                    ReminderLog.debt_id.in_([c[0] for c in candidates])
                )
            )
        ).all()
    }
    out: dict[int, Reminder] = {}
    for debt_id, cid, code, rem, due, name, form, chat, (kind, seq) in candidates:
        if (debt_id, kind, seq) in done:
            continue
        r = out.setdefault(cid, Reminder(cid, chat, name, form))
        r.lines.append((code, rem, due, kind))
        r.steps.append(Step(debt_id, kind, seq))
    return list(out.values())


async def mark_sent(session: AsyncSession, reminder: Reminder) -> None:
    """Record the reminder (call it right after Telegram accepted the message)."""
    for st in reminder.steps:
        session.add(
            ReminderLog(
                debt_id=st.debt_id, customer_id=reminder.customer_id, kind=st.kind, seq=st.seq
            )
        )
    await session.flush()


# ---------------------------------------------------------------- 08:00 call list (BR-180)
@dataclass(slots=True)
class CallItem:
    name: str
    form: str
    phone: str | None
    section: str
    amount: int
    days_overdue: int = 0
    due: date | None = None


@dataclass(slots=True)
class CallList:
    overdue: list[CallItem]
    no_phone: list[CallItem]
    no_due: list[CallItem]

    @property
    def empty(self) -> bool:
        return not (self.overdue or self.no_phone or self.no_due)


async def call_list(session: AsyncSession, today: date) -> CallList:
    """Who to phone today: overdue debts, debtors without a phone (Q-35: debtors only), debts with no due date."""
    paid = ledger.paid_subquery()
    remaining = Debt.total_amount - func.coalesce(paid.c.paid, 0)
    rows = (
        await session.execute(
            select(Customer.id, Customer.name, Customer.address_form, Customer.phone, Section.code,
                   cast(remaining, BigInteger), Debt.due_date)
            .join(Customer, Customer.id == Debt.customer_id)
            .join(Section, Section.id == Debt.section_id)
            .outerjoin(paid, paid.c.debt_id == Debt.id)
            .where(Debt.status == LedgerStatus.ACTIVE, remaining > 0)
            .order_by(Debt.due_date.asc().nulls_last(), Debt.id)
        )
    ).all()  # fmt: skip
    cl = CallList([], [], [])
    no_phone: dict[tuple[int, str], CallItem] = {}
    for cid, name, form, phone, code, rem, due in rows:
        item = CallItem(
            name, form, phone, code, int(rem), (today - due).days if due and due < today else 0, due
        )
        if due is None:
            cl.no_due.append(item)
        elif due < today:
            cl.overdue.append(item)
        if phone is None:
            known = no_phone.get((cid, code))
            if known is None:
                no_phone[(cid, code)] = CallItem(name, form, None, code, int(rem))
            else:
                known.amount += int(rem)  # the whole debt of this customer in this section
    cl.no_phone = sorted(no_phone.values(), key=lambda i: -i.amount)
    return cl
