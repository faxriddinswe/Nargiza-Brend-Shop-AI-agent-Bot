"""Admin paneli (BR-012, BR-012a, BR-014, BR-015, BR-016a, BR-100).

Router filtri faqat adminni o'tkazadi; service'lar ham `_require_admin` bilan qayta tekshiradi.
"""

from __future__ import annotations

from typing import Any

import structlog
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Customer, Role, User
from bot.db.session import read_session, uow
from bot.keyboards import common as kb
from bot.middlewares.auth import RoleFilter
from bot.services import pending
from bot.services import settings as settings_svc
from bot.services import staff as staff_svc
from bot.services import users as users_svc
from bot.texts import uz_latn as t
from bot.utils.guards import required
from bot.utils.phone import InvalidPhoneError, format_phone, normalize_phone

log = structlog.get_logger(__name__)
router = Router(name="admin")
router.message.filter(RoleFilter(Role.ADMIN))
router.callback_query.filter(RoleFilter(Role.ADMIN))

SM = async_sessionmaker[AsyncSession]


class AddStaff(StatesGroup):
    phone = State()
    name = State()
    sections = State()


class ShopMedia(StatesGroup):
    photo = State()
    location = State()


# ------------------------------------------------------------------ panel
@router.message(Command("admin"))
@router.message(F.text == t.BTN_STAFF_MORE)  # adminda "⚙️ Boshqa" → admin paneli
async def panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t.ADMIN_PANEL, reply_markup=kb.admin_panel())


@router.callback_query(kb.AdminCb.filter(F.action == "stats"))
async def stats(cb: CallbackQuery, sm: SM) -> None:
    await cb.answer()
    async with read_session(sm) as s:
        counts = await users_svc.role_counts(s)
        active = Customer.deleted_at.is_(None)
        total = await s.scalar(select(func.count()).select_from(Customer).where(active)) or 0
        linked = (
            await s.scalar(
                select(func.count())
                .select_from(Customer)
                .where(active, Customer.user_id.is_not(None))
            )
            or 0
        )
    if isinstance(cb.message, Message):
        await cb.message.answer(t.stats(counts, total, linked))


# ------------------------------------------------------------------ xodimlar ro'yxati
@router.callback_query(kb.AdminCb.filter(F.action == "staff"))
async def staff_list(cb: CallbackQuery, sm: SM) -> None:
    await cb.answer()
    if not isinstance(cb.message, Message):
        return
    async with read_session(sm) as s:
        views = await staff_svc.list_staff(s)
    if not views:
        await cb.message.answer(t.NO_STAFF)
        return
    for v in views:
        await cb.message.answer(
            t.staff_line(
                v.display_name,
                format_phone(v.phone),
                list(v.section_codes),
                v.user_id is not None,
                v.is_blocked,
            ),
            reply_markup=kb.staff_actions(v.id, v.is_blocked, v.user_id is not None),
        )


# ------------------------------------------------------------------ xodim qo'shish (FSM → karta)
@router.callback_query(kb.AdminCb.filter(F.action == "add_staff"))
async def add_staff_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(AddStaff.phone)
    if isinstance(cb.message, Message):
        await cb.message.answer(t.ADD_STAFF_ASK_PHONE)


@router.message(AddStaff.phone, F.text)
async def add_staff_phone(message: Message, state: FSMContext) -> None:
    try:
        phone = normalize_phone(message.text or "")
    except InvalidPhoneError:
        await message.answer(t.ADD_STAFF_BAD_PHONE)
        return
    await state.update_data(phone=phone)
    await state.set_state(AddStaff.name)
    await message.answer(t.ADD_STAFF_ASK_NAME)


@router.message(AddStaff.name, F.text)
async def add_staff_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not 2 <= len(name) <= 40:
        await message.answer(t.ADD_STAFF_ASK_NAME)
        return
    await state.update_data(name=name, sections=[])
    await state.set_state(AddStaff.sections)
    await message.answer(t.ADD_STAFF_ASK_SECTIONS, reply_markup=kb.section_toggles([]))


@router.callback_query(AddStaff.sections, kb.SectionToggleCb.filter())
async def add_staff_sections(
    cb: CallbackQuery, callback_data: kb.SectionToggleCb, state: FSMContext, user: User, sm: SM
) -> None:
    await cb.answer()
    data = await state.get_data()
    selected: list[str] = list(data.get("sections", []))
    if not isinstance(cb.message, Message):
        return
    if callback_data.code != "done":
        if callback_data.code in selected:
            selected.remove(callback_data.code)
        elif callback_data.code in t.SECTION_NAMES:
            selected.append(callback_data.code)
        await state.update_data(sections=selected)
        await cb.message.edit_reply_markup(reply_markup=kb.section_toggles(selected))
        return

    payload = {"phone": data["phone"], "name": data["name"], "sections": selected}
    async with uow(sm, actor_id=user.id) as s:
        key = await pending.create(s, user_id=user.id, action="add_staff", payload=payload)
    await state.clear()
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(
        t.staff_card(data["name"], format_phone(data["phone"]), selected),
        reply_markup=kb.confirm(key),
    )


# ------------------------------------------------------------------ bloklash / olish → karta
@router.callback_query(kb.AdminCb.filter(F.action.in_({"block", "unblock", "remove"})))
async def staff_action(cb: CallbackQuery, callback_data: kb.AdminCb, user: User, sm: SM) -> None:
    await cb.answer()
    if not isinstance(cb.message, Message):
        return
    action = {"block": "block_staff", "unblock": "unblock_staff", "remove": "remove_staff"}[
        callback_data.action
    ]
    async with uow(sm, actor_id=user.id) as s:
        view = await staff_svc.get_staff(s, callback_data.staff_id)
        key = await pending.create(s, user_id=user.id, action=action, payload={"staff_id": view.id})
    await cb.message.answer(
        t.confirm_staff_action(action, view.display_name), reply_markup=kb.confirm(key)
    )


# ------------------------------------------------------------------ kartani tasdiqlash (idempotent)
@router.callback_query(kb.PendingCb.filter())
async def on_pending(
    cb: CallbackQuery, callback_data: kb.PendingCb, user: User, sm: SM, bot: Bot
) -> None:
    msg = cb.message if isinstance(cb.message, Message) else None
    if not callback_data.ok:
        async with uow(sm, actor_id=user.id) as s:
            await pending.cancel(s, callback_data.key, user_id=user.id)
        await cb.answer()
        if msg:
            await msg.edit_text(t.CANCELLED)
        return

    notify: list[tuple[int, str]] = []
    try:
        async with uow(sm, actor_id=user.id) as s:
            actor = required(await s.get(User, user.id), "user")
            pa = await pending.claim(s, callback_data.key, user_id=user.id)
            if isinstance(pa, pending.AlreadyDone):
                await cb.answer(t.CARD_ALREADY_DONE)
                return
            text, notify = await _execute(s, actor, pa.action, pa.payload)
            pending.complete(pa, {"text": text})
    except pending.PendingExpiredError:
        await cb.answer(t.CARD_EXPIRED, show_alert=True)
        return
    except pending.PendingForbiddenError:
        await cb.answer(t.CARD_NOT_YOURS, show_alert=True)
        return
    except pending.PendingError:
        await cb.answer(t.CANCELLED)
        return
    except staff_svc.StaffExistsError:
        await cb.answer(t.STAFF_EXISTS, show_alert=True)
        return
    except staff_svc.StaffError:
        log.exception("staff_action_failed")
        await cb.answer(t.STAFF_NOT_LINKED, show_alert=True)
        return
    await cb.answer()
    if msg:
        await msg.edit_text(text)
    for chat_id, note in notify:
        try:
            await bot.send_message(chat_id, note)
        except Exception:
            log.exception("notify_failed")


async def _execute(
    s: AsyncSession, actor: User, action: str, payload: dict[str, Any]
) -> tuple[str, list[tuple[int, str]]]:
    """Tasdiqlangan admin amalini bajaradi. Qaytaradi: (javob matni, [(chat_id, xabar)])."""
    if action == "add_staff":
        view = await staff_svc.add_staff(
            s,
            actor,
            raw_phone=payload["phone"],
            display_name=payload["name"],
            section_codes=payload["sections"],
        )
        return t.staff_added(view.display_name, view.user_id is not None), []
    if action in {"block_staff", "unblock_staff"}:
        await staff_svc.set_blocked(s, actor, int(payload["staff_id"]), action == "block_staff")
        return (t.STAFF_BLOCKED if action == "block_staff" else t.STAFF_UNBLOCKED), []
    if action == "remove_staff":
        await staff_svc.remove_staff(s, actor, int(payload["staff_id"]))
        return t.STAFF_REMOVED, []
    if action == "relink_staff":
        staff_id, new_user_id = int(payload["staff_id"]), int(payload["new_user_id"])
        await staff_svc.approve_relink(s, actor, staff_id, new_user_id)
        view = await staff_svc.get_staff(s, staff_id)
        return t.RELINK_APPROVED, [
            (int(payload["new_tg"]), t.relink_approved_for_staff(view.display_name))
        ]
    if action == "move_customer":
        try:
            await users_svc.move_customer_link(
                s, actor, int(payload["customer_id"]), int(payload["new_user_id"])
            )
        except (PermissionError, LookupError) as exc:
            raise staff_svc.StaffError("mijoz ko'chirilmadi") from exc
        return t.CUSTOMER_MOVED, []
    raise pending.PendingNotFoundError(action)


# ------------------------------------------------------------------ do'kon rasmi va lokatsiyasi
@router.callback_query(kb.AdminCb.filter(F.action == "photo"))
async def ask_photo(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ShopMedia.photo)
    if isinstance(cb.message, Message):
        await cb.message.answer(t.ASK_SHOP_PHOTO)


@router.message(ShopMedia.photo, F.photo)
async def save_photo(message: Message, state: FSMContext, user: User, sm: SM) -> None:
    if not message.photo:
        return
    async with uow(sm, actor_id=user.id) as s:
        await settings_svc.set_value(
            s, "shop.photo_file_id", message.photo[-1].file_id, actor_id=user.id
        )
    await state.clear()
    await message.answer(t.SHOP_PHOTO_SAVED)


@router.callback_query(kb.AdminCb.filter(F.action == "location"))
async def ask_location(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ShopMedia.location)
    if isinstance(cb.message, Message):
        await cb.message.answer(t.ASK_SHOP_LOCATION)


@router.message(ShopMedia.location, F.location)
async def save_location(message: Message, state: FSMContext, user: User, sm: SM) -> None:
    if message.location is None:
        return
    loc = {"lat": message.location.latitude, "lon": message.location.longitude}
    async with uow(sm, actor_id=user.id) as s:
        await settings_svc.set_value(s, "shop.location", loc, actor_id=user.id)
    await state.clear()
    await message.answer(t.SHOP_LOCATION_SAVED)
