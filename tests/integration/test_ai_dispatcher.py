"""AI dispatcher with a fake model: what happens to spoken requests. Real Postgres, fake data only.

The model only *asks* for tools; these tests prove that code resolves customers/products/numbers,
asks instead of guessing, never saves without a card, and enforces permissions.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.ai import dispatcher as d
from bot.ai.base import ToolCall
from bot.ai.tools import REGISTRY
from bot.db.models import AddressForm, Debt, Payment, PendingAction, User
from bot.db.session import read_session, uow
from bot.services import customers as cust
from bot.services import ledger
from bot.services.ledger import ItemInput

SM = async_sessionmaker[AsyncSession]
TODAY = date(2026, 11, 11)
CTX = d.Context(today=TODAY)


class W:
    staff: User
    customer_role: User
    umida: int
    jasur: int
    cats: dict[str, ledger.CategoryRef]


async def _world(sm: SM) -> W:
    w = W()
    async with uow(sm, actor_kind="system") as s:
        s.add_all([User(telegram_id=1, role="staff"), User(telegram_id=2, role="customer")])
    async with read_session(sm) as s:
        w.staff = (await s.scalars(select(User).where(User.telegram_id == 1))).one()
        w.customer_role = (await s.scalars(select(User).where(User.telegram_id == 2))).one()
        w.cats = {c.name: c for c in await ledger.categories(s)}
    async with uow(sm, actor_id=w.staff.id) as s:
        w.umida = (
            await cust.create(
                s, w.staff, name="Umida", address_form=AddressForm.OPA, raw_phone="+998900000501"
            )
        ).id
        w.jasur = (
            await cust.create(
                s, w.staff, name="Jasur", address_form=AddressForm.AKA, raw_phone="+998900000502"
            )
        ).id
    return w


async def _debt(sm: SM, w: W, cid: int, items: list[ItemInput]) -> None:
    async with uow(sm, actor_id=w.staff.id) as s:
        await ledger.create_debts(
            s, w.staff, customer_id=cid, items=items, due_date=None, today=TODAY
        )


async def _run(sm: SM, actor: User, call: ToolCall, ctx: d.Context = CTX) -> d.Outcome:
    async with uow(sm, actor_id=actor.id) as s:
        return (await d.run_calls(s, actor, [call], ctx))[0]


def _pay(**kw: Any) -> ToolCall:
    return ToolCall("add_payment", kw)


async def _payload(sm: SM, key: str) -> dict[str, Any]:
    async with read_session(sm) as s:
        pa = await s.get(PendingAction, key)
        assert pa is not None
        return pa.payload


async def _counts(sm: SM) -> tuple[int, int]:
    async with read_session(sm) as s:
        return (
            int(await s.scalar(select(func.count()).select_from(Debt)) or 0),
            int(await s.scalar(select(func.count()).select_from(Payment)) or 0),
        )


# ------------------------------------------------------------------ happy paths
@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("100 ming", 100_000),
        ("yuz ming", 100_000),
        ("100k", 100_000),
        ("yarim million", 500_000),
        ("uch yuz ellik ming", 350_000),
    ],
)
async def test_payment_card_with_amount_in_words(sm: SM, spoken: str, expected: int) -> None:
    """Master §8.4: "uch yuz ellik ming", "yarim million" → exact int, parsed by OUR code."""
    w = await _world(sm)
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 600_000)])
    out = await _run(sm, w.staff, _pay(customer_query="Umida", amount_text=spoken))
    assert out.card is not None and out.question is None
    payload = await _payload(sm, out.card.key)
    assert payload["amount"] == expected and payload["kind"] == "payment"
    assert await _counts(sm) == (1, 0)  # card only — NOTHING written to the ledger yet


async def test_nothing_is_saved_without_confirmation(sm: SM) -> None:
    w = await _world(sm)
    await _run(sm, w.staff, ToolCall("add_debt", {"customer_query": "Umida", "due_text": "2 hafta",
        "items": [{"item": "ko'ylak", "quantity": 2, "unit_price_text": "175 ming"}]}))  # fmt: skip
    assert await _counts(sm) == (0, 0)


async def test_debt_card_splits_sections_and_parses_due(sm: SM) -> None:
    w = await _world(sm)
    out = await _run(sm, w.staff, ToolCall("add_debt", {"customer_query": "Umida", "due_text": "2 hafta", "items": [
        {"item": "ko'ylakni", "quantity": 2, "unit_price_text": "175 ming"},
        {"item": "ичкий кийим", "quantity": 1, "unit_price_text": "80000"}]}))  # fmt: skip
    assert out.card is not None
    payload = await _payload(sm, out.card.key)
    assert payload["due"] == "2026-11-25"
    assert [(i["category_id"], i["quantity"], i["unit_price"]) for i in payload["items"]] == [
        (w.cats["ko'ylak"].id, 2, 175_000), (w.cats["ichki kiyim"].id, 1, 80_000)]  # fmt: skip
    assert "350 000 so'm" in (out.text or "") and "80 000 so'm" in (out.text or "")


# ------------------------------------------------------------------ asks instead of guessing
async def test_amount_not_understood_asks(sm: SM) -> None:
    w = await _world(sm)
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 600_000)])
    for bad in ("bir necha ming", "1500", "ko'p", "350-400 ming"):
        out = await _run(sm, w.staff, _pay(customer_query="Umida", amount_text=bad))
        assert out.card is None and out.question, bad


async def test_two_customers_same_name_asks_then_resumes(sm: SM) -> None:
    """BR-045: bir xil ismlar → tanlatadi; tanlangach davom etadi."""
    w = await _world(sm)
    async with uow(sm, actor_id=w.staff.id) as s:
        second = await cust.create(
            s,
            w.staff,
            name="Umida",
            address_form=AddressForm.OPA,
            raw_phone="+998900000503",
            note="Shahlo opaning qizi",
        )
    await _debt(sm, w, second.id, [ItemInput(w.cats["ko'ylak"].id, 1, 600_000)])
    call = _pay(customer_query="Umida", amount_text="100 ming")
    out = await _run(sm, w.staff, call)
    assert out.card is None and len(out.choices) == 2 and out.resume == call
    picked = next(c for c in out.choices if c.patch["customer_id"] == second.id)
    out2 = await _run(sm, w.staff, d.with_choice(out.resume, picked.patch))
    assert out2.card is not None
    assert (await _payload(sm, out2.card.key))["customer_id"] == second.id


async def test_unknown_product_asks_with_all_categories(sm: SM) -> None:
    w = await _world(sm)
    call = ToolCall("add_debt", {"customer_query": "Umida", "due_text": "muddatsiz",
        "items": [{"item": "mozaika", "quantity": 1, "unit_price_text": "50 ming"}]})  # fmt: skip
    out = await _run(sm, w.staff, call)
    assert out.card is None and out.question and len(out.choices) == len(w.cats)
    pick = next(c for c in out.choices if c.label.lower() == "yubka")
    out2 = await _run(sm, w.staff, d.with_choice(call, pick.patch))
    assert out2.card is not None


async def test_missing_due_date_asks_with_four_buttons(sm: SM) -> None:
    """BR-052: muddat aytilmasa so'raydi."""
    w = await _world(sm)
    call = ToolCall(
        "add_debt",
        {"customer_query": "Umida", "items": [{"item": "shim", "unit_price_text": "200 ming"}]},
    )
    out = await _run(sm, w.staff, call)
    assert out.question and [c.patch["due_text"] for c in out.choices] == [
        "1 hafta",
        "2 hafta",
        "1 oy",
        "muddatsiz",
    ]
    out2 = await _run(sm, w.staff, d.with_choice(call, out.choices[3].patch))
    assert out2.card is not None and (await _payload(sm, out2.card.key))["due"] is None


async def test_two_sections_without_section_asks(sm: SM) -> None:
    """BR-066: ikkala bo'limda qarz bo'lsa — bo'limni so'raydi."""
    w = await _world(sm)
    await _debt(
        sm,
        w,
        w.umida,
        [
            ItemInput(w.cats["ko'ylak"].id, 1, 300_000),
            ItemInput(w.cats["ichki kiyim"].id, 1, 200_000),
        ],
    )
    call = _pay(customer_query="Umida", amount_text="100 ming")
    out = await _run(sm, w.staff, call)
    assert out.card is None and {c.patch["section"] for c in out.choices} == {"shop", "lingerie"}
    out2 = await _run(sm, w.staff, d.with_choice(call, {"section": "lingerie"}))
    assert out2.card is not None


async def test_specific_debt_by_product(sm: SM) -> None:
    """BR-062: "oyoq kiyim qarzidan ayir"."""
    w = await _world(sm)
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    await _debt(sm, w, w.umida, [ItemInput(w.cats["oyoq kiyim"].id, 1, 200_000)])
    out = await _run(sm, w.staff, _pay(customer_query="Umida", amount_text="50 ming", item="tufli"))
    assert out.card is not None
    payload = await _payload(sm, out.card.key)
    assert payload["debt_id"] is not None and payload["expected"] == [[payload["debt_id"], 50_000]]


async def test_overpayment_is_explained_not_saved(sm: SM) -> None:
    w = await _world(sm)
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 250_000)])
    out = await _run(sm, w.staff, _pay(customer_query="Umida", amount_text="300 ming"))
    assert (
        out.card is None
        and "250 000 so'm" in (out.text or "")
        and "300 000 so'm" in (out.text or "")
    )


async def test_unknown_customer_and_no_debt(sm: SM) -> None:
    w = await _world(sm)
    out = await _run(sm, w.staff, _pay(customer_query="Zebo", amount_text="10 ming"))
    assert out.card is None and "Zebo" in (out.text or "")
    out = await _run(sm, w.staff, _pay(customer_query="Jasur", amount_text="10 ming"))
    assert out.card is None and "qarzi yo'q" in (out.text or "")


async def test_last_customer_context_for_pronouns(sm: SM) -> None:
    """BR-110: "unga yana 20 ming qo'sh" — customer_query bo'sh, oxirgi mijoz ishlatiladi."""
    w = await _world(sm)
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    out = await _run(
        sm, w.staff, _pay(amount_text="100 ming"), d.Context(today=TODAY, last_customer_id=w.umida)
    )
    assert out.card is not None
    out = await _run(sm, w.staff, _pay(amount_text="100 ming"))
    assert out.card is None and out.question  # no context → asks who


# ------------------------------------------------------------------ safety
async def test_customer_role_cannot_use_tools(sm: SM) -> None:
    w = await _world(sm)
    out = await _run(sm, w.customer_role, ToolCall("list_debtors", {}))
    assert out.card is None and out.text and "Umida" not in out.text


@pytest.mark.parametrize(
    "call",
    [
        ToolCall("drop_database", {}),
        ToolCall("add_payment", {"amount_text": 5}),
        ToolCall("add_debt", {"customer_query": "Umida", "items": []}),
        ToolCall(
            "add_debt",
            {
                "customer_query": "Umida",
                "items": [{"item": "x", "quantity": -3, "unit_price_text": "5"}],
            },
        ),
    ],
)
async def test_garbage_from_model_is_refused_politely(sm: SM, call: ToolCall) -> None:
    w = await _world(sm)
    out = await _run(sm, w.staff, call)
    assert out.card is None and out.text
    assert await _counts(sm) == (0, 0)


async def test_model_cannot_choose_customer_id(sm: SM) -> None:
    """A smuggled customer_id in the model's args is ignored; only our own `_fix` (from a tapped button)."""
    w = await _world(sm)
    await _debt(sm, w, w.jasur, [ItemInput(w.cats["shim"].id, 1, 300_000)])
    out = await _run(
        sm, w.staff, _pay(customer_query="Zebo", amount_text="10 ming", customer_id=w.jasur)
    )
    assert out.card is None  # "Zebo" not found; the extra field changed nothing


async def test_every_registered_tool_is_handled() -> None:
    import inspect

    src = inspect.getsource(d.run_call)
    for name, (model, _desc, _w) in REGISTRY.items():
        assert model.__name__ in src, f"{name} has no branch in run_call"


# ------------------------------------------------------------------ reads
async def test_debtors_and_overdue_lists(sm: SM) -> None:
    w = await _world(sm)
    async with uow(sm, actor_id=w.staff.id) as s:
        await ledger.create_debts(
            s,
            w.staff,
            customer_id=w.umida,
            items=[ItemInput(w.cats["ko'ylak"].id, 1, 300_000)],
            due_date=date(2026, 11, 11),
            today=date(2026, 11, 1),
        )
    await _debt(sm, w, w.jasur, [ItemInput(w.cats["shim"].id, 1, 500_000)])
    out = await _run(sm, w.staff, ToolCall("list_debtors", {}))
    assert out.text and out.text.index("Jasur") < out.text.index("Umida")  # biggest first
    assert "Jami Do'kon: 800 000 so'm" in out.text
    late = await _run(
        sm, w.staff, ToolCall("list_overdue", {}), d.Context(today=date(2026, 11, 20))
    )
    assert late.text and "Umida" in late.text and "9 kun" in late.text and "Jasur" not in late.text


async def test_customer_debt_question(sm: SM) -> None:
    w = await _world(sm)
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    out = await _run(sm, w.staff, ToolCall("get_customer_debt", {"customer_query": "умида"}))
    assert out.text and "300 000 so'm" in out.text and out.customer_id == w.umida


# ------------------------------------------------------------------ product words
@pytest.mark.parametrize(
    ("spoken", "expected"),
    [("ko'ylak", "ko'ylak"), ("ko'ylakni", "ko'ylak"), ("платье", "ko'ylak"), ("yubkalar", "yubka"), ("туфли", "oyoq kiyim"),
     ("poyabzal", "oyoq kiyim"), ("ичкий кийим", "ichki kiyim"), ("pijamacha", "pijama"), ("kolgotki", "kolgotka"), ("xalatni", "xalat")],
)  # fmt: skip
async def test_resolve_category_variants(sm: SM, spoken: str, expected: str) -> None:
    async with read_session(sm) as s:
        cat = await d.resolve_category(s, spoken)
    assert cat is not None and cat.name == expected


async def test_unknown_word_is_not_guessed(sm: SM) -> None:
    async with read_session(sm) as s:
        assert await d.resolve_category(s, "mozaika") is None
        assert await d.resolve_category(s, "") is None


async def test_model_cannot_smuggle_fix(sm: SM) -> None:
    """Security: `_fix` inside the model's args is ignored — only server-side `fix` (from tapped buttons) counts."""
    w = await _world(sm)
    await _debt(sm, w, w.jasur, [ItemInput(w.cats["shim"].id, 1, 300_000)])
    evil = ToolCall(
        "get_customer_debt", {"customer_query": "Zebo", "_fix": {"customer_id": w.jasur}}
    )
    out = await _run(sm, w.staff, evil)
    assert out.text and "Zebo" in out.text and "300 000" not in out.text
    trusted = ToolCall("get_customer_debt", {"customer_query": "Zebo"}, {"customer_id": w.jasur})
    out = await _run(sm, w.staff, trusted)
    assert out.text and "300 000 so'm" in out.text


async def test_choice_patch_goes_into_trusted_fix(sm: SM) -> None:
    call = ToolCall("add_payment", {"amount_text": "1 ming"})
    new = d.with_choice(d.with_choice(call, {"customer_id": 7}), {"section": "shop"})
    assert new.fix == {"customer_id": 7, "section": "shop"} and "_fix" not in new.args


# ------------------------------------------------------------------ business review (stage 3/4)
async def test_single_fuzzy_customer_is_confirmed_not_assumed(sm: SM) -> None:
    """A misheard "Umid" must not silently become "Umida" — a wrong customer means a wrong debt."""
    w = await _world(sm)
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    call = _pay(customer_query="Umid", amount_text="100 ming")
    out = await _run(sm, w.staff, call)
    assert (
        out.card is None and out.question and [c.label for c in out.choices] == ["✅ Ha", "❌ Yo'q"]
    )
    yes = await _run(sm, w.staff, d.with_choice(call, out.choices[0].patch))
    assert yes.card is not None
    no = await _run(sm, w.staff, d.with_choice(call, out.choices[1].patch))
    assert no.card is None and no.question is None


async def test_whole_word_and_phone_tail_are_accepted_silently(sm: SM) -> None:
    w = await _world(sm)
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    for q in ("Umida", "умида", "0501"):  # name, Cyrillic, phone tail (+998900000501)
        out = await _run(sm, w.staff, _pay(customer_query=q, amount_text="100 ming"))
        assert out.card is not None, q


async def test_unit_less_amount_is_flagged_on_the_card(sm: SM) -> None:
    """BR-076: "350" → 350 000, and the staff member is told above the card."""
    w = await _world(sm)
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 600_000)])
    out = await _run(sm, w.staff, _pay(customer_query="Umida", amount_text="350"))
    assert (
        out.card is not None
        and out.text
        and out.text.startswith("⚠️ «350» ni 350 000 so'm deb tushundim")
    )
    debt = await _run(sm, w.staff, ToolCall("add_debt", {"customer_query": "Umida", "due_text": "muddatsiz",
        "items": [{"item": "shim", "unit_price_text": "450"}]}))  # fmt: skip
    assert debt.text and "450 000 so'm" in debt.text and debt.text.startswith("⚠️")


async def test_write_off_all_with_amount_asks(sm: SM) -> None:
    w = await _world(sm)
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 300_000)])
    call = ToolCall("write_off", {"customer_query": "Umida", "all": True, "amount_text": "50 ming"})
    out = await _run(sm, w.staff, call)
    assert out.card is None and len(out.choices) == 2
    only = await _run(sm, w.staff, d.with_choice(call, {"amount_only": True}))
    assert only.card is not None and (await _payload(sm, only.card.key))["amount"] == 50_000
    whole = await _run(sm, w.staff, d.with_choice(call, {"all_only": True}))
    assert whole.card is not None and (await _payload(sm, whole.card.key))["amount"] == 300_000


async def test_new_customer_card_stops_the_following_requests(sm: SM) -> None:
    """ "Yangi mijoz Laylo, unga qarz": the debt must wait until the customer is confirmed."""
    w = await _world(sm)
    calls = [
        ToolCall("create_customer", {"name": "Laylo", "form": "opa"}),
        ToolCall(
            "add_debt",
            {"customer_query": "Laylo", "items": [{"item": "shim", "unit_price_text": "200 ming"}]},
        ),
    ]
    async with uow(sm, actor_id=w.staff.id) as s:
        outcomes = await d.run_calls(s, w.staff, calls, CTX)
    assert len(outcomes) == 1 and outcomes[0].card is not None


async def test_cancel_last_prefers_my_own_record_and_shows_who(sm: SM) -> None:
    w = await _world(sm)
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=9, role="staff", tg_first_name="Boshqa"))
    async with read_session(sm) as s:
        other = (await s.scalars(select(User).where(User.telegram_id == 9))).one()
    await _debt(sm, w, w.umida, [ItemInput(w.cats["ko'ylak"].id, 1, 100_000)])  # mine
    async with uow(sm, actor_id=other.id) as s:  # someone else's, newer
        await ledger.create_debts(
            s,
            other,
            customer_id=w.jasur,
            items=[ItemInput(w.cats["shim"].id, 1, 777_000)],
            due_date=None,
            today=TODAY,
        )
    out = await _run(sm, w.staff, ToolCall("cancel_last_entry", {}))
    assert (
        out.card is not None and "Umida" in (out.text or "") and "777 000" not in (out.text or "")
    )
    assert "Yozgan:" in (out.text or "")
    named = await _run(sm, w.staff, ToolCall("cancel_last_entry", {"customer_query": "Jasur"}))
    assert named.card is not None and "777 000 so'm" in (named.text or "")


async def test_context_older_than_15_minutes_is_forgotten() -> None:
    import time

    from bot.handlers.staff.agent import _fresh_last

    assert _fresh_last({"ai_last_customer": 5, "ai_at": time.time()}) == 5
    assert _fresh_last({"ai_last_customer": 5, "ai_at": time.time() - 16 * 60}) is None
    assert _fresh_last({}) is None


async def test_short_words_do_not_hit_products(sm: SM) -> None:
    async with read_session(sm) as s:
        for word in ("ko", "kof", "shi", "sum", "ship"):
            assert await d.resolve_category(s, word) is None, word
