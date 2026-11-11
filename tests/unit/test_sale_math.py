"""BR-071a, BR-072a, BR-073a: sale arithmetic. Amounts computed by hand."""

from __future__ import annotations

import pytest

from bot.services.sale_math import (
    CustomerRequiredError,
    PaidAboveTotalError,
    PriceAboveListError,
    SaleMathError,
    SalePlan,
    item_value,
    plan_sale,
    split_total,
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


# ---- exact shares and refund values (discount spread; sums never exceed what was paid)
def test_split_total_is_exact_and_deterministic() -> None:
    assert (
        split_total(200, [100, 100, 100]) == [67, 67, 66]
        and sum(split_total(200, [100, 100, 100])) == 200
    )
    assert split_total(450_000, [500_000]) == [450_000]
    assert split_total(300, [100, 100, 100]) == [100, 100, 100]
    assert split_total(10, [1, 1, 1]) == [4, 3, 3]


@pytest.mark.parametrize("total", [1, 2, 7, 199, 200, 250_000, 999_999])
def test_split_total_always_adds_up(total: int) -> None:
    weights = [100_000, 175_000, 333_333, 90_000]
    parts = split_total(total, weights)
    assert sum(parts) == total and all(p >= 0 for p in parts)


def test_owner_review_case_three_lines_never_refund_more_than_paid() -> None:
    """3 lines × 100, agreed price 200: refunds add up to exactly 200 (was 201 with per-line rounding)."""
    shares = split_total(200, [100, 100, 100])
    values = [
        item_value(1, share=sh, item_quantity=1, already_returned_value=0, already_returned_qty=0)
        for sh in shares
    ]
    assert values == [67, 67, 66] and sum(values) == 200


def test_partial_returns_of_one_line_add_up_exactly() -> None:
    """3 pieces @ 100 000 sold for 250 000: return 1, 1, 1 → exactly 250 000."""
    [share] = split_total(250_000, [300_000])
    kw = dict(share=share, item_quantity=3)
    a = item_value(1, already_returned_value=0, already_returned_qty=0, **kw)
    b = item_value(1, already_returned_value=a, already_returned_qty=1, **kw)
    c = item_value(1, already_returned_value=a + b, already_returned_qty=2, **kw)
    assert (a, b, c) == (83_333, 83_334, 83_333) and a + b + c == 250_000


def test_return_more_than_sold_is_refused() -> None:
    with pytest.raises(SaleMathError):
        item_value(
            2, share=100_000, item_quantity=2, already_returned_value=0, already_returned_qty=1
        )
    with pytest.raises(SaleMathError):
        item_value(
            0, share=100_000, item_quantity=2, already_returned_value=0, already_returned_qty=0
        )


def test_no_discount_value_is_plain_price() -> None:
    [share] = split_total(350_000, [350_000])
    assert (
        item_value(
            1, share=share, item_quantity=2, already_returned_value=0, already_returned_qty=0
        )
        == 175_000
    )


@pytest.mark.parametrize("bad", [(-1, [1]), (5, []), (5, [0]), (5, [3, -1])])
def test_split_total_rejects_nonsense(bad: tuple[int, list[int]]) -> None:
    with pytest.raises(SaleMathError):
        split_total(*bad)
