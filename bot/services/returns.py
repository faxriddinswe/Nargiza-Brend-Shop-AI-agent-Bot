"""Returns (BR-080…BR-087, BR-084a, Q-11/Q-29): goods taken back from a sale or from credit goods.

- The original record is never edited; "returned so far" is derived from active returns per source item.
- Value of returned units = their price with the sale's discount spread proportionally; partial returns add up
  to exactly what was paid (`sale_math.split_total`, `item_value`).
- Money: the linked/own debt is reduced first (a `return` payment), the EXCESS is a cash refund (BR-084a).
- Stock goes back up. Cancelling a return reverses all of it.
Exchange = return + new sale in one transaction (see handlers/staff/actions.py).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import BigInteger, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    Category,
    Customer,
    Debt,
    DebtItem,
    LedgerStatus,
    PaymentKind,
    Return,
    ReturnItem,
    Sale,
    SaleItem,
    User,
)
from bot.services import inventory, ledger
from bot.services.customers import require_staff
from bot.services.sale_math import SaleMathError, item_value, split_total


class ReturnError(ledger.LedgerError):
    pass


class SourceNotFoundError(ReturnError):
    pass


class NothingReturnableError(ReturnError):
    pass


@dataclass(frozen=True, slots=True)
class SourceItem:
    id: int
    category_id: int
    name: str
    quantity: int
    unit_price: int
    returned_qty: int
    returned_value: int
    share: int  # this line's part of the agreed price (discount spread, exact)

    @property
    def returnable(self) -> int:
        return self.quantity - self.returned_qty


@dataclass(frozen=True, slots=True)
class SourceView:
    type: str  # "sale" | "debt"
    id: int
    customer_id: int | None
    customer_name: str | None
    section_id: int
    when: date
    total: int  # what the customer actually owes/paid for the record (after discount)
    items_total: int  # Σ list prices
    items: tuple[SourceItem, ...]
    debt_id: int | None  # the debt a return is applied to first


@dataclass(frozen=True, slots=True)
class ReturnLine:
    source_item_id: int
    category_id: int
    name: str
    quantity: int
    value: int


@dataclass(frozen=True, slots=True)
class ReturnPlan:
    source: SourceView
    lines: tuple[ReturnLine, ...]
    value: int
    debt_id: int | None
    debt_remaining: int
    debt_reduction: int
    cash_refund: int


async def _returned(
    session: AsyncSession, source_type: str, item_ids: list[int]
) -> dict[int, tuple[int, int]]:
    if not item_ids:
        return {}
    rows = await session.execute(
        select(
            ReturnItem.source_item_id,
            cast(func.sum(ReturnItem.quantity), BigInteger),
            cast(func.sum(ReturnItem.value), BigInteger),
        )
        .join(Return, Return.id == ReturnItem.return_id)
        .where(
            Return.status == LedgerStatus.ACTIVE,
            Return.source_type == source_type,
            ReturnItem.source_item_id.in_(item_ids),
        )
        .group_by(ReturnItem.source_item_id)
    )
    return {iid: (int(q), int(v)) for iid, q, v in rows.all()}


async def source_view(session: AsyncSession, source_type: str, source_id: int) -> SourceView:
    cats = {c.id: c.name for c in (await session.execute(select(Category))).scalars()}
    raw: Sequence[Any]  # SaleItem rows or DebtItem rows (same columns used below)
    if source_type == "sale":
        sale = await session.get(Sale, source_id)
        if sale is None or sale.status != LedgerStatus.ACTIVE:
            raise SourceNotFoundError(source_id)
        raw = (
            await session.scalars(
                select(SaleItem).where(SaleItem.sale_id == sale.id).order_by(SaleItem.id)
            )
        ).all()
        linked = await session.scalar(
            select(Debt.id).where(Debt.sale_id == sale.id, Debt.status == LedgerStatus.ACTIVE)
        )
        total, items_total, when = sale.total_amount, sale.items_total, sale.sale_date
        customer_id, section_id, debt_id = sale.customer_id, sale.section_id, linked
    elif source_type == "debt":
        debt = await session.get(Debt, source_id)
        if debt is None or debt.status != LedgerStatus.ACTIVE or debt.kind != "regular":
            raise SourceNotFoundError(source_id)
        raw = (
            await session.scalars(
                select(DebtItem).where(DebtItem.debt_id == debt.id).order_by(DebtItem.id)
            )
        ).all()
        total = items_total = debt.total_amount
        when, customer_id, section_id, debt_id = (
            debt.debt_date,
            debt.customer_id,
            debt.section_id,
            debt.id,
        )
    else:
        raise SourceNotFoundError(source_type)
    rows: list[Any] = list(raw)  # SaleItem or DebtItem rows: same columns used below
    done = await _returned(session, source_type, [r.id for r in rows])
    shares = split_total(total, [r.quantity * r.unit_price for r in rows]) if rows else []
    items_list: list[SourceItem] = []
    for row, sh in zip(rows, shares, strict=True):  # SaleItem | DebtItem both have the fields used
        done_qty, done_value = done.get(row.id, (0, 0))
        items_list.append(
            SourceItem(
                row.id,
                row.category_id,
                cats.get(row.category_id, "?"),
                row.quantity,
                row.unit_price,
                done_qty,
                done_value,
                sh,
            )
        )
    items = tuple(items_list)
    name = None
    if customer_id is not None:
        c = await session.get(Customer, customer_id)
        name = f"{c.name} {c.address_form}" if c else None
    return SourceView(
        source_type,
        source_id,
        customer_id,
        name,
        section_id,
        when,
        total,
        items_total,
        items,
        debt_id,
    )


async def returnable_sources(
    session: AsyncSession, *, customer_id: int | None, category_id: int, limit: int = 8
) -> list[SourceView]:
    """Newest first: records that still contain returnable units of this product type."""
    found: list[tuple[date, str, int]] = []
    sq = (
        select(Sale.sale_date, Sale.id)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .where(Sale.status == LedgerStatus.ACTIVE, SaleItem.category_id == category_id)
        .order_by(Sale.sale_date.desc(), Sale.id.desc())
        .limit(limit * 3)
    )
    dq = (
        select(Debt.debt_date, Debt.id)
        .join(DebtItem, DebtItem.debt_id == Debt.id)
        .where(
            Debt.status == LedgerStatus.ACTIVE,
            Debt.kind == "regular",
            DebtItem.category_id == category_id,
        )
        .order_by(Debt.debt_date.desc(), Debt.id.desc())
        .limit(limit * 3)
    )
    if customer_id is not None:
        sq = sq.where(Sale.customer_id == customer_id)
        dq = dq.where(Debt.customer_id == customer_id)
    else:  # nobody named: only sales made without a customer — never someone else's purchase
        sq = sq.where(Sale.customer_id.is_(None))
        dq = dq.where(Debt.customer_id.is_(None))
    found += [(d, "sale", i) for d, i in (await session.execute(sq)).all()]
    found += [(d, "debt", i) for d, i in (await session.execute(dq)).all()]
    found.sort(key=lambda x: (x[0], x[2]), reverse=True)
    views: list[SourceView] = []
    seen: set[tuple[str, int]] = set()
    for _, typ, sid in found:
        if (typ, sid) in seen:
            continue
        seen.add((typ, sid))
        v = await source_view(session, typ, sid)
        if any(i.category_id == category_id and i.returnable > 0 for i in v.items):
            views.append(v)
        if len(views) >= limit:
            break
    return views


async def lock_source(session: AsyncSession, source_type: str, source_id: int) -> None:
    """Row lock on the original record: two staff can't return / cancel the same sale at once."""
    model = Sale if source_type == "sale" else Debt
    await session.execute(select(model.id).where(model.id == source_id).with_for_update())


async def plan_return(
    session: AsyncSession, source_type: str, source_id: int, qty_by_item: Mapping[int, int]
) -> ReturnPlan:
    src = await source_view(session, source_type, source_id)
    by_id = {i.id: i for i in src.items}
    lines: list[ReturnLine] = []
    for item_id, qty in qty_by_item.items():
        item = by_id.get(item_id)
        if item is None or qty <= 0:
            raise NothingReturnableError(item_id)
        try:
            value = item_value(
                qty, share=item.share, item_quantity=item.quantity,
                already_returned_value=item.returned_value, already_returned_qty=item.returned_qty,
            )  # fmt: skip
        except SaleMathError as exc:
            raise NothingReturnableError(item_id) from exc
        if value <= 0:
            raise NothingReturnableError(item_id)
        lines.append(ReturnLine(item.id, item.category_id, item.name, qty, value))
    if not lines:
        raise NothingReturnableError(source_id)
    value = sum(line.value for line in lines)
    remaining = 0
    if src.debt_id is not None and src.customer_id is not None:
        for dv in await ledger.debts_with_remaining(
            session, src.customer_id, section_id=src.section_id
        ):
            if dv.id == src.debt_id:
                remaining = dv.remaining
    reduction = min(value, remaining)
    return ReturnPlan(
        src, tuple(lines), value, src.debt_id, remaining, reduction, value - reduction
    )


async def register_return(
    session: AsyncSession,
    actor: User,
    *,
    source_type: str,
    source_id: int,
    qty_by_item: Mapping[int, int],
    today: date,
    expected: tuple[int, int, int] | None = None,
    note: str | None = None,
) -> tuple[Return, ReturnPlan]:
    """`expected` = (value, debt_reduction, cash_refund) shown on the card; if anything moved → PlanChangedError."""
    require_staff(actor)
    first = await source_view(session, source_type, source_id)
    if first.customer_id is not None:
        await ledger.lock_customer(session, first.customer_id)
    await lock_source(session, source_type, source_id)
    plan = await plan_return(session, source_type, source_id, qty_by_item)
    if expected is not None and (plan.value, plan.debt_reduction, plan.cash_refund) != tuple(
        expected
    ):
        raise ledger.PlanChangedError
    payment_id = None
    if plan.debt_reduction > 0 and plan.debt_id is not None and plan.source.customer_id is not None:
        payment, _ = await ledger.record_payment(
            session, actor, customer_id=plan.source.customer_id, section_id=plan.source.section_id,
            amount=plan.debt_reduction, kind=PaymentKind.RETURN, today=today, debt_id=plan.debt_id,
            note="qaytarilgan tovar",
        )  # fmt: skip
        payment_id = payment.id
    ret = Return(
        section_id=plan.source.section_id,
        customer_id=plan.source.customer_id,
        source_type=source_type,
        source_id=source_id,
        value=plan.value,
        debt_reduction=plan.debt_reduction,
        cash_refund=plan.cash_refund,
        return_payment_id=payment_id,
        return_date=today,
        note=note,
        created_by=actor.id,
    )
    session.add(ret)
    await session.flush()
    qty_by_cat: dict[int, int] = defaultdict(int)
    for line in plan.lines:
        session.add(
            ReturnItem(return_id=ret.id, source_item_id=line.source_item_id, category_id=line.category_id, quantity=line.quantity, value=line.value)
        )  # fmt: skip
        qty_by_cat[line.category_id] += line.quantity
    for cat_id, n in qty_by_cat.items():
        await inventory.add_movement(
            session, category_id=cat_id, quantity=n, reason="return", ref_type="return", ref_id=ret.id, actor_id=actor.id
        )  # fmt: skip
    await session.flush()
    return ret, plan


async def active_returns_count(session: AsyncSession, source_type: str, source_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Return)
            .where(
                Return.source_type == source_type,
                Return.source_id == source_id,
                Return.status == LedgerStatus.ACTIVE,
            )
        )
        or 0
    )


async def cancel_return(
    session: AsyncSession, actor: User, return_id: int, reason: str | None = None
) -> Return:
    """Undo a return: the `return` payment is cancelled (debt is back), the goods leave the stock again.

    A cash refund that was already handed over cannot be undone by software — the record says so.
    """
    require_staff(actor)
    ret = await session.get(Return, return_id)
    if ret is None:
        raise ReturnError("return not found")
    if ret.customer_id is not None:
        await ledger.lock_customer(session, ret.customer_id)
    await lock_source(session, ret.source_type, ret.source_id)
    await session.refresh(ret)
    if ret.status != LedgerStatus.ACTIVE:
        raise ledger.AlreadyCancelledError
    if ret.return_payment_id is not None:
        await ledger.cancel_payment(
            session,
            actor,
            ret.return_payment_id,
            reason or "qaytarish bekor qilindi",
            from_return=True,
        )
    ret.status = LedgerStatus.CANCELLED
    ret.cancelled_at = datetime.now(UTC)
    ret.cancelled_by = actor.id
    ret.cancel_reason = reason
    items = (await session.scalars(select(ReturnItem).where(ReturnItem.return_id == ret.id))).all()
    qty: dict[int, int] = defaultdict(int)
    for it in items:
        qty[it.category_id] += it.quantity
    for cat_id, n in qty.items():
        await inventory.add_movement(
            session, category_id=cat_id, quantity=-n, reason="cancel", ref_type="return", ref_id=ret.id, actor_id=actor.id
        )  # fmt: skip
    await session.flush()
    return ret
