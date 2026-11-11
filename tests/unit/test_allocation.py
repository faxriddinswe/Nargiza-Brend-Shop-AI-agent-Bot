"""Payment allocation rules (BR-061, BR-062, BR-064, BR-065). Amounts computed by hand."""

from __future__ import annotations

from datetime import date

import pytest

from bot.services.allocation import (
    Allocation,
    AllocationError,
    DebtNotOpenError,
    NothingToPayError,
    OpenDebt,
    OverpaymentError,
    allocate,
    total_owed,
)

MARCH = OpenDebt(id=1, debt_date=date(2026, 3, 5), remaining=200_000)
MAY = OpenDebt(id=2, debt_date=date(2026, 5, 10), remaining=300_000)


def test_fifo_closes_oldest_debt_first() -> None:
    """BR-061: 250k → March 200k closed, 50k from May."""
    assert allocate([MAY, MARCH], 250_000) == [Allocation(1, 200_000), Allocation(2, 50_000)]


def test_partial_payment_stays_on_oldest_debt() -> None:
    """BR-064"""
    assert allocate([MARCH, MAY], 50_000) == [Allocation(1, 50_000)]


def test_exact_full_payment_closes_everything() -> None:
    assert allocate([MARCH, MAY], 500_000) == [Allocation(1, 200_000), Allocation(2, 300_000)]


def test_overpayment_rejected_with_owed_amount() -> None:
    """BR-065"""
    with pytest.raises(OverpaymentError) as e:
        allocate([MARCH, MAY], 500_001)
    assert (e.value.amount, e.value.owed) == (500_001, 500_000)


def test_same_day_debts_ordered_by_id() -> None:
    """BR-061: barqaror tartib — bir kundagi qarzlar ID bo'yicha."""
    a = OpenDebt(id=7, debt_date=date(2026, 3, 5), remaining=100_000)
    b = OpenDebt(id=3, debt_date=date(2026, 3, 5), remaining=100_000)
    assert allocate([a, b], 150_000) == [Allocation(3, 100_000), Allocation(7, 50_000)]


def test_specific_debt_is_used() -> None:
    """BR-062: "oyoq kiyim qarzidan ayir" — newer debt chosen explicitly."""
    assert allocate([MARCH, MAY], 100_000, debt_id=2) == [Allocation(2, 100_000)]


def test_specific_debt_overpayment_not_spilled() -> None:
    """BR-062 💡: more than that debt's remaining → rejected, not spread to others."""
    with pytest.raises(OverpaymentError) as e:
        allocate([MARCH, MAY], 250_000, debt_id=1)
    assert e.value.owed == 200_000


def test_specific_debt_must_be_open() -> None:
    with pytest.raises(DebtNotOpenError):
        allocate([MARCH], 10_000, debt_id=99)


def test_paid_off_debts_are_skipped() -> None:
    closed = OpenDebt(id=5, debt_date=date(2026, 1, 1), remaining=0)
    assert allocate([closed, MAY], 10_000) == [Allocation(2, 10_000)]


def test_no_open_debts() -> None:
    with pytest.raises(NothingToPayError):
        allocate([OpenDebt(id=5, debt_date=date(2026, 1, 1), remaining=0)], 10_000)


@pytest.mark.parametrize("bad", [0, -5, 10.5, True])
def test_amount_must_be_positive_int(bad: object) -> None:
    with pytest.raises(AllocationError):
        allocate([MARCH], bad)  # type: ignore[arg-type]


def test_sum_of_allocations_equals_amount_for_many_debts() -> None:
    debts = [OpenDebt(id=i, debt_date=date(2026, 1, i), remaining=i * 1_000) for i in range(1, 29)]
    owed = total_owed(debts)
    for amount in (1, 999, 1_000, 123_456, owed):
        parts = allocate(debts, amount)
        assert sum(p.amount for p in parts) == amount
        by_id = {d.id: d.remaining for d in debts}
        assert all(0 < p.amount <= by_id[p.debt_id] for p in parts)
