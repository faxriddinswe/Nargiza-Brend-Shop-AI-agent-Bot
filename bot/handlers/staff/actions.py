"""Executes confirmed staff actions (after the ✅ on a confirmation card).

Runs inside the caller's transaction (`uow`). Returns the reply text and the notifications to send
AFTER commit (customer messages BR-054/055a, section-owner messages BR-026/027).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import AddressForm, Customer, PaymentKind, User
from bot.services import customers as cust
from bot.services import inventory, ledger, returns, sales
from bot.services import staff as staff_svc
from bot.services import users as users_svc
from bot.services.ledger import ItemInput
from bot.texts import uz_latn as t
from bot.utils.dates import today_tashkent
from bot.utils.money import format_amount

Notify = list[tuple[int, str]]


class UnknownActionError(Exception):
    pass


def form_word(customer: Customer) -> str:
    return customer.address_form


def display(customer: Customer) -> str:
    return f"{customer.name} {customer.address_form}"


async def _owners_notice(
    session: AsyncSession, actor: User, section_code: str, text: str
) -> Notify:
    """BR-026/027: owners of the section hear about it, unless the actor is one of them."""
    owners = await staff_svc.section_owner_telegram_ids(session, section_code)
    if actor.telegram_id in owners:
        return []
    return [(chat, text) for chat in owners]


async def _customer_notice(session: AsyncSession, customer: Customer, text: str) -> Notify:
    chat = await users_svc.customer_chat_id(session, customer)
    return [(chat, text)] if chat else []


async def execute(
    session: AsyncSession, actor: User, action: str, payload: dict[str, Any]
) -> tuple[str, Notify]:
    today = today_tashkent()

    if action == "create_customer":
        c = await cust.create(
            session,
            actor,
            name=payload["name"],
            address_form=AddressForm(payload["form"]),
            raw_phone=payload.get("phone"),
            note=payload.get("note"),
        )
        return t.customer_created(c.name, c.address_form), []

    if action == "create_debts":
        return await _create_debts(session, actor, payload, today)

    if action == "record_payment":
        return await _record_payment(session, actor, payload, today)

    if action == "register_return":
        return await _register_return(session, actor, payload, today)

    if action == "create_sale":
        return await _create_sale(session, actor, payload, today)

    if action == "stock_in":
        row = await inventory.stock_in(
            session, actor, int(payload["category_id"]), int(payload["quantity"])
        )
        return t.stock_in_saved(row.name, row.qty), []

    if action == "stock_count":
        done = await inventory.stock_count(
            session, actor, {int(k): int(v) for k, v in payload["counts"].items()}
        )
        return t.stock_count_saved(len(done)), []

    if action == "cancel_entry":
        return await _cancel_entry(session, actor, payload)

    if action == "delete_customer":
        c = await cust.soft_delete(session, actor, int(payload["id"]))
        return t.customer_deleted(c.name), []

    if action == "restore_customer":
        c = await cust.restore(session, actor, int(payload["id"]))
        return t.customer_restored(c.name), []

    # admin actions (staff management etc.)
    from bot.handlers.admin.panel import execute_admin_action

    return await execute_admin_action(session, actor, action, payload)


async def _create_debts(
    session: AsyncSession, actor: User, payload: dict[str, Any], today: date
) -> tuple[str, Notify]:
    customer = await cust.get(session, int(payload["customer_id"]))
    items = [
        ItemInput(int(i["category_id"]), int(i["quantity"]), int(i["unit_price"]), i.get("note"))
        for i in payload["items"]
    ]
    due = date.fromisoformat(payload["due"]) if payload.get("due") else None
    created = await ledger.create_debts(
        session, actor, customer_id=customer.id, items=items, due_date=due, today=today
    )
    cats = {c.id: c for c in await ledger.categories(session, active_only=False)}
    codes = await ledger.section_codes(session)
    by_section = await ledger.balances(session, customer.id)
    who = await staff_svc.actor_label(session, actor)
    notify: Notify = []
    for d in created:
        rows = t.items_summary(
            [(cats[i.category_id].name, i.quantity, i.unit_price, i.note) for i in d.items]
        )
        code = codes[d.section_id]
        notify += await _customer_notice(
            session,
            customer,
            t.customer_debt_notice(
                display(customer), code, rows, d.total, due, by_section.get(d.section_id, 0)
            ),
        )
        notify += await _owners_notice(
            session, actor, code, t.owner_notice(who, "qarz yozdi", display(customer), d.total)
        )
    return t.debt_saved(display(customer)), notify


async def _record_payment(
    session: AsyncSession, actor: User, payload: dict[str, Any], today: date
) -> tuple[str, Notify]:
    customer = await cust.get(session, int(payload["customer_id"]))
    kind = PaymentKind(payload["kind"])
    payment, plan = await ledger.record_payment(
        session,
        actor,
        customer_id=customer.id,
        section_id=int(payload["section_id"]),
        amount=int(payload["amount"]),
        kind=kind,
        today=today,
        debt_id=payload.get("debt_id"),
        expected=[tuple(x) for x in payload.get("expected", [])] or None,
        expected_owed=payload.get("owed_before"),
    )
    code = (await ledger.section_codes(session))[payment.section_id]
    left = plan.owed_after
    who = await staff_svc.actor_label(session, actor)
    if kind == PaymentKind.PAYMENT:
        text = t.customer_payment_notice(display(customer), code, payment.amount, left)
        what = "to'lov yozdi"
    else:
        text = t.customer_writeoff_notice(display(customer), code, payment.amount, left)
        what = "qarzdan kechdi"
    notify = await _customer_notice(session, customer, text)
    notify += await _owners_notice(
        session, actor, code, t.owner_notice(who, what, display(customer), payment.amount)
    )
    return t.payment_saved(display(customer), kind.value), notify


async def _cancel_entry(
    session: AsyncSession, actor: User, payload: dict[str, Any]
) -> tuple[str, Notify]:
    kind, rid = payload["kind"], int(payload["id"])
    who = await staff_svc.actor_label(session, actor)
    codes = await ledger.section_codes(session)
    customer: Customer | None
    told = True  # was the customer ever messaged about this record? then tell them about the correction too
    if kind == "debt":
        debt = await ledger.cancel_debt(session, actor, rid)
        customer = await cust.get(session, debt.customer_id, include_deleted=True)
        amount, section_id = debt.total_amount, debt.section_id
    elif kind == "sale":
        sale = await sales.cancel_sale(session, actor, rid)
        customer = (
            await cust.get(session, sale.customer_id, include_deleted=True)
            if sale.customer_id
            else None
        )
        amount, section_id = sale.total_amount, sale.section_id
        told = (
            sale.total_amount > sale.paid_amount
        )  # a fully cash sale was never announced to the customer
    elif kind == "return":
        ret = await returns.cancel_return(session, actor, rid)
        customer = (
            await cust.get(session, ret.customer_id, include_deleted=True)
            if ret.customer_id
            else None
        )
        amount, section_id = ret.value, ret.section_id
    else:
        pay = await ledger.cancel_payment(session, actor, rid)
        customer = await cust.get(session, pay.customer_id, include_deleted=True)
        amount, section_id = pay.amount, pay.section_id
        kind = pay.kind
    what = t.KIND_NAMES[kind].lower()
    notify: Notify = []
    if customer is not None and customer.deleted_at is None and told:
        notify += await _customer_notice(
            session,
            customer,
            t.customer_correction_notice(display(customer), f"{what} ({format_amount(amount)})"),
        )
    label = display(customer) if customer else "mijozsiz"
    notify += await _owners_notice(
        session, actor, codes[section_id], t.owner_cancel_notice(who, what, label, amount)
    )
    return t.cancelled_ok(kind, customer.name if customer else "mijozsiz"), notify


async def _create_sale(
    session: AsyncSession, actor: User, payload: dict[str, Any], today: date
) -> tuple[str, Notify]:
    customer = (
        await cust.get(session, int(payload["customer_id"])) if payload.get("customer_id") else None
    )
    items = [
        ItemInput(int(i["category_id"]), int(i["quantity"]), int(i["unit_price"]), i.get("note"))
        for i in payload["items"]
    ]
    due = date.fromisoformat(payload["due"]) if payload.get("due") else None
    made = await sales.create_sales(
        session,
        actor,
        customer_id=customer.id if customer else None,
        items=items,
        final_total=payload.get("final_total"),
        paid=payload.get("paid"),
        due_date=due,
        today=today,
    )
    cats = {c.id: c for c in await ledger.categories(session, active_only=False)}
    codes = await ledger.section_codes(session)
    by_section = await ledger.balances(session, customer.id) if customer else {}
    who = await staff_svc.actor_label(session, actor)
    notify: Notify = []
    warn: dict[str, int] = {}
    for m in made:
        code = codes[m.section_id]
        for w in m.warnings:
            warn[w.name] = w.qty
        if (
            customer is not None and m.plan.debt > 0
        ):  # the customer hears about the credit part (BR-054)
            rows = t.items_summary(
                [(cats[i.category_id].name, i.quantity, i.unit_price, i.note) for i in m.items]
            )
            notify += await _customer_notice(
                session,
                customer,
                t.customer_sale_notice(
                    display(customer),
                    code,
                    rows,
                    m.plan.total,
                    m.plan.paid,
                    m.plan.debt,
                    due,
                    by_section.get(m.section_id, 0),
                ),
            )
        notify += await _owners_notice(
            session,
            actor,
            code,
            t.owner_notice(
                who, "savdo yozdi", display(customer) if customer else "mijozsiz", m.plan.total
            ),
        )
    text = t.sale_saved(display(customer) if customer else None)
    if warn:
        text += t.stock_warning(list(warn.items()))
    return text, notify


async def _register_return(
    session: AsyncSession, actor: User, payload: dict[str, Any], today: date
) -> tuple[str, Notify]:
    ret, plan = await returns.register_return(
        session,
        actor,
        source_type=payload["source_type"],
        source_id=int(payload["source_id"]),
        qty_by_item={int(k): int(v) for k, v in payload["items"].items()},
        today=today,
        expected=tuple(payload["expected"]) if payload.get("expected") else None,
    )
    customer = (
        await cust.get(session, ret.customer_id, include_deleted=True) if ret.customer_id else None
    )
    codes = await ledger.section_codes(session)
    who = await staff_svc.actor_label(session, actor)
    code = codes[ret.section_id]
    left = plan.debt_remaining - plan.debt_reduction
    notify: Notify = []
    if customer is not None and customer.deleted_at is None:
        notify += await _customer_notice(
            session,
            customer,
            t.customer_return_notice(
                display(customer), code, plan.debt_reduction, plan.cash_refund, left
            ),
        )
    notify += await _owners_notice(
        session,
        actor,
        code,
        t.owner_notice(
            who, "qaytarish yozdi", display(customer) if customer else "mijozsiz", ret.value
        ),
    )
    text = t.return_saved(display(customer) if customer else None)
    ex = payload.get("exchange")
    if ex:
        items = [
            ItemInput(
                int(i["category_id"]), int(i["quantity"]), int(i["unit_price"]), i.get("note")
            )
            for i in ex["items"]
        ]
        made = await sales.create_sales(
            session,
            actor,
            customer_id=customer.id if customer else None,
            items=items,
            final_total=ex.get("final_total"),
            paid=ex.get("paid"),
            due_date=date.fromisoformat(ex["due"]) if ex.get("due") else None,
            today=today,
            note=f"almashtirish: qaytarish №{ret.id}",
        )
        text += "\n" + t.sale_saved(display(customer) if customer else None)
        for m in made:
            ncode = codes[m.section_id]
            if customer is not None and m.plan.debt > 0:
                bal = (await ledger.balances(session, customer.id)).get(m.section_id, 0)
                rows = t.items_summary(
                    [
                        (c.name, i.quantity, i.unit_price, i.note)
                        for i in m.items
                        for c in [await _cat(session, i.category_id)]
                    ]
                )
                due = date.fromisoformat(ex["due"]) if ex.get("due") else None
                notify += await _customer_notice(
                    session,
                    customer,
                    t.customer_sale_notice(
                        display(customer),
                        ncode,
                        rows,
                        m.plan.total,
                        m.plan.paid,
                        m.plan.debt,
                        due,
                        bal,
                    ),
                )
            if ncode != code:
                notify += await _owners_notice(
                    session,
                    actor,
                    ncode,
                    t.owner_notice(
                        who,
                        "almashtirish (yangi savdo)",
                        display(customer) if customer else "mijozsiz",
                        m.plan.total,
                    ),
                )
    return text, notify


async def _cat(session: AsyncSession, category_id: int) -> Any:
    return next(
        c for c in await ledger.categories(session, active_only=False) if c.id == category_id
    )
