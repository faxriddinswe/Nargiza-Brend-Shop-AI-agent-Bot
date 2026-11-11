"""Sales (BR-070…BR-075): cash sales, mixed sales (cash + linked debt), discounts, cancellation.

One call = one transaction. A sale with an unpaid part creates a linked debt (`sale_remainder`) in the debt ledger,
so balances, FIFO payments, reminders and reports all keep working unchanged. Goods leave the stock.
Telegram- and AI-free.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Debt, LedgerStatus, Sale, SaleItem, User
from bot.services import inventory, ledger
from bot.services.customers import CustomerNotFoundError, require_staff
from bot.services.inventory import StockRow
from bot.services.ledger import ItemInput, LedgerError
from bot.services.sale_math import SaleMathError, SalePlan, plan_sale


class SaleError(LedgerError):
    pass


class SaleHasReturnsError(SaleError):
    """Cancel the returns first (the goods were already taken back)."""


class MultiSectionOverrideError(SaleMathError):
    """Different sections can't share one agreed price / one payment — say them separately."""


@dataclass(slots=True)
class CreatedSale:
    sale_id: int
    section_id: int
    plan: SalePlan
    items: list[ItemInput]
    debt_id: int | None = None
    warnings: list[StockRow] = field(default_factory=list)


async def create_sales(
    session: AsyncSession,
    actor: User,
    *,
    customer_id: int | None,
    items: Sequence[ItemInput],
    final_total: int | None,
    paid: int | None,
    due_date: date | None,
    today: date,
    note: str | None = None,
) -> list[CreatedSale]:
    require_staff(actor)
    if not items:
        raise ledger.EmptyDebtError
    if len(items) > ledger.MAX_ITEMS or sum(i.total for i in items) > ledger.MAX_DEBT_TOTAL:
        raise SaleError("sale too large")
    if due_date is not None and due_date < today:
        raise ledger.DueDatePassedError
    if customer_id is not None:
        customer = await ledger.lock_customer(session, customer_id)
        if customer.deleted_at is not None:
            raise CustomerNotFoundError(customer_id)
    cat_section = {c.id: c.section_id for c in await ledger.categories(session)}
    groups = ledger.split_by_section(items, cat_section)
    if len(groups) > 1 and (final_total is not None or paid is not None):
        raise MultiSectionOverrideError

    created: list[CreatedSale] = []
    touched: set[int] = set()
    for section_id, group in sorted(groups.items()):
        items_total = sum(i.total for i in group)
        plan = plan_sale(
            items_total, final_total=final_total, paid=paid, has_customer=customer_id is not None
        )
        sale = Sale(
            section_id=section_id,
            customer_id=customer_id,
            sale_date=today,
            items_total=plan.items_total,
            discount_amount=plan.discount,
            total_amount=plan.total,
            paid_amount=plan.paid,
            note=note,
            created_by=actor.id,
        )
        session.add(sale)
        await session.flush()
        session.add_all(
            SaleItem(
                sale_id=sale.id,
                section_id=section_id,
                category_id=i.category_id,
                quantity=i.quantity,
                unit_price=i.unit_price,
                note=i.note,
            )
            for i in group
        )
        qty_by_cat: dict[int, int] = defaultdict(int)
        for i in group:
            qty_by_cat[i.category_id] += i.quantity
        for cat_id, qty in qty_by_cat.items():
            await inventory.add_movement(
                session,
                category_id=cat_id,
                quantity=-qty,
                reason="sale",
                ref_type="sale",
                ref_id=sale.id,
                actor_id=actor.id,
            )
            touched.add(cat_id)
        debt_id = None
        if plan.debt > 0:
            debt = Debt(
                customer_id=customer_id,
                section_id=section_id,
                kind="sale_remainder",
                sale_id=sale.id,
                debt_date=today,
                due_date=due_date,
                total_amount=plan.debt,
                created_by=actor.id,
            )
            session.add(debt)
            await session.flush()
            debt_id = debt.id
        created.append(CreatedSale(sale.id, section_id, plan, list(group), debt_id))
    await session.flush()
    warnings = await inventory.negative_after(session, touched)
    for c in created:
        c.warnings = [w for w in warnings if cat_section.get(w.category_id) == c.section_id]
    return created


async def cancel_sale(
    session: AsyncSession, actor: User, sale_id: int, reason: str | None = None
) -> Sale:
    """BR-104: the sale stays in history as cancelled; goods go back to the stock; its linked debt is cancelled."""
    require_staff(actor)
    sale = await session.get(Sale, sale_id)
    if sale is None:
        raise SaleError("sale not found")
    if sale.customer_id is not None:
        await ledger.lock_customer(session, sale.customer_id)
    await session.refresh(sale)
    if sale.status != LedgerStatus.ACTIVE:
        raise ledger.AlreadyCancelledError
    from bot.services import returns

    if await returns.active_returns_count(session, "sale", sale.id):
        raise SaleHasReturnsError
    linked = await session.scalar(
        select(Debt).where(Debt.sale_id == sale.id, Debt.status == LedgerStatus.ACTIVE)
    )
    if linked is not None:
        await ledger.cancel_debt(session, actor, linked.id, reason)  # raises DebtHasPaymentsError
    sale.status = LedgerStatus.CANCELLED
    sale.cancelled_at = datetime.now(UTC)
    sale.cancelled_by = actor.id
    sale.cancel_reason = reason
    items = (await session.scalars(select(SaleItem).where(SaleItem.sale_id == sale.id))).all()
    qty: dict[int, int] = defaultdict(int)
    for it in items:
        qty[it.category_id] += it.quantity
    for cat_id, n in qty.items():
        await inventory.add_movement(
            session,
            category_id=cat_id,
            quantity=n,
            reason="cancel",
            ref_type="sale",
            ref_id=sale.id,
            actor_id=actor.id,
        )
    await session.flush()
    return sale
