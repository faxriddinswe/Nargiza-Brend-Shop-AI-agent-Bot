"""/start va ro'yxatdan o'tish (BR-150…BR-153, BR-012, BR-012a, BR-047)."""

from __future__ import annotations

import re

import structlog
from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import Settings
from bot.db.models import AddressForm, Role, StaffProfile, User
from bot.db.session import read_session, uow
from bot.keyboards import common as kb
from bot.services import pending
from bot.services import settings as settings_svc
from bot.services import users as users_svc
from bot.services.users import ContactNotOwnError
from bot.texts import uz_latn as t
from bot.utils.guards import required
from bot.utils.phone import mask_phone

log = structlog.get_logger(__name__)
router = Router(name="start")

NAME_RE = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ '\-ʻʼ’]){1,39}$")


class Reg(StatesGroup):
    name = State()
    address_form = State()
    phone = State()


def menu_text(role: Role) -> str:
    return t.MENU_HINT if role == Role.CUSTOMER else t.STAFF_MENU_HINT


@router.message(CommandStart())
async def on_start(
    message: Message, user: User, state: FSMContext, sm: async_sessionmaker[AsyncSession]
) -> None:
    await state.clear()
    if user.phone is not None:
        await message.answer(menu_text(Role(user.role)), reply_markup=kb.menu_for(Role(user.role)))
        return
    async with read_session(sm) as s:
        shop = await settings_svc.shop_info(s)
    if shop.photo_file_id:
        await message.answer_photo(
            shop.photo_file_id, caption=t.welcome(shop), reply_markup=kb.register_start()
        )
    else:
        await message.answer(t.welcome(shop), reply_markup=kb.register_start())


@router.callback_query(kb.RegCb.filter(F.step == "start"))
async def on_register(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    await cb.answer()
    if user.phone is not None:
        if isinstance(cb.message, Message):
            await cb.message.answer(t.ALREADY_REGISTERED, reply_markup=kb.menu_for(Role(user.role)))
        return
    await state.set_state(Reg.name)
    if isinstance(cb.message, Message):
        await cb.message.answer(
            t.ASK_NAME, reply_markup=kb.name_suggestion(cb.from_user.first_name)
        )


@router.message(Reg.name, F.text)
async def on_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not NAME_RE.match(name):
        await message.answer(t.NAME_INVALID)
        return
    await state.update_data(name=name)
    await state.set_state(Reg.address_form)
    await message.answer(t.ASK_ADDRESS_FORM, reply_markup=ReplyKeyboardRemove())
    await message.answer(t.POINT_DOWN, reply_markup=kb.address_form())


@router.callback_query(Reg.address_form, kb.RegCb.filter(F.step == "form"))
async def on_form(cb: CallbackQuery, callback_data: kb.RegCb, state: FSMContext) -> None:
    await cb.answer()
    await state.update_data(address_form=AddressForm(callback_data.value).value)
    await state.set_state(Reg.phone)
    if isinstance(cb.message, Message):
        await cb.message.answer(t.ASK_PHONE, reply_markup=kb.share_phone())


@router.message(Reg.phone, F.contact)
async def on_contact(
    message: Message,
    user: User,
    state: FSMContext,
    sm: async_sessionmaker[AsyncSession],
    settings: Settings,
    bot: Bot,
) -> None:
    contact = message.contact
    if contact is None or message.from_user is None:
        return
    try:
        users_svc.verify_own_contact(contact.user_id, message.from_user.id)  # BR-152
    except ContactNotOwnError:
        log.warning("foreign_contact_rejected", user_id=user.id)
        await message.answer(t.CONTACT_NOT_OWN, reply_markup=kb.share_phone())
        return

    data = await state.get_data()
    async with uow(sm, actor_id=user.id) as s:
        db_user = required(await s.get(User, user.id), "user")
        result = await users_svc.register(
            s,
            db_user,
            raw_phone=contact.phone_number,
            name=data.get("name") or message.from_user.first_name,
            address_form=AddressForm(data.get("address_form", AddressForm.OPA.value)),
            admin_phones=settings.admin_phones,
        )
        admin_list = await users_svc.admins(s)
        relink_cards: list[tuple[int, str, str]] = []
        if result.staff_relink_profile_id is not None:
            profile = required(await s.get(StaffProfile, result.staff_relink_profile_id), "staff")
            for adm in admin_list:
                key = await pending.create(
                    s,
                    user_id=adm.id,
                    action="relink_staff",
                    payload={
                        "staff_id": profile.id,
                        "new_user_id": db_user.id,
                        "new_tg": db_user.telegram_id,
                    },
                )
                relink_cards.append((adm.telegram_id, key, profile.display_name))
        phone_masked = mask_phone(db_user.phone)
    await state.clear()
    log.info(
        "registered", user_id=user.id, role=result.role, customer_created=result.customer_created
    )

    role = result.role
    if role == Role.ADMIN:
        text = t.registered_admin(result.display_name)
    elif role == Role.STAFF:
        text = t.registered_staff(result.display_name)
    elif result.staff_relink_profile_id is not None:
        text = t.STAFF_RELINK_WAIT
    else:
        text = t.registered_customer(result.display_name)
    await message.answer(text, reply_markup=kb.menu_for(role))

    # Adminlarga xabarlar
    for tg_id, key, staff_name in relink_cards:
        await _safe_send(bot, tg_id, t.relink_request(staff_name, phone_masked), kb.confirm(key))
    if (
        result.previous_holder_role in (Role.STAFF, Role.ADMIN)
        and result.staff_relink_profile_id is None
    ):
        for adm in admin_list:
            await _safe_send(
                bot,
                adm.telegram_id,
                t.phone_moved_alert(str(result.previous_holder_role), phone_masked),
            )


@router.message(Reg.phone)
async def on_phone_text(message: Message) -> None:
    await message.answer(t.PHONE_USE_BUTTON, reply_markup=kb.share_phone())


async def _safe_send(bot: Bot, chat_id: int, text: str, markup: object | None = None) -> None:
    try:
        await bot.send_message(chat_id, text, reply_markup=markup)  # type: ignore[arg-type]
    except Exception:
        log.exception("notify_failed", chat_id=chat_id)
