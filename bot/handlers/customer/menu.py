"""Mijoz menyusi — faqat tugmalar, AI yo'q (BR-018, BR-154, BR-155)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Role, User
from bot.db.session import read_session, uow
from bot.keyboards import common as kb
from bot.middlewares.auth import RegisteredFilter
from bot.services import ledger
from bot.services import settings as settings_svc
from bot.services import users as users_svc
from bot.texts import uz_latn as t
from bot.utils.guards import required

router = Router(name="customer")
router.message.filter(RegisteredFilter())


@router.message(F.text == t.BTN_MY_DEBT)
async def my_debt(message: Message, user: User, sm: async_sessionmaker[AsyncSession]) -> None:
    """BR-018/155: a customer sees only their own record (found by their Telegram link), per section."""
    async with read_session(sm) as s:
        customer = await users_svc.customer_of_user(s, user.id)
        if customer is None:
            # not linked yet (e.g. waiting for the admin to approve a phone that moved)
            await message.answer(t.ACCOUNT_CHECKING)
            return
        view = await ledger.customer_ledger(s, customer.id)
        codes = await ledger.section_codes(s)
    if not view:
        await message.answer(t.NO_DEBT)
        return
    sections = [
        (
            codes[sl.section_id],
            sl.balance,
            [
                t.debt_line(d.debt_date, d.due_date, d.remaining, t.items_short(items))
                for d, items in sl.open_debts
            ],
            [
                t.my_payment_line(paid_on, kind, amount)
                for paid_on, kind, amount in sl.recent_payments
            ],
        )
        for sl in view
    ]
    await message.answer(t.my_debt(sections))


@router.message(F.text == t.BTN_NEWS)
async def news(message: Message) -> None:
    await message.answer(t.NO_NEWS)


@router.message(F.text == t.BTN_ABOUT)
async def about(message: Message, sm: async_sessionmaker[AsyncSession]) -> None:
    async with read_session(sm) as s:
        shop = await settings_svc.shop_info(s)
    if shop.photo_file_id:
        await message.answer_photo(shop.photo_file_id, caption=t.about(shop))
    else:
        await message.answer(t.about(shop))
    if shop.location:
        await message.answer_location(latitude=shop.location["lat"], longitude=shop.location["lon"])


@router.message(F.text == t.BTN_CONTACT)
async def contact(message: Message, sm: async_sessionmaker[AsyncSession]) -> None:
    async with read_session(sm) as s:
        shop = await settings_svc.shop_info(s)
    await message.answer(t.contact_us(shop), disable_web_page_preview=True)


@router.message(F.text == t.BTN_SETTINGS)
async def settings_menu(message: Message, user: User) -> None:
    await message.answer(t.SETTINGS_TITLE, reply_markup=kb.customer_settings(user.ads_opt_out))


@router.message(F.text.in_({t.BTN_ADS_OFF, t.BTN_ADS_ON}))
async def toggle_ads(message: Message, user: User, sm: async_sessionmaker[AsyncSession]) -> None:
    opt_out = message.text == t.BTN_ADS_OFF
    async with uow(sm, actor_id=user.id) as s:
        db_user = required(await s.get(User, user.id), "user")
        await users_svc.set_ads_opt_out(s, db_user, opt_out)
    await message.answer(
        t.ADS_OFF_DONE if opt_out else t.ADS_ON_DONE, reply_markup=kb.customer_settings(opt_out)
    )


@router.message(F.text == t.BTN_BACK)
async def back(message: Message, user: User) -> None:
    role = Role(user.role)
    await message.answer(t.MENU_HINT, reply_markup=kb.menu_for(role))
