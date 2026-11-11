"""Confirmation-card builders shared by the button flows and the AI agent.

Each builder reads the current state, stores a pending action (BR-100…103) and returns the card text.
The money plan comes from `services.ledger` (never from the AI). Telegram-free.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Customer, PaymentKind, User
from bot.services import ledger, pending, returns
from bot.services import staff as staff_svc
from bot.texts import uz_latn as t
from bot.utils.dates import TASHKENT


@dataclass(frozen=True, slots=True)
class Card:
    key: str
    text: str


def who(c: Customer) -> str:
    return f"{c.name} {c.address_form}"


async def debt_card(
    session: AsyncSession,
    actor: User,
    customer: Customer,
    items: Sequence[ledger.ItemInput],
    due: date | None,
) -> Card:
    cats = {c.id: c for c in await ledger.categories(session)}
    groups = ledger.split_by_section(items, {i: c.section_id for i, c in cats.items()})
    codes = await ledger.section_codes(session)
    after = {codes[sid]: bal for sid, bal in (await ledger.balances(session, customer.id)).items()}
    card_groups = []
    for sid, group in sorted(groups.items()):
        subtotal = sum(i.total for i in group)
        rows = [(cats[i.category_id].name, i.quantity, i.unit_price, i.note) for i in group]
        card_groups.append((codes[sid], rows, subtotal))
        after[codes[sid]] = after.get(codes[sid], 0) + subtotal
    key = await pending.create(
        session,
        user_id=actor.id,
        action="create_debts",
        payload={
            "customer_id": customer.id,
            "items": [
                {
                    "category_id": i.category_id,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "note": i.note,
                }
                for i in items
            ],
            "due": due.isoformat() if due else None,
        },
    )
    return Card(key, t.debt_card(who(customer), card_groups, due, after))


async def payment_card(
    session: AsyncSession,
    actor: User,
    customer: Customer,
    *,
    section_id: int,
    amount: int,
    kind: PaymentKind,
    debt_id: int | None = None,
) -> Card:
    """Raises OverpaymentError / NothingToPayError / DebtNotOpenError (services.allocation)."""
    plan = await ledger.plan_payment(
        session,
        customer_id=customer.id,
        section_id=section_id,
        amount=amount,
        kind=kind,
        debt_id=debt_id,
    )
    view = await ledger.customer_ledger(session, customer.id)
    names = {dv.id: t.items_short(items) for sl in view for dv, items in sl.open_debts}
    dates = {dv.id: dv.debt_date for sl in view for dv, _ in sl.open_debts}
    lines = [(dates[a.debt_id], a.amount, names.get(a.debt_id, "qarz")) for a in plan.allocations]
    codes = await ledger.section_codes(session)
    key = await pending.create(
        session,
        user_id=actor.id,
        action="record_payment",
        payload={
            "customer_id": customer.id,
            "section_id": section_id,
            "kind": kind.value,
            "amount": amount,
            "debt_id": debt_id,
            "expected": [[a.debt_id, a.amount] for a in plan.allocations],
            "owed_before": plan.owed_before,
        },
    )
    text = t.payment_card(
        who(customer),
        codes[section_id],
        kind.value,
        amount,
        lines,
        plan.owed_before,
        plan.owed_after,
    )
    return Card(key, text)


async def cancel_entry_card(session: AsyncSession, actor: User, entry: ledger.Entry) -> Card:
    key = await pending.create(
        session,
        user_id=actor.id,
        action="cancel_entry",
        payload={"kind": entry.kind, "id": entry.id},
    )
    by = "—"
    if entry.created_by is not None:
        author = await session.get(User, entry.created_by)
        by = await staff_svc.actor_label(session, author) if author else "—"
    local = entry.created_at.astimezone(TASHKENT)
    text = t.cancel_card_by(
        entry.kind, entry.customer_name, entry.amount, local.date(), by, f"{local:%H:%M}"
    )
    return Card(key, text)


async def delete_customer_card(session: AsyncSession, actor: User, customer: Customer) -> Card:
    codes = await ledger.section_codes(session)
    owed = {codes[sid]: b for sid, b in (await ledger.balances(session, customer.id)).items()}
    key = await pending.create(
        session, user_id=actor.id, action="delete_customer", payload={"id": customer.id}
    )
    return Card(key, t.delete_card(customer.name, owed))


async def new_customer_card(
    session: AsyncSession,
    actor: User,
    *,
    name: str,
    form: str,
    phone: str | None,
    note: str | None,
) -> Card:
    payload: dict[str, Any] = {"name": name, "form": form, "phone": phone, "note": note}
    key = await pending.create(session, user_id=actor.id, action="create_customer", payload=payload)
    return Card(key, t.new_customer_card(name, form, phone, note))


async def customer_card_text(session: AsyncSession, customer: Customer) -> tuple[str, bool]:
    """Customer card text and whether the customer owes anything."""
    view = await ledger.customer_ledger(session, customer.id)
    codes = await ledger.section_codes(session)
    sections = [
        (
            codes[sl.section_id],
            sl.balance,
            [
                t.debt_line(d.debt_date, d.due_date, d.remaining, t.items_short(items))
                for d, items in sl.open_debts
            ],
        )
        for sl in view
    ]
    text = t.customer_card(
        customer.name, customer.address_form, customer.phone, customer.note, sections
    )
    return text, bool(sections)


async def sale_card(
    session: AsyncSession,
    actor: User,
    customer: Customer | None,
    items: Sequence[ledger.ItemInput],
    *,
    final_total: int | None,
    paid: int | None,
    due: date | None,
) -> Card:
    """Raises SaleMathError subclasses (price above list, paid above total, customer required, …)."""
    from bot.services.sale_math import plan_sale
    from bot.services.sales import MultiSectionOverrideError

    cats = {c.id: c for c in await ledger.categories(session)}
    groups = ledger.split_by_section(items, {i: c.section_id for i, c in cats.items()})
    if len(groups) > 1 and (final_total is not None or paid is not None):
        raise MultiSectionOverrideError
    codes = await ledger.section_codes(session)
    after = (
        {codes[sid]: bal for sid, bal in (await ledger.balances(session, customer.id)).items()}
        if customer
        else {}
    )
    card_groups = []
    for sid, group in sorted(groups.items()):
        plan = plan_sale(
            sum(i.total for i in group),
            final_total=final_total,
            paid=paid,
            has_customer=customer is not None,
        )
        rows = [(cats[i.category_id].name, i.quantity, i.unit_price, i.note) for i in group]
        card_groups.append(
            (codes[sid], rows, plan.items_total, plan.discount, plan.paid, plan.debt)
        )
        if plan.debt:
            after[codes[sid]] = after.get(codes[sid], 0) + plan.debt
    key = await pending.create(
        session,
        user_id=actor.id,
        action="create_sale",
        payload={
            "customer_id": customer.id if customer else None,
            "items": [
                {
                    "category_id": i.category_id,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "note": i.note,
                }
                for i in items
            ],
            "final_total": final_total,
            "paid": paid,
            "due": due.isoformat() if due else None,
        },
    )
    return Card(key, t.sale_card(who(customer) if customer else None, card_groups, due, after))


async def stock_in_card(session: AsyncSession, actor: User, category_id: int, qty: int) -> Card:
    from bot.services import inventory

    row = (await inventory.levels(session, [category_id]))[0]
    key = await pending.create(
        session,
        user_id=actor.id,
        action="stock_in",
        payload={"category_id": category_id, "quantity": qty},
    )
    return Card(key, t.stock_in_card(row.name, qty, row.qty))


async def stock_count_card(session: AsyncSession, actor: User, counts: dict[int, int]) -> Card:
    from bot.services import inventory

    plan = await inventory.plan_count(session, counts)
    key = await pending.create(
        session,
        user_id=actor.id,
        action="stock_count",
        payload={"counts": {str(k): v for k, v in counts.items()}},
    )
    return Card(key, t.stock_count_card([(d.name, d.before, d.counted) for d in plan]))


async def return_card(
    session: AsyncSession,
    actor: User,
    plan: returns.ReturnPlan,
    *,
    exchange_items: Sequence[ledger.ItemInput] | None = None,
    final_total: int | None = None,
    paid: int | None = None,
    due: date | None = None,
) -> Card:
    """Return (and optional exchange) card. Raises SaleMathError subclasses for the new purchase."""
    from bot.services.sale_math import plan_sale
    from bot.services.sales import MultiSectionOverrideError

    src = plan.source
    codes = await ledger.section_codes(session)
    cats = {c.id: c for c in await ledger.categories(session, active_only=False)}
    exchange_text = None
    payload_ex = None
    if exchange_items:
        groups = ledger.split_by_section(exchange_items, {i: c.section_id for i, c in cats.items()})
        if len(groups) > 1 and (final_total is not None or paid is not None):
            raise MultiSectionOverrideError
        card_groups = []
        cash_in = 0
        for sid, group in sorted(groups.items()):
            sp = plan_sale(
                sum(i.total for i in group),
                final_total=final_total,
                paid=paid,
                has_customer=src.customer_id is not None,
            )
            rows = [(cats[i.category_id].name, i.quantity, i.unit_price, i.note) for i in group]
            card_groups.append((codes[sid], rows, sp.items_total, sp.discount, sp.paid, sp.debt))
            cash_in += sp.paid
        exchange_text = (card_groups, cash_in - plan.cash_refund)
        payload_ex = {
            "items": [
                {
                    "category_id": i.category_id,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "note": i.note,
                }
                for i in exchange_items
            ],
            "final_total": final_total,
            "paid": paid,
            "due": due.isoformat() if due else None,
        }
    key = await pending.create(
        session,
        user_id=actor.id,
        action="register_return",
        payload={
            "source_type": src.type,
            "source_id": src.id,
            "items": {str(line.source_item_id): line.quantity for line in plan.lines},
            "expected": [plan.value, plan.debt_reduction, plan.cash_refund],
            "exchange": payload_ex,
        },
    )
    text = t.return_card(
        src.customer_name, codes[src.section_id], src.when,
        [(line.name, line.quantity, line.value) for line in plan.lines],
        plan.value, plan.debt_reduction, plan.cash_refund, exchange_text,
    )  # fmt: skip
    return Card(key, text)
