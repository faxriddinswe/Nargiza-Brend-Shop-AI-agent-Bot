"""Turns the model's tool requests into confirmation cards, answers or clarifying questions.

The model only *asks*; this module decides (master §8.4):
- permissions are checked here, in code;
- the customer, the product category, the section and every number are resolved by our own code;
- anything unclear becomes a question with buttons (`Outcome.question` + `choices`) — never a guess;
- every write stops at a confirmation card; nothing is saved here.

It reuses the same services and card builders as the button flows, so both paths follow identical rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pydantic import ValidationError
from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot import cards
from bot.ai import tools
from bot.ai.base import ToolCall
from bot.db.models import CategorySynonym, Customer, PaymentKind, Role, User
from bot.services import customers as cust
from bot.services import ledger
from bot.services.allocation import DebtNotOpenError, NothingToPayError, OverpaymentError
from bot.texts import uz_latn as t
from bot.utils.dates import format_date, parse_due_text
from bot.utils.money import AmountParseError, format_amount, parse_amount
from bot.utils.phone import InvalidPhoneError, normalize_phone
from bot.utils.translit import search_key

MAX_CALLS = 5
STAFF = {Role.STAFF.value, Role.ADMIN.value}


@dataclass(frozen=True, slots=True)
class Choice:
    label: str
    patch: dict[str, Any]  # merged into the call's `_fix` when the user taps it


@dataclass(slots=True)
class Outcome:
    text: str | None = None
    card: cards.Card | None = None  # a confirmation card was created
    question: str | None = None  # needs an answer; shown with `choices` as buttons if any
    choices: list[Choice] = field(default_factory=list)
    resume: ToolCall | None = None  # re-run with the chosen patch
    customer_id: int | None = None  # becomes the conversation's "last customer" (BR-110)
    heard: str | None = None


@dataclass(frozen=True, slots=True)
class Context:
    today: date
    last_customer_id: int | None = None


# ----------------------------------------------------------------- resolvers
async def _customer(
    session: AsyncSession, call: ToolCall, query: str | None, fix: dict[str, Any], ctx: Context
) -> Customer | Outcome:
    if (cid := fix.get("customer_id")) is not None:
        try:
            return await cust.get(session, int(cid))
        except cust.CustomerNotFoundError:
            return Outcome(text=t.CUSTOMER_NOT_FOUND)
    q = (query or "").strip()
    if not q:
        if ctx.last_customer_id is not None:
            try:
                return await cust.get(session, ctx.last_customer_id)
            except cust.CustomerNotFoundError:
                pass
        return Outcome(question=t.AI_WHO_QUESTION)
    found = await cust.search(session, q, limit=6)
    if not found:
        return Outcome(text=t.ai_customer_missing(q))
    if len(found) == 1:
        return found[0]
    key = search_key(q)
    exact = [c for c in found if c.search_name == key]
    if len(exact) == 1:  # one exact name among fuzzy neighbours
        return exact[0]
    choices = []
    for c in found[:5]:
        owed = sum((await ledger.balances(session, c.id)).values())
        label = t.customer_button(
            f"{c.name} {c.address_form}", c.note or (f"…{c.phone[-4:]}" if c.phone else None), owed
        )
        choices.append(Choice(label, {"customer_id": c.id}))
    return Outcome(question=t.ai_customer_question(q), choices=choices, resume=call)


async def resolve_category(session: AsyncSession, text: str) -> ledger.CategoryRef | None:
    """Spoken product → category via names, synonyms (Cyrillic/Latin), suffix forms and light fuzziness."""
    key = search_key(text)
    if not key:
        return None
    refs = {c.id: c for c in await ledger.categories(session)}
    words: dict[str, int] = {}
    for c in refs.values():
        words[search_key(c.name)] = c.id
    for cat_id, syn in (
        await session.execute(select(CategorySynonym.category_id, CategorySynonym.synonym))
    ).all():
        if cat_id in refs:
            words[syn] = cat_id
    if key in words:
        return refs[words[key]]
    hits = {
        cid
        for w, cid in words.items()
        if len(w) >= 3 and (key.startswith(w) or (len(key) >= 4 and w.startswith(key)))
    }
    if len(hits) == 1:  # "ko'ylakni", "yubkalar", "tufl"
        return refs[hits.pop()]
    if not hits:
        best = process.extractOne(key, list(words), scorer=fuzz.ratio, score_cutoff=82)
        if best:
            return refs[words[best[0]]]
    return None


async def _all_choices_for_item(
    session: AsyncSession, call: ToolCall, idx: int, fix: dict[str, Any], item: str
) -> Outcome:
    mapping = dict(fix.get("item_categories", {}))
    choices = []
    for c in await ledger.categories(session):
        choices.append(
            Choice(c.name.capitalize(), {"item_categories": {**mapping, str(idx): c.id}})
        )
    return Outcome(question=t.ai_item_question(item), choices=choices, resume=call)


# ----------------------------------------------------------------- handlers
Handler = Any


async def _add_debt(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.AddDebt,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    c = await _customer(session, call, args.customer_query, fix, ctx)
    if isinstance(c, Outcome):
        return c
    mapping = fix.get("item_categories", {})
    by_id = {x.id: x for x in await ledger.categories(session)}
    items: list[ledger.ItemInput] = []
    for idx, it in enumerate(args.items):
        cat = (
            by_id.get(int(mapping[str(idx)]))
            if str(idx) in mapping
            else await resolve_category(session, it.item)
        )
        if cat is None:
            return await _all_choices_for_item(session, call, idx, fix, it.item)
        try:
            price = parse_amount(it.unit_price_text).value
        except AmountParseError:
            return Outcome(question=t.ai_price_question(it.item), customer_id=c.id)
        items.append(ledger.ItemInput(cat.id, it.quantity, price, it.note))
    due_text = fix.get("due_text", args.due_text)
    if due_text is None:
        opts = [
            ("📅 1 hafta", "1 hafta"),
            ("📅 2 hafta", "2 hafta"),
            ("📅 1 oy", "1 oy"),
            ("♾ Muddatsiz", "muddatsiz"),
        ]
        return Outcome(
            question=t.AI_DUE_QUESTION,
            choices=[Choice(label, {"due_text": v}) for label, v in opts],
            resume=call,
            customer_id=c.id,
        )
    understood, due = parse_due_text(due_text, ctx.today)
    if not understood:
        return Outcome(question=t.ai_due_question(), customer_id=c.id)
    try:
        card = await cards.debt_card(session, actor, c, items, due)
    except ledger.LedgerError:
        return Outcome(text=t.AI_NOT_UNDERSTOOD, customer_id=c.id)
    return Outcome(text=card.text, card=card, customer_id=c.id)


async def _pay(
    session: AsyncSession, actor: User, call: ToolCall, args: tools.AddPayment | tools.WriteOff,
    fix: dict[str, Any], ctx: Context, kind: PaymentKind,
) -> Outcome:  # fmt: skip
    c = await _customer(session, call, args.customer_query, fix, ctx)
    if isinstance(c, Outcome):
        return c
    balances = await ledger.balances(session, c.id)
    if not balances:
        return Outcome(text=t.no_debt_for(cards.who(c)), customer_id=c.id)
    ids = await ledger.section_ids(session)
    codes = {v: k for k, v in ids.items()}
    section_code = fix.get("section") or args.section
    debt_id = fix.get("debt_id")
    item = getattr(args, "item", None)

    if item and debt_id is None:  # "oyoq kiyim qarzidan ayir" (BR-062)
        cat = await resolve_category(session, item)
        if cat is None:
            return Outcome(question=t.ai_item_question(item), customer_id=c.id)
        view = await ledger.customer_ledger(session, c.id)
        cands = [
            (dv, items_)
            for sl in view
            for dv, items_ in sl.open_debts
            if any(n == cat.name for n, *_ in items_)
            and (section_code is None or codes[sl.section_id] == section_code)
        ]
        if not cands:
            return Outcome(text=t.AI_NO_DEBT_ITEM, customer_id=c.id)
        if len(cands) > 1:
            return Outcome(
                question=t.AI_DEBT_QUESTION,
                choices=[
                    Choice(
                        f"{format_date(dv.debt_date)} · {t.items_short(it_)} · {format_amount(dv.remaining)}",
                        {"debt_id": dv.id},
                    )
                    for dv, it_ in cands[:6]
                ],
                resume=call,
                customer_id=c.id,
            )
        debt_id = cands[0][0].id
    if debt_id is not None:
        debt = next(
            (
                dv
                for sl in await ledger.customer_ledger(session, c.id)
                for dv, _ in sl.open_debts
                if dv.id == int(debt_id)
            ),
            None,
        )
        if debt is None:
            return Outcome(text=t.PAY_CHANGED, customer_id=c.id)
        section_id = debt.section_id
    elif section_code is not None:
        section_id = ids[section_code]
    elif len(balances) == 1:
        section_id = next(iter(balances))
    else:
        return Outcome(
            question=t.AI_SECTION_QUESTION,
            choices=[
                Choice(
                    f"{t.SECTION_NAMES[codes[sid]]} — {format_amount(b)}", {"section": codes[sid]}
                )
                for sid, b in balances.items()
            ],
            resume=call,
            customer_id=c.id,
        )
    owed = balances.get(section_id, 0)
    if not owed:
        return Outcome(text=t.no_debt_for(cards.who(c)), customer_id=c.id)

    if isinstance(args, tools.WriteOff) and args.all:
        amount = owed
    else:
        try:
            amount = parse_amount(args.amount_text or "").value
        except AmountParseError:
            return Outcome(question=t.ai_amount_question(), customer_id=c.id)
    try:
        card = await cards.payment_card(
            session, actor, c, section_id=section_id, amount=amount, kind=kind,
            debt_id=int(debt_id) if debt_id is not None else None,
        )  # fmt: skip
    except OverpaymentError as e:
        return Outcome(text=t.overpay(cards.who(c), e.owed, e.amount), customer_id=c.id)
    except (NothingToPayError, DebtNotOpenError):
        return Outcome(text=t.no_debt_for(cards.who(c)), customer_id=c.id)
    return Outcome(text=card.text, card=card, customer_id=c.id)


async def _create_customer(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.CreateCustomer,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    phone = None
    if args.phone_text:
        try:
            phone = normalize_phone(args.phone_text)
        except InvalidPhoneError:
            return Outcome(question=t.ai_phone_question())
        if (existing := await cust.find_by_phone(session, phone)) is not None:
            return Outcome(text=f"{t.PHONE_TAKEN}\n{cards.who(existing)}", customer_id=existing.id)
    card = await cards.new_customer_card(
        session,
        actor,
        name=" ".join(args.name.split()),
        form=args.form,
        phone=phone,
        note=args.note,
    )
    return Outcome(text=card.text, card=card)


async def _delete_customer(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.DeleteCustomer,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    c = await _customer(session, call, args.customer_query, fix, ctx)
    if isinstance(c, Outcome):
        return c
    card = await cards.delete_customer_card(session, actor, c)
    return Outcome(text=card.text, card=card, customer_id=c.id)


async def _cancel_last(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.CancelLast,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    customer_id = None
    if args.customer_query or fix.get("customer_id"):
        c = await _customer(session, call, args.customer_query, fix, ctx)
        if isinstance(c, Outcome):
            return c
        customer_id = c.id
    entries = await ledger.recent_entries(session, limit=30)
    entry = next((e for e in entries if customer_id is None or e.customer_id == customer_id), None)
    if entry is None:
        return Outcome(text=t.AI_NOTHING_TO_CANCEL)
    card = await cards.cancel_entry_card(session, actor, entry)
    return Outcome(text=card.text, card=card, customer_id=entry.customer_id)


async def _customer_debt(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.GetCustomerDebt,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    c = await _customer(session, call, args.customer_query, fix, ctx)
    if isinstance(c, Outcome):
        return c
    text, _ = await cards.customer_card_text(session, c)
    return Outcome(text=text, customer_id=c.id)


async def _search(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.SearchCustomer,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    found = await cust.search(session, args.query, limit=5)
    if not found:
        return Outcome(text=t.AI_NO_RESULTS)
    lasts = await ledger.last_debt_date(session, [c.id for c in found])
    lines = [t.search_header(len(found)), ""]
    for i, c in enumerate(found, 1):
        owed = sum((await ledger.balances(session, c.id)).values())
        lines.append(
            t.result_line(i, c.name, c.address_form, c.note, c.phone, owed, lasts.get(c.id))
        )
    return Outcome(text="\n".join(lines), customer_id=found[0].id if len(found) == 1 else None)


async def _debtors(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.ListDebtors,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    ids = await ledger.section_ids(session)
    codes = {v: k for k, v in ids.items()}
    rows = await ledger.debtors(session, section_id=ids[args.section] if args.section else None)
    if not rows:
        return Outcome(text=t.AI_NO_DEBTORS)
    totals: dict[str, int] = {}
    for r in rows:
        totals[codes[r.section_id]] = totals.get(codes[r.section_id], 0) + r.owed
    return Outcome(
        text=t.ai_debtors(
            [(f"{r.name} {r.form}", codes[r.section_id], r.owed, r.next_due) for r in rows], totals
        )
    )


async def _overdue(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.ListOverdue,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    codes = await ledger.section_codes(session)
    rows = await ledger.overdue(session, ctx.today)
    if not rows:
        return Outcome(text=t.AI_NO_OVERDUE)
    return Outcome(
        text=t.ai_overdue(
            [(f"{r.name} {r.form}", codes[r.section_id], r.remaining, r.days_overdue) for r in rows]
        )
    )


# ----------------------------------------------------------------- entry points
async def run_call(session: AsyncSession, actor: User, call: ToolCall, ctx: Context) -> Outcome:
    """Validate and run ONE tool request. Never raises for bad model output — it asks instead."""
    if (
        actor.role not in STAFF or actor.is_blocked
    ):  # permissions are decided here, never by the model
        return Outcome(text=t.CARD_NOT_YOURS)
    fix = call.args.get("_fix", {}) if isinstance(call.args.get("_fix", {}), dict) else {}
    raw = {k: v for k, v in call.args.items() if k != "_fix"}
    try:
        args = tools.validate(call.name, raw)
    except (ValidationError, tools.UnknownToolError):
        return Outcome(text=t.AI_NOT_UNDERSTOOD)
    heard = getattr(args, "heard", None)
    if isinstance(args, tools.Ask):
        return Outcome(question=args.question, heard=heard)
    if isinstance(args, tools.Say):
        return Outcome(text=args.text, heard=heard)
    outcome: Outcome
    if isinstance(args, tools.AddDebt):
        outcome = await _add_debt(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.AddPayment):
        outcome = await _pay(session, actor, call, args, fix, ctx, PaymentKind.PAYMENT)
    elif isinstance(args, tools.WriteOff):
        outcome = await _pay(session, actor, call, args, fix, ctx, PaymentKind.WRITE_OFF)
    elif isinstance(args, tools.CreateCustomer):
        outcome = await _create_customer(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.DeleteCustomer):
        outcome = await _delete_customer(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.CancelLast):
        outcome = await _cancel_last(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.GetCustomerDebt):
        outcome = await _customer_debt(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.SearchCustomer):
        outcome = await _search(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.ListDebtors):
        outcome = await _debtors(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.ListOverdue):
        outcome = await _overdue(session, actor, call, args, fix, ctx)
    else:  # pragma: no cover — registry and dispatcher are kept in sync by a test
        outcome = Outcome(text=t.AI_NOT_UNDERSTOOD)
    outcome.heard = heard
    return outcome


def with_choice(call: ToolCall, patch: dict[str, Any]) -> ToolCall:
    """The call to re-run after the user tapped a choice (patch merges into `_fix`)."""
    fix = {**(call.args.get("_fix") or {}), **patch}
    if "item_categories" in patch:  # keep earlier item answers
        fix["item_categories"] = {
            **(call.args.get("_fix") or {}).get("item_categories", {}),
            **patch["item_categories"],
        }
    return ToolCall(call.name, {**call.args, "_fix": fix})


async def run_calls(
    session: AsyncSession, actor: User, calls: list[ToolCall], ctx: Context
) -> list[Outcome]:
    """Run up to MAX_CALLS requests in order. The first unanswered question stops the rest."""
    outcomes: list[Outcome] = []
    current = ctx
    for call in calls[:MAX_CALLS]:
        out = await run_call(session, actor, call, current)
        outcomes.append(out)
        if out.customer_id is not None:
            current = Context(today=ctx.today, last_customer_id=out.customer_id)
        if out.question is not None:
            break
    return outcomes


async def load_hints(session: AsyncSession) -> list[Any]:
    """Category names + synonyms for the system prompt."""
    from bot.ai.prompts import CategoryHint

    codes = await ledger.section_codes(session)
    syn: dict[int, list[str]] = {}
    for cat_id, word in (
        await session.execute(select(CategorySynonym.category_id, CategorySynonym.synonym))
    ).all():
        syn.setdefault(cat_id, []).append(word)
    return [
        CategoryHint(c.name, codes[c.section_id], tuple(syn.get(c.id, [])))
        for c in await ledger.categories(session)
    ]
