"""Pure sale arithmetic (BR-071a, BR-072a, BR-073a). No database, no Telegram — easy to test exhaustively.

All amounts are integer so'm. The AI never does this math; it passes spoken numbers that our parsers read.
"""

from __future__ import annotations

from dataclasses import dataclass


class SaleMathError(ValueError):
    pass


class PriceAboveListError(SaleMathError):
    """Agreed final price is higher than the list price — ask, don't assume (BR-073a)."""

    def __init__(self, items_total: int, final_total: int) -> None:
        super().__init__(f"{final_total} > {items_total}")
        self.items_total = items_total
        self.final_total = final_total


class PaidAboveTotalError(SaleMathError):
    def __init__(self, total: int, paid: int) -> None:
        super().__init__(f"{paid} > {total}")
        self.total = total
        self.paid = paid


class CustomerRequiredError(SaleMathError):
    """An unpaid part becomes a debt, and a debt needs a customer (BR-072a)."""


@dataclass(frozen=True, slots=True)
class SalePlan:
    items_total: int  # Σ quantity × list price
    discount: int  # list price − agreed price
    total: int  # what the customer pays for the sale (= the sale amount in reports)
    paid: int  # cash received now
    debt: int  # on credit (linked debt), total − paid


def plan_sale(
    items_total: int, *, final_total: int | None, paid: int | None, has_customer: bool
) -> SalePlan:
    for v in (items_total, final_total, paid):
        if v is not None and (not isinstance(v, int) or isinstance(v, bool)):
            raise SaleMathError("amounts must be int")
    if items_total <= 0:
        raise SaleMathError("empty sale")
    total = items_total if final_total is None else final_total
    if total <= 0:
        raise SaleMathError("total must be positive")
    if total > items_total:
        raise PriceAboveListError(items_total, total)
    paid_now = total if paid is None else paid
    if paid_now < 0:
        raise SaleMathError("paid must not be negative")
    if paid_now > total:
        raise PaidAboveTotalError(total, paid_now)
    debt = total - paid_now
    if debt > 0 and not has_customer:
        raise CustomerRequiredError
    return SalePlan(items_total, items_total - total, total, paid_now, debt)


def split_total(total: int, weights: list[int]) -> list[int]:
    """Spread `total` over lines in proportion to `weights` so that the parts add up to EXACTLY `total`.

    Largest-remainder method on integers (no floats); ties go to the earlier line. Used to give every sale
    line its share of the agreed price (discount included).
    """
    if total < 0 or not weights or any(w <= 0 for w in weights):
        raise SaleMathError("bad split")
    whole = sum(weights)
    base = [total * w // whole for w in weights]
    order = sorted(range(len(weights)), key=lambda i: (-(total * weights[i] % whole), i))
    for i in order[: total - sum(base)]:
        base[i] += 1
    return base


def item_value(
    quantity: int,
    *,
    share: int,
    item_quantity: int,
    already_returned_value: int,
    already_returned_qty: int,
) -> int:
    """Refund value of returning `quantity` more units of one sale line whose price share is `share`.

    Computed on the CUMULATIVE returned quantity (round-half-up) minus what was already refunded, so partial
    returns add up to exactly `share` and the whole sale never refunds more than was paid.
    """
    if quantity <= 0 or quantity + already_returned_qty > item_quantity:
        raise SaleMathError("bad return quantity")
    cumulative = _round_div((quantity + already_returned_qty) * share, item_quantity)
    return cumulative - already_returned_value


def _round_div(numerator: int, denominator: int) -> int:
    return (2 * numerator + denominator) // (2 * denominator)
