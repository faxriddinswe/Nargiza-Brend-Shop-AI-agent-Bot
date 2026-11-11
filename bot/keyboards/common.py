"""Klaviaturalar. Matnlar — bot/texts dan."""

from __future__ import annotations

from collections.abc import Iterable

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.db.models import Role
from bot.texts import uz_latn as t


class RegCb(CallbackData, prefix="reg"):
    step: str  # start | form
    value: str = ""


class PendingCb(CallbackData, prefix="pa"):
    key: str
    ok: bool


class AdminCb(CallbackData, prefix="adm"):
    action: str
    staff_id: int = 0


class SectionToggleCb(CallbackData, prefix="sec"):
    code: str  # shop | lingerie | done


def _reply(rows: list[list[str]], placeholder: str | None = None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=x) for x in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=placeholder,
    )


def register_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t.BTN_REGISTER, callback_data=RegCb(step="start").pack())]
        ]
    )


def name_suggestion(first_name: str | None) -> ReplyKeyboardMarkup | None:
    if not first_name:
        return None
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=first_name)]], resize_keyboard=True, one_time_keyboard=True
    )


def address_form() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t.BTN_OPA, callback_data=RegCb(step="form", value="opa").pack()
                ),
                InlineKeyboardButton(
                    text=t.BTN_AKA, callback_data=RegCb(step="form", value="aka").pack()
                ),
            ]
        ]
    )


def share_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t.BTN_SHARE_PHONE, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def customer_menu() -> ReplyKeyboardMarkup:
    return _reply(
        [
            [t.BTN_MY_DEBT, t.BTN_NEWS],
            [t.BTN_ABOUT, t.BTN_CONTACT],
            [t.BTN_SETTINGS],
        ]
    )


def staff_menu(role: Role) -> ReplyKeyboardMarkup:
    rows = [
        [t.BTN_STAFF_DEBT, t.BTN_STAFF_SALE, t.BTN_STAFF_PAYMENT],
        [t.BTN_STAFF_SEARCH, t.BTN_STAFF_REPORT, t.BTN_STAFF_STOCK],
        [t.BTN_STAFF_BROADCAST, t.BTN_STAFF_MORE],
    ]
    # Admin paneli "⚙️ Boshqa" orqali (UX: bir klaviaturada ko'pi bilan 8 tugma)
    return _reply(rows)


def menu_for(role: Role) -> ReplyKeyboardMarkup:
    return customer_menu() if role == Role.CUSTOMER else staff_menu(role)


def customer_settings(ads_opt_out: bool) -> ReplyKeyboardMarkup:
    return _reply([[t.BTN_ADS_ON if ads_opt_out else t.BTN_ADS_OFF], [t.BTN_BACK]])


def confirm(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t.BTN_CONFIRM, callback_data=PendingCb(key=key, ok=True).pack()
                ),
                InlineKeyboardButton(
                    text=t.BTN_CANCEL, callback_data=PendingCb(key=key, ok=False).pack()
                ),
            ]
        ]
    )


def admin_panel() -> InlineKeyboardMarkup:
    def b(text: str, action: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=text, callback_data=AdminCb(action=action).pack())

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [b(t.BTN_ADMIN_STAFF, "staff"), b(t.BTN_ADMIN_ADD_STAFF, "add_staff")],
            [b(t.BTN_ADMIN_STATS, "stats")],
            [b(t.BTN_RECENT, "recent"), b(t.BTN_ADMIN_DELETED, "deleted")],
            [b(t.BTN_ADMIN_SHOP_PHOTO, "photo"), b(t.BTN_ADMIN_SHOP_LOCATION, "location")],
        ]
    )


def staff_actions(staff_id: int, blocked: bool, linked: bool) -> InlineKeyboardMarkup:
    row: list[InlineKeyboardButton] = []
    if linked:
        row.append(
            InlineKeyboardButton(
                text=t.BTN_UNBLOCK if blocked else t.BTN_BLOCK,
                callback_data=AdminCb(
                    action="unblock" if blocked else "block", staff_id=staff_id
                ).pack(),
            )
        )
    row.append(
        InlineKeyboardButton(
            text=t.BTN_REMOVE_STAFF,
            callback_data=AdminCb(action="remove", staff_id=staff_id).pack(),
        )
    )
    return InlineKeyboardMarkup(inline_keyboard=[row])


def section_toggles(selected: Iterable[str]) -> InlineKeyboardMarkup:
    sel = set(selected)
    rows = [
        [
            InlineKeyboardButton(
                text=("☑️ " if code in sel else "▫️ ") + name,
                callback_data=SectionToggleCb(code=code).pack(),
            )
        ]
        for code, name in t.SECTION_NAMES.items()
    ]
    rows.append(
        [InlineKeyboardButton(text=t.BTN_DONE, callback_data=SectionToggleCb(code="done").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
