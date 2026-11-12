"""Old paper notebook → debts (BR-140…144). Typed lines are PLANNED first (nothing is written), then SAVED in one transaction.

Row status:  ok = clear · warn = saved with a note (no phone / no date) · bad = unclear, NOT saved (never guessed) ·
             dup = the same debt was already imported, skipped.
A line with a phone of an existing customer adds the debt to that customer (duplicate check by phone, BR-144).
A new customer needs "opa/aka" in the line. A name without phone that matches an existing customer is `bad`:
we cannot know if it is the same person, so staff must give the phone.
All imported debts belong to the shop section (Q-19) and change neither stock nor the "new debt" reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import AddressForm, Customer, Debt, LedgerStatus, User
from bot.services import customers as cust
from bot.services import ledger
from bot.utils.notebook import NotebookLine, parse_line
from bot.utils.translit import search_key

MAX_ROWS = 40
NOTEBOOK_LOCK = 7_300_001


@dataclass(slots=True)
class Row:
    n: int
    text: str
    line: NotebookLine
    status: str  # ok | warn | bad | dup
    customer_id: int | None = None  # existing customer
    notes: list[str] = field(default_factory=list)

    @property
    def saved(self) -> bool:
        return self.status in ("ok", "warn")

    @property
    def date(self) -> date | None:
        return self.line.debt_date


@dataclass(slots=True)
class SaveResult:
    debts: int = 0
    new_customers: int = 0
    skipped: int = 0
    total: int = 0


class NotebookError(ValueError):
    pass


async def plan_row(
    session: AsyncSession, n: int, text: str, today: date, seen: set[tuple[Any, ...]]
) -> Row:
    line = parse_line(text, today)
    row = Row(n, text, line, "ok")
    row.notes = list(line.problems)
    if line.problems:
        row.status = "bad"
        return row
    assert line.name is not None and line.amount is not None  # noqa: S101 — no problems ⇒ present
    when = line.debt_date or today
    existing: Customer | None = None
    if line.phone:
        existing = await cust.find_by_phone(session, line.phone)
    else:
        key = search_key(line.name)
        same = (
            await session.scalars(
                select(Customer).where(Customer.search_name == key, Customer.deleted_at.is_(None))
            )
        ).all()
        if same:
            row.status, row.notes = "bad", ["shu ismli mijoz bor — telefonini yozing"]
            return row
    if existing is None and line.form is None:
        row.status, row.notes = "bad", ["opa yoki aka yozilmagan"]
        return row
    ident = line.phone or search_key(line.name)
    if line.phone is None and ("name", ident, date.min) in seen:
        row.status, row.notes = (
            "bad",
            ["ro'yxatda shu ism takrorlandi — telefonini yozing (bir odammi, boshqami?)"],
        )
        return row
    if line.phone is None:
        seen.add(("name", ident, date.min))
    if existing is not None:
        row.customer_id = existing.id
        if not set(search_key(line.name).split()) & set(existing.search_name.split()):
            row.status = "bad"
            row.notes = [f"telefon boshqa mijozniki: {existing.name} — raqamni tekshiring"]
            return row
        row.notes.append(f"mavjud mijoz: {existing.name}")
        dup = await session.scalar(
            select(Debt.id).where(
                Debt.customer_id == existing.id, Debt.source == "import", Debt.status == LedgerStatus.ACTIVE,
                Debt.total_amount == line.amount,
                *([Debt.debt_date == when] if line.debt_date else []),  # no date: same amount on ANY date counts
            ).limit(1)
        )  # fmt: skip
        if dup is not None:
            row.status, row.notes = "dup", ["bu qarz allaqachon kiritilgan"]
            return row
    if (ident, line.amount, when) in seen:
        row.status, row.notes = "dup", ["ro'yxatda takror"]
        return row
    seen.add((ident, line.amount, when))
    if existing is None:
        row.notes.append("yangi mijoz yaratiladi")
    if line.warnings or existing is None:
        row.status = "warn"
        row.notes += line.warnings
    return row


async def plan(session: AsyncSession, lines: list[str], today: date) -> list[Row]:
    clean = [x for x in (ln.strip() for ln in lines) if x]
    if len(clean) > MAX_ROWS:
        raise NotebookError("too many rows")
    seen: set[tuple[Any, ...]] = set()
    return [await plan_row(session, i, text, today, seen) for i, text in enumerate(clean, 1)]


async def save(session: AsyncSession, actor: User, rows: list[Row], today: date) -> SaveResult:
    """Write every ok/warn row in the caller's transaction. Rows are re-checked against the database first."""
    result = SaveResult()
    # one import at a time: a double tap waits here, then sees the first save and skips it as a duplicate
    await session.execute(select(func.pg_advisory_xact_lock(NOTEBOOK_LOCK)))
    fresh = await plan(session, [r.text for r in rows], today)
    created: dict[str, int] = {}  # a customer created earlier in this very batch
    for row in fresh:
        if not row.saved:
            result.skipped += 1
            continue
        line = row.line
        assert line.name is not None and line.amount is not None  # noqa: S101
        ident = line.phone or search_key(line.name)
        cid = row.customer_id or created.get(ident)
        if cid is None:
            assert line.form is not None  # noqa: S101 — plan_row guarantees it for new customers
            c = await cust.create(
                session,
                actor,
                name=line.name,
                address_form=AddressForm(line.form),
                raw_phone=line.phone,
                note="eski daftardan",
            )
            cid = created[ident] = c.id
            result.new_customers += 1
        await ledger.import_debt(
            session,
            actor,
            customer_id=cid,
            amount=line.amount,
            debt_date=line.debt_date or today,
            today=today,
            note="eski daftar",
        )
        result.debts += 1
        result.total += line.amount
    return result
