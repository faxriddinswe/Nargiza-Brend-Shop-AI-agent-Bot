"""Debt ledger: debts, payments, write-offs, cancellations, balances (BR-050…BR-067, BR-104).

Concurrency (architect review): every money write locks the customer row first, then that
customer's open debts (`FOR UPDATE`, same order everywhere → no deadlocks). The database
re-checks at COMMIT (deferred triggers), so even a bug here cannot overpay a debt.

Balances are never stored: remaining = total − Σ allocations of active payments.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import BigInteger, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    Category,
    Customer,
    Debt,
    DebtItem,
    LedgerStatus,
    Payment,
    PaymentAllocation,
    PaymentKind,
    Section,
    User,
)
from bot.services import inventory
from bot.services.allocation import Allocation, OpenDebt, allocate
from bot.services.customers import CustomerNotFoundError, require_staff

MAX_ITEMS = 30
MAX_DEBT_TOTAL = 10_000_000_000  # 10 mlrd so'm — anything above is certainly a typo


class LedgerError(Exception):
    pass


class EmptyDebtError(LedgerError):
    pass


class InactiveCategoryError(LedgerError):
    pass


class PlanChangedError(LedgerError):
    """Balances changed between the confirmation card and the tap (another payment came in)."""


class AlreadyCancelledError(LedgerError):
    pass


class DueDatePassedError(LedgerError):
    """The due date on the card is now in the past (card confirmed after midnight)."""


class DebtHasReturnsError(LedgerError):
    """Goods of this record were already taken back — cancel the return first."""


class DebtHasPaymentsError(LedgerError):
    """BR-104 💡: cancel the payments first."""


# ---------------------------------------------------------------- reference data
@dataclass(frozen=True, slots=True)
class CategoryRef:
    id: int
    name: str
    section_id: int
    section_code: str


async def categories(session: AsyncSession, *, active_only: bool = True) -> list[CategoryRef]:
    q = (
        select(Category.id, Category.name, Category.section_id, Section.code)
        .join(Section, Section.id == Category.section_id)
        .order_by(Section.id, Category.id)
    )
    if active_only:
        q = q.where(Category.is_active.is_(True))
    return [CategoryRef(*row) for row in (await session.execute(q)).all()]


async def section_ids(session: AsyncSession) -> dict[str, int]:
    return {
        code: sid for sid, code in (await session.execute(select(Section.id, Section.code))).all()
    }


async def section_codes(session: AsyncSession) -> dict[int, str]:
    return {sid: code for code, sid in (await section_ids(session)).items()}


# ---------------------------------------------------------------- locking & reading
async def lock_customer(session: AsyncSession, customer_id: int) -> Customer:
    c = await session.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    if c is None:
        raise CustomerNotFoundError(customer_id)
    return c


def paid_subquery() -> Any:
    return (
        select(
            PaymentAllocation.debt_id,
            cast(func.sum(PaymentAllocation.amount), BigInteger).label("paid"),
        )
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(Payment.status == LedgerStatus.ACTIVE)
        .group_by(PaymentAllocation.debt_id)
        .subquery()
    )


@dataclass(frozen=True, slots=True)
class DebtView:
    id: int
    section_id: int
    debt_date: date
    due_date: date | None
    total: int
    paid: int
    note: str | None

    @property
    def remaining(self) -> int:
        return self.total - self.paid


async def debts_with_remaining(
    session: AsyncSession,
    customer_id: int,
    *,
    section_id: int | None = None,
    only_open: bool = True,
    lock: bool = False,
) -> list[DebtView]:
    paid = paid_subquery()
    q = (
        select(
            Debt.id,
            Debt.section_id,
            Debt.debt_date,
            Debt.due_date,
            Debt.total_amount,
            func.coalesce(paid.c.paid, 0),
            Debt.note,
        )
        .outerjoin(paid, paid.c.debt_id == Debt.id)
        .where(Debt.customer_id == customer_id, Debt.status == LedgerStatus.ACTIVE)
        .order_by(Debt.debt_date, Debt.id)
    )
    if section_id is not None:
        q = q.where(Debt.section_id == section_id)
    if lock:
        # lock the debt rows (not the aggregate) — order matches FIFO → deterministic lock order
        ids_q = select(Debt.id).where(
            Debt.customer_id == customer_id, Debt.status == LedgerStatus.ACTIVE
        )
        if section_id is not None:
            ids_q = ids_q.where(Debt.section_id == section_id)
        await session.execute(ids_q.order_by(Debt.debt_date, Debt.id).with_for_update())
    # money is ALWAYS int (never Decimal/float): normalise whatever the driver returns
    views = [
        DebtView(did, sid, dd, due, int(total), int(paid_amt), note)
        for did, sid, dd, due, total, paid_amt, note in (await session.execute(q)).all()
    ]
    return [v for v in views if v.remaining > 0] if only_open else views


async def balances(session: AsyncSession, customer_id: int) -> dict[int, int]:
    """section_id → remaining (only sections with debt > 0). BR-055/056."""
    result: dict[int, int] = defaultdict(int)
    for d in await debts_with_remaining(session, customer_id):
        result[d.section_id] += d.remaining
    return dict(result)


# ---------------------------------------------------------------- debts
@dataclass(frozen=True, slots=True)
class ItemInput:
    category_id: int
    quantity: int
    unit_price: int
    note: str | None = None

    @property
    def total(self) -> int:
        return self.quantity * self.unit_price


@dataclass(slots=True)
class CreatedDebt:
    debt_id: int
    section_id: int
    total: int
    items: list[ItemInput] = field(default_factory=list)


def split_by_section(
    items: Sequence[ItemInput], cat_section: dict[int, int]
) -> dict[int, list[ItemInput]]:
    """BR-021/022: section comes from the category; one debt per section."""
    groups: dict[int, list[ItemInput]] = defaultdict(list)
    for it in items:
        if it.category_id not in cat_section:
            raise InactiveCategoryError(it.category_id)
        if it.quantity <= 0 or it.unit_price <= 0:
            raise LedgerError("quantity and price must be positive")
        groups[cat_section[it.category_id]].append(it)
    return dict(groups)


async def create_debts(
    session: AsyncSession,
    actor: User,
    *,
    customer_id: int,
    items: Sequence[ItemInput],
    due_date: date | None,
    today: date,
    note: str | None = None,
) -> list[CreatedDebt]:
    require_staff(actor)
    if not items:
        raise EmptyDebtError
    if due_date is not None and due_date < today:
        raise DueDatePassedError
    if len(items) > MAX_ITEMS or sum(i.total for i in items) > MAX_DEBT_TOTAL:
        raise LedgerError("debt too large")
    customer = await lock_customer(session, customer_id)
    if customer.deleted_at is not None:
        raise CustomerNotFoundError(customer_id)
    cat_section = {c.id: c.section_id for c in await categories(session)}
    created: list[CreatedDebt] = []
    for section_id, group in sorted(split_by_section(items, cat_section).items()):
        total = sum(it.total for it in group)
        debt = Debt(
            customer_id=customer_id,
            section_id=section_id,
            debt_date=today,
            due_date=due_date,
            total_amount=total,
            note=note,
            created_by=actor.id,
        )
        session.add(debt)
        await session.flush()
        session.add_all(
            DebtItem(
                debt_id=debt.id,
                section_id=section_id,
                category_id=it.category_id,
                quantity=it.quantity,
                unit_price=it.unit_price,
                note=it.note,
            )
            for it in group
        )
        created.append(CreatedDebt(debt.id, section_id, total, list(group)))
    await session.flush()
    for c in created:  # Q-26: goods given on credit leave the stock too
        qty: dict[int, int] = {}
        for i in c.items:
            qty[i.category_id] = qty.get(i.category_id, 0) + i.quantity
        for cat_id, n in qty.items():
            await inventory.add_movement(
                session,
                category_id=cat_id,
                quantity=-n,
                reason="debt",
                ref_type="debt",
                ref_id=c.debt_id,
                actor_id=actor.id,
            )
    await session.flush()
    return created


async def set_due_date(session: AsyncSession, actor: User, debt_id: int, due: date | None) -> None:
    require_staff(actor)
    debt = await session.get(Debt, debt_id)
    if debt is None or debt.status != LedgerStatus.ACTIVE:
        raise LedgerError("debt not active")
    debt.due_date = due
    await session.flush()


# ---------------------------------------------------------------- payments / write-offs
@dataclass(frozen=True, slots=True)
class PaymentPlan:
    customer_id: int
    section_id: int
    kind: PaymentKind
    amount: int
    debt_id: int | None
    allocations: tuple[Allocation, ...]
    owed_before: int

    @property
    def owed_after(self) -> int:
        return self.owed_before - self.amount


async def plan_payment(
    session: AsyncSession,
    *,
    customer_id: int,
    section_id: int,
    amount: int,
    kind: PaymentKind = PaymentKind.PAYMENT,
    debt_id: int | None = None,
    lock: bool = False,
) -> PaymentPlan:
    """Preview for the confirmation card (BR-063). Raises OverpaymentError / NothingToPayError."""
    debts = await debts_with_remaining(session, customer_id, section_id=section_id, lock=lock)
    open_debts = [OpenDebt(d.id, d.debt_date, d.remaining) for d in debts]
    allocations = allocate(open_debts, amount, debt_id=debt_id)
    return PaymentPlan(
        customer_id=customer_id,
        section_id=section_id,
        kind=kind,
        amount=amount,
        debt_id=debt_id,
        allocations=tuple(allocations),
        owed_before=sum(d.remaining for d in open_debts),
    )


async def record_payment(
    session: AsyncSession,
    actor: User,
    *,
    customer_id: int,
    section_id: int,
    amount: int,
    kind: PaymentKind,
    today: date,
    debt_id: int | None = None,
    expected: Sequence[tuple[int, int]] | None = None,
    expected_owed: int | None = None,
    note: str | None = None,
) -> tuple[Payment, PaymentPlan]:
    """Writes a payment or write-off with its allocations — locked and re-planned.

    `expected` = allocations shown on the card; if the fresh plan differs, PlanChangedError.
    """
    require_staff(actor)
    customer = await lock_customer(session, customer_id)
    if customer.deleted_at is not None:
        raise CustomerNotFoundError(customer_id)
    plan = await plan_payment(
        session,
        customer_id=customer_id,
        section_id=section_id,
        amount=amount,
        kind=kind,
        debt_id=debt_id,
        lock=True,
    )
    if expected is not None and [(a.debt_id, a.amount) for a in plan.allocations] != [
        tuple(x) for x in expected
    ]:
        raise PlanChangedError
    # Two cards drawn from the same balance (one abandoned, one new) must not both go through:
    # the section balance has to be exactly what the card showed.
    if expected_owed is not None and plan.owed_before != expected_owed:
        raise PlanChangedError
    payment = Payment(
        customer_id=customer_id,
        section_id=section_id,
        kind=kind.value,
        method="cash" if kind == PaymentKind.PAYMENT else None,
        amount=amount,
        paid_on=today,
        note=note,
        created_by=actor.id,
    )
    session.add(payment)
    await session.flush()
    session.add_all(
        PaymentAllocation(
            payment_id=payment.id,
            debt_id=a.debt_id,
            section_id=section_id,
            customer_id=customer_id,
            amount=a.amount,
        )
        for a in plan.allocations
    )
    await session.flush()
    return payment, plan


# ---------------------------------------------------------------- cancellation (BR-104)
async def cancel_payment(
    session: AsyncSession,
    actor: User,
    payment_id: int,
    reason: str | None = None,
    *,
    from_return: bool = False,
) -> Payment:
    require_staff(actor)
    p = await session.get(Payment, payment_id)
    if p is None:
        raise LedgerError("payment not found")
    await lock_customer(session, p.customer_id)
    await session.refresh(p)
    if p.status != LedgerStatus.ACTIVE:
        raise AlreadyCancelledError
    if p.kind == "return" and not from_return:
        raise LedgerError("belongs to a return: cancel the return instead")
    p.status = LedgerStatus.CANCELLED
    p.cancelled_at = datetime.now(UTC)
    p.cancelled_by = actor.id
    p.cancel_reason = reason
    await session.flush()
    return p


async def cancel_debt(
    session: AsyncSession,
    actor: User,
    debt_id: int,
    reason: str | None = None,
    *,
    from_sale: bool = False,
) -> Debt:
    require_staff(actor)
    d = await session.get(Debt, debt_id)
    if d is None:
        raise LedgerError("debt not found")
    await lock_customer(session, d.customer_id)
    await session.refresh(d)
    if d.status != LedgerStatus.ACTIVE:
        raise AlreadyCancelledError
    if d.kind != "regular" and not from_sale:
        raise LedgerError("linked to a sale: cancel the sale instead")
    from bot.services import returns

    if d.kind == "regular" and await returns.active_returns_count(session, "debt", d.id):
        raise DebtHasReturnsError
    has_payments = await session.scalar(
        select(func.count())
        .select_from(PaymentAllocation)
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(PaymentAllocation.debt_id == debt_id, Payment.status == LedgerStatus.ACTIVE)
    )
    if has_payments:
        raise DebtHasPaymentsError
    d.status = LedgerStatus.CANCELLED
    d.cancelled_at = datetime.now(UTC)
    d.cancelled_by = actor.id
    d.cancel_reason = reason
    if d.kind == "regular":  # goods of a credit record go back to the stock
        rows = (await session.scalars(select(DebtItem).where(DebtItem.debt_id == d.id))).all()
        back: dict[int, int] = {}
        for it in rows:
            back[it.category_id] = back.get(it.category_id, 0) + it.quantity
        for cat_id, n in back.items():
            await inventory.add_movement(
                session,
                category_id=cat_id,
                quantity=n,
                reason="cancel",
                ref_type="debt",
                ref_id=d.id,
                actor_id=actor.id,
            )
    await session.flush()
    return d


# ---------------------------------------------------------------- history / views
@dataclass(frozen=True, slots=True)
class Entry:
    kind: str  # "debt" | "payment" | "write_off"
    id: int
    customer_id: int
    customer_name: str
    section_id: int
    amount: int
    created_at: datetime
    created_by: int | None


async def recent_entries(
    session: AsyncSession, *, limit: int = 10, customer_id: int | None = None
) -> list[Entry]:
    """Latest active ledger records (for "Oxirgi yozuvni bekor qilish")."""
    debts_q = (
        select(Debt.id, Debt.customer_id, Customer.name, Debt.section_id, Debt.total_amount, Debt.created_at, Debt.created_by)
        .join(Customer, Customer.id == Debt.customer_id)
        .where(Debt.status == LedgerStatus.ACTIVE, Debt.kind == "regular")
        .order_by(Debt.created_at.desc())
        .limit(limit)
    )  # fmt: skip
    if customer_id is not None:
        debts_q = debts_q.where(Debt.customer_id == customer_id)
    pay_q = (
        select(Payment.id, Payment.customer_id, Customer.name, Payment.section_id, Payment.amount, Payment.created_at, Payment.created_by, Payment.kind)
        .join(Customer, Customer.id == Payment.customer_id)
        .where(Payment.status == LedgerStatus.ACTIVE, Payment.kind != "return")
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )  # fmt: skip
    if customer_id is not None:
        pay_q = pay_q.where(Payment.customer_id == customer_id)
    entries = [Entry("debt", *row) for row in (await session.execute(debts_q)).all()]
    entries += [
        Entry(kind, pid, cid, name, sid, amt, at, by)
        for pid, cid, name, sid, amt, at, by, kind in (await session.execute(pay_q)).all()
    ]
    from bot.db.models import Return, Sale

    sale_q = (
        select(Sale.id, Sale.customer_id, Customer.name, Sale.section_id, Sale.total_amount, Sale.created_at, Sale.created_by)
        .outerjoin(Customer, Customer.id == Sale.customer_id)
        .where(Sale.status == LedgerStatus.ACTIVE)
        .order_by(Sale.created_at.desc())
        .limit(limit)
    )  # fmt: skip
    ret_q = (
        select(Return.id, Return.customer_id, Customer.name, Return.section_id, Return.value, Return.created_at, Return.created_by)
        .outerjoin(Customer, Customer.id == Return.customer_id)
        .where(Return.status == LedgerStatus.ACTIVE)
        .order_by(Return.created_at.desc())
        .limit(limit)
    )  # fmt: skip
    if customer_id is not None:
        sale_q = sale_q.where(Sale.customer_id == customer_id)
        ret_q = ret_q.where(Return.customer_id == customer_id)
    entries += [
        Entry("sale", sid, cid or 0, name or "mijozsiz", sec, amt, at, by)
        for sid, cid, name, sec, amt, at, by in (await session.execute(sale_q)).all()
    ]
    entries += [
        Entry("return", rid, cid or 0, name or "mijozsiz", sec, amt, at, by)
        for rid, cid, name, sec, amt, at, by in (await session.execute(ret_q)).all()
    ]
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries[:limit]


@dataclass(slots=True)
class SectionLedger:
    section_id: int
    balance: int
    open_debts: list[tuple[DebtView, list[tuple[str, int, int, str | None]]]]
    recent_payments: list[tuple[date, str, int]]


async def customer_ledger(
    session: AsyncSession, customer_id: int, *, payments_limit: int = 5
) -> list[SectionLedger]:
    """Per-section view: open debts with items, balance, recent payments (BR-121, BR-155)."""
    debts = await debts_with_remaining(session, customer_id)
    items_rows = (
        await session.execute(
            select(DebtItem.debt_id, Category.name, DebtItem.quantity, DebtItem.unit_price, DebtItem.note)
            .join(Category, Category.id == DebtItem.category_id)
            .where(DebtItem.debt_id.in_([d.id for d in debts] or [0]))
            .order_by(DebtItem.id)
        )
    ).all()  # fmt: skip
    items: dict[int, list[tuple[str, int, int, str | None]]] = defaultdict(list)
    for debt_id, name, qty, price, note in items_rows:
        items[debt_id].append((name, qty, price, note))
    pays = (
        await session.execute(
            select(Payment.section_id, Payment.paid_on, Payment.kind, Payment.amount)
            .where(Payment.customer_id == customer_id, Payment.status == LedgerStatus.ACTIVE)
            .order_by(Payment.created_at.desc())
            .limit(payments_limit * 2)
        )
    ).all()
    sections: dict[int, SectionLedger] = {}
    for d in debts:
        sl = sections.setdefault(d.section_id, SectionLedger(d.section_id, 0, [], []))
        sl.balance += d.remaining
        sl.open_debts.append((d, items[d.id]))
    for sid, paid_on, kind, amount in pays:
        if sid in sections and len(sections[sid].recent_payments) < payments_limit:
            sections[sid].recent_payments.append((paid_on, kind, amount))
    return [sections[k] for k in sorted(sections)]


async def last_debt_date(session: AsyncSession, customer_ids: Sequence[int]) -> dict[int, date]:
    if not customer_ids:
        return {}
    rows = await session.execute(
        select(Debt.customer_id, func.max(Debt.debt_date))
        .where(and_(Debt.customer_id.in_(list(customer_ids)), Debt.status == LedgerStatus.ACTIVE))
        .group_by(Debt.customer_id)
    )
    return {cid: d for cid, d in rows.all()}


# ---------------------------------------------------------------- lists for questions (BR-120, BR-122)
@dataclass(frozen=True, slots=True)
class DebtorRow:
    customer_id: int
    name: str
    form: str
    section_id: int
    owed: int
    next_due: date | None


async def debtors(session: AsyncSession, *, section_id: int | None = None) -> list[DebtorRow]:
    """Everyone who owes, biggest first. Deleted customers stay (their debt is still owed, Q-33)."""
    paid = paid_subquery()
    remaining = Debt.total_amount - func.coalesce(paid.c.paid, 0)
    q = (
        select(
            Debt.customer_id,
            Customer.name,
            Customer.address_form,
            Debt.section_id,
            cast(func.sum(remaining), BigInteger),
            func.min(Debt.due_date),
        )
        .join(Customer, Customer.id == Debt.customer_id)
        .outerjoin(paid, paid.c.debt_id == Debt.id)
        .where(Debt.status == LedgerStatus.ACTIVE, remaining > 0)
        .group_by(Debt.customer_id, Customer.name, Customer.address_form, Debt.section_id)
        .order_by(func.sum(remaining).desc())
    )
    if section_id is not None:
        q = q.where(Debt.section_id == section_id)
    return [
        DebtorRow(cid, name, form, sid, int(owed), due)
        for cid, name, form, sid, owed, due in (await session.execute(q)).all()
    ]


@dataclass(frozen=True, slots=True)
class OverdueRow:
    customer_id: int
    name: str
    form: str
    section_id: int
    remaining: int
    due_date: date
    days_overdue: int


async def overdue(session: AsyncSession, today: date) -> list[OverdueRow]:
    paid = paid_subquery()
    remaining = Debt.total_amount - func.coalesce(paid.c.paid, 0)
    q = (
        select(
            Debt.customer_id, Customer.name, Customer.address_form, Debt.section_id,
            cast(remaining, BigInteger), Debt.due_date,
        )
        .join(Customer, Customer.id == Debt.customer_id)
        .outerjoin(paid, paid.c.debt_id == Debt.id)
        .where(Debt.status == LedgerStatus.ACTIVE, Debt.due_date < today, remaining > 0)
        .order_by(Debt.due_date, Debt.id)
    )  # fmt: skip
    return [
        OverdueRow(cid, name, form, sid, int(rem), due, (today - due).days)
        for cid, name, form, sid, rem, due in (await session.execute(q)).all()
        if due is not None
    ]
