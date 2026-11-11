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


def proportional_value(
    quantity: int,
    unit_price: int,
    *,
    total: int,
    items_total: int,
    already_returned_value: int,
    already_returned_qty: int,
    item_quantity: int,
) -> int:
    """Refund value of returning `quantity` units of one sale item, discount included (BR-081, returns).

    The sale's discount is spread over its items in proportion to price. To make sure partial returns add up to
    exactly the amount paid, the value is computed on the CUMULATIVE returned quantity and the earlier value is
    subtracted. Rounding is half-up on integers (no floats).
    """
    if quantity <= 0 or quantity + already_returned_qty > item_quantity:
        raise SaleMathError("bad return quantity")
    cumulative = quantity + already_returned_qty
    value_all = _round_div(cumulative * unit_price * total, items_total)
    return value_all - already_returned_value


def _round_div(numerator: int, denominator: int) -> int:
    return (2 * numerator + denominator) // (2 * denominator)
