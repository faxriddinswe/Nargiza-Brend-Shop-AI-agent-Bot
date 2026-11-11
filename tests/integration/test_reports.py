"""Reports: hand-computed numbers; sections never mixed; cash vs credit vs write-off vs return kept apart."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, PaymentKind, User
from bot.db.session import read_session, uow
from bot.services import customers as cust
from bot.services import ledger, reports, returns, sales
from bot.services.ledger import ItemInput
from bot.services.reports import Delta
from bot.utils.dates import Period

SM = async_sessionmaker[AsyncSession]
D10, D11, D12 = date(2026, 11, 10), date(2026, 11, 11), date(2026, 11, 12)


async def _scenario(sm: SM) -> User:
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=1, role="staff"))
    async with read_session(sm) as s:
        st = (await s.scalars(select(User))).one()
        cats = {c.name: c for c in await ledger.categories(s)}
    async with uow(sm, actor_id=st.id) as s:
        c = await cust.create(
            s, st, name="Umida", address_form=AddressForm.OPA, raw_phone="+998900000951"
        )
        cid = c.id
    shop = cats["ko'ylak"].section_id
    async with uow(sm, actor_id=st.id) as s:
        # day 10 — shop: cash sale 500 000 list → 450 000 agreed (customer-less)
        await sales.create_sales(
            s,
            st,
            customer_id=None,
            items=[ItemInput(cats["ko'ylak"].id, 1, 500_000)],
            final_total=450_000,
            paid=None,
            due_date=None,
            today=D10,
        )
        # shop: mixed sale 500 000, 200 000 paid, 300 000 on credit
        await sales.create_sales(
            s,
            st,
            customer_id=cid,
            items=[ItemInput(cats["shim"].id, 1, 500_000)],
            final_total=None,
            paid=200_000,
            due_date=None,
            today=D10,
        )
        # lingerie: pure credit goods 80 000
        [debt] = await ledger.create_debts(
            s,
            st,
            customer_id=cid,
            items=[ItemInput(cats["ichki kiyim"].id, 2, 40_000)],
            due_date=None,
            today=D10,
        )
    async with uow(sm, actor_id=st.id) as s:
        # day 11 — shop: payment 100 000 (FIFO onto the mixed sale's credit part) and a 20 000 write-off
        await ledger.record_payment(
            s,
            st,
            customer_id=cid,
            section_id=shop,
            amount=100_000,
            kind=PaymentKind.PAYMENT,
            today=D11,
        )
        await ledger.record_payment(
            s,
            st,
            customer_id=cid,
            section_id=shop,
            amount=20_000,
            kind=PaymentKind.WRITE_OFF,
            today=D11,
        )
    async with read_session(sm) as s:
        view = await returns.source_view(s, "debt", debt.debt_id)
    async with uow(sm, actor_id=st.id) as s:  # lingerie: the credit goods come back
        await returns.register_return(
            s,
            st,
            source_type="debt",
            source_id=debt.debt_id,
            qty_by_item={view.items[0].id: 2},
            today=D11,
        )
    return st


async def _report(sm: SM, start: date, end: date) -> reports.PeriodReport:
    async with read_session(sm) as s:
        return await reports.sales_report(s, Period(start, end, "test"))


async def test_two_day_report_numbers(sm: SM) -> None:
    await _scenario(sm)
    r = await _report(sm, D10, D11)
    shop, lin = r.sections["shop"], r.sections["lingerie"]
    assert (
        shop.sales_count,
        shop.sales_total,
        shop.sales_cash,
        shop.sales_on_credit,
        shop.discount_total,
    ) == (2, 950_000, 650_000, 300_000, 50_000)
    assert (shop.credit_goods_total, shop.turnover) == (0, 950_000)
    assert (shop.payments_cash, shop.write_offs, shop.cash_in, shop.net_cash, shop.debt_given) == (
        100_000,
        20_000,
        750_000,
        750_000,
        300_000,
    )
    assert (lin.sales_total, lin.credit_goods_count, lin.credit_goods_total, lin.turnover) == (
        0,
        1,
        80_000,
        80_000,
    )
    assert (
        lin.returns_count,
        lin.returns_value,
        lin.returns_debt_reduction,
        lin.returns_cash_refund,
    ) == (1, 80_000, 80_000, 0)
    assert (lin.cash_in, lin.payments_cash) == (
        0,
        0,
    )  # underwear money never leaks into the shop section
    assert shop.returns_count == 0 and r.new_customers == 1


async def test_report_respects_the_period(sm: SM) -> None:
    await _scenario(sm)
    d10 = await _report(sm, D10, D10)
    assert d10.sections["shop"].sales_total == 950_000 and d10.sections["shop"].payments_cash == 0
    d11 = await _report(sm, D11, D11)
    assert d11.sections["shop"].sales_total == 0 and d11.sections["shop"].payments_cash == 100_000
    assert d11.sections["lingerie"].returns_count == 1
    assert (await _report(sm, D12, D12)).sections["shop"].turnover == 0


async def test_product_types_by_quantity(sm: SM) -> None:
    await _scenario(sm)
    r = await _report(sm, D10, D10)
    shop = {c.name: (c.quantity, c.amount) for c in r.sections["shop"].categories}
    assert shop == {"ko'ylak": (1, 500_000), "shim": (1, 500_000)}  # list prices
    assert {c.name: (c.quantity, c.amount) for c in r.sections["lingerie"].categories} == {
        "ichki kiyim": (2, 80_000)
    }


async def test_single_section_filter(sm: SM) -> None:
    await _scenario(sm)
    async with read_session(sm) as s:
        r = await reports.sales_report(s, Period(D10, D11, "x"), section_code="lingerie")
    assert list(r.sections) == ["lingerie"]


async def test_cancelled_records_are_not_counted(sm: SM) -> None:
    st = await _scenario(sm)
    async with read_session(sm) as s:
        entry = next(
            e
            for e in await ledger.recent_entries(s, limit=20)
            if e.kind == "sale" and e.amount == 450_000
        )
    async with uow(sm, actor_id=st.id) as s:
        await sales.cancel_sale(s, st, entry.id)
    r = await _report(sm, D10, D11)
    assert r.sections["shop"].sales_count == 1 and r.sections["shop"].sales_total == 500_000


async def test_compare_two_periods(sm: SM) -> None:
    await _scenario(sm)
    async with read_session(sm) as s:
        cmp = await reports.compare_periods(s, Period(D10, D10, "a"), Period(D11, D11, "b"))
    t = cmp.turnover("shop")
    assert (t.a, t.b, t.diff, t.percent) == (950_000, 0, -950_000, "-100,0%")
    assert cmp.net_cash("shop").diff == 100_000 - 650_000


def test_delta_percent_is_integer_math() -> None:
    assert Delta(200_000, 300_000).percent == "+50,0%"
    assert Delta(300_000, 200_000).percent == "-33,3%"
    assert Delta(3, 4).percent == "+33,3%"
    assert Delta(100, 100).percent == "0,0%"
    assert Delta(0, 500).percent is None
    assert Delta(1_000_000, 1_000_001).percent == "+0,0%"


def test_excel_formula_injection_is_neutralised() -> None:
    from io import BytesIO

    from openpyxl import load_workbook

    from bot.services.excel_export import debtors_workbook
    from bot.services.ledger import DebtorRow

    row = DebtorRow(1, "=HYPERLINK(1)", "opa", 1, 100_000, None)
    wb = load_workbook(BytesIO(debtors_workbook([row], {1: "+998900000000"}, {1: "shop"})))
    cell = wb.worksheets[0]["B2"]
    assert cell.data_type == "s" and cell.value.startswith("'=")
