"""Returns (BR-080…087, BR-084a). Every amount computed by hand; fake data only."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, Payment, PaymentKind, Return, User
from bot.db.session import read_session, uow
from bot.services import customers as cust
from bot.services import inventory, ledger, returns, sales
from bot.services.ledger import ItemInput

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
                s, w.staff, name="Umida", address_form=AddressForm.OPA, raw_phone="+998900000801"
            )
        ).id
    return w


async def _sell(
    sm: SM,
    w: W,
    items: list[ItemInput],
    *,
    customer: int | None = None,
    total: int | None = None,
    paid: int | None = None,
) -> sales.CreatedSale:
    async with uow(sm, actor_id=w.staff.id) as s:
        made = await sales.create_sales(
            s,
            w.staff,
            items=items,
            final_total=total,
            paid=paid,
            customer_id=customer,
            due_date=None,
            today=TODAY,
        )
    return made[0]


async def _debt(sm: SM, w: W, items: list[ItemInput]) -> ledger.CreatedDebt:
    async with uow(sm, actor_id=w.staff.id) as s:
        return (
            await ledger.create_debts(
                s, w.staff, customer_id=w.customer, items=items, due_date=None, today=TODAY
            )
        )[0]


async def _item_ids(sm: SM, typ: str, sid: int) -> list[returns.SourceItem]:
    async with read_session(sm) as s:
        return list((await returns.source_view(s, typ, sid)).items)


async def _return(
    sm: SM,
    w: W,
    typ: str,
    sid: int,
    qty: dict[int, int],
    expected: tuple[int, int, int] | None = None,
) -> tuple[Return, returns.ReturnPlan]:
    async with uow(sm, actor_id=w.staff.id) as s:
        return await returns.register_return(
            s,
            w.staff,
            source_type=typ,
            source_id=sid,
            qty_by_item=qty,
            today=TODAY,
            expected=expected,
        )


async def _qty(sm: SM, w: W, name: str) -> int:
    async with read_session(sm) as s:
        return (await inventory.levels(s, [w.cats[name].id]))[0].qty


async def _owed(sm: SM, w: W) -> int:
    async with read_session(sm) as s:
        return sum((await ledger.balances(s, w.customer)).values())


# ---------------------------------------------------------------- cash sales
async def test_cash_sale_return_refunds_cash_and_restores_stock(sm: SM) -> None:
    w = await _world(sm)
    sale = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 2, 175_000)])
    [item] = await _item_ids(sm, "sale", sale.sale_id)
    ret, plan = await _return(sm, w, "sale", sale.sale_id, {item.id: 1})
    assert (ret.value, ret.debt_reduction, ret.cash_refund, ret.return_payment_id) == (
        175_000,
        0,
        175_000,
        None,
    )
    assert await _qty(sm, w, "ko'ylak") == -1  # sold 2 (from 0), took 1 back
    assert plan.lines[0].quantity == 1


async def test_discounted_sale_refund_is_what_was_paid(sm: SM) -> None:
    """500 minglik ko'ylak 450 ga sotilgan → to'liq qaytarishda 450 000 qaytadi (500 000 emas)."""
    w = await _world(sm)
    sale = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 500_000)], total=450_000)
    [item] = await _item_ids(sm, "sale", sale.sale_id)
    ret, _ = await _return(sm, w, "sale", sale.sale_id, {item.id: 1})
    assert ret.value == 450_000 and ret.cash_refund == 450_000


async def test_partial_returns_add_up_to_exactly_the_total(sm: SM) -> None:
    w = await _world(sm)
    sale = await _sell(sm, w, [ItemInput(w.cats["shim"].id, 3, 100_000)], total=250_000)
    [item] = await _item_ids(sm, "sale", sale.sale_id)
    values = [(await _return(sm, w, "sale", sale.sale_id, {item.id: 1}))[0].value for _ in range(3)]
    assert values == [83_333, 83_334, 83_333] and sum(values) == 250_000
    with pytest.raises(returns.NothingReturnableError):
        await _return(sm, w, "sale", sale.sale_id, {item.id: 1})  # nothing left to return


# ---------------------------------------------------------------- credit goods (BR-084a)
async def test_return_of_unpaid_credit_goods_only_reduces_the_debt(sm: SM) -> None:
    w = await _world(sm)
    debt = await _debt(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    [item] = await _item_ids(sm, "debt", debt.debt_id)
    ret, _ = await _return(sm, w, "debt", debt.debt_id, {item.id: 1})
    assert (ret.debt_reduction, ret.cash_refund) == (300_000, 0)
    assert await _owed(sm, w) == 0
    async with read_session(sm) as s:
        pay = await s.get(Payment, ret.return_payment_id)
    assert pay is not None and (pay.kind, pay.method, pay.amount) == (
        "return",
        None,
        300_000,
    )  # not cash, not a loss


async def test_owner_example_partly_paid_debt_closes_and_excess_is_refunded(sm: SM) -> None:
    """Qarz 300 000, 200 000 to'langan, 300 000 lik tovar qaytdi → qarz yopiladi, 200 000 naqd qaytariladi."""
    w = await _world(sm)
    debt = await _debt(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    async with uow(sm, actor_id=w.staff.id) as s:
        await ledger.record_payment(
            s,
            w.staff,
            customer_id=w.customer,
            section_id=w.cats["ko'ylak"].section_id,
            amount=200_000,
            kind=PaymentKind.PAYMENT,
            today=TODAY,
        )
    [item] = await _item_ids(sm, "debt", debt.debt_id)
    ret, _ = await _return(sm, w, "debt", debt.debt_id, {item.id: 1})
    assert (ret.value, ret.debt_reduction, ret.cash_refund) == (300_000, 100_000, 200_000)
    assert await _owed(sm, w) == 0


async def test_mixed_sale_return(sm: SM) -> None:
    """Sale 500 000, paid 200 000, debt 300 000; everything comes back → debt closed, 200 000 refunded."""
    w = await _world(sm)
    sale = await _sell(
        sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 500_000)], customer=w.customer, paid=200_000
    )
    [item] = await _item_ids(sm, "sale", sale.sale_id)
    ret, _ = await _return(sm, w, "sale", sale.sale_id, {item.id: 1})
    assert (ret.value, ret.debt_reduction, ret.cash_refund) == (
        500_000,
        300_000,
        200_000,
    ) and await _owed(sm, w) == 0


async def test_return_stays_inside_its_section(sm: SM) -> None:
    w = await _world(sm)
    debt = await _debt(
        sm,
        w,
        [
            ItemInput(w.cats["ko'ylak"].id, 1, 300_000),
            ItemInput(w.cats["ichki kiyim"].id, 1, 100_000),
        ],
    )
    async with read_session(sm) as s:
        view = await ledger.customer_ledger(s, w.customer)
    assert len(view) == 2 and debt  # two sections, two debts
    lingerie_debt = next(
        dv
        for sl in view
        for dv, _ in sl.open_debts
        if sl.section_id == w.cats["ichki kiyim"].section_id
    )
    [item] = await _item_ids(sm, "debt", lingerie_debt.id)
    await _return(sm, w, "debt", lingerie_debt.id, {item.id: 1})
    async with read_session(sm) as s:
        assert await ledger.balances(s, w.customer) == {w.cats["ko'ylak"].section_id: 300_000}


# ---------------------------------------------------------------- safety
async def test_cannot_return_more_than_sold(sm: SM) -> None:
    w = await _world(sm)
    sale = await _sell(sm, w, [ItemInput(w.cats["yubka"].id, 1, 90_000)])
    [item] = await _item_ids(sm, "sale", sale.sale_id)
    with pytest.raises(returns.NothingReturnableError):
        await _return(sm, w, "sale", sale.sale_id, {item.id: 2})
    with pytest.raises(returns.NothingReturnableError):
        await _return(sm, w, "sale", sale.sale_id, {item.id: 0})
    with pytest.raises(returns.NothingReturnableError):
        await _return(sm, w, "sale", sale.sale_id, {item.id + 999: 1})


async def test_stale_card_is_refused(sm: SM) -> None:
    """The card showed value/refund; a payment moved the debt in between → refuse, nothing written."""
    w = await _world(sm)
    debt = await _debt(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    [item] = await _item_ids(sm, "debt", debt.debt_id)
    async with read_session(sm) as s:
        plan = await returns.plan_return(s, "debt", debt.debt_id, {item.id: 1})
    shown = (plan.value, plan.debt_reduction, plan.cash_refund)
    async with uow(sm, actor_id=w.staff.id) as s:
        await ledger.record_payment(
            s,
            w.staff,
            customer_id=w.customer,
            section_id=w.cats["ko'ylak"].section_id,
            amount=100_000,
            kind=PaymentKind.PAYMENT,
            today=TODAY,
        )
    with pytest.raises(ledger.PlanChangedError):
        await _return(sm, w, "debt", debt.debt_id, {item.id: 1}, expected=shown)
    async with read_session(sm) as s:
        assert (await s.scalars(select(Return))).first() is None


async def test_cancel_return_restores_debt_and_stock_and_unblocks_cancel_of_source(sm: SM) -> None:
    w = await _world(sm)
    debt = await _debt(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    [item] = await _item_ids(sm, "debt", debt.debt_id)
    ret, _ = await _return(sm, w, "debt", debt.debt_id, {item.id: 1})
    assert await _owed(sm, w) == 0 and await _qty(sm, w, "ko'ylak") == 0
    with pytest.raises(ledger.DebtHasReturnsError):  # the goods came back: cancel the return first
        async with uow(sm, actor_id=w.staff.id) as s:
            await ledger.cancel_debt(s, w.staff, debt.debt_id)
    async with uow(sm, actor_id=w.staff.id) as s:
        await returns.cancel_return(s, w.staff, ret.id)
    assert await _owed(sm, w) == 300_000 and await _qty(sm, w, "ko'ylak") == -1
    async with uow(sm, actor_id=w.staff.id) as s:
        await ledger.cancel_debt(s, w.staff, debt.debt_id)  # now allowed
    assert await _owed(sm, w) == 0


async def test_sale_with_active_return_cannot_be_cancelled(sm: SM) -> None:
    w = await _world(sm)
    sale = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 100_000)])
    [item] = await _item_ids(sm, "sale", sale.sale_id)
    await _return(sm, w, "sale", sale.sale_id, {item.id: 1})
    with pytest.raises(sales.SaleHasReturnsError):
        async with uow(sm, actor_id=w.staff.id) as s:
            await sales.cancel_sale(s, w.staff, sale.sale_id)


async def test_returnable_sources_newest_first_and_hide_fully_returned(sm: SM) -> None:
    w = await _world(sm)
    old = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 100_000)], customer=w.customer)
    new = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 120_000)], customer=w.customer)
    async with read_session(sm) as s:
        found = await returns.returnable_sources(
            s, customer_id=w.customer, category_id=w.cats["ko'ylak"].id
        )
    assert [(v.type, v.id) for v in found] == [("sale", new.sale_id), ("sale", old.sale_id)]
    [item] = await _item_ids(sm, "sale", new.sale_id)
    await _return(sm, w, "sale", new.sale_id, {item.id: 1})
    async with read_session(sm) as s:
        found = await returns.returnable_sources(
            s, customer_id=w.customer, category_id=w.cats["ko'ylak"].id
        )
    assert [(v.type, v.id) for v in found] == [("sale", old.sale_id)]


async def test_db_guards_on_returns(sm: SM) -> None:
    w = await _world(sm)
    sale = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 100_000)])
    with pytest.raises(DBAPIError):  # value must equal debt_reduction + cash_refund
        async with uow(sm, actor_id=w.staff.id) as s:
            await s.execute(
                text(
                    "INSERT INTO returns (section_id, source_type, source_id, value, debt_reduction, cash_refund, return_date) VALUES (:s, 'sale', :i, 100, 10, 10, :d)"
                ),
                {"s": w.cats["ko'ylak"].section_id, "i": sale.sale_id, "d": TODAY},
            )
    with pytest.raises(DBAPIError):  # a debt reduction needs its payment
        async with uow(sm, actor_id=w.staff.id) as s:
            await s.execute(
                text(
                    "INSERT INTO returns (section_id, source_type, source_id, value, debt_reduction, cash_refund, return_date) VALUES (:s, 'sale', :i, 100, 100, 0, :d)"
                ),
                {"s": w.cats["ko'ylak"].section_id, "i": sale.sale_id, "d": TODAY},
            )


# ---------------------------------------------------------------- review fixes (stage 5)
async def test_discounted_three_lines_never_refund_more_than_paid(sm: SM) -> None:
    """3 lines of 100, agreed price 200 → returning all lines refunds exactly 200 (was 201)."""
    w = await _world(sm)
    cats = [w.cats["yubka"], w.cats["shim"], w.cats["kofta"]]
    sale = await _sell(sm, w, [ItemInput(c.id, 1, 100_000) for c in cats], total=200_000)
    assert sale.plan.total == 200_000
    items = await _item_ids(sm, "sale", sale.sale_id)
    values = [(await _return(sm, w, "sale", sale.sale_id, {i.id: 1}))[0].value for i in items]
    assert sum(values) == 200_000 and sorted(values) == [66_666, 66_667, 66_667]


async def test_linked_debt_cannot_be_cancelled_on_its_own(sm: SM) -> None:
    w = await _world(sm)
    sale = await _sell(
        sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 500_000)], customer=w.customer, paid=200_000
    )
    with pytest.raises(ledger.LedgerError):
        async with uow(sm, actor_id=w.staff.id) as s:
            await ledger.cancel_debt(s, w.staff, sale.debt_id or 0)
    async with read_session(sm) as s:
        assert not [
            e for e in await ledger.recent_entries(s) if e.kind == "debt"
        ]  # not offered for cancelling
        assert [e.kind for e in await ledger.recent_entries(s)] == ["sale"]


async def test_return_payment_can_only_be_cancelled_with_its_return(sm: SM) -> None:
    w = await _world(sm)
    debt = await _debt(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    [item] = await _item_ids(sm, "debt", debt.debt_id)
    ret, _ = await _return(sm, w, "debt", debt.debt_id, {item.id: 1})
    with pytest.raises(ledger.LedgerError):
        async with uow(sm, actor_id=w.staff.id) as s:
            await ledger.cancel_payment(s, w.staff, ret.return_payment_id or 0)
    assert await _owed(sm, w) == 0  # untouched


async def test_returning_the_same_customerless_sale_twice_in_parallel(sm: SM) -> None:
    """Two staff return the same cash sale at the same moment: only one succeeds (source row is locked)."""
    import asyncio

    w = await _world(sm)
    sale = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 100_000)])
    [item] = await _item_ids(sm, "sale", sale.sale_id)
    results = await asyncio.gather(
        _return(sm, w, "sale", sale.sale_id, {item.id: 1}),
        _return(sm, w, "sale", sale.sale_id, {item.id: 1}),
        return_exceptions=True,
    )
    assert sum(not isinstance(r, BaseException) for r in results) == 1
    assert await _qty(sm, w, "ko'ylak") == 0  # sold 1, returned 1 — once


async def test_customerless_search_never_shows_other_customers_purchases(sm: SM) -> None:
    w = await _world(sm)
    await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 100_000)], customer=w.customer)
    anon = await _sell(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 120_000)])
    async with read_session(sm) as s:
        found = await returns.returnable_sources(
            s, customer_id=None, category_id=w.cats["ko'ylak"].id
        )
    assert [(v.type, v.id) for v in found] == [("sale", anon.sale_id)]
