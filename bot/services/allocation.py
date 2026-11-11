"""Payment / write-off allocation across open debts (BR-061, BR-062, BR-064, BR-065, BR-058).

Pure functions — no database, no Telegram — so every money rule is unit-tested.

- FIFO (default): the oldest debt first (by debt_date, then id — stable for same-day debts).
- Specific debt (BR-062): only that debt; amount above its remaining is rejected (not spilled).
- Overpayment (BR-065): rejected — the caller shows the balance and asks again.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class OpenDebt:
    id: int
    debt_date: date
    remaining: int  # so'm, > 0


@dataclass(frozen=True, slots=True)
class Allocation:
    debt_id: int
    amount: int


class AllocationError(ValueError):
    pass


class NothingToPayError(AllocationError):
    """The customer has no open debt in this section."""


class OverpaymentError(AllocationError):
    """Amount is larger than what is owed (BR-065)."""

    def __init__(self, amount: int, owed: int) -> None:
        super().__init__(f"amount {amount} > owed {owed}")
        self.amount = amount
        self.owed = owed


class DebtNotOpenError(AllocationError):
    """The chosen debt is not among the open debts (paid off, cancelled, other section)."""


def _check_amount(amount: int) -> None:
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise AllocationError("amount must be a positive int (so'm)")


def fifo_order(debts: Sequence[OpenDebt]) -> list[OpenDebt]:
    return sorted((d for d in debts if d.remaining > 0), key=lambda d: (d.debt_date, d.id))


def allocate(
    debts: Sequence[OpenDebt], amount: int, *, debt_id: int | None = None
) -> list[Allocation]:
    """Split `amount` over open debts. Σ result == amount, each part ≤ that debt's remaining."""
    _check_amount(amount)
    open_debts = fifo_order(debts)
    if not open_debts:
        raise NothingToPayError

    if debt_id is not None:
        target = next((d for d in open_debts if d.id == debt_id), None)
        if target is None:
            raise DebtNotOpenError(debt_id)
        if amount > target.remaining:
            raise OverpaymentError(amount, target.remaining)
        return [Allocation(target.id, amount)]

    owed = sum(d.remaining for d in open_debts)
    if amount > owed:
        raise OverpaymentError(amount, owed)

    result: list[Allocation] = []
    left = amount
    for d in open_debts:
        if left == 0:
            break
        part = min(left, d.remaining)
        result.append(Allocation(d.id, part))
        left -= part
    return result


def total_owed(debts: Sequence[OpenDebt]) -> int:
    return sum(d.remaining for d in debts if d.remaining > 0)
