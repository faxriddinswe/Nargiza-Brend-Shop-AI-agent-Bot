"""Turns the model's tool requests into confirmation cards, answers or clarifying questions.

The model only *asks*; this module decides (master §8.4):
- permissions are checked here, in code;
- the customer, the product category, the section and every number are resolved by our own code;
- anything unclear becomes a question with buttons (`Outcome.question` + `choices`) — never a guess;
- every write stops at a confirmation card; nothing is saved here.

It reuses the same services and card builders as the button flows, so both paths follow identical rules.
"""

from __future__ import annotations

import re
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
from bot.services import ledger, reports
from bot.services.allocation import DebtNotOpenError, NothingToPayError, OverpaymentError
from bot.texts import uz_latn as t
from bot.utils.dates import Period, format_date, parse_due_text, parse_period
from bot.utils.money import AmountParseError, format_amount, parse_amount
from bot.utils.phone import InvalidPhoneError, normalize_phone
from bot.utils.translit import search_key

MAX_CALLS = 5
PRONOUNS = {
    "u",
    "unga",
    "uni",
    "uning",
    "undan",
    "shu",
    "shunga",
    "shu odam",
    "osha",
    "osha odam",
    "ushbu",
    "ushbu odam",
    "o'sha",
}
STAFF = {Role.STAFF.value, Role.ADMIN.value}


@dataclass(frozen=True, slots=True)
class Choice:
    label: str
    patch: dict[str, Any]  # merged into the call's trusted `fix` when the user taps it


@dataclass(slots=True)
class Outcome:
    text: str | None = None
    card: cards.Card | None = None  # a confirmation card was created
    question: str | None = None  # needs an answer; shown with `choices` as buttons if any
    choices: list[Choice] = field(default_factory=list)
    resume: ToolCall | None = None  # re-run with the chosen patch
    customer_id: int | None = None  # becomes the conversation's "last customer" (BR-110)
    heard: str | None = None
    document: tuple[str, bytes] | None = None  # (file name, content) to send as a file


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
    if search_key(q) in PRONOUNS:  # "unga", "uning", "shu odam" -> the last discussed customer
        q = ""
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
    # A name is accepted WITHOUT asking only when every spoken word is a whole word of exactly one
    # customer's name (or the digits match the end of exactly one phone). A single fuzzy hit like
    # "Umid" -> "Umida" is confirmed first (a wrong customer = a wrong debt).
    tokens = set(search_key(re.sub(r"[\d+()\-]", " ", q)).split())
    digits = re.sub(r"\D", "", q)
    strong = [
        c
        for c in found
        if (tokens and tokens <= set(c.search_name.split()))
        or (not tokens and len(digits) >= 4 and (c.phone or "").endswith(digits))
    ]
    if len(strong) == 1:
        return strong[0]
    pool = strong if len(strong) > 1 else found
    if len(strong) == 0 and len(found) == 1:
        only = found[0]
        return Outcome(
            question=t.ai_customer_confirm(f"{only.name} {only.address_form}"),
            choices=[
                Choice(t.BTN_YES, {"customer_id": only.id}),
                Choice(t.BTN_NO, {"abort": True}),
            ],
            resume=call,
        )
    choices = []
    for c in pool[:5]:
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
        if len(w) >= 4 and (key.startswith(w) or (len(key) >= 5 and w.startswith(key)))
    }
    if len(hits) == 1:  # "ko'ylakni", "yubkalar", "tufl"
        return refs[hits.pop()]
    if not hits:
        best = (
            process.extractOne(key, list(words), scorer=fuzz.ratio, score_cutoff=82)
            if len(key) >= 5
            else None
        )
        if best:
            return refs[words[best[0]]]
    return None


async def _all_choices_for_item(
    session: AsyncSession, call: ToolCall, idx: int | str, fix: dict[str, Any], item: str
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


async def _resolve_items(
    session: AsyncSession,
    call: ToolCall,
    args_items: list[tools.ItemArg],
    fix: dict[str, Any],
    customer_id: int | None,
) -> tuple[list[ledger.ItemInput], list[tuple[str, int]]] | Outcome:
    """Spoken items → category + price, by our own code. Unknown product / unclear price → an Outcome that asks."""
    mapping = fix.get("item_categories", {})
    by_id = {x.id: x for x in await ledger.categories(session)}
    items: list[ledger.ItemInput] = []
    assumed: list[tuple[str, int]] = []
    for idx, it in enumerate(args_items):
        cat = (
            by_id.get(int(mapping[str(idx)]))
            if str(idx) in mapping
            else await resolve_category(session, it.item)
        )
        if cat is None:
            return await _all_choices_for_item(session, call, idx, fix, it.item)
        try:
            parsed_price = parse_amount(it.unit_price_text)
        except AmountParseError:
            return Outcome(question=t.ai_price_question(it.item), customer_id=customer_id)
        if parsed_price.assumed_thousands:
            assumed.append((it.unit_price_text, parsed_price.value))
        items.append(ledger.ItemInput(cat.id, it.quantity, parsed_price.value, it.note))
    return items, assumed


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
    resolved = await _resolve_items(session, call, args.items, fix, c.id)
    if isinstance(resolved, Outcome):
        return resolved
    items, assumed = resolved
    due_text = fix.get("due_text", args.due_text)
    if due_text is None:
        return _due_question(call, c.id)
    understood, due = parse_due_text(due_text, ctx.today)
    if not understood:
        return Outcome(question=t.ai_due_question(), customer_id=c.id)
    try:
        card = await cards.debt_card(session, actor, c, items, due)
    except ledger.LedgerError:
        return Outcome(text=t.AI_NOT_UNDERSTOOD, customer_id=c.id)
    return Outcome(text=_with_assumed(card.text, assumed), card=card, customer_id=c.id)


def _due_question(call: ToolCall, customer_id: int | None) -> Outcome:
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
        customer_id=customer_id,
    )


async def _add_sale(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.AddSale,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    from bot.services.sale_math import (
        CustomerRequiredError,
        PaidAboveTotalError,
        PriceAboveListError,
        SaleMathError,
    )
    from bot.services.sales import MultiSectionOverrideError

    customer: Customer | None = None
    if args.customer_query or fix.get("customer_id"):
        c = await _customer(session, call, args.customer_query, fix, ctx)
        if isinstance(c, Outcome):
            return c
        customer = c
    cid = customer.id if customer else None
    resolved = await _resolve_items(session, call, args.items, fix, cid)
    if isinstance(resolved, Outcome):
        return resolved
    items, assumed = resolved
    final_total = paid = None
    try:
        if args.total_text:
            parsed = parse_amount(args.total_text)
            final_total = parsed.value
            if parsed.assumed_thousands:
                assumed.append((args.total_text, parsed.value))
        if args.paid_text:
            parsed = parse_amount(args.paid_text)
            paid = parsed.value
            if parsed.assumed_thousands:
                assumed.append((args.paid_text, parsed.value))
    except AmountParseError:
        return Outcome(question=t.ai_amount_question(), customer_id=cid)
    due: date | None = None
    if paid is not None and customer is not None:
        due_text = fix.get("due_text", args.due_text)
        if due_text is None:
            # only ask when part of the price really stays unpaid
            list_total = sum(i.total for i in items)
            if paid < (final_total if final_total is not None else list_total):
                return _due_question(call, cid)
        else:
            understood, due = parse_due_text(due_text, ctx.today)
            if not understood:
                return Outcome(question=t.ai_due_question(), customer_id=cid)
    try:
        card = await cards.sale_card(
            session, actor, customer, items, final_total=final_total, paid=paid, due=due
        )
    except PriceAboveListError:
        return Outcome(text=t.PRICE_ABOVE_LIST, customer_id=cid)
    except PaidAboveTotalError as e:
        return Outcome(
            text=t.overpay(cards.who(customer) if customer else "Mijoz", e.total, e.paid),
            customer_id=cid,
        )
    except CustomerRequiredError:
        return Outcome(question=t.SALE_NEEDS_CUSTOMER)
    except MultiSectionOverrideError:
        return Outcome(text=t.MULTI_SECTION_PRICE, customer_id=cid)
    except SaleMathError:
        return Outcome(text=t.AI_NOT_UNDERSTOOD, customer_id=cid)
    return Outcome(text=_with_assumed(card.text, assumed), card=card, customer_id=cid)


async def _register_return(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.RegisterReturn,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    from bot.services import returns
    from bot.services.sale_math import (
        CustomerRequiredError,
        PaidAboveTotalError,
        PriceAboveListError,
        SaleMathError,
    )
    from bot.services.sales import MultiSectionOverrideError

    customer: Customer | None = None
    if args.customer_query or fix.get("customer_id"):
        c = await _customer(session, call, args.customer_query, fix, ctx)
        if isinstance(c, Outcome):
            return c
        customer = c
    cid = customer.id if customer else None
    # 1. which product came back
    cat_map = fix.get("item_categories", {})
    cat = (
        next(
            (
                x
                for x in await ledger.categories(session)
                if "ret" in cat_map and x.id == int(cat_map["ret"])
            ),
            None,
        )
        if "ret" in cat_map
        else await resolve_category(session, args.item)
    )
    if cat is None:
        return await _all_choices_for_item(session, call, "ret", fix, args.item)
    # 2. which purchase it came from
    src_key = fix.get("source")
    if src_key is None:
        found = await returns.returnable_sources(session, customer_id=cid, category_id=cat.id)
        if not found:
            return Outcome(text=t.RETURN_NOT_FOUND, customer_id=cid)
        if len(found) > 1:
            choices = [
                Choice(
                    t.return_source_label(
                        v.when, v.type, ", ".join(i.name for i in v.items), v.total
                    )[:60],
                    {"source": f"{v.type}:{v.id}"},
                )
                for v in found[:6]
            ]
            return Outcome(
                question=t.RETURN_SOURCE_QUESTION, choices=choices, resume=call, customer_id=cid
            )
        src_key = f"{found[0].type}:{found[0].id}"
    typ, _, raw_id = str(src_key).partition(":")
    try:
        src = await returns.source_view(session, typ, int(raw_id))
    except (returns.ReturnError, ValueError):
        return Outcome(text=t.RETURN_NOT_FOUND, customer_id=cid)
    if cid is not None and src.customer_id != cid:
        return Outcome(
            text=t.RETURN_NOT_FOUND, customer_id=cid
        )  # a button for another customer's purchase
    items = [i for i in src.items if i.category_id == cat.id and i.returnable > 0]
    available = sum(i.returnable for i in items)
    if not items:
        return Outcome(text=t.RETURN_NOT_FOUND, customer_id=cid)
    # 3. how many
    qty = fix.get("quantity", args.quantity)
    if qty is None:
        if available == 1:
            qty = 1
        else:
            return Outcome(
                question=t.RETURN_QTY_QUESTION,
                choices=[
                    Choice(f"{n} ta", {"quantity": n}) for n in range(1, min(available, 6) + 1)
                ],
                resume=call,
                customer_id=cid,
            )
    qty = int(qty)
    if not 1 <= qty <= available:
        return Outcome(text=t.RETURN_NOT_FOUND, customer_id=cid)
    qty_by_item: dict[int, int] = {}
    left = qty
    for i in items:
        take = min(left, i.returnable)
        qty_by_item[i.id] = take
        left -= take
        if not left:
            break
    try:
        plan = await returns.plan_return(session, typ, int(raw_id), qty_by_item)
    except returns.ReturnError:
        return Outcome(text=t.RETURN_NOT_FOUND, customer_id=cid)
    # 4. exchange: the new goods
    new_items: list[ledger.ItemInput] | None = None
    final_total = paid = None
    due: date | None = None
    assumed: list[tuple[str, int]] = []
    if args.new_items:
        resolved = await _resolve_items(session, call, args.new_items, fix, cid)
        if isinstance(resolved, Outcome):
            return resolved
        new_items, assumed = resolved
        try:
            if args.total_text:
                final_total = parse_amount(args.total_text).value
            if args.paid_text:
                paid = parse_amount(args.paid_text).value
        except AmountParseError:
            return Outcome(question=t.ai_amount_question(), customer_id=cid)
        if paid is not None and customer is not None:
            due_text = fix.get("due_text", args.due_text)
            if due_text is None:
                if paid < (
                    final_total if final_total is not None else sum(i.total for i in new_items)
                ):
                    return _due_question(call, cid)
            else:
                understood, due = parse_due_text(due_text, ctx.today)
                if not understood:
                    return Outcome(question=t.ai_due_question(), customer_id=cid)
    try:
        card = await cards.return_card(
            session,
            actor,
            plan,
            exchange_items=new_items,
            final_total=final_total,
            paid=paid,
            due=due,
        )
    except PriceAboveListError:
        return Outcome(text=t.PRICE_ABOVE_LIST, customer_id=cid)
    except PaidAboveTotalError as e:
        return Outcome(
            text=t.overpay(cards.who(customer) if customer else "Mijoz", e.total, e.paid),
            customer_id=cid,
        )
    except CustomerRequiredError:
        return Outcome(question=t.SALE_NEEDS_CUSTOMER)
    except MultiSectionOverrideError:
        return Outcome(text=t.MULTI_SECTION_PRICE, customer_id=cid)
    except SaleMathError:
        return Outcome(text=t.AI_NOT_UNDERSTOOD, customer_id=cid)
    return Outcome(text=_with_assumed(card.text, assumed), card=card, customer_id=cid)


async def _period_or_ask(text: str | None, ctx: Context) -> Period | Outcome:
    period = parse_period(text or "bugun", ctx.today)
    return period if period is not None else Outcome(question=t.AI_PERIOD_QUESTION)


async def _sales_report(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.GetSalesReport,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    period = await _period_or_ask(args.period_text, ctx)
    if isinstance(period, Outcome):
        return period
    report = await reports.sales_report(session, period, section_code=args.section)
    return Outcome(text=t.report_text(report))


async def _compare(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.ComparePeriods,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    if not args.period_a_text.strip() or not args.period_b_text.strip():
        return Outcome(question=t.AI_PERIOD_QUESTION)  # never compare "today with today" by default
    a = await _period_or_ask(args.period_a_text, ctx)
    b = await _period_or_ask(args.period_b_text, ctx)
    if isinstance(a, Outcome) or isinstance(b, Outcome):
        return Outcome(question=t.AI_PERIOD_QUESTION)
    return Outcome(text=t.compare_text(await reports.compare_periods(session, a, b)))


async def _payments(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.ListPayments,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    period = await _period_or_ask(args.period_text, ctx)
    if isinstance(period, Outcome):
        return period
    rows = await reports.payments_in(session, period, section_code=args.section)
    if not rows:
        return Outcome(text=t.NO_PAYMENTS)
    return Outcome(text=t.payments_list(rows, period.label))


async def _export(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.ExportExcel,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    from bot.services import inventory
    from bot.services.excel_export import debtors_workbook, sales_workbook, stock_workbook

    stamp = ctx.today.isoformat()
    if args.kind == "sales":
        period = await _period_or_ask(args.period_text, ctx)
        if isinstance(period, Outcome):
            return period
        data = sales_workbook(await reports.sales_report(session, period))
        return Outcome(
            text=t.EXCEL_CAPTION, document=(f"hisobot_{period.start}_{period.end}.xlsx", data)
        )
    if args.kind == "debtors":
        rows = await ledger.debtors(session)
        phones = {c.id: c.phone for c in (await session.execute(select(Customer))).scalars()}
        data = debtors_workbook(rows, phones, await ledger.section_codes(session))
        return Outcome(text=t.EXCEL_CAPTION, document=(f"qarzdorlar_{stamp}.xlsx", data))
    data = stock_workbook(await inventory.levels(session))
    return Outcome(text=t.EXCEL_CAPTION, document=(f"ombor_{stamp}.xlsx", data))


async def _stock_in(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.AddStockIn,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    mapping = fix.get("item_categories", {})
    cat = (
        next(
            (
                x
                for x in await ledger.categories(session)
                if str(0) in mapping and x.id == int(mapping["0"])
            ),
            None,
        )
        if mapping
        else await resolve_category(session, args.item)
    )
    if cat is None:
        return await _all_choices_for_item(session, call, 0, fix, args.item)
    card = await cards.stock_in_card(session, actor, cat.id, args.quantity)
    return Outcome(text=card.text, card=card)


async def _stock_count(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.StockCount,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    mapping = fix.get("item_categories", {})
    counts: dict[int, int] = {}
    for idx, ci in enumerate(args.counts):
        if str(idx) in mapping:
            cat_id = int(mapping[str(idx)])
        else:
            cat = await resolve_category(session, ci.item)
            if cat is None:
                return await _all_choices_for_item(session, call, idx, fix, ci.item)
            cat_id = cat.id
        counts[cat_id] = ci.counted
    card = await cards.stock_count_card(session, actor, counts)
    return Outcome(text=card.text, card=card)


async def _get_stock(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.GetStock,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    from bot.services import inventory

    only = None
    if args.item:
        cat = await resolve_category(session, args.item)
        if cat is None:
            return Outcome(question=t.ai_item_question(args.item))
        only = [cat.id]
    rows = await inventory.levels(session, only)
    if not rows:
        return Outcome(text=t.STOCK_EMPTY)
    return Outcome(text=t.stock_list([(r.section_code, r.name, r.qty, r.threshold) for r in rows]))


async def _low_stock(
    session: AsyncSession,
    actor: User,
    call: ToolCall,
    args: tools.ListLowStock,
    fix: dict[str, Any],
    ctx: Context,
) -> Outcome:
    from bot.services import inventory

    rows = await inventory.low_stock(session)
    if not rows:
        return Outcome(text=t.NO_LOW_STOCK)
    return Outcome(text=t.low_stock_list([(r.section_code, r.name, r.qty) for r in rows]))


def _with_assumed(text: str, assumed: list[tuple[str, int]]) -> str:
    """BR-076: "350" was read as 350 000 — say so above the card, like the button flow does."""
    if not assumed:
        return text
    return "\n".join(t.ai_assumed_thousands(raw, value) for raw, value in assumed) + "\n\n" + text


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
    debt_remaining: int | None = None
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
        debt_remaining = debt.remaining
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

    want_all = isinstance(args, tools.WriteOff) and args.all and not fix.get("amount_only")
    spoken = None if fix.get("all_only") else args.amount_text
    if want_all and spoken:  # "hammasini" AND an amount: do not guess which one
        return Outcome(
            question=t.ai_all_or_amount(spoken),
            choices=[
                Choice(t.BTN_WO_ALL, {"all_only": True}),
                Choice(f"Faqat {spoken}", {"amount_only": True}),
            ],
            resume=call,
            customer_id=c.id,
        )
    assumed: list[tuple[str, int]] = []
    if want_all:
        amount = debt_remaining if debt_remaining is not None else owed
    else:
        try:
            parsed = parse_amount(spoken or "")
        except AmountParseError:
            return Outcome(question=t.ai_amount_question(), customer_id=c.id)
        amount = parsed.value
        if parsed.assumed_thousands:
            assumed.append((spoken or "", amount))
    try:
        card = await cards.payment_card(
            session, actor, c, section_id=section_id, amount=amount, kind=kind,
            debt_id=int(debt_id) if debt_id is not None else None,
        )  # fmt: skip
    except OverpaymentError as e:
        return Outcome(text=t.overpay(cards.who(c), e.owed, e.amount), customer_id=c.id)
    except (NothingToPayError, DebtNotOpenError):
        return Outcome(text=t.no_debt_for(cards.who(c)), customer_id=c.id)
    return Outcome(text=_with_assumed(card.text, assumed), card=card, customer_id=c.id)


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
    entries = await ledger.recent_entries(session, limit=30, customer_id=customer_id)
    # without a name, "the last record" means MY last record; only if I have none, the latest of anyone
    entry = next((e for e in entries if customer_id is not None or e.created_by == actor.id), None)
    if entry is None and customer_id is None:
        entry = entries[0] if entries else None
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
    fix = call.fix  # trusted: only our own code sets it (never taken from model output)
    if fix.get("abort"):
        return Outcome(text=t.AI_ABORTED)
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
    elif isinstance(args, tools.AddSale):
        outcome = await _add_sale(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.RegisterReturn):
        outcome = await _register_return(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.GetSalesReport):
        outcome = await _sales_report(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.ComparePeriods):
        outcome = await _compare(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.ListPayments):
        outcome = await _payments(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.ExportExcel):
        outcome = await _export(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.AddStockIn):
        outcome = await _stock_in(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.StockCount):
        outcome = await _stock_count(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.GetStock):
        outcome = await _get_stock(session, actor, call, args, fix, ctx)
    elif isinstance(args, tools.ListLowStock):
        outcome = await _low_stock(session, actor, call, args, fix, ctx)
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
    """The call to re-run after the user tapped a choice (the patch merges into the trusted `fix`)."""
    fix = {**call.fix, **patch}
    if "item_categories" in patch:  # keep earlier item answers
        fix["item_categories"] = {**call.fix.get("item_categories", {}), **patch["item_categories"]}
    return ToolCall(call.name, call.args, fix)


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
        if out.question is not None or (out.card is not None and "create_customer" in call.name):
            break  # the rest must wait for the answer / for the new customer to be confirmed
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
