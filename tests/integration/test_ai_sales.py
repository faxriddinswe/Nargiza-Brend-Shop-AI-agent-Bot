"""AI path for sales and stock: cards, questions, confirmed execution and notifications. Fake data only."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.ai import dispatcher as d
from bot.ai.base import ToolCall
from bot.db.models import AddressForm, PendingAction, Sale, User
from bot.db.session import read_session, uow
from bot.handlers.staff.actions import execute
from bot.services import customers as cust
from bot.services import inventory, ledger
from bot.services import staff as staff_svc

SM = async_sessionmaker[AsyncSession]
TODAY = date(2026, 11, 11)
CTX = d.Context(today=TODAY)


class W:
    staff: User
    shop_owner: User
    lingerie_owner: User
    umida: int
    cats: dict[str, ledger.CategoryRef]


async def _world(sm: SM, *, linked: bool = True) -> W:
    w = W()
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=1, role="admin"))
        for tg, phone in ((2, "+998900000702"), (3, "+998900000703"), (4, "+998900000704")):
            s.add(User(telegram_id=tg, role="customer", phone=phone))
    async with read_session(sm) as s:
        w.staff = (await s.scalars(select(User).where(User.telegram_id == 1))).one()
        w.cats = {c.name: c for c in await ledger.categories(s)}
        customer_user = (await s.scalars(select(User).where(User.telegram_id == 4))).one()
    async with uow(sm, actor_id=w.staff.id) as s:
        await staff_svc.add_staff(
            s, w.staff, raw_phone="+998900000702", display_name="Nodira opa", section_codes=["shop"]
        )
        await staff_svc.add_staff(
            s,
            w.staff,
            raw_phone="+998900000703",
            display_name="Nilufar opa",
            section_codes=["lingerie"],
        )
    async with read_session(sm) as s:
        w.shop_owner = (await s.scalars(select(User).where(User.telegram_id == 2))).one()
        w.lingerie_owner = (await s.scalars(select(User).where(User.telegram_id == 3))).one()
    async with uow(sm, actor_id=w.staff.id) as s:
        c = await cust.create(
            s, w.staff, name="Umida", address_form=AddressForm.OPA, raw_phone="+998900000704"
        )
        if linked:
            c.user_id = customer_user.id
        w.umida = c.id
    return w


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


def _sale(**kw: Any) -> ToolCall:
    return ToolCall("add_sale", kw)


async def _sales_count(sm: SM) -> int:
    async with read_session(sm) as s:
        return int(await s.scalar(select(func.count()).select_from(Sale)) or 0)


# ------------------------------------------------------------------ cards
async def test_plain_sale_card_without_customer(sm: SM) -> None:
    w = await _world(sm)
    out = await _run(sm, w.staff, _sale(items=[{"item": "ko'ylak", "unit_price_text": "450 ming"}]))
    assert (
        out.card is not None
        and "Mijozsiz" in (out.text or "")
        and "450 000 so'm" in (out.text or "")
    )
    assert await _sales_count(sm) == 0  # a card only — nothing saved


async def test_discount_card(sm: SM) -> None:
    """ "500 minglik ko'ylakni 450 ga sotdim" """
    w = await _world(sm)
    out = await _run(
        sm,
        w.staff,
        _sale(items=[{"item": "ko'ylak", "unit_price_text": "500 minglik"}], total_text="450"),
    )
    assert out.card is not None
    assert (await _payload(sm, out.card.key))["final_total"] == 450_000
    assert "Chegirma: −50 000 so'm" in (out.text or "") and "Savdo: 450 000 so'm" in (
        out.text or ""
    )


async def test_mixed_sale_asks_due_then_shows_split(sm: SM) -> None:
    """ "Umidaga ko'ylak 500 ming, 200 berdi, qolgani qarz" """
    w = await _world(sm)
    call = _sale(
        customer_query="Umida",
        items=[{"item": "ko'ylak", "unit_price_text": "500 ming"}],
        paid_text="200 ming",
    )
    out = await _run(sm, w.staff, call)
    assert out.card is None and [c.patch["due_text"] for c in out.choices][-1] == "muddatsiz"
    out2 = await _run(sm, w.staff, d.with_choice(call, {"due_text": "2 hafta"}))
    assert out2.card is not None
    text = out2.text or ""
    assert (
        "Savdo: 500 000 so'm" in text
        and "Naqd tushdi: 200 000 so'm" in text
        and "Nasiyaga: 300 000 so'm" in text
    )
    assert (await _payload(sm, out2.card.key))["due"] == "2026-11-25"


async def test_credit_part_without_customer_asks_who(sm: SM) -> None:
    w = await _world(sm)
    out = await _run(
        sm,
        w.staff,
        _sale(items=[{"item": "ko'ylak", "unit_price_text": "500 ming"}], paid_text="100 ming"),
    )
    assert out.card is None and out.question


async def test_price_above_list_and_overpaid_are_explained(sm: SM) -> None:
    w = await _world(sm)
    out = await _run(
        sm,
        w.staff,
        _sale(items=[{"item": "ko'ylak", "unit_price_text": "500 ming"}], total_text="600 ming"),
    )
    assert out.card is None and out.text and "yuqori" in out.text
    out = await _run(
        sm,
        w.staff,
        _sale(
            customer_query="Umida",
            items=[{"item": "ko'ylak", "unit_price_text": "500 ming"}],
            paid_text="700 ming",
        ),
    )
    assert out.card is None and out.text and "700 000" in out.text


async def test_unknown_product_in_sale_asks(sm: SM) -> None:
    w = await _world(sm)
    out = await _run(sm, w.staff, _sale(items=[{"item": "mozaika", "unit_price_text": "50 ming"}]))
    assert out.card is None and out.choices


async def test_stock_cards_and_reads(sm: SM) -> None:
    w = await _world(sm)
    out = await _run(sm, w.staff, ToolCall("add_stock_in", {"item": "yubkalar", "quantity": 20}))
    assert out.card is not None and "+20 ta" in (out.text or "")
    out = await _run(
        sm,
        w.staff,
        ToolCall(
            "stock_count",
            {"counts": [{"item": "ko'ylak", "counted": 45}, {"item": "kofta", "counted": 30}]},
        ),
    )
    assert out.card is not None and "0 → 45" in (out.text or "")
    unknown = await _run(
        sm, w.staff, ToolCall("stock_count", {"counts": [{"item": "mozaika", "counted": 3}]})
    )
    assert unknown.card is None and unknown.choices
    empty = await _run(sm, w.staff, ToolCall("get_stock", {}))
    assert empty.text and "Yubka: 0 ta" in empty.text
    assert (await _run(sm, w.staff, ToolCall("list_low_stock", {}))).text


# ------------------------------------------------------------------ confirmed execution
async def test_executed_mixed_sale_notifies_customer_and_other_owner(sm: SM) -> None:
    w = await _world(sm)
    payload = {"customer_id": w.umida, "items": [{"category_id": w.cats["ichki kiyim"].id, "quantity": 2, "unit_price": 150_000, "note": None}],
        "final_total": None, "paid": 100_000, "due": "2026-12-01"}  # fmt: skip
    text, notify = await _exec(
        sm, w.shop_owner, "create_sale", payload
    )  # shop owner sells underwear
    chats = {c for c, _ in notify}
    assert chats == {4, 3}  # customer (credit part) + lingerie owner; not the actor
    customer_msg = next(m for c, m in notify if c == 4)
    assert "Nasiyaga: 200 000 so'm" in customer_msg and "To'langan: 100 000 so'm" in customer_msg
    assert "qarzingiz: 200 000 so'm" in customer_msg
    assert "Nodira opa" in next(m for c, m in notify if c == 3)
    assert (
        "ombor" in text.lower() or "Ombor" in text
    )  # underwear stock is 0 → went negative → warned


async def test_cash_sale_does_not_message_the_customer(sm: SM) -> None:
    w = await _world(sm)
    payload = {"customer_id": w.umida, "items": [{"category_id": w.cats["ko'ylak"].id, "quantity": 1, "unit_price": 300_000, "note": None}],
        "final_total": None, "paid": None, "due": None}  # fmt: skip
    _, notify = await _exec(sm, w.shop_owner, "create_sale", payload)
    assert notify == []  # fully paid in cash, same-section owner: nobody to tell


async def test_stock_actions_change_the_stock(sm: SM) -> None:
    w = await _world(sm)
    text, _ = await _exec(
        sm, w.staff, "stock_in", {"category_id": w.cats["yubka"].id, "quantity": 20}
    )
    assert "20 ta" in text
    await _exec(
        sm,
        w.staff,
        "stock_count",
        {"counts": {str(w.cats["yubka"].id): 18, str(w.cats["sumka"].id): 2}},
    )
    async with read_session(sm) as s:
        qty = {r.name: r.qty for r in await inventory.levels(s)}
    assert (qty["yubka"], qty["sumka"]) == (18, 2)
