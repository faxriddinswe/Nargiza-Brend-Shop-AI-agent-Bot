"""Keyboards and callback data for customers, debts and payments (Stage 2)."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from bot.keyboards.common import AdminCb, PendingCb
from bot.texts import uz_latn as t

__all__ = ["AdminCb", "PendingCb"]


class CustCb(CallbackData, prefix="cu"):
    action: str  # pick | new | more | debt | pay | wo | woall | del
    id: int = 0


class CatCb(CallbackData, prefix="ct"):
    id: int


class QtyCb(CallbackData, prefix="qt"):
    n: int


class StepCb(CallbackData, prefix="st"):
    step: str  # more | done | skipnote | nophone | skipcnote


class DueCb(CallbackData, prefix="du"):
    v: str  # 1w | 2w | 1m | date | none


class SecCb(CallbackData, prefix="se"):
    id: int


class DebtPickCb(CallbackData, prefix="dp"):
    id: int  # 0 = FIFO (oldest first)


class FormCb(CallbackData, prefix="fo"):
    v: str  # opa | aka


class RecentCb(CallbackData, prefix="rc"):
    kind: str  # debt | payment | write_off
    id: int


class AiChoiceCb(CallbackData, prefix="ai"):
    i: int


class RestoreCb(CallbackData, prefix="rs"):
    id: int


def _btn(text: str, data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack())


def customer_list(
    rows: Sequence[tuple[int, str]], *, more_offset: int | None, with_new: bool = True
) -> InlineKeyboardMarkup:
    kb = [[_btn(label, CustCb(action="pick", id=cid))] for cid, label in rows]
    if more_offset is not None:
        kb.append([_btn(t.BTN_MORE_RESULTS, CustCb(action="more", id=more_offset))])
    if with_new:
        kb.append([_btn(t.BTN_NEW_CUSTOMER, CustCb(action="new"))])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def customer_actions(customer_id: int, has_debt: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(t.BTN_C_DEBT, CustCb(action="debt", id=customer_id)),
            _btn(t.BTN_C_PAY, CustCb(action="pay", id=customer_id)),
        ]
    ]
    second = []
    if has_debt:
        second.append(_btn(t.BTN_C_WRITEOFF, CustCb(action="wo", id=customer_id)))
    second.append(_btn(t.BTN_C_DELETE, CustCb(action="del", id=customer_id)))
    rows.append(second)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def address_form() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(t.BTN_OPA, FormCb(v="opa")), _btn(t.BTN_AKA, FormCb(v="aka"))]]
    )


def no_phone() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(t.BTN_NO_PHONE, StepCb(step="nophone"))]])


def skip_note() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(t.BTN_SKIP, StepCb(step="skipcnote"))]])


def categories(rows: Sequence[tuple[int, str]]) -> InlineKeyboardMarkup:
    buttons = [_btn(name.capitalize(), CatCb(id=cid)) for cid, name in rows]
    return InlineKeyboardMarkup(
        inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    )


def quantity() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(str(n), QtyCb(n=n)) for n in range(1, 6)]])


def skip_item_note() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(t.BTN_SKIP, StepCb(step="skipnote"))]])


def more_items() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t.BTN_ADD_ITEM, StepCb(step="more")), _btn(t.BTN_ITEMS_DONE, StepCb(step="done"))]
        ]
    )


def due_options() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(t.BTN_DUE_1W, DueCb(v="1w")),
                _btn(t.BTN_DUE_2W, DueCb(v="2w")),
                _btn(t.BTN_DUE_1M, DueCb(v="1m")),
            ],
            [_btn(t.BTN_DUE_DATE, DueCb(v="date")), _btn(t.BTN_DUE_NONE, DueCb(v="none"))],
        ]
    )


def sections(rows: Sequence[tuple[int, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(label, SecCb(id=sid))] for sid, label in rows]
    )


def writeoff_all(customer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(t.BTN_WO_ALL, CustCb(action="woall", id=customer_id))]]
    )


def payment_confirm(key: str, can_pick_debt: bool, picked: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=t.BTN_CONFIRM, callback_data=PendingCb(key=key, ok=True).pack()
            ),
            InlineKeyboardButton(
                text=t.BTN_CANCEL, callback_data=PendingCb(key=key, ok=False).pack()
            ),
        ]
    ]
    if picked:
        rows.append([_btn(t.BTN_FIFO, DebtPickCb(id=0))])
    elif can_pick_debt:
        rows.append(
            [
                InlineKeyboardButton(
                    text=t.BTN_PICK_DEBT, callback_data=AdminCb(action="pickdebt").pack()
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def debt_choices(rows: Sequence[tuple[int, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(label, DebtPickCb(id=did))] for did, label in rows]
    )


def recent(rows: Sequence[tuple[str, int, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(label, RecentCb(kind=kind, id=rid))] for kind, rid, label in rows]
    )


def restore_list(rows: Sequence[tuple[int, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(label, RestoreCb(id=cid))] for cid, label in rows]
    )


def ai_choices(labels: Sequence[str]) -> InlineKeyboardMarkup:
    """One button per answer the AI offers (customer, section, debt, due date, product type)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(label[:60], AiChoiceCb(i=i))] for i, label in enumerate(labels)]
    )
