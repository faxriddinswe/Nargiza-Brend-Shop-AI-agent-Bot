"""AI path for returns and exchanges: finding the original purchase, asking, cards and executed effects."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.ai import dispatcher as d
from bot.ai.base import ToolCall
from bot.db.models import AddressForm, PendingAction, User
from bot.db.session import read_session, uow
from bot.handlers.staff.actions import execute
from bot.services import customers as cust
from bot.services import inventory, ledger, sales
from bot.services import staff as staff_svc
from bot.services.ledger import ItemInput

SM = async_sessionmaker[AsyncSession]
TODAY = date(2026, 11, 11)
CTX = d.Context(today=TODAY)


class W:
    staff: User
    shop_owner: User
    lingerie_owner: User
    umida: int
    cats: dict[str, ledger.CategoryRef]


async def _world(sm: SM) -> W:
    w = W()
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=1, role="admin"))
        for tg, phone in ((2, "+998900000902"), (3, "+998900000903"), (4, "+998900000904")):
            s.add(User(telegram_id=tg, role="customer", phone=phone))
    async with read_session(sm) as s:
        w.staff = (await s.scalars(select(User).where(User.telegram_id == 1))).one()
        w.cats = {c.name: c for c in await ledger.categories(s)}
        cu = (await s.scalars(select(User).where(User.telegram_id == 4))).one()
    async with uow(sm, actor_id=w.staff.id) as s:
        await staff_svc.add_staff(
            s, w.staff, raw_phone="+998900000902", display_name="Nodira opa", section_codes=["shop"]
        )
        await staff_svc.add_staff(
            s,
            w.staff,
            raw_phone="+998900000903",
            display_name="Nilufar opa",
            section_codes=["lingerie"],
        )
    async with read_session(sm) as s:
        w.shop_owner = (await s.scalars(select(User).where(User.telegram_id == 2))).one()
        w.lingerie_owner = (await s.scalars(select(User).where(User.telegram_id == 3))).one()
    async with uow(sm, actor_id=w.staff.id) as s:
        c = await cust.create(
            s, w.staff, name="Umida", address_form=AddressForm.OPA, raw_phone="+998900000904"
        )
        c.user_id = cu.id
        w.umida = c.id
    return w


async def _debt(sm: SM, w: W, items: list[ItemInput]) -> None:
    async with uow(sm, actor_id=w.staff.id) as s:
        await ledger.create_debts(
            s, w.staff, customer_id=w.umida, items=items, due_date=None, today=TODAY
        )


async def _cash_sale(sm: SM, w: W, items: list[ItemInput], customer: int | None = None) -> None:
    async with uow(sm, actor_id=w.staff.id) as s:
        await sales.create_sales(
            s,
            w.staff,
            customer_id=customer,
            items=items,
            final_total=None,
            paid=None,
            due_date=None,
            today=TODAY,
        )


async def _run(sm: SM, actor: User, call: ToolCall) -> d.Outcome:
    async with uow(sm, actor_id=actor.id) as s:
        return (await d.run_calls(s, actor, [call], CTX))[0]


async def _payload(sm: SM, key: str) -> dict[str, Any]:
    async with read_session(sm) as s:
        pa = await s.get(PendingAction, key)
        assert pa is not None
        return pa.payload


async def _exec(
    sm: SM, actor: User, action: str, payload: dict[str, Any]
) -> tuple[str, list[tuple[int, str]]]:
    async with uow(sm, actor_id=actor.id) as s:
        return await execute(s, actor, action, payload)


async def _qty(sm: SM, w: W, name: str) -> int:
    async with read_session(sm) as s:
        return (await inventory.levels(s, [w.cats[name].id]))[0].qty


def _ret(**kw: Any) -> ToolCall:
    return ToolCall("register_return", kw)


async def test_return_of_credit_goods_card_and_execution(sm: SM) -> None:
    w = await _world(sm)
    await _debt(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    out = await _run(sm, w.staff, _ret(customer_query="Umida", item="ko'ylakni"))
    assert out.card is not None
    assert (await _payload(sm, out.card.key))["expected"] == [300_000, 300_000, 0]
    assert "Qarzdan ayiriladi: 300 000 so'm" in (out.text or "")
    text, notify = await _exec(
        sm, w.shop_owner, "register_return", await _payload(sm, out.card.key)
    )
    assert "Qaytarish saqlandi" in text
    assert [c for c, _ in notify] == [4]  # the customer; same-section owner is the actor
    assert "Qarzingiz yopildi" in notify[0][1]
    async with read_session(sm) as s:
        assert await ledger.balances(s, w.umida) == {}


async def test_several_purchases_ask_which_one(sm: SM) -> None:
    w = await _world(sm)
    await _debt(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    await _cash_sale(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 200_000)], customer=w.umida)
    call = _ret(customer_query="Umida", item="ko'ylak")
    out = await _run(sm, w.staff, call)
    assert out.card is None and len(out.choices) == 2
    picked = next(c for c in out.choices if "savdo" in c.label)
    out2 = await _run(sm, w.staff, d.with_choice(call, picked.patch))
    assert out2.card is not None and (await _payload(sm, out2.card.key))["expected"] == [
        200_000,
        0,
        200_000,
    ]


async def test_quantity_is_asked_when_unclear(sm: SM) -> None:
    w = await _world(sm)
    await _cash_sale(sm, w, [ItemInput(w.cats["shim"].id, 3, 100_000)])
    call = _ret(item="shim")
    out = await _run(sm, w.staff, call)
    assert out.card is None and [c.label for c in out.choices] == ["1 ta", "2 ta", "3 ta"]
    out2 = await _run(sm, w.staff, d.with_choice(call, {"quantity": 2}))
    assert out2.card is not None and (await _payload(sm, out2.card.key))["expected"][0] == 200_000
    stated = await _run(sm, w.staff, _ret(item="shim", quantity=1))
    assert stated.card is not None  # said "bittasini" → no question


async def test_nothing_to_return(sm: SM) -> None:
    w = await _world(sm)
    out = await _run(sm, w.staff, _ret(customer_query="Umida", item="ko'ylak"))
    assert out.card is None and out.text and "topilmadi" in out.text
    await _debt(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    too_many = await _run(sm, w.staff, _ret(customer_query="Umida", item="ko'ylak", quantity=5))
    assert too_many.card is None


async def test_exchange_cash_sale_for_more_expensive_item(sm: SM) -> None:
    """Ko'ylak 175 000 (naqd) → o'rniga oyoq kiyim 280 000: sof farq +105 000."""
    w = await _world(sm)
    await _cash_sale(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 175_000)])
    out = await _run(
        sm,
        w.staff,
        _ret(item="ko'ylak", new_items=[{"item": "tufli", "unit_price_text": "280 ming"}]),
    )
    assert out.card is not None and "mijoz 105 000 so'm qo'shib beradi" in (out.text or "")
    text, _ = await _exec(sm, w.staff, "register_return", await _payload(sm, out.card.key))
    assert "Qaytarish saqlandi" in text and "Savdo saqlandi" in text
    assert (
        await _qty(sm, w, "ko'ylak") == 0 and await _qty(sm, w, "oyoq kiyim") == -1
    )  # one in, one out (from 0)


async def test_exchange_for_cheaper_item_returns_the_difference(sm: SM) -> None:
    w = await _world(sm)
    await _cash_sale(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    out = await _run(
        sm,
        w.staff,
        _ret(item="ko'ylak", new_items=[{"item": "sumka", "unit_price_text": "120 ming"}]),
    )
    assert out.card is not None and "mijozga 180 000 so'm qaytariladi" in (out.text or "")


async def test_cross_section_exchange_notifies_both_owners(sm: SM) -> None:
    """Ichki kiyim (Nilufar) qaytarildi, o'rniga ko'ylak (Nodira) — Nodira yozadi → Nilufar xabar oladi."""
    w = await _world(sm)
    await _debt(sm, w, [ItemInput(w.cats["ichki kiyim"].id, 1, 100_000)])
    out = await _run(
        sm,
        w.shop_owner,
        _ret(
            customer_query="Umida",
            item="ichki kiyim",
            new_items=[{"item": "ko'ylak", "unit_price_text": "150 ming"}],
            paid_text="150 ming",
        ),
    )
    assert out.card is not None
    _, notify = await _exec(sm, w.shop_owner, "register_return", await _payload(sm, out.card.key))
    chats = {c for c, _ in notify}
    assert (
        3 in chats and 4 in chats and 2 not in chats
    )  # lingerie owner told, customer told, actor not


async def test_stale_return_card_is_refused(sm: SM) -> None:
    w = await _world(sm)
    await _debt(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    out = await _run(sm, w.staff, _ret(customer_query="Umida", item="ko'ylak"))
    assert out.card is not None
    payload = await _payload(sm, out.card.key)
    async with uow(sm, actor_id=w.staff.id) as s:
        from bot.db.models import PaymentKind

        await ledger.record_payment(
            s,
            w.staff,
            customer_id=w.umida,
            section_id=w.cats["ko'ylak"].section_id,
            amount=100_000,
            kind=PaymentKind.PAYMENT,
            today=TODAY,
        )
    with pytest.raises(ledger.PlanChangedError):
        await _exec(sm, w.staff, "register_return", payload)


async def test_cancel_entry_covers_sales_and_returns(sm: SM) -> None:
    w = await _world(sm)
    await _cash_sale(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 100_000)])
    async with read_session(sm) as s:
        entry = (await ledger.recent_entries(s))[0]
    assert entry.kind == "sale"
    text, _ = await _exec(sm, w.staff, "cancel_entry", {"kind": "sale", "id": entry.id})
    assert "Bekor qilindi" in text and await _qty(sm, w, "ko'ylak") == 0
    await _debt(sm, w, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    out = await _run(sm, w.staff, _ret(customer_query="Umida", item="ko'ylak"))
    assert out.card is not None
    await _exec(sm, w.staff, "register_return", await _payload(sm, out.card.key))
    async with read_session(sm) as s:
        entries = await ledger.recent_entries(s)
    ret_entry = next(e for e in entries if e.kind == "return")
    await _exec(sm, w.staff, "cancel_entry", {"kind": "return", "id": ret_entry.id})
    async with read_session(sm) as s:
        assert sum((await ledger.balances(s, w.umida)).values()) == 300_000
