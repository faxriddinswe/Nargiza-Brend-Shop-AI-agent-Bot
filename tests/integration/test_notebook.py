"""Old notebook import: planning statuses, saving, duplicates, and that imported debt is debt ONLY."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, User
from bot.db.session import read_session, uow
from bot.services import customers as cust
from bot.services import inventory, ledger, notebook, reports
from bot.utils.dates import Period

SM = async_sessionmaker[AsyncSession]
TODAY = date(2026, 11, 11)


async def _staff(sm: SM) -> User:
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=1, role="staff"))
    async with read_session(sm) as s:
        return (await s.scalars(select(User))).one()


async def _plan(sm: SM, lines: list[str]) -> list[notebook.Row]:
    async with read_session(sm) as s:
        return await notebook.plan(s, lines, TODAY)


async def _save(sm: SM, st: User, lines: list[str]) -> notebook.SaveResult:
    rows = await _plan(sm, lines)
    async with uow(sm, actor_id=st.id) as s:
        return await notebook.save(s, st, rows, TODAY)


async def test_statuses(sm: SM) -> None:
    await _staff(sm)
    rows = await _plan(
        sm,
        [
            "Umida opa, 90 123 45 67, 350 ming, 12-oktabr",  # clear
            "Jasur aka 450 ming",  # no phone, no date → warn
            "Laylo 200 ming",  # no opa/aka for a new customer → unclear
            "Zuhra opa",  # no amount → unclear
            "Umida opa, 90 123 45 67, 350 ming, 12-oktabr",  # same line twice → duplicate
        ],
    )
    assert [r.status for r in rows] == [
        "warn",
        "warn",
        "bad",
        "bad",
        "dup",
    ]  # new customers are always flagged ⚠️


async def test_save_creates_customers_and_dated_debts_in_shop(sm: SM) -> None:
    st = await _staff(sm)
    res = await _save(
        sm,
        st,
        ["Umida opa, 90 123 45 67, 350 ming, 12-oktabr", "Jasur aka 450 ming", "Laylo 200 ming"],
    )
    assert (res.debts, res.new_customers, res.skipped, res.total) == (2, 2, 1, 800_000)
    async with read_session(sm) as s:
        umida = await cust.find_by_phone(s, "+998901234567")
        assert umida is not None
        [view] = await ledger.debts_with_remaining(s, umida.id)
        assert (view.total, view.debt_date, view.due_date) == (350_000, date(2026, 10, 12), None)
        shop = (await ledger.section_ids(s))["shop"]
        assert view.section_id == shop


async def test_existing_phone_adds_to_that_customer_and_rerun_is_duplicate(sm: SM) -> None:
    st = await _staff(sm)
    async with uow(sm, actor_id=st.id) as s:
        c = await cust.create(
            s, st, name="Umida", address_form=AddressForm.OPA, raw_phone="+998901234567"
        )
    line = "Umida opa, 90 123 45 67, 100 ming, 1.10"
    assert (await _save(sm, st, [line])).new_customers == 0
    assert [r.status for r in await _plan(sm, [line])] == [
        "dup"
    ]  # importing the same page twice is harmless
    async with read_session(sm) as s:
        assert sum((await ledger.balances(s, c.id)).values()) == 100_000


async def test_same_name_without_phone_is_not_guessed(sm: SM) -> None:
    st = await _staff(sm)
    async with uow(sm, actor_id=st.id) as s:
        await cust.create(s, st, name="Umida", address_form=AddressForm.OPA, raw_phone=None)
    [row] = await _plan(sm, ["Umida opa 100 ming"])
    assert row.status == "bad" and "telefon" in row.notes[0]


async def test_imported_debt_is_debt_only(sm: SM) -> None:
    """No stock change, not in 'new debt' / turnover, cancel puts nothing back, cannot be 'returned'."""
    st = await _staff(sm)
    await _save(sm, st, ["Umida opa, 90 123 45 67, 350 ming, 12-oktabr"])
    async with read_session(sm) as s:
        assert not any(r.qty for r in await inventory.levels(s, active_only=False))
        rep = await reports.sales_report(s, Period(date(2026, 10, 1), TODAY, "x"))
        shop = rep.sections["shop"]
        assert (shop.credit_goods_total, shop.debt_given, shop.turnover) == (0, 0, 0)
        assert shop.categories == []
        entry = next(e for e in await ledger.recent_entries(s) if e.kind == "debt")
    async with uow(sm, actor_id=st.id) as s:
        await ledger.cancel_debt(s, st, entry.id)
    async with read_session(sm) as s:
        assert not any(r.qty for r in await inventory.levels(s, active_only=False))


async def test_wrong_phone_is_not_given_to_another_customer(sm: SM) -> None:
    st = await _staff(sm)
    async with uow(sm, actor_id=st.id) as s:
        await cust.create(
            s, st, name="Nodira", address_form=AddressForm.OPA, raw_phone="+998901234567"
        )
    [row] = await _plan(sm, ["Umida opa, 90 123 45 67, 350 ming"])
    assert row.status == "bad" and "boshqa mijoz" in row.notes[0]


async def test_parallel_save_writes_once(sm: SM) -> None:
    import asyncio

    st = await _staff(sm)
    rows = await _plan(sm, ["Umida opa, 90 123 45 67, 350 ming, 12-oktabr"])

    async def go() -> notebook.SaveResult:
        async with uow(sm, actor_id=st.id) as s:
            return await notebook.save(s, st, rows, TODAY)

    a, b = await asyncio.gather(go(), go())
    assert a.debts + b.debts == 1
    async with read_session(sm) as s:
        c = await cust.find_by_phone(s, "+998901234567")
        assert c is not None and sum((await ledger.balances(s, c.id)).values()) == 350_000


def test_long_line_is_rejected() -> None:
    from bot.utils.notebook import parse_line

    assert "qator juda uzun" in parse_line("A" * 500, TODAY).problems


async def test_same_name_twice_without_phone_is_not_merged(sm: SM) -> None:
    await _staff(sm)
    rows = await _plan(sm, ["Jasur aka 100 ming", "Jasur aka 200 ming"])
    assert [r.status for r in rows] == ["warn", "bad"]


async def test_undated_line_retyped_later_is_a_duplicate(sm: SM) -> None:
    st = await _staff(sm)
    line = "Umida opa, 90 123 45 67, 350 ming"
    await _save(sm, st, [line])
    assert [r.status for r in await _plan(sm, [line])] == ["dup"]
