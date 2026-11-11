"""Debt ledger on real Postgres (BR-050…BR-067, BR-104). Amounts computed by hand; fake data only."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, Debt, Payment, PaymentKind, User
from bot.db.session import read_session, uow
from bot.services import customers as cust
from bot.services import ledger
from bot.services.allocation import NothingToPayError, OverpaymentError
from bot.services.ledger import ItemInput

SM = async_sessionmaker[AsyncSession]
D1 = date(2026, 3, 5)
D2 = date(2026, 5, 10)
TODAY = date(2026, 11, 11)


async def _staff(sm: SM, tg: int = 1) -> User:
    async with uow(sm, actor_kind="system") as s:
        u = User(telegram_id=tg, role="staff")
        s.add(u)
        await s.flush()
        await s.refresh(u)
        return u


async def _customer(sm: SM, actor: User, phone: str = "+998900000101") -> int:
    async with uow(sm, actor_id=actor.id) as s:
        c = await cust.create(s, actor, name="Umida", address_form=AddressForm.OPA, raw_phone=phone)
        return c.id


async def _cats(sm: SM) -> dict[str, ledger.CategoryRef]:
    async with read_session(sm) as s:
        return {c.name: c for c in await ledger.categories(s)}


async def _debt(
    sm: SM, actor: User, cid: int, items: list[ItemInput], day: date = TODAY
) -> list[ledger.CreatedDebt]:
    async with uow(sm, actor_id=actor.id) as s:
        return await ledger.create_debts(
            s, actor, customer_id=cid, items=items, due_date=None, today=day
        )


async def _pay(
    sm: SM, actor: User, cid: int, sid: int, amount: int, **kw: object
) -> tuple[Payment, ledger.PaymentPlan]:
    async with uow(sm, actor_id=actor.id) as s:
        return await ledger.record_payment(
            s, actor, customer_id=cid, section_id=sid, amount=amount,
            kind=kw.pop("kind", PaymentKind.PAYMENT), today=TODAY, **kw,  # type: ignore[arg-type]
        )  # fmt: skip


async def _balances(sm: SM, cid: int) -> dict[int, int]:
    async with read_session(sm) as s:
        return await ledger.balances(s, cid)


# ---------------------------------------------------------------- debts
async def test_debt_total_is_quantity_times_price(sm: SM) -> None:
    """BR-053: 2 × 175 000 + 1 × 90 000 = 440 000."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    created = await _debt(
        sm, st, cid, [ItemInput(c["ko'ylak"].id, 2, 175_000), ItemInput(c["yubka"].id, 1, 90_000)]
    )
    assert [(d.section_id, d.total) for d in created] == [(c["ko'ylak"].section_id, 440_000)]
    assert await _balances(sm, cid) == {c["ko'ylak"].section_id: 440_000}


async def test_mixed_sections_split_into_two_debts(sm: SM) -> None:
    """BR-022: ko'ylak (shop) + ichki kiyim (lingerie) → two debts, balances never mixed (BR-025)."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    created = await _debt(
        sm,
        st,
        cid,
        [ItemInput(c["ko'ylak"].id, 1, 300_000), ItemInput(c["ichki kiyim"].id, 2, 40_000)],
    )
    shop, lingerie = c["ko'ylak"].section_id, c["ichki kiyim"].section_id
    assert sorted((d.section_id, d.total) for d in created) == sorted(
        [(shop, 300_000), (lingerie, 80_000)]
    )
    assert await _balances(sm, cid) == {shop: 300_000, lingerie: 80_000}


async def test_db_rejects_item_in_wrong_section(sm: SM) -> None:
    """BR-021 enforced by composite FK: lingerie category cannot go into a shop debt."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    shop = c["ko'ylak"].section_id
    with pytest.raises(DBAPIError):
        async with uow(sm, actor_id=st.id) as s:
            d = Debt(
                customer_id=cid,
                section_id=shop,
                debt_date=TODAY,
                total_amount=50_000,
                created_by=st.id,
            )
            s.add(d)
            await s.flush()
            await s.execute(
                text(
                    "INSERT INTO debt_items (debt_id, section_id, category_id, quantity, unit_price) VALUES (:d, :s, :c, 1, 50000)"
                ),
                {"d": d.id, "s": shop, "c": c["ichki kiyim"].id},
            )


async def test_db_rejects_total_not_matching_items(sm: SM) -> None:
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    with pytest.raises(DBAPIError, match="teng emas"):
        async with uow(sm, actor_id=st.id) as s:
            d = Debt(
                customer_id=cid,
                section_id=c["yubka"].section_id,
                debt_date=TODAY,
                total_amount=999_999,
                created_by=st.id,
            )
            s.add(d)
            await s.flush()
            await s.execute(
                text(
                    "INSERT INTO debt_items (debt_id, section_id, category_id, quantity, unit_price) VALUES (:d, :s, :c, 1, 50000)"
                ),
                {"d": d.id, "s": c["yubka"].section_id, "c": c["yubka"].id},
            )


# ---------------------------------------------------------------- payments
async def test_fifo_payment_closes_oldest_first(sm: SM) -> None:
    """BR-061: March 200k + May 300k, pay 250k → March closed, May 250k left."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    shop = c["ko'ylak"].section_id
    march = (await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 200_000)], D1))[0]
    may = (await _debt(sm, st, cid, [ItemInput(c["shim"].id, 1, 300_000)], D2))[0]
    _, plan = await _pay(sm, st, cid, shop, 250_000)
    assert [(a.debt_id, a.amount) for a in plan.allocations] == [
        (march.debt_id, 200_000),
        (may.debt_id, 50_000),
    ]
    assert await _balances(sm, cid) == {shop: 250_000}


async def test_overpayment_rejected(sm: SM) -> None:
    """BR-065"""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 250_000)])
    with pytest.raises(OverpaymentError) as e:
        await _pay(sm, st, cid, c["ko'ylak"].section_id, 300_000)
    assert e.value.owed == 250_000
    async with read_session(sm) as s:
        assert await s.scalar(select(func.count()).select_from(Payment)) == 0


async def test_write_off_partial_is_separate_from_cash(sm: SM) -> None:
    """BR-057/058: write-off reduces the balance but is kind=write_off, no cash method."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    shop = c["ko'ylak"].section_id
    await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 300_000)])
    p, _ = await _pay(sm, st, cid, shop, 50_000, kind=PaymentKind.WRITE_OFF)
    assert (p.kind, p.method) == ("write_off", None)
    assert await _balances(sm, cid) == {shop: 250_000}


async def test_plan_changed_between_card_and_confirm(sm: SM) -> None:
    """Card shows FIFO plan; another payment lands first → confirm is refused, nothing written twice."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    shop = c["ko'ylak"].section_id
    d = (await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 100_000)]))[0]
    async with read_session(sm) as s:
        plan = await ledger.plan_payment(s, customer_id=cid, section_id=shop, amount=100_000)
    await _pay(sm, st, cid, shop, 40_000)
    with pytest.raises((ledger.PlanChangedError, OverpaymentError)):
        await _pay(
            sm, st, cid, shop, 100_000, expected=[(a.debt_id, a.amount) for a in plan.allocations]
        )
    assert await _balances(sm, cid) == {shop: 60_000}
    assert d.total == 100_000


async def test_concurrent_payments_cannot_overpay(sm: SM) -> None:
    """Two staff pay the same 100k debt at the same moment — only one 100k payment survives."""
    a, b = await _staff(sm, 1), await _staff(sm, 2)
    cid = await _customer(sm, a)
    c = await _cats(sm)
    shop = c["ko'ylak"].section_id
    await _debt(sm, a, cid, [ItemInput(c["ko'ylak"].id, 1, 100_000)])
    results = await asyncio.gather(
        _pay(sm, a, cid, shop, 100_000), _pay(sm, b, cid, shop, 100_000), return_exceptions=True
    )
    ok = [r for r in results if not isinstance(r, BaseException)]
    assert len(ok) == 1
    assert await _balances(sm, cid) == {}
    async with read_session(sm) as s:
        assert (
            await s.scalar(select(func.sum(Payment.amount)).where(Payment.status == "active"))
            == 100_000
        )


# ---------------------------------------------------------------- cancellation (BR-104)
async def test_cancel_payment_restores_balance(sm: SM) -> None:
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    shop = c["ko'ylak"].section_id
    await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 200_000)])
    p, _ = await _pay(sm, st, cid, shop, 150_000)
    async with uow(sm, actor_id=st.id) as s:
        await ledger.cancel_payment(s, st, p.id, "xato")
    assert await _balances(sm, cid) == {shop: 200_000}
    # bekor qilingan to'lov tarixda qoladi
    async with read_session(sm) as s:
        assert (await s.get(Payment, p.id)).status == "cancelled"  # type: ignore[union-attr]


async def test_cannot_cancel_debt_with_active_payment(sm: SM) -> None:
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    shop = c["ko'ylak"].section_id
    d = (await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 200_000)]))[0]
    p, _ = await _pay(sm, st, cid, shop, 50_000)
    with pytest.raises(ledger.DebtHasPaymentsError):
        async with uow(sm, actor_id=st.id) as s:
            await ledger.cancel_debt(s, st, d.debt_id)
    async with uow(sm, actor_id=st.id) as s:
        await ledger.cancel_payment(s, st, p.id)
    async with uow(sm, actor_id=st.id) as s:
        await ledger.cancel_debt(s, st, d.debt_id)
    assert await _balances(sm, cid) == {}


async def test_db_forbids_editing_amount_and_reactivation(sm: SM) -> None:
    """Ledger rows are immutable except active → cancelled (Q-34)."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    d = (await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 200_000)]))[0]
    with pytest.raises(DBAPIError, match="o'zgartirilmaydi"):
        async with uow(sm, actor_id=st.id) as s:
            await s.execute(update(Debt).where(Debt.id == d.debt_id).values(total_amount=1))
    async with uow(sm, actor_id=st.id) as s:
        await ledger.cancel_debt(s, st, d.debt_id)
    with pytest.raises(DBAPIError, match="qayta faollashtirilmaydi"):
        async with uow(sm, actor_id=st.id) as s:
            await s.execute(
                text("UPDATE debts SET status='active', cancelled_at=NULL WHERE id=:i"),
                {"i": d.debt_id},
            )


async def test_db_rejects_allocation_over_debt_even_bypassing_service(sm: SM) -> None:
    """Deferred trigger: raw SQL cannot overpay a debt either."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    shop = c["ko'ylak"].section_id
    d = (await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 100_000)]))[0]
    with pytest.raises(DBAPIError, match="ortiq"):
        async with uow(sm, actor_id=st.id) as s:
            pid = (
                await s.execute(
                    text(
                        "INSERT INTO payments (customer_id, section_id, kind, method, amount, paid_on) "
                        "VALUES (:c, :s, 'payment', 'cash', 150000, :d) RETURNING id"
                    ),
                    {"c": cid, "s": shop, "d": TODAY},
                )
            ).scalar_one()
            await s.execute(text(
                "INSERT INTO payment_allocations (payment_id, debt_id, section_id, customer_id, amount) "
                "VALUES (:p, :d, :s, :c, 150000)"), {"p": pid, "d": d.debt_id, "s": shop, "c": cid})  # fmt: skip


async def test_app_role_cannot_update_allocations(app_sm: SM, sm: SM) -> None:
    st = await _staff(sm)
    with pytest.raises(DBAPIError):
        async with uow(app_sm, actor_id=st.id) as s:
            await s.execute(text("UPDATE payment_allocations SET amount = 1"))
    with pytest.raises(DBAPIError):
        async with uow(app_sm, actor_id=st.id) as s:
            await s.execute(text("DELETE FROM payments"))


# ---------------------------------------------------------------- views
async def test_customer_ledger_view(sm: SM) -> None:
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    shop = c["ko'ylak"].section_id
    await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 200_000, "qizil, 46")], D1)
    await _pay(sm, st, cid, shop, 50_000)
    async with read_session(sm) as s:
        view = await ledger.customer_ledger(s, cid)
    assert len(view) == 1 and view[0].balance == 150_000
    debt_view, items = view[0].open_debts[0]
    assert items == [("ko'ylak", 1, 200_000, "qizil, 46")]
    assert debt_view.remaining == 150_000
    assert view[0].recent_payments[0][2] == 50_000


# ---------------------------------------------------------------- business review (stage 2)
async def test_second_card_from_same_balance_is_refused(sm: SM) -> None:
    """Card A (100k) abandoned, card B (100k) created, both confirmed → only the first may pass."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    shop = c["ko'ylak"].section_id
    await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 500_000)])
    async with read_session(sm) as s:
        plan = await ledger.plan_payment(s, customer_id=cid, section_id=shop, amount=100_000)
    kw = {
        "expected": [(a.debt_id, a.amount) for a in plan.allocations],
        "expected_owed": plan.owed_before,
    }
    await _pay(sm, st, cid, shop, 100_000, **kw)  # card A confirmed
    with pytest.raises(ledger.PlanChangedError):
        await _pay(sm, st, cid, shop, 100_000, **kw)  # card B: same expected plan, balance moved
    assert await _balances(sm, cid) == {shop: 400_000}


async def test_due_date_in_the_past_is_refused(sm: SM) -> None:
    """Card made before midnight, confirmed after: due date is now before the debt date."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    with pytest.raises(ledger.DueDatePassedError):
        async with uow(sm, actor_id=st.id) as s:
            await ledger.create_debts(
                s,
                st,
                customer_id=cid,
                items=[ItemInput(c["yubka"].id, 1, 90_000)],
                due_date=date(2026, 11, 10),
                today=TODAY,
            )
    assert await _balances(sm, cid) == {}


async def test_payments_in_two_sections_do_not_affect_each_other(sm: SM) -> None:
    """BR-025/066: shop payment never touches the lingerie debt."""
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    shop, lingerie = c["ko'ylak"].section_id, c["ichki kiyim"].section_id
    await _debt(
        sm,
        st,
        cid,
        [ItemInput(c["ko'ylak"].id, 1, 300_000), ItemInput(c["ichki kiyim"].id, 1, 200_000)],
    )
    await _pay(sm, st, cid, shop, 300_000)
    assert await _balances(sm, cid) == {lingerie: 200_000}
    with pytest.raises(NothingToPayError):
        await _pay(sm, st, cid, shop, 1)  # the shop debt is already zero


async def test_payment_to_deleted_customer_refused(sm: SM) -> None:
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1, 100_000)])
    async with uow(sm, actor_id=st.id) as s:
        await cust.soft_delete(s, st, cid)
    with pytest.raises(cust.CustomerNotFoundError):
        await _pay(sm, st, cid, c["ko'ylak"].section_id, 50_000)


async def test_oversized_debt_refused(sm: SM) -> None:
    st = await _staff(sm)
    cid = await _customer(sm, st)
    c = await _cats(sm)
    with pytest.raises(ledger.LedgerError):
        await _debt(sm, st, cid, [ItemInput(c["ko'ylak"].id, 1000, 1_000_000_000)])
