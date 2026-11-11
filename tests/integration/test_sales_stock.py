"""Sales, mixed sales, discounts, stock ledger (BR-070…BR-075, BR-090…BR-096). Fake data only."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, Debt, PaymentKind, Sale, User
from bot.db.session import read_session, uow
from bot.services import customers as cust
from bot.services import inventory, ledger, sales
from bot.services.ledger import ItemInput
from bot.services.sale_math import CustomerRequiredError, PriceAboveListError

SM = async_sessionmaker[AsyncSession]
TODAY = date(2026, 11, 11)


class W:
    staff: User
    customer: int
    cats: dict[str, ledger.CategoryRef]


async def _world(sm: SM) -> W:
    w = W()
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=1, role="staff"))
    async with read_session(sm) as s:
        w.staff = (await s.scalars(select(User))).one()
        w.cats = {c.name: c for c in await ledger.categories(s)}
    async with uow(sm, actor_id=w.staff.id) as s:
        w.customer = (
            await cust.create(
                s, w.staff, name="Umida", address_form=AddressForm.OPA, raw_phone="+998900000601"
            )
        ).id
    return w


async def _stock_in(sm: SM, w: W, name: str, n: int) -> None:
    async with uow(sm, actor_id=w.staff.id) as s:
        await inventory.stock_in(s, w.staff, w.cats[name].id, n)


async def _qty(sm: SM, w: W, name: str) -> int:
    async with read_session(sm) as s:
        return (await inventory.levels(s, [w.cats[name].id]))[0].qty


async def _sell(
    sm: SM,
    w: W,
    items: list[ItemInput],
    *,
    customer: int | None = None,
    total: int | None = None,
    paid: int | None = None,
    due: date | None = None,
) -> list[sales.CreatedSale]:
    async with uow(sm, actor_id=w.staff.id) as s:
        return await sales.create_sales(
            s,
            w.staff,
            customer_id=customer,
            items=items,
            final_total=total,
            paid=paid,
            due_date=due,
            today=TODAY,
        )


# ---------------------------------------------------------------- sales
async def test_cash_sale_reduces_stock_and_has_no_debt(sm: SM) -> None:
    w = await _world(sm)
    await _stock_in(sm, w, "ko'ylak", 10)
    [sale] = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 2, 175_000)])
    assert (sale.plan.total, sale.plan.paid, sale.plan.debt, sale.debt_id) == (
        350_000,
        350_000,
        0,
        None,
    )
    assert await _qty(sm, w, "ko'ylak") == 8


async def test_discount_is_stored_separately(sm: SM) -> None:
    """BR-073: 500 minglik ko'ylak 450 ga → savdo 450 000, chegirma 50 000."""
    w = await _world(sm)
    [sale] = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 500_000)], total=450_000)
    async with read_session(sm) as s:
        row = await s.get(Sale, sale.sale_id)
    assert row is not None and (row.items_total, row.discount_amount, row.total_amount) == (
        500_000,
        50_000,
        450_000,
    )


async def test_mixed_sale_creates_linked_debt(sm: SM) -> None:
    """BR-071a: savdo 500 000; naqd 200 000; qarz 300 000 — and paying it later closes it."""
    w = await _world(sm)
    [sale] = await _sell(
        sm,
        w,
        [ItemInput(w.cats["ko'ylak"].id, 1, 500_000)],
        customer=w.customer,
        paid=200_000,
        due=date(2026, 12, 1),
    )
    assert (sale.plan.total, sale.plan.paid, sale.plan.debt) == (
        500_000,
        200_000,
        300_000,
    ) and sale.debt_id
    async with read_session(sm) as s:
        debt = await s.get(Debt, sale.debt_id)
        assert debt is not None and (debt.kind, debt.sale_id, debt.total_amount, debt.due_date) == (
            "sale_remainder",
            sale.sale_id,
            300_000,
            date(2026, 12, 1),
        )
        shop = (await ledger.section_ids(s))["shop"]
        assert await ledger.balances(s, w.customer) == {shop: 300_000}
    async with uow(sm, actor_id=w.staff.id) as s:
        await ledger.record_payment(
            s,
            w.staff,
            customer_id=w.customer,
            section_id=shop,
            amount=300_000,
            kind=PaymentKind.PAYMENT,
            today=TODAY,
        )
    async with read_session(sm) as s:
        assert await ledger.balances(s, w.customer) == {}


async def test_unpaid_part_without_customer_is_refused(sm: SM) -> None:
    w = await _world(sm)
    with pytest.raises(CustomerRequiredError):
        await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 500_000)], paid=100_000)


async def test_price_above_list_is_refused(sm: SM) -> None:
    w = await _world(sm)
    with pytest.raises(PriceAboveListError):
        await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 500_000)], total=600_000)


async def test_two_sections_become_two_sales_but_not_with_one_price(sm: SM) -> None:
    w = await _world(sm)
    made = await _sell(
        sm,
        w,
        [
            ItemInput(w.cats["ko'ylak"].id, 1, 300_000),
            ItemInput(w.cats["ichki kiyim"].id, 2, 40_000),
        ],
    )
    assert sorted((m.section_id, m.plan.total) for m in made) == sorted(
        [(w.cats["ko'ylak"].section_id, 300_000), (w.cats["ichki kiyim"].section_id, 80_000)]
    )
    with pytest.raises(sales.MultiSectionOverrideError):
        await _sell(
            sm,
            w,
            [
                ItemInput(w.cats["ko'ylak"].id, 1, 300_000),
                ItemInput(w.cats["ichki kiyim"].id, 1, 40_000),
            ],
            total=300_000,
        )


async def test_negative_stock_is_allowed_but_warned(sm: SM) -> None:
    """BR-093a"""
    w = await _world(sm)
    await _stock_in(sm, w, "yubka", 1)
    [sale] = await _sell(sm, w, [ItemInput(w.cats["yubka"].id, 3, 90_000)])
    assert [(x.name, x.qty) for x in sale.warnings] == [("yubka", -2)]


# ---------------------------------------------------------------- credit goods leave the stock (Q-26)
async def test_credit_goods_leave_stock_and_cancel_returns_them(sm: SM) -> None:
    w = await _world(sm)
    await _stock_in(sm, w, "shim", 5)
    async with uow(sm, actor_id=w.staff.id) as s:
        [d] = await ledger.create_debts(
            s,
            w.staff,
            customer_id=w.customer,
            items=[ItemInput(w.cats["shim"].id, 2, 200_000)],
            due_date=None,
            today=TODAY,
        )
    assert await _qty(sm, w, "shim") == 3
    async with uow(sm, actor_id=w.staff.id) as s:
        await ledger.cancel_debt(s, w.staff, d.debt_id)
    assert await _qty(sm, w, "shim") == 5


async def test_cancel_sale_restores_stock_and_cancels_linked_debt(sm: SM) -> None:
    w = await _world(sm)
    await _stock_in(sm, w, "ko'ylak", 4)
    [sale] = await _sell(
        sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 500_000)], customer=w.customer, paid=200_000
    )
    async with uow(sm, actor_id=w.staff.id) as s:
        await sales.cancel_sale(s, w.staff, sale.sale_id)
    assert await _qty(sm, w, "ko'ylak") == 4
    async with read_session(sm) as s:
        assert await ledger.balances(s, w.customer) == {}
        with pytest.raises(ledger.AlreadyCancelledError):
            async with uow(sm, actor_id=w.staff.id) as s2:
                await sales.cancel_sale(s2, w.staff, sale.sale_id)


async def test_cancel_sale_refused_when_its_debt_has_payments(sm: SM) -> None:
    w = await _world(sm)
    [sale] = await _sell(
        sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 500_000)], customer=w.customer, paid=200_000
    )
    shop = w.cats["ko'ylak"].section_id
    async with uow(sm, actor_id=w.staff.id) as s:
        await ledger.record_payment(
            s,
            w.staff,
            customer_id=w.customer,
            section_id=shop,
            amount=50_000,
            kind=PaymentKind.PAYMENT,
            today=TODAY,
        )
    before = await _qty(sm, w, "ko'ylak")
    with pytest.raises(ledger.DebtHasPaymentsError):
        async with uow(sm, actor_id=w.staff.id) as s:
            await sales.cancel_sale(s, w.staff, sale.sale_id)
    assert await _qty(sm, w, "ko'ylak") == before  # nothing half-done


# ---------------------------------------------------------------- stock
async def test_stock_in_count_and_low_stock(sm: SM) -> None:
    """BR-091/094/095/096: kirim, sanoq (farq tuzatish yozuvi), kam qoldi (sukut 3)."""
    w = await _world(sm)
    await _stock_in(sm, w, "kofta", 20)
    async with uow(sm, actor_id=w.staff.id) as s:
        plan = await inventory.stock_count(
            s, w.staff, {w.cats["kofta"].id: 18, w.cats["sumka"].id: 2}
        )
    assert [(d.name, d.before, d.counted, d.diff) for d in plan] == [
        ("kofta", 20, 18, -2),
        ("sumka", 0, 2, 2),
    ]
    async with read_session(sm) as s:
        low = {r.name: r.qty for r in await inventory.low_stock(s)}
    assert low["sumka"] == 2 and "kofta" not in low  # 2 <= threshold 3 → low; 18 is fine
    assert await _qty(sm, w, "kofta") == 18


async def test_stock_count_preview_writes_nothing(sm: SM) -> None:
    w = await _world(sm)
    async with read_session(sm) as s:
        plan = await inventory.plan_count(s, {w.cats["kofta"].id: 7})
    assert plan[0].diff == 7 and await _qty(sm, w, "kofta") == 0


async def test_only_staff_can_change_stock(sm: SM) -> None:
    w = await _world(sm)
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=2, role="customer"))
    async with read_session(sm) as s:
        outsider = (await s.scalars(select(User).where(User.telegram_id == 2))).one()
    with pytest.raises(cust.NotAllowedError):
        async with uow(sm, actor_id=outsider.id) as s:
            await inventory.stock_in(s, outsider, w.cats["kofta"].id, 5)


# ---------------------------------------------------------------- database guards
async def test_db_rejects_inconsistent_sale(sm: SM) -> None:
    w = await _world(sm)
    shop = w.cats["ko'ylak"].section_id
    with pytest.raises(DBAPIError, match="teng emas"):  # items don't add up to items_total
        async with uow(sm, actor_id=w.staff.id) as s:
            sid = (
                await s.execute(
                    text(
                        "INSERT INTO sales (section_id, sale_date, items_total, discount_amount, total_amount, paid_amount) VALUES (:s, :d, 500000, 0, 500000, 500000) RETURNING id"
                    ),
                    {"s": shop, "d": TODAY},
                )
            ).scalar_one()
            await s.execute(
                text(
                    "INSERT INTO sale_items (sale_id, section_id, category_id, quantity, unit_price) VALUES (:i, :s, :c, 1, 100000)"
                ),
                {"i": sid, "s": shop, "c": w.cats["ko'ylak"].id},
            )
    with pytest.raises(DBAPIError):  # paid more than total
        async with uow(sm, actor_id=w.staff.id) as s:
            await s.execute(
                text(
                    "INSERT INTO sales (section_id, sale_date, items_total, discount_amount, total_amount, paid_amount, customer_id) VALUES (:s, :d, 100, 0, 100, 101, :c)"
                ),
                {"s": shop, "d": TODAY, "c": w.customer},
            )
    with pytest.raises(DBAPIError):  # unpaid part without a customer
        async with uow(sm, actor_id=w.staff.id) as s:
            await s.execute(
                text(
                    "INSERT INTO sales (section_id, sale_date, items_total, discount_amount, total_amount, paid_amount) VALUES (:s, :d, 100, 0, 100, 50)"
                ),
                {"s": shop, "d": TODAY},
            )


async def test_sale_amounts_and_stock_history_are_immutable(sm: SM) -> None:
    w = await _world(sm)
    [sale] = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 100_000)])
    with pytest.raises(DBAPIError, match="o'zgartirilmaydi"):
        async with uow(sm, actor_id=w.staff.id) as s:
            await s.execute(
                text(
                    "UPDATE sales SET paid_amount = 1, total_amount = 1, items_total = 1 WHERE id = :i"
                ),
                {"i": sale.sale_id},
            )
    with pytest.raises(DBAPIError):
        async with uow(sm, actor_id=w.staff.id) as s:
            await s.execute(text("UPDATE stock_movements SET quantity = 99"))
    with pytest.raises(DBAPIError):
        async with uow(sm, actor_id=w.staff.id) as s:
            await s.execute(text("DELETE FROM stock_movements"))


async def test_app_role_cannot_edit_or_delete_stock_and_sale_items(app_sm: SM, sm: SM) -> None:
    w = await _world(sm)
    for sql in (
        "UPDATE stock_movements SET quantity = 1",
        "DELETE FROM sale_items",
        "UPDATE sale_items SET quantity = 1",
        "DELETE FROM sales",
    ):
        with pytest.raises(DBAPIError):
            async with uow(app_sm, actor_id=w.staff.id) as s:
                await s.execute(text(sql))
