"""Staff flows: find customers, write debts, record payments / write-offs, cancel, delete, restore.

Every write ends in a confirmation card (BR-100); the card is executed by `confirm.py`.
Money amounts are parsed by `utils.money` (strict — ambiguous input is asked again, never guessed),
every calculation happens in `services/` (FIFO, balances), never here.
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, Customer, PaymentKind, Role, User
from bot.db.session import read_session, uow
from bot.keyboards import common as kb_common
from bot.keyboards import ledger as kb
from bot.middlewares.auth import RoleFilter
from bot.services import customers as cust
from bot.services import ledger, pending
from bot.services.allocation import AllocationError, NothingToPayError, OverpaymentError
from bot.texts import uz_latn as t
from bot.utils.dates import due_from_preset, format_date, parse_due_date, today_tashkent
from bot.utils.money import AmountParseError, format_amount, parse_amount
from bot.utils.phone import InvalidPhoneError, normalize_phone

router = Router(name="staff_ledger")
router.message.filter(RoleFilter(Role.STAFF, Role.ADMIN))
router.callback_query.filter(RoleFilter(Role.STAFF, Role.ADMIN))

SM = async_sessionmaker[AsyncSession]
PAGE = 5

MENU_TEXTS = {
    t.BTN_STAFF_DEBT, t.BTN_STAFF_SALE, t.BTN_STAFF_PAYMENT, t.BTN_STAFF_SEARCH,
    t.BTN_STAFF_REPORT, t.BTN_STAFF_STOCK, t.BTN_STAFF_BROADCAST, t.BTN_STAFF_MORE,
}  # fmt: skip
# Text that is a real answer (not a menu button or /command) — used by every text-input state
PLAIN_TEXT = F.text & ~F.text.in_(MENU_TEXTS) & ~F.text.startswith("/")


class Find(StatesGroup):
    query = State()


class NewC(StatesGroup):
    name = State()
    form = State()
    phone = State()
    note = State()


class DebtFlow(StatesGroup):
    category = State()
    qty = State()
    price = State()
    note = State()
    more = State()
    due = State()
    due_date = State()


class PayFlow(StatesGroup):
    section = State()
    amount = State()
    card = State()


def _msg(cb: CallbackQuery) -> Message | None:
    return cb.message if isinstance(cb.message, Message) else None


# ================================================================ menu entry points
async def _start_find(message: Message, state: FSMContext, flow: str, prompt: str) -> None:
    await state.clear()
    await state.set_state(Find.query)
    await state.update_data(flow=flow)
    await message.answer(prompt)


@router.message(F.text == t.BTN_STAFF_DEBT)
async def menu_debt(message: Message, state: FSMContext) -> None:
    await _start_find(message, state, "debt", t.ASK_CUSTOMER_DEBT)


@router.message(F.text == t.BTN_STAFF_PAYMENT)
async def menu_payment(message: Message, state: FSMContext) -> None:
    await _start_find(message, state, "pay", t.ASK_CUSTOMER_PAYMENT)


@router.message(F.text == t.BTN_STAFF_SEARCH)
async def menu_search(message: Message, state: FSMContext) -> None:
    await _start_find(message, state, "find", t.ASK_CUSTOMER_SEARCH)


@router.message(F.text == t.BTN_STAFF_MORE, RoleFilter(Role.STAFF))
async def menu_more_staff(message: Message, state: FSMContext, sm: SM) -> None:
    """Admins get the admin panel on this button (it has the same entry)."""
    await state.clear()
    await _show_recent(message, sm)


# ================================================================ search & pick
@router.message(Find.query, PLAIN_TEXT)
async def got_query(message: Message, state: FSMContext, sm: SM) -> None:
    await state.update_data(query=message.text or "", offset=0)
    await _show_results(message, state, sm, offset=0)


async def _show_results(target: Message, state: FSMContext, sm: SM, offset: int) -> None:
    data = await state.get_data()
    async with read_session(sm) as s:
        found = await cust.search(s, data.get("query", ""), limit=60)
        page = found[offset : offset + PAGE]
        lasts = await ledger.last_debt_date(s, [c.id for c in page])
        sums = {c.id: sum((await ledger.balances(s, c.id)).values()) for c in page}
    if not found:
        await target.answer(
            t.SEARCH_TOO_SHORT if len((data.get("query") or "").strip()) < 2 else t.SEARCH_EMPTY,
            reply_markup=kb.customer_list([], more_offset=None),
        )
        return
    lines = [t.search_header(len(found)), ""]
    for i, c in enumerate(page, start=offset + 1):
        lines.append(
            t.result_line(i, c.name, c.address_form, c.note, c.phone, sums[c.id], lasts.get(c.id))
        )
    rows = [(c.id, f"{i}. {c.name}") for i, c in enumerate(page, start=offset + 1)]
    more = offset + PAGE if len(found) > offset + PAGE else None
    await target.answer("\n".join(lines), reply_markup=kb.customer_list(rows, more_offset=more))


@router.callback_query(kb.CustCb.filter(F.action == "more"))
async def more_results(
    cb: CallbackQuery, callback_data: kb.CustCb, state: FSMContext, sm: SM
) -> None:
    await cb.answer()
    if (msg := _msg(cb)) is not None:
        await state.update_data(offset=callback_data.id)
        await _show_results(msg, state, sm, callback_data.id)


@router.callback_query(kb.CustCb.filter(F.action == "pick"))
async def pick_customer(
    cb: CallbackQuery, callback_data: kb.CustCb, state: FSMContext, sm: SM, user: User
) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    flow = (await state.get_data()).get("flow", "find")
    async with read_session(sm) as s:
        try:
            customer = await cust.get(s, callback_data.id)
        except cust.CustomerNotFoundError:
            await msg.answer(t.CUSTOMER_NOT_FOUND)
            return
    if flow == "debt":
        await _begin_debt(msg, state, sm, customer)
    elif flow == "pay":
        await _begin_pay(msg, state, sm, customer, PaymentKind.PAYMENT)
    else:
        await state.clear()
        await _show_card(msg, sm, customer.id)


async def _show_card(msg: Message, sm: SM, customer_id: int) -> None:
    async with read_session(sm) as s:
        try:
            c = await cust.get(s, customer_id)
        except cust.CustomerNotFoundError:
            await msg.answer(t.CUSTOMER_NOT_FOUND)
            return
        view = await ledger.customer_ledger(s, customer_id)
        codes = await ledger.section_codes(s)
    sections = [
        (
            codes[sl.section_id],
            sl.balance,
            [
                t.debt_line(d.debt_date, d.due_date, d.remaining, t.items_short(items))
                for d, items in sl.open_debts
            ],
        )
        for sl in view
    ]
    await msg.answer(
        t.customer_card(c.name, c.address_form, c.phone, c.note, sections),
        reply_markup=kb.customer_actions(c.id, has_debt=bool(sections)),
    )


@router.callback_query(kb.CustCb.filter(F.action.in_({"debt", "pay", "wo"})))
async def card_action(
    cb: CallbackQuery, callback_data: kb.CustCb, state: FSMContext, sm: SM
) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    async with read_session(sm) as s:
        try:
            customer = await cust.get(s, callback_data.id)
        except cust.CustomerNotFoundError:
            await msg.answer(t.CUSTOMER_NOT_FOUND)
            return
    if callback_data.action == "debt":
        await _begin_debt(msg, state, sm, customer)
    else:
        kind = PaymentKind.PAYMENT if callback_data.action == "pay" else PaymentKind.WRITE_OFF
        await _begin_pay(msg, state, sm, customer, kind)


# ================================================================ new customer
@router.callback_query(kb.CustCb.filter(F.action == "new"))
async def new_customer(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await state.set_state(NewC.name)
    if (msg := _msg(cb)) is not None:
        await msg.answer(t.NEWC_ASK_NAME)


@router.message(NewC.name, PLAIN_TEXT)
async def newc_name(message: Message, state: FSMContext) -> None:
    name = " ".join((message.text or "").split())
    if not 2 <= len(name) <= 40:
        await message.answer(t.NAME_INVALID)
        return
    await state.update_data(name=name)
    await state.set_state(NewC.form)
    await message.answer(t.NEWC_ASK_FORM, reply_markup=kb.address_form())


@router.callback_query(NewC.form, kb.FormCb.filter())
async def newc_form(cb: CallbackQuery, callback_data: kb.FormCb, state: FSMContext) -> None:
    await cb.answer()
    if callback_data.v not in {f.value for f in AddressForm}:
        return
    await state.update_data(form=callback_data.v)
    await state.set_state(NewC.phone)
    if (msg := _msg(cb)) is not None:
        await msg.answer(t.NEWC_ASK_PHONE, reply_markup=kb.no_phone())


@router.message(NewC.phone, PLAIN_TEXT)
async def newc_phone(message: Message, state: FSMContext, sm: SM) -> None:
    try:
        phone = normalize_phone(message.text or "")
    except InvalidPhoneError:
        await message.answer(t.NEWC_BAD_PHONE, reply_markup=kb.no_phone())
        return
    async with read_session(sm) as s:
        existing = await cust.find_by_phone(s, phone)
    if existing is not None:
        await state.clear()
        await message.answer(t.PHONE_TAKEN)
        await _show_card(message, sm, existing.id)
        return
    await state.update_data(phone=phone)
    await state.set_state(NewC.note)
    await message.answer(t.NEWC_ASK_NOTE, reply_markup=kb.skip_note())


@router.callback_query(NewC.phone, kb.StepCb.filter(F.step == "nophone"))
async def newc_nophone(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.update_data(phone=None)
    await state.set_state(NewC.note)
    if (msg := _msg(cb)) is not None:
        await msg.answer(t.NEWC_ASK_NOTE, reply_markup=kb.skip_note())


async def _finish_new_customer(
    msg: Message, state: FSMContext, sm: SM, user: User, note: str | None
) -> None:
    d = await state.get_data()
    payload = {"name": d["name"], "form": d["form"], "phone": d.get("phone"), "note": note}
    async with uow(sm, actor_id=user.id) as s:
        key = await pending.create(s, user_id=user.id, action="create_customer", payload=payload)
    await state.clear()
    await msg.answer(
        t.new_customer_card(d["name"], d["form"], d.get("phone"), note),
        reply_markup=kb_common.confirm(key),
    )


@router.message(NewC.note, PLAIN_TEXT)
async def newc_note(message: Message, state: FSMContext, sm: SM, user: User) -> None:
    await _finish_new_customer(message, state, sm, user, (message.text or "").strip()[:80] or None)


@router.callback_query(NewC.note, kb.StepCb.filter(F.step == "skipcnote"))
async def newc_skip_note(cb: CallbackQuery, state: FSMContext, sm: SM, user: User) -> None:
    await cb.answer()
    if (msg := _msg(cb)) is not None:
        await _finish_new_customer(msg, state, sm, user, None)


# ================================================================ debt flow
async def _begin_debt(msg: Message, state: FSMContext, sm: SM, customer: Customer) -> None:
    await state.clear()
    await state.update_data(customer_id=customer.id, items=[])
    await state.set_state(DebtFlow.category)
    async with read_session(sm) as s:
        cats = await ledger.categories(s)
    await msg.answer(
        t.debt_start(f"{customer.name} {customer.address_form}"),
        reply_markup=kb.categories([(c.id, c.name) for c in cats]),
    )


@router.callback_query(DebtFlow.category, kb.CatCb.filter())
async def debt_category(
    cb: CallbackQuery, callback_data: kb.CatCb, state: FSMContext, sm: SM
) -> None:
    await cb.answer()
    async with read_session(sm) as s:
        if callback_data.id not in {c.id for c in await ledger.categories(s)}:
            return  # forged or deactivated category
    await state.update_data(cur_cat=callback_data.id)
    await state.set_state(DebtFlow.qty)
    if (msg := _msg(cb)) is not None:
        await msg.answer(t.DEBT_ASK_QTY, reply_markup=kb.quantity())


async def _set_qty(msg: Message, state: FSMContext, qty: int) -> None:
    await state.update_data(cur_qty=qty)
    await state.set_state(DebtFlow.price)
    await msg.answer(t.DEBT_ASK_PRICE)


@router.callback_query(DebtFlow.qty, kb.QtyCb.filter())
async def debt_qty_button(cb: CallbackQuery, callback_data: kb.QtyCb, state: FSMContext) -> None:
    await cb.answer()
    if not 1 <= callback_data.n <= 1000:
        return
    if (msg := _msg(cb)) is not None:
        await _set_qty(msg, state, callback_data.n)


@router.message(DebtFlow.qty, PLAIN_TEXT)
async def debt_qty_text(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 1000:
        await message.answer(t.DEBT_BAD_QTY)
        return
    await _set_qty(message, state, int(raw))


@router.message(DebtFlow.price, PLAIN_TEXT)
async def debt_price(message: Message, state: FSMContext) -> None:
    try:
        parsed = parse_amount(message.text or "")
    except AmountParseError:
        await message.answer(t.DEBT_PRICE_UNCLEAR)
        return
    await state.update_data(cur_price=parsed.value)
    await state.set_state(DebtFlow.note)
    if parsed.assumed_thousands:
        await message.answer(t.price_assumed(parsed.value))
    await message.answer(t.DEBT_ASK_NOTE, reply_markup=kb.skip_item_note())


async def _add_item(msg: Message, state: FSMContext, sm: SM, note: str | None) -> None:
    d = await state.get_data()
    items: list[dict[str, Any]] = list(d.get("items", []))
    items.append(
        {
            "category_id": d["cur_cat"],
            "quantity": d["cur_qty"],
            "unit_price": d["cur_price"],
            "note": note,
        }
    )
    await state.update_data(items=items)
    await state.set_state(DebtFlow.more)
    async with read_session(sm) as s:
        names = {c.id: c.name for c in await ledger.categories(s)}
    rows = [(names[i["category_id"]], i["quantity"], i["unit_price"], i["note"]) for i in items]
    total = sum(i["quantity"] * i["unit_price"] for i in items)
    await msg.answer(
        f"{t.items_summary(rows)}\n\nJami: {format_amount(total)}", reply_markup=kb.more_items()
    )


@router.message(DebtFlow.note, PLAIN_TEXT)
async def debt_note(message: Message, state: FSMContext, sm: SM) -> None:
    await _add_item(message, state, sm, (message.text or "").strip()[:80] or None)


@router.callback_query(DebtFlow.note, kb.StepCb.filter(F.step == "skipnote"))
async def debt_skip_note(cb: CallbackQuery, state: FSMContext, sm: SM) -> None:
    await cb.answer()
    if (msg := _msg(cb)) is not None:
        await _add_item(msg, state, sm, None)


@router.callback_query(DebtFlow.more, kb.StepCb.filter())
async def debt_more(cb: CallbackQuery, callback_data: kb.StepCb, state: FSMContext, sm: SM) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    if callback_data.step == "more":
        await state.set_state(DebtFlow.category)
        async with read_session(sm) as s:
            cats = await ledger.categories(s)
        await msg.answer(
            t.DEBT_ASK_CATEGORY, reply_markup=kb.categories([(c.id, c.name) for c in cats])
        )
    elif callback_data.step == "done":
        await state.set_state(DebtFlow.due)
        await msg.answer(t.DEBT_ASK_DUE, reply_markup=kb.due_options())


@router.callback_query(DebtFlow.due, kb.DueCb.filter())
async def debt_due(
    cb: CallbackQuery, callback_data: kb.DueCb, state: FSMContext, sm: SM, user: User
) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    if callback_data.v == "date":
        await state.set_state(DebtFlow.due_date)
        await msg.answer(t.DEBT_ASK_DUE_DATE)
        return
    due = None if callback_data.v == "none" else due_from_preset(callback_data.v, today_tashkent())
    await _finish_debt(msg, state, sm, user, due)


@router.message(DebtFlow.due_date, PLAIN_TEXT)
async def debt_due_text(message: Message, state: FSMContext, sm: SM, user: User) -> None:
    due = parse_due_date(message.text or "", today_tashkent())
    if due is None:
        await message.answer(t.DEBT_BAD_DUE)
        return
    await _finish_debt(message, state, sm, user, due)


async def _finish_debt(msg: Message, state: FSMContext, sm: SM, user: User, due: Any) -> None:
    d = await state.get_data()
    items = [
        ledger.ItemInput(i["category_id"], i["quantity"], i["unit_price"], i["note"])
        for i in d["items"]
    ]
    async with uow(sm, actor_id=user.id) as s:
        customer = await cust.get(s, d["customer_id"])
        cats = {c.id: c for c in await ledger.categories(s)}
        groups = ledger.split_by_section(items, {i: c.section_id for i, c in cats.items()})
        codes = await ledger.section_codes(s)
        current = await ledger.balances(s, customer.id)
        key = await pending.create(
            s,
            user_id=user.id,
            action="create_debts",
            payload={
                "customer_id": customer.id,
                "items": d["items"],
                "due": due.isoformat() if due else None,
            },
        )
    card_groups = []
    after: dict[str, int] = {codes[sid]: bal for sid, bal in current.items()}
    for sid, group in sorted(groups.items()):
        subtotal = sum(i.total for i in group)
        rows = [(cats[i.category_id].name, i.quantity, i.unit_price, i.note) for i in group]
        card_groups.append((codes[sid], rows, subtotal))
        after[codes[sid]] = after.get(codes[sid], 0) + subtotal
    await state.clear()
    await msg.answer(
        t.debt_card(f"{customer.name} {customer.address_form}", card_groups, due, after),
        reply_markup=kb_common.confirm(key),
    )


# ================================================================ payment / write-off flow
async def _begin_pay(
    msg: Message, state: FSMContext, sm: SM, customer: Customer, kind: PaymentKind
) -> None:
    await state.clear()
    async with read_session(sm) as s:
        balances = await ledger.balances(s, customer.id)
        codes = await ledger.section_codes(s)
    if not balances:
        await msg.answer(t.no_debt_for(f"{customer.name} {customer.address_form}"))
        return
    await state.update_data(customer_id=customer.id, kind=kind.value)
    if len(balances) == 1:
        sid = next(iter(balances))
        await state.update_data(section_id=sid)
        await _ask_amount(msg, state, customer, kind, balances[sid])
        return
    await state.set_state(PayFlow.section)
    await msg.answer(
        t.PAY_ASK_SECTION,
        reply_markup=kb.sections(
            [
                (sid, f"{t.SECTION_NAMES[codes[sid]]} — {format_amount(b)}")
                for sid, b in balances.items()
            ]
        ),
    )


async def _ask_amount(
    msg: Message, state: FSMContext, customer: Customer, kind: PaymentKind, owed: int
) -> None:
    await state.set_state(PayFlow.amount)
    head = t.pay_header(f"{customer.name} {customer.address_form}", owed)
    if kind == PaymentKind.PAYMENT:
        await msg.answer(head + t.PAY_ASK_AMOUNT)
    else:
        await msg.answer(head + t.WO_ASK_AMOUNT, reply_markup=kb.writeoff_all(customer.id))


@router.callback_query(PayFlow.section, kb.SecCb.filter())
async def pay_section(
    cb: CallbackQuery, callback_data: kb.SecCb, state: FSMContext, sm: SM
) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    d = await state.get_data()
    async with read_session(sm) as s:
        customer = await cust.get(s, d["customer_id"])
        owed = (await ledger.balances(s, customer.id)).get(callback_data.id, 0)
    if not owed:
        await msg.answer(t.PAY_NO_DEBT)
        await state.clear()
        return
    await state.update_data(section_id=callback_data.id)
    await _ask_amount(msg, state, customer, PaymentKind(d["kind"]), owed)


@router.message(PayFlow.amount, PLAIN_TEXT)
async def pay_amount(message: Message, state: FSMContext, sm: SM, user: User) -> None:
    try:
        parsed = parse_amount(message.text or "")
    except AmountParseError:
        await message.answer(t.PAY_AMOUNT_UNCLEAR)
        return
    await _show_payment_card(message, state, sm, user, parsed.value, debt_id=None, edit=False)


@router.callback_query(PayFlow.amount, kb.CustCb.filter(F.action == "woall"))
async def pay_writeoff_all(cb: CallbackQuery, state: FSMContext, sm: SM, user: User) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    d = await state.get_data()
    async with read_session(sm) as s:
        owed = (await ledger.balances(s, d["customer_id"])).get(d["section_id"], 0)
    if owed:
        await _show_payment_card(msg, state, sm, user, owed, debt_id=None, edit=False)


async def _show_payment_card(
    msg: Message,
    state: FSMContext,
    sm: SM,
    user: User,
    amount: int,
    *,
    debt_id: int | None,
    edit: bool,
) -> None:
    d = await state.get_data()
    kind = PaymentKind(d["kind"])
    try:
        async with uow(sm, actor_id=user.id) as s:
            customer = await cust.get(s, d["customer_id"])
            plan = await ledger.plan_payment(
                s,
                customer_id=d["customer_id"],
                section_id=d["section_id"],
                amount=amount,
                kind=kind,
                debt_id=debt_id,
            )
            customer = await cust.get(s, d["customer_id"])
            debts = {
                v.id: v
                for v in await ledger.debts_with_remaining(
                    s, customer.id, section_id=d["section_id"]
                )
            }
            codes = await ledger.section_codes(s)
            view = await ledger.customer_ledger(s, customer.id)
            if old := d.get("card_key"):
                await pending.cancel(s, old, user_id=user.id)  # one live card at a time
            key = await pending.create(
                s,
                user_id=user.id,
                action="record_payment",
                payload={
                    "customer_id": customer.id,
                    "section_id": d["section_id"],
                    "kind": kind.value,
                    "amount": amount,
                    "debt_id": debt_id,
                    "expected": [[a.debt_id, a.amount] for a in plan.allocations],
                    "owed_before": plan.owed_before,
                },
            )
    except OverpaymentError as e:
        await msg.answer(t.overpay(f"{customer.name} {customer.address_form}", e.owed, e.amount))
        return
    except (NothingToPayError, AllocationError):
        await msg.answer(t.PAY_NO_DEBT)
        await state.clear()
        return
    names = {dv.id: t.items_short(items) for sl in view for dv, items in sl.open_debts}
    lines = [
        (debts[a.debt_id].debt_date, a.amount, names.get(a.debt_id, "qarz"))
        for a in plan.allocations
    ]
    text = t.payment_card(
        f"{customer.name} {customer.address_form}", codes[d["section_id"]], kind.value, amount, lines,
        plan.owed_before, plan.owed_after,
    )  # fmt: skip
    markup = kb.payment_confirm(key, can_pick_debt=len(debts) > 1, picked=debt_id is not None)
    await state.update_data(card_key=key, amount=amount)
    await state.set_state(PayFlow.card)
    if edit:
        await msg.edit_text(text, reply_markup=markup)
    else:
        await msg.answer(text, reply_markup=markup)


@router.callback_query(PayFlow.card, kb_common.AdminCb.filter(F.action == "pickdebt"))
async def pay_pick_debt(cb: CallbackQuery, state: FSMContext, sm: SM, user: User) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    d = await state.get_data()
    async with uow(sm, actor_id=user.id) as s:
        if old := d.get("card_key"):
            await pending.cancel(s, old, user_id=user.id)
        await state.update_data(card_key=None)
        debts = await ledger.debts_with_remaining(s, d["customer_id"], section_id=d["section_id"])
        cats = {}
        view = await ledger.customer_ledger(s, d["customer_id"])
        for sl in view:
            for dv, items in sl.open_debts:
                cats[dv.id] = t.items_short(items)
    rows = [
        (
            v.id,
            f"{format_date(v.debt_date)} · {cats.get(v.id, 'qarz')} · {format_amount(v.remaining)}",
        )
        for v in debts
    ]
    await msg.edit_text(t.PAY_PICK_DEBT, reply_markup=kb.debt_choices(rows))


@router.callback_query(PayFlow.card, kb.DebtPickCb.filter())
async def pay_debt_chosen(
    cb: CallbackQuery, callback_data: kb.DebtPickCb, state: FSMContext, sm: SM, user: User
) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    d = await state.get_data()
    await _show_payment_card(
        msg, state, sm, user, int(d["amount"]), debt_id=callback_data.id or None, edit=True
    )


# ================================================================ cancel recent entries (BR-104)
async def _show_recent(msg: Message, sm: SM) -> None:
    async with read_session(sm) as s:
        entries = await ledger.recent_entries(s, limit=10)
    if not entries:
        await msg.answer(t.RECENT_EMPTY)
        return
    rows = [
        (e.kind, e.id, t.recent_button(e.kind, e.customer_name, e.amount, e.created_at.date()))
        for e in entries
    ]
    await msg.answer(t.RECENT_HEADER, reply_markup=kb.recent(rows))


@router.callback_query(kb_common.AdminCb.filter(F.action == "recent"))
async def recent_from_admin(cb: CallbackQuery, sm: SM) -> None:
    await cb.answer()
    if (msg := _msg(cb)) is not None:
        await _show_recent(msg, sm)


@router.callback_query(kb.RecentCb.filter())
async def recent_chosen(cb: CallbackQuery, callback_data: kb.RecentCb, sm: SM, user: User) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    async with uow(sm, actor_id=user.id) as s:
        entries = {(e.kind, e.id): e for e in await ledger.recent_entries(s, limit=50)}
        e = entries.get((callback_data.kind, callback_data.id))
        if e is None:
            await msg.answer(t.CANCEL_ALREADY)
            return
        key = await pending.create(
            s, user_id=user.id, action="cancel_entry", payload={"kind": e.kind, "id": e.id}
        )
    await msg.answer(
        t.cancel_card(e.kind, e.customer_name, e.amount, e.created_at.date()),
        reply_markup=kb_common.confirm(key),
    )


# ================================================================ delete / restore customers
@router.callback_query(kb.CustCb.filter(F.action == "del"))
async def delete_customer(cb: CallbackQuery, callback_data: kb.CustCb, sm: SM, user: User) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    async with uow(sm, actor_id=user.id) as s:
        try:
            c = await cust.get(s, callback_data.id)
        except cust.CustomerNotFoundError:
            await msg.answer(t.CUSTOMER_NOT_FOUND)
            return
        codes = await ledger.section_codes(s)
        owed = {codes[sid]: b for sid, b in (await ledger.balances(s, c.id)).items()}
        key = await pending.create(
            s, user_id=user.id, action="delete_customer", payload={"id": c.id}
        )
    await msg.answer(t.delete_card(c.name, owed), reply_markup=kb_common.confirm(key))


@router.callback_query(kb_common.AdminCb.filter(F.action == "deleted"), RoleFilter(Role.ADMIN))
async def deleted_list(cb: CallbackQuery, sm: SM) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    async with read_session(sm) as s:
        rows = await cust.list_deleted(s)
    if not rows:
        await msg.answer(t.DELETED_EMPTY)
        return
    await msg.answer(
        t.DELETED_HEADER,
        reply_markup=kb.restore_list([(c.id, f"{c.name} {c.address_form}") for c in rows]),
    )


@router.callback_query(kb.RestoreCb.filter(), RoleFilter(Role.ADMIN))
async def restore_chosen(
    cb: CallbackQuery, callback_data: kb.RestoreCb, sm: SM, user: User
) -> None:
    await cb.answer()
    msg = _msg(cb)
    if msg is None:
        return
    async with uow(sm, actor_id=user.id) as s:
        key = await pending.create(
            s, user_id=user.id, action="restore_customer", payload={"id": callback_data.id}
        )
    await msg.answer(t.restore_card(), reply_markup=kb_common.confirm(key))


# keep state-only handlers from swallowing menu presses: a menu button always resets the flow
@router.message(
    StateFilter("*"),
    F.text.in_({t.BTN_STAFF_REPORT, t.BTN_STAFF_BROADCAST}),
)
async def other_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t.COMING_SOON)
