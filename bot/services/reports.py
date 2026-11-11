"""Reports (BR-120…BR-130, master §4.7): per period, sections NEVER mixed, every number computed by SQL.

Definitions (owner decisions BR-071a, BR-084a, Q-26):
- Sales (naqd/aralash) = Σ `sales.total_amount` — the whole price, also the part left on credit.
- Credit goods (to'liq nasiya) = Σ regular `debts.total_amount`. A mixed sale's unpaid part (`sale_remainder`) is shown as
  "shundan nasiyaga" and is NOT added again to the turnover.
- Turnover = sales + credit goods.
- Cash in = Σ `sales.paid_amount` + Σ payments(kind=payment); cash out = Σ returns.cash_refund.
  Write-offs and 'return' payments are neither cash nor turnover — they are shown as their own lines.
Dates are business dates in Asia/Tashkent (sale_date, debt_date, paid_on, return_date).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    Category,
    Customer,
    Debt,
    DebtItem,
    LedgerStatus,
    Payment,
    Return,
    Sale,
    SaleItem,
    Section,
)
from bot.utils.dates import Period

ACTIVE = LedgerStatus.ACTIVE


def _i(value: Any) -> int:
    return int(value or 0)


@dataclass(slots=True)
class CategoryLine:
    name: str
    quantity: int = 0
    amount: int = 0  # at list price


@dataclass(slots=True)
class SectionReport:
    code: str
    sales_count: int = 0
    sales_total: int = 0  # whole price of cash/mixed sales
    sales_cash: int = 0  # paid at the moment of sale
    sales_on_credit: int = 0  # unpaid part of mixed sales (included in sales_total)
    discount_total: int = 0
    credit_goods_count: int = 0
    credit_goods_total: int = 0  # pure credit records (regular debts)
    payments_cash: int = 0  # debt payments received (cash)
    write_offs: int = 0  # forgiven — not cash
    returns_count: int = 0
    returns_value: int = 0
    returns_cash_refund: int = 0
    returns_debt_reduction: int = 0
    categories: list[CategoryLine] = field(default_factory=list)

    @property
    def turnover(self) -> int:
        return self.sales_total + self.credit_goods_total

    @property
    def cash_in(self) -> int:
        return self.sales_cash + self.payments_cash

    @property
    def net_cash(self) -> int:
        return self.cash_in - self.returns_cash_refund

    @property
    def debt_given(self) -> int:
        """New credit in the period: pure credit goods + the unpaid part of mixed sales."""
        return self.credit_goods_total + self.sales_on_credit


@dataclass(slots=True)
class PeriodReport:
    period: Period
    sections: dict[str, SectionReport]
    new_customers: int = 0


async def sales_report(
    session: AsyncSession, period: Period, *, section_code: str | None = None
) -> PeriodReport:
    start, end = period.start, period.end
    sections = {
        code: SectionReport(code)
        for code in (await session.scalars(select(Section.code).order_by(Section.id))).all()
    }
    code_of = {
        sid: code for sid, code in (await session.execute(select(Section.id, Section.code))).all()
    }

    r_sales = await session.execute(
        select(
            Sale.section_id,
            func.count(),
            cast(func.sum(Sale.total_amount), BigInteger),
            cast(func.sum(Sale.paid_amount), BigInteger),
            cast(func.sum(Sale.discount_amount), BigInteger),
        )
        .where(Sale.status == ACTIVE, Sale.sale_date.between(start, end))
        .group_by(Sale.section_id)
    )
    for sid, n, total, paid, disc in r_sales.all():
        s = sections[code_of[sid]]
        s.sales_count, s.sales_total, s.sales_cash, s.discount_total = (
            _i(n),
            _i(total),
            _i(paid),
            _i(disc),
        )
        s.sales_on_credit = s.sales_total - s.sales_cash

    r_debts = await session.execute(
        select(Debt.section_id, func.count(), cast(func.sum(Debt.total_amount), BigInteger))
        .where(Debt.status == ACTIVE, Debt.kind == "regular", Debt.debt_date.between(start, end))
        .group_by(Debt.section_id)
    )
    for sid, n, total in r_debts.all():
        sections[code_of[sid]].credit_goods_count, sections[code_of[sid]].credit_goods_total = (
            _i(n),
            _i(total),
        )

    r_pay = await session.execute(
        select(Payment.section_id, Payment.kind, cast(func.sum(Payment.amount), BigInteger))
        .where(
            Payment.status == ACTIVE,
            Payment.paid_on.between(start, end),
            Payment.kind.in_(["payment", "write_off"]),
        )
        .group_by(Payment.section_id, Payment.kind)
    )
    for sid, kind, total in r_pay.all():
        s = sections[code_of[sid]]
        if kind == "payment":
            s.payments_cash = _i(total)
        else:
            s.write_offs = _i(total)

    r_ret = await session.execute(
        select(
            Return.section_id,
            func.count(),
            cast(func.sum(Return.value), BigInteger),
            cast(func.sum(Return.cash_refund), BigInteger),
            cast(func.sum(Return.debt_reduction), BigInteger),
        )
        .where(Return.status == ACTIVE, Return.return_date.between(start, end))
        .group_by(Return.section_id)
    )
    for sid, n, value, refund, red in r_ret.all():
        s = sections[code_of[sid]]
        s.returns_count, s.returns_value, s.returns_cash_refund, s.returns_debt_reduction = (
            _i(n),
            _i(value),
            _i(refund),
            _i(red),
        )

    # product types: quantities and list-price amounts from sales and from credit goods
    cat_name = {
        cid: name for cid, name in (await session.execute(select(Category.id, Category.name))).all()
    }
    acc: dict[str, dict[int, CategoryLine]] = defaultdict(dict)

    async def add(rows_: object, sect_col: str) -> None:
        for sid, cid, qty, amount in rows_.all():  # type: ignore[attr-defined]
            line = acc[code_of[sid]].setdefault(cid, CategoryLine(cat_name[cid]))
            line.quantity += _i(qty)
            line.amount += _i(amount)

    await add(
        await session.execute(
            select(
                SaleItem.section_id,
                SaleItem.category_id,
                cast(func.sum(SaleItem.quantity), BigInteger),
                cast(func.sum(SaleItem.quantity * SaleItem.unit_price), BigInteger),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.status == ACTIVE, Sale.sale_date.between(start, end))
            .group_by(SaleItem.section_id, SaleItem.category_id)
        ),
        "section_id",
    )
    await add(
        await session.execute(
            select(
                DebtItem.section_id,
                DebtItem.category_id,
                cast(func.sum(DebtItem.quantity), BigInteger),
                cast(func.sum(DebtItem.quantity * DebtItem.unit_price), BigInteger),
            )
            .join(Debt, Debt.id == DebtItem.debt_id)
            .where(
                Debt.status == ACTIVE, Debt.kind == "regular", Debt.debt_date.between(start, end)
            )
            .group_by(DebtItem.section_id, DebtItem.category_id)
        ),
        "section_id",
    )
    for code, lines in acc.items():
        sections[code].categories = sorted(lines.values(), key=lambda x: -x.amount)

    from bot.utils.dates import TASHKENT

    lo = datetime.combine(start, datetime.min.time(), TASHKENT)
    hi = datetime.combine(end, datetime.max.time(), TASHKENT)
    new_customers = _i(
        await session.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.deleted_at.is_(None), Customer.created_at.between(lo, hi))
        )
    )
    if section_code is not None:
        sections = {section_code: sections[section_code]}
    return PeriodReport(period, sections, new_customers)


@dataclass(frozen=True, slots=True)
class Delta:
    a: int
    b: int

    @property
    def diff(self) -> int:
        return self.b - self.a

    @property
    def percent(self) -> str | None:
        """Change in % with one decimal, integer math only. None when the base is 0."""
        if self.a == 0:
            return None
        tenths = (
            abs(self.diff) * 1000 * 2 // self.a
        )  # tenths of a percent, doubled for half-up rounding
        tenths = (tenths + 1) // 2
        sign = "+" if self.diff > 0 else ("-" if self.diff < 0 else "")
        return f"{sign}{tenths // 10},{tenths % 10}%"


@dataclass(slots=True)
class Comparison:
    a: PeriodReport
    b: PeriodReport

    def turnover(self, code: str) -> Delta:
        return Delta(self.a.sections[code].turnover, self.b.sections[code].turnover)

    def net_cash(self, code: str) -> Delta:
        return Delta(self.a.sections[code].net_cash, self.b.sections[code].net_cash)

    def debt_given(self, code: str) -> Delta:
        return Delta(self.a.sections[code].debt_given, self.b.sections[code].debt_given)


async def compare_periods(session: AsyncSession, a: Period, b: Period) -> Comparison:
    return Comparison(await sales_report(session, a), await sales_report(session, b))


async def payments_in(
    session: AsyncSession, period: Period, *, section_code: str | None = None
) -> list[tuple[date, str, str, int, str]]:
    """Who paid (or was forgiven) in the period: (date, customer, section code, amount, kind)."""
    q = (
        select(Payment.paid_on, Customer.name, Customer.address_form, Section.code, Payment.amount, Payment.kind)
        .join(Customer, Customer.id == Payment.customer_id)
        .join(Section, Section.id == Payment.section_id)
        .where(Payment.status == ACTIVE, Payment.kind.in_(["payment", "write_off"]), Payment.paid_on.between(period.start, period.end))
        .order_by(Payment.paid_on.desc(), Payment.id.desc())
    )  # fmt: skip
    if section_code is not None:
        q = q.where(Section.code == section_code)
    return [
        (d, f"{n} {f}", code, int(a), k) for d, n, f, code, a, k in (await session.execute(q)).all()
    ]
