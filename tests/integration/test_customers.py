"""Customers service: create, phone rules, search, delete/restore (BR-040…BR-046). Fake data only."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, User
from bot.db.session import read_session, uow
from bot.services import customers as cust

SM = async_sessionmaker[AsyncSession]


async def _user(sm: SM, role: str, tg: int) -> User:
    async with uow(sm, actor_kind="system") as s:
        u = User(telegram_id=tg, role=role)
        s.add(u)
        await s.flush()
        await s.refresh(u)
        return u


async def _create(
    sm: SM, actor: User, name: str, phone: str | None, note: str | None = None
) -> int:
    async with uow(sm, actor_id=actor.id) as s:
        return (
            await cust.create(
                s, actor, name=name, address_form=AddressForm.OPA, raw_phone=phone, note=note
            )
        ).id


async def _search(sm: SM, q: str) -> list[str]:
    async with read_session(sm) as s:
        return [f"{c.name}|{c.note or ''}" for c in await cust.search(s, q)]


async def test_customer_cannot_create_customers(sm: SM) -> None:
    customer = await _user(sm, "customer", 1)
    with pytest.raises(cust.NotAllowedError):
        await _create(sm, customer, "X", None)


async def test_duplicate_phone_rejected_with_owner(sm: SM) -> None:
    """BR-041: "90 123 45 67" and "+998901234567" are the same key."""
    st = await _user(sm, "staff", 1)
    first = await _create(sm, st, "Umida", "90 000 01 01")
    with pytest.raises(cust.PhoneTakenError) as e:
        await _create(sm, st, "Umida 2", "+998900000101")
    assert e.value.customer_id == first


async def test_phone_missing_allowed(sm: SM) -> None:
    """BR-042"""
    st = await _user(sm, "staff", 1)
    cid = await _create(sm, st, "Telefonsiz", None)
    async with read_session(sm) as s:
        assert (await cust.get(s, cid)).phone_missing is True


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Umida", "Umida"),
        ("умида", "Umida"),  # kirill
        ("umda", "Umida"),  # xato yozilgan
        ("4567", "Umida"),  # telefon oxiri
        ("45 67", "Umida"),
        ("shahlo", "Shahlo"),
        ("Шаҳло", "Shahlo"),
    ],
)
async def test_search_variants(sm: SM, query: str, expected: str) -> None:
    """BR-044"""
    st = await _user(sm, "staff", 1)
    await _create(sm, st, "Umida", "+998901234567", "Shahlo opaning qizi")
    await _create(sm, st, "Shahlo", "+998907654321")
    await _create(sm, st, "Jasur", "+998909999999")
    found = [r.split("|")[0] for r in await _search(sm, query)]
    assert found and found[0] == expected


async def test_same_names_all_found(sm: SM) -> None:
    """BR-045: three "Umida" — all listed, with notes to tell them apart."""
    st = await _user(sm, "staff", 1)
    for i, note in enumerate(["Shahlo opaning qizi", "Yunusobodlik", None]):
        await _create(sm, st, "Umida", f"+99890000020{i}", note)
    rows = await _search(sm, "umida")
    assert len(rows) == 3
    assert {"Umida|Shahlo opaning qizi", "Umida|Yunusobodlik", "Umida|"} == set(rows)


async def test_soft_delete_hides_and_admin_restores(sm: SM) -> None:
    """BR-046: soft delete; only admin restores."""
    st = await _user(sm, "staff", 1)
    admin = await _user(sm, "admin", 2)
    cid = await _create(sm, st, "Dilnoza", "+998900000301")
    async with uow(sm, actor_id=st.id) as s:
        await cust.soft_delete(s, st, cid)
    assert await _search(sm, "dilnoza") == []
    with pytest.raises(cust.NotAllowedError):
        async with uow(sm, actor_id=st.id) as s:
            await cust.restore(s, st, cid)
    async with uow(sm, actor_id=admin.id) as s:
        await cust.restore(s, admin, cid)
    assert await _search(sm, "dilnoza") == ["Dilnoza|"]


async def test_restore_refused_when_phone_reused(sm: SM) -> None:
    st = await _user(sm, "staff", 1)
    admin = await _user(sm, "admin", 2)
    old = await _create(sm, st, "Old", "+998900000302")
    async with uow(sm, actor_id=st.id) as s:
        await cust.soft_delete(s, st, old)
    await _create(sm, st, "New", "+998900000302")
    with pytest.raises(cust.PhoneTakenError):
        async with uow(sm, actor_id=admin.id) as s:
            await cust.restore(s, admin, old)


async def test_phone_change_unlinks_telegram(sm: SM) -> None:
    """Security: a new number is not proven by the old Telegram link."""
    st = await _user(sm, "staff", 1)
    linked = await _user(sm, "customer", 3)
    cid = await _create(sm, st, "Linked", "+998900000303")
    async with uow(sm, actor_id=st.id) as s:
        c = await cust.get(s, cid)
        c.user_id = linked.id
    async with uow(sm, actor_id=st.id) as s:
        c = await cust.update(s, st, cid, raw_phone="+998900000304")
        assert c.user_id is None
