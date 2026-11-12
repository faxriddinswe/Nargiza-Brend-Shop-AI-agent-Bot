"""Nightly integrity check (master 9.3). Read-only: it only REPORTS, it never "fixes" money.

Looks for records that the application rules should make impossible, so any hit means a bug or a manual DB edit:
  overpaid debt · payment whose allocations differ from its amount · payment allocated to a cancelled debt ·
  possible duplicate payment · negative stock · regular debt without items · imported debt whose items differ from its total ·
  a sale-remainder debt that is active while its sale is cancelled.
Only record ids are reported — never names or phone numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services import inventory

SAMPLE = 5  # ids shown per problem

_CHECKS: dict[str, str] = {
    "overpaid_debt": """
        SELECT d.id FROM debts d
        JOIN payment_allocations a ON a.debt_id = d.id
        JOIN payments p ON p.id = a.payment_id AND p.status = 'active'
        WHERE d.status = 'active'
        GROUP BY d.id, d.total_amount HAVING sum(a.amount) > d.total_amount ORDER BY d.id""",
    "allocation_mismatch": """
        SELECT p.id FROM payments p
        LEFT JOIN payment_allocations a ON a.payment_id = p.id
        WHERE p.status = 'active'
        GROUP BY p.id, p.amount HAVING coalesce(sum(a.amount), 0) <> p.amount ORDER BY p.id""",
    "allocated_to_cancelled_debt": """
        SELECT DISTINCT p.id FROM payments p
        JOIN payment_allocations a ON a.payment_id = p.id
        JOIN debts d ON d.id = a.debt_id
        WHERE p.status = 'active' AND d.status = 'cancelled' ORDER BY p.id""",
    "possible_duplicate_payment": """
        SELECT DISTINCT p2.id FROM payments p1
        JOIN payments p2 ON p2.id > p1.id AND p2.customer_id = p1.customer_id
            AND p2.section_id = p1.section_id AND p2.kind = p1.kind AND p2.amount = p1.amount
            AND p2.paid_on = p1.paid_on AND p2.created_at - p1.created_at < interval '60 seconds'
        WHERE p1.status = 'active' AND p2.status = 'active' ORDER BY p2.id""",
    "debt_without_items": """
        SELECT d.id FROM debts d
        WHERE d.status = 'active' AND d.kind = 'regular'
          AND NOT EXISTS (SELECT 1 FROM debt_items i WHERE i.debt_id = d.id) ORDER BY d.id""",
    "import_total_mismatch": """
        SELECT d.id FROM debts d
        JOIN debt_items i ON i.debt_id = d.id
        WHERE d.status = 'active' AND d.source = 'import'
        GROUP BY d.id, d.total_amount HAVING sum(i.quantity * i.unit_price) <> d.total_amount ORDER BY d.id""",
    "remainder_of_cancelled_sale": """
        SELECT d.id FROM debts d JOIN sales s ON s.id = d.sale_id
        WHERE d.status = 'active' AND s.status = 'cancelled' ORDER BY d.id""",
}


@dataclass(slots=True)
class Problem:
    code: str
    count: int
    ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class IntegrityReport:
    problems: list[Problem] = field(default_factory=list)
    debts: int = 0
    payments: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems


async def run_checks(session: AsyncSession) -> IntegrityReport:
    report = IntegrityReport()
    for code, sql in _CHECKS.items():
        ids = [int(x) for x in (await session.scalars(text(sql))).all()]
        if ids:
            report.problems.append(Problem(code, len(ids), ids[:SAMPLE]))
    negative = [r for r in await inventory.levels(session, active_only=False) if r.negative]
    if negative:
        report.problems.append(
            Problem("negative_stock", len(negative), [r.category_id for r in negative][:SAMPLE])
        )
    report.debts = int(await session.scalar(text("SELECT count(*) FROM debts")) or 0)
    report.payments = int(await session.scalar(text("SELECT count(*) FROM payments")) or 0)
    return report
