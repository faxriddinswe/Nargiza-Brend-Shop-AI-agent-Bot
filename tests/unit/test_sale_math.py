"""BR-071a, BR-072a, BR-073a: sale arithmetic. Amounts computed by hand."""

from __future__ import annotations

import pytest

from bot.services.sale_math import (
    CustomerRequiredError,
    PaidAboveTotalError,
    PriceAboveListError,
    SaleMathError,
    SalePlan,
    plan_sale,
    proportional_value,
)


def test_plain_cash_sale() -> None:
    assert plan_sale(450_000, final_total=None, paid=None, has_customer=False) == SalePlan(
        450_000, 0, 450_000, 450_000, 0
    )


def test_discount_is_list_minus_agreed() -> None:
    """BR-073: 500 minglik ko'ylakni 450 ga sotdim → savdo 450 000, chegirma 50 000."""
    assert plan_sale(500_000, final_total=450_000, paid=None, has_customer=False) == SalePlan(
        500_000, 50_000, 450_000, 450_000, 0
    )


def test_mixed_sale() -> None:
    """BR-071: ko'ylak 500 ming, 200 berdi, qolgani qarz → savdo 500 000, naqd 200 000, qarz 300 000."""
    assert plan_sale(500_000, final_total=None, paid=200_000, has_customer=True) == SalePlan(
        500_000, 0, 500_000, 200_000, 300_000
    )


def test_discount_and_mixed() -> None:
    assert plan_sale(500_000, final_total=450_000, paid=100_000, has_customer=True) == SalePlan(
        500_000, 50_000, 450_000, 100_000, 350_000
    )


def test_unpaid_part_needs_customer() -> None:
    """BR-072a"""
    with pytest.raises(CustomerRequiredError):
        plan_sale(500_000, final_total=None, paid=200_000, has_customer=False)


def test_price_above_list_is_refused() -> None:
    with pytest.raises(PriceAboveListError):
        plan_sale(500_000, final_total=600_000, paid=None, has_customer=True)


def test_paid_above_total_is_refused() -> None:
    with pytest.raises(PaidAboveTotalError) as e:
        plan_sale(500_000, final_total=None, paid=500_001, has_customer=True)
    assert (e.value.total, e.value.paid) == (500_000, 500_001)


@pytest.mark.parametrize(
    "bad",
    [
        dict(items_total=0),
        dict(items_total=-5),
        dict(items_total=100, final_total=0),
        dict(items_total=100, paid=-1),
        dict(items_total=100.0),
    ],
)
def test_bad_numbers(bad: dict[str, float]) -> None:
    kw = {"final_total": None, "paid": None, "has_customer": True, **bad}
    with pytest.raises(SaleMathError):
        plan_sale(**kw)  # type: ignore[arg-type]


def test_zero_paid_with_customer_is_all_credit() -> None:
    assert plan_sale(300_000, final_total=None, paid=0, has_customer=True).debt == 300_000


# ---- refund value of returned units (discount spread proportionally, partials add up exactly)
def test_full_return_refunds_exactly_what_was_paid() -> None:
    v = proportional_value(
        2,
        250_000,
        total=450_000,
        items_total=500_000,
        already_returned_value=0,
        already_returned_qty=0,
        item_quantity=2,
    )
    assert v == 450_000


def test_partial_returns_add_up_exactly() -> None:
    """3 pieces @ 100 000 sold for 250 000 (discount 50 000): return 1, 1, 1 → sums to exactly 250 000."""
    kw = dict(total=250_000, items_total=300_000, item_quantity=3)
    a = proportional_value(1, 100_000, already_returned_value=0, already_returned_qty=0, **kw)
    b = proportional_value(1, 100_000, already_returned_value=a, already_returned_qty=1, **kw)
    c = proportional_value(1, 100_000, already_returned_value=a + b, already_returned_qty=2, **kw)
    assert (a, b, c) == (83_333, 83_334, 83_333) and a + b + c == 250_000


def test_return_more_than_sold_is_refused() -> None:
    with pytest.raises(SaleMathError):
        proportional_value(
            2,
            100_000,
            total=100_000,
            items_total=100_000,
            already_returned_value=0,
            already_returned_qty=1,
            item_quantity=2,
        )


def test_no_discount_value_is_plain_price() -> None:
    assert (
        proportional_value(
            1,
            175_000,
            total=350_000,
            items_total=350_000,
            already_returned_value=0,
            already_returned_qty=0,
            item_quantity=2,
        )
        == 175_000
    )
