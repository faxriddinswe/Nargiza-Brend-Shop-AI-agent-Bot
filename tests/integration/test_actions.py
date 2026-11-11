"""Confirmed staff actions: ledger writes + who gets notified (BR-026, BR-027, BR-054, BR-055a)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, Payment, User
from bot.db.session import read_session, uow
from bot.handlers.staff.actions import execute
from bot.services import customers as cust
from bot.services import ledger
from bot.services import staff as staff_svc

SM = async_sessionmaker[AsyncSession]
TODAY = date(2026, 11, 11)


class World:
    admin: User
    shop_owner: User  # "Nodira opa" — owns shop
    lingerie_owner: User  # "Nilufar opa" — owns lingerie
    customer_id: int
    shop_cat: int
    lingerie_cat: int


async def _world(sm: SM, *, linked_customer: bool = True) -> World:
    w = World()
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=1, role="admin"))
        for tg, phone in ((2, "+998900000402"), (3, "+998900000403"), (4, "+998900000404")):
            s.add(User(telegram_id=tg, role="customer", phone=phone))
        await s.flush()
        w.admin = (await s.scalars(select(User).where(User.telegram_id == 1))).one()
    async with uow(sm, actor_id=w.admin.id) as s:
        await staff_svc.add_staff(
            s, w.admin, raw_phone="+998900000402", display_name="Nodira opa", section_codes=["shop"]
        )
        await staff_svc.add_staff(
            s,
            w.admin,
            raw_phone="+998900000403",
            display_name="Nilufar opa",
            section_codes=["lingerie"],
        )
    async with read_session(sm) as s:
        w.shop_owner = (await s.scalars(select(User).where(User.telegram_id == 2))).one()
        w.lingerie_owner = (await s.scalars(select(User).where(User.telegram_id == 3))).one()
        cats = {c.name: c.id for c in await ledger.categories(s)}
        customer_user = (await s.scalars(select(User).where(User.telegram_id == 4))).one()
    w.shop_cat, w.lingerie_cat = cats["ko'ylak"], cats["ichki kiyim"]
    async with uow(sm, actor_id=w.shop_owner.id) as s:
        c = await cust.create(
            s, w.shop_owner, name="Umida", address_form=AddressForm.OPA, raw_phone="+998900000404"
        )
        if linked_customer:
            c.user_id = customer_user.id
        w.customer_id = c.id
    return w


def _items(*pairs: tuple[int, int, int]) -> list[dict[str, object]]:
    return [{"category_id": c, "quantity": q, "unit_price": p, "note": None} for c, q, p in pairs]


async def _run(
    sm: SM, actor: User, action: str, payload: dict[str, object]
) -> tuple[str, list[tuple[int, str]]]:
    async with uow(sm, actor_id=actor.id) as s:
        return await execute(s, actor, action, payload)


async def test_debt_by_section_owner_notifies_only_customer(sm: SM) -> None:
    """BR-027: owners of the same section are not pinged; BR-054: the customer is told."""
    w = await _world(sm)
    _, notify = await _run(sm, w.shop_owner, "create_debts",
        {"customer_id": w.customer_id, "items": _items((w.shop_cat, 2, 175_000)), "due": "2026-12-25"})  # fmt: skip
    assert [chat for chat, _ in notify] == [4]
    text = notify[0][1]
    assert "350 000 so'm" in text and "25-dekabr" in text and "Umida opa" in text


async def test_debt_in_other_section_notifies_that_owner(sm: SM) -> None:
    """BR-026: Nodira (shop) writes an underwear debt → Nilufar (lingerie owner) gets a 🔔."""
    w = await _world(sm)
    _, notify = await _run(sm, w.shop_owner, "create_debts",
        {"customer_id": w.customer_id, "items": _items((w.shop_cat, 1, 300_000), (w.lingerie_cat, 2, 40_000)), "due": None})  # fmt: skip
    by_chat = {chat: text for chat, text in notify}
    assert set(by_chat) == {4, 3}  # customer + lingerie owner; NOT the shop owner herself
    owner_text = next(txt for chat, txt in notify if chat == 3)
    assert "Nodira opa" in owner_text and "80 000 so'm" in owner_text
    customer_texts = [txt for chat, txt in notify if chat == 4]
    assert len(customer_texts) == 2  # one message per section, amounts never mixed
    assert any("300 000 so'm" in x for x in customer_texts) and any(
        "80 000 so'm" in x for x in customer_texts
    )


async def test_admin_writing_notifies_owners(sm: SM) -> None:
    w = await _world(sm)
    _, notify = await _run(sm, w.admin, "create_debts",
        {"customer_id": w.customer_id, "items": _items((w.shop_cat, 1, 100_000)), "due": None})  # fmt: skip
    assert {chat for chat, _ in notify} == {4, 2}


async def test_unlinked_customer_gets_no_message(sm: SM) -> None:
    """BR-165: customers who never pressed Start are called instead — no Telegram message."""
    w = await _world(sm, linked_customer=False)
    _, notify = await _run(sm, w.shop_owner, "create_debts",
        {"customer_id": w.customer_id, "items": _items((w.shop_cat, 1, 100_000)), "due": None})  # fmt: skip
    assert notify == []


async def test_payment_notice_shows_remaining(sm: SM) -> None:
    """BR-055a"""
    w = await _world(sm)
    await _run(sm, w.shop_owner, "create_debts",
        {"customer_id": w.customer_id, "items": _items((w.shop_cat, 1, 300_000)), "due": None})  # fmt: skip
    async with read_session(sm) as s:
        sid = (await ledger.section_ids(s))["shop"]
    text, notify = await _run(sm, w.shop_owner, "record_payment",
        {"customer_id": w.customer_id, "section_id": sid, "kind": "payment", "amount": 100_000, "debt_id": None, "expected": []})  # fmt: skip
    assert "To'lov saqlandi" in text
    assert [c for c, _ in notify] == [4]
    assert "100 000 so'm" in notify[0][1] and "Qolgan qarz: 200 000 so'm" in notify[0][1]


async def test_full_payment_message_and_writeoff_not_cash(sm: SM) -> None:
    w = await _world(sm)
    await _run(sm, w.shop_owner, "create_debts",
        {"customer_id": w.customer_id, "items": _items((w.shop_cat, 1, 100_000)), "due": None})  # fmt: skip
    async with read_session(sm) as s:
        sid = (await ledger.section_ids(s))["shop"]
    _, notify = await _run(sm, w.shop_owner, "record_payment",
        {"customer_id": w.customer_id, "section_id": sid, "kind": "write_off", "amount": 100_000, "debt_id": None, "expected": []})  # fmt: skip
    assert "hisobdan chiqarildi" in notify[0][1]
    async with read_session(sm) as s:
        pay = (await s.scalars(select(Payment))).one()
    assert (pay.kind, pay.method) == ("write_off", None)


async def test_cancel_sends_correction_and_owner_notice(sm: SM) -> None:
    w = await _world(sm)
    await _run(sm, w.shop_owner, "create_debts",
        {"customer_id": w.customer_id, "items": _items((w.lingerie_cat, 1, 50_000)), "due": None})  # fmt: skip
    async with read_session(sm) as s:
        debt_id = (await ledger.recent_entries(s))[0].id
    text, notify = await _run(sm, w.shop_owner, "cancel_entry", {"kind": "debt", "id": debt_id})
    assert "Bekor qilindi" in text
    chats = {c for c, _ in notify}
    assert chats == {4, 3}
    assert any("adashibmiz" in x and "50 000 so'm" in x for _, x in notify)
    async with read_session(sm) as s:
        assert await ledger.balances(s, w.customer_id) == {}


async def test_customer_cannot_execute_ledger_actions(sm: SM) -> None:
    w = await _world(sm)
    async with read_session(sm) as s:
        outsider = (await s.scalars(select(User).where(User.telegram_id == 4))).one()
    with pytest.raises(cust.NotAllowedError):
        await _run(sm, outsider, "create_debts",
            {"customer_id": w.customer_id, "items": _items((w.shop_cat, 1, 100_000)), "due": None})  # fmt: skip


async def test_delete_with_debt_keeps_debt_in_balances(sm: SM) -> None:
    """Q-33: a deleted customer's debt stays; the customer record is recoverable by admin only."""
    w = await _world(sm)
    await _run(sm, w.shop_owner, "create_debts",
        {"customer_id": w.customer_id, "items": _items((w.shop_cat, 1, 100_000)), "due": None})  # fmt: skip
    await _run(sm, w.shop_owner, "delete_customer", {"id": w.customer_id})
    async with read_session(sm) as s:
        assert sum((await ledger.balances(s, w.customer_id)).values()) == 100_000
        assert await cust.search(s, "umida") == []
    with pytest.raises(cust.NotAllowedError):
        await _run(sm, w.shop_owner, "restore_customer", {"id": w.customer_id})
    await _run(sm, w.admin, "restore_customer", {"id": w.customer_id})
    async with read_session(sm) as s:
        assert len(await cust.search(s, "umida")) == 1


async def test_two_section_customer_notices_never_mix_balances(sm: SM) -> None:
    """BR-025/054: Shop 300k + Underwear 200k → each message names only its own section's balance."""
    w = await _world(sm)
    _, notify = await _run(sm, w.shop_owner, "create_debts",
        {"customer_id": w.customer_id, "items": _items((w.shop_cat, 1, 300_000), (w.lingerie_cat, 1, 200_000)), "due": None})  # fmt: skip
    msgs = [txt for chat, txt in notify if chat == 4]
    assert len(msgs) == 2
    shop_msg = next(m for m in msgs if "Do'kon" in m)
    lin_msg = next(m for m in msgs if "Ichki kiyim" in m)
    assert "qarzingiz: 300 000 so'm" in shop_msg and "500 000" not in shop_msg
    assert "qarzingiz: 200 000 so'm" in lin_msg and "500 000" not in lin_msg
