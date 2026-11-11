"""Foydalanuvchilar, ro'yxatdan o'tish va rollar (BR-010…BR-019, BR-040…BR-047, BR-150…BR-153).

Telegram'ni bilmaydi: handler kontaktni tekshiradi va bu yerga oddiy qiymatlar beradi.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import AddressForm, Customer, Role, StaffProfile, User
from bot.utils.phone import mask_phone, normalize_contact_phone
from bot.utils.translit import search_key

log = structlog.get_logger(__name__)


class ContactNotOwnError(Exception):
    """Kontakt yuboruvchining o'ziniki emas (BR-152)."""


def verify_own_contact(contact_user_id: int | None, sender_telegram_id: int) -> None:
    """BR-152: faqat o'z raqamini ulashish mumkin. `user_id` yo'q bo'lsa ham rad etiladi."""
    if contact_user_id is None or contact_user_id != sender_telegram_id:
        raise ContactNotOwnError


async def get_or_create_user(
    session: AsyncSession, telegram_id: int, first_name: str | None
) -> User:
    """BR-011: botga kirgan har kim avtomatik `customer`. Sessiya aktori: system."""
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(telegram_id=telegram_id, tg_first_name=first_name, role=Role.CUSTOMER)
        session.add(user)
        await session.flush()
        await session.refresh(user)
    elif first_name and user.tg_first_name != first_name:
        user.tg_first_name = first_name
    return user


@dataclass(slots=True)
class RegistrationResult:
    role: Role
    display_name: str  # "Umida opa" / "Nodira opa"
    customer_id: int | None = None
    customer_created: bool = False
    # Raqam boshqa akkauntdan ko'chdi: eski egasi (agar xodim/admin bo'lsa — adminga xabar)
    previous_holder_id: int | None = None
    previous_holder_role: Role | None = None
    # BR-012a: xodim raqami yangi akkauntdan — admin tasdig'i kerak
    staff_relink_profile_id: int | None = None
    # Daftardagi mijoz boshqa akkauntga bog'langan — avtomatik ko'chirilmaydi, admin tasdiqlaydi
    customer_conflict_id: int | None = None
    notes: list[str] = field(default_factory=list)


def display_name(name: str, form: AddressForm | str) -> str:
    return f"{name.strip()} {AddressForm(form).value}"


async def register(
    session: AsyncSession,
    user: User,
    *,
    raw_phone: str,
    name: str,
    address_form: AddressForm,
    admin_phones: Collection[str],
    admin_telegram_ids: Collection[int] = (),
    now: datetime | None = None,
) -> RegistrationResult:
    """Kontakt tasdiqlangandan keyin chaqiriladi (handler `verify_own_contact` qilgan bo'lishi shart).

    1. Raqam boshqa akkauntda bo'lsa — o'sha akkauntdan olinadi (raqam endi shu odamniki,
       Telegram tasdiqlagan). Eski akkaunt xodim/admin bo'lsa — `customer` ga tushiriladi.
    2. Rol: ADMIN_PHONES → admin; faol xodim profili → staff (BR-012, BR-012a); aks holda customer.
    3. Mijoz yozuvi: telefon mos kelsa bog'lanadi, mos kelmasa (customer uchun) yaratiladi (BR-047).
    """
    now = now or datetime.now(UTC)
    phone = normalize_contact_phone(raw_phone)
    result = RegistrationResult(role=Role(user.role), display_name=display_name(name, address_form))

    # 1. Raqamni boshqa akkauntdan olish
    holder = await session.scalar(select(User).where(User.phone == phone, User.id != user.id))
    if holder is not None:
        result.previous_holder_id = holder.id
        result.previous_holder_role = Role(holder.role)
        holder.phone = None
        holder.phone_verified_at = None
        if holder.role != Role.CUSTOMER and holder.telegram_id not in admin_telegram_ids:
            holder.role = Role.CUSTOMER
        await session.flush()  # unique(phone) to'qnashmasligi uchun avval bo'shatamiz
        log.warning("phone_moved_between_accounts", phone=mask_phone(phone))

    user.phone = phone
    user.phone_verified_at = now
    user.consent_at = now

    # 2. Rol
    staff = await session.scalar(
        select(StaffProfile).where(StaffProfile.phone == phone, StaffProfile.deleted_at.is_(None))
    )
    if phone in admin_phones:
        user.role = Role.ADMIN
    elif staff is not None and staff.is_active:
        if staff.user_id is None or staff.user_id == user.id:
            staff.user_id = user.id
            user.role = Role.STAFF
            result.display_name = staff.display_name
        else:
            # BR-012a: profil boshqa akkauntga bog'langan — avtomatik o'tkazilmaydi, admin tasdiqlaydi
            result.staff_relink_profile_id = staff.id
            if user.role != Role.ADMIN:
                user.role = Role.CUSTOMER
    elif user.role == Role.STAFF:
        # Xodim profili o'chirilgan/faol emas — rol ham olinadi
        user.role = Role.CUSTOMER
    result.role = Role(user.role)
    if result.role == Role.ADMIN and staff is not None:
        result.display_name = staff.display_name

    # 3. Mijoz yozuvi
    customer = await session.scalar(
        select(Customer).where(Customer.phone == phone, Customer.deleted_at.is_(None))
    )
    relink_pending = result.staff_relink_profile_id is not None
    if customer is None and result.role == Role.CUSTOMER and not relink_pending:
        # Shu akkauntga avval boshqa raqam bilan bog'langan yozuv bo'lsa — uzamiz
        await _unlink_customers_of_user(session, user.id)
        customer = Customer(
            name=name.strip(),
            search_name=search_key(name),
            phone=phone,
            address_form=address_form.value,
            user_id=user.id,
        )
        session.add(customer)
        await session.flush()
        result.customer_created = True
    elif customer is not None and customer.user_id is None:
        # BR-047: daftardagi mijoz birinchi marta botga ulanmoqda
        await _unlink_customers_of_user(session, user.id)
        customer.user_id = user.id
        await session.flush()
    elif customer is not None and customer.user_id != user.id:
        # Raqam boshqa odamga o'tgan bo'lishi mumkin (operator raqamni qayta sotgan) —
        # qarz ma'lumoti begona odamga ochilmasin: admin tasdiqlaydi.
        result.customer_conflict_id = customer.id
        customer = None
    if customer is not None:
        result.customer_id = customer.id
        if result.role == Role.CUSTOMER:
            # Daftardagi ism va murojaat — xodim yozgani; mijozga shu bilan murojaat qilinadi
            result.display_name = display_name(customer.name, customer.address_form)

    await session.flush()
    return result


async def _unlink_customers_of_user(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(Customer)
        .where(Customer.user_id == user_id, Customer.deleted_at.is_(None))
        .values(user_id=None)
    )


async def move_customer_link(
    session: AsyncSession, actor: User, customer_id: int, new_user_id: int
) -> None:
    """Admin tasdig'i bilan: daftardagi mijoz yozuvini yangi akkauntga bog'lash."""
    if actor.role != Role.ADMIN or actor.is_blocked:
        raise PermissionError
    customer = await session.get(Customer, customer_id)
    new_user = await session.get(User, new_user_id)
    if customer is None or customer.deleted_at is not None or new_user is None:
        raise LookupError
    if new_user.phone != customer.phone:
        raise LookupError  # raqam o'zgargan — eski so'rov endi yaroqsiz
    await _unlink_customers_of_user(session, new_user_id)
    customer.user_id = new_user_id
    await session.flush()


async def customer_of_user(session: AsyncSession, user_id: int) -> Customer | None:
    return await session.scalar(
        select(Customer).where(Customer.user_id == user_id, Customer.deleted_at.is_(None))
    )


async def set_ads_opt_out(session: AsyncSession, user: User, opt_out: bool) -> None:
    user.ads_opt_out = opt_out


async def sync_admins(
    session: AsyncSession, *, admin_phones: Collection[str], admin_telegram_ids: Collection[int]
) -> tuple[list[int], list[int]]:
    """Bot ishga tushganda: `.env` dagi ro'yxat bilan moslash.

    Ro'yxatda yo'q admin → customer (yoki faol xodim profili bo'lsa staff). Ro'yxatdagi → admin.
    Qaytaradi: (ko'tarilganlar, tushirilganlar) — user.id lar.
    """
    promoted: list[int] = []
    demoted: list[int] = []
    users = (
        await session.scalars(
            select(User).where(
                (User.role == Role.ADMIN)
                | User.phone.in_(list(admin_phones))
                | User.telegram_id.in_(list(admin_telegram_ids))
            )
        )
    ).all()
    for u in users:
        should_be_admin = (u.phone in admin_phones) or (u.telegram_id in admin_telegram_ids)
        if should_be_admin and u.role != Role.ADMIN:
            u.role = Role.ADMIN
            promoted.append(u.id)
        elif not should_be_admin and u.role == Role.ADMIN:
            staff = await session.scalar(
                select(StaffProfile).where(
                    StaffProfile.user_id == u.id,
                    StaffProfile.deleted_at.is_(None),
                    StaffProfile.is_active.is_(True),
                )
            )
            u.role = Role.STAFF if staff is not None else Role.CUSTOMER
            demoted.append(u.id)
    await session.flush()
    return promoted, demoted


async def admins(session: AsyncSession) -> list[User]:
    return list(
        (
            await session.scalars(
                select(User).where(User.role == Role.ADMIN, User.is_blocked.is_(False))
            )
        ).all()
    )


async def role_counts(session: AsyncSession) -> dict[str, int]:
    from sqlalchemy import func

    rows = (await session.execute(select(User.role, func.count()).group_by(User.role))).all()
    return {role: count for role, count in rows}


async def customer_chat_id(session: AsyncSession, customer: Customer) -> int | None:
    """Telegram chat of a registered, reachable customer (None = call them instead, BR-165)."""
    if customer.user_id is None:
        return None
    user = await session.get(User, customer.user_id)
    if user is None or user.is_blocked or user.bot_blocked_at is not None:
        return None
    return user.telegram_id


async def mark_bot_blocked(session: AsyncSession, telegram_id: int) -> None:
    """The user blocked the bot (Telegram said Forbidden): stop trying, they go to the call list (BR-165)."""
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is not None and user.bot_blocked_at is None:
        user.bot_blocked_at = datetime.now(UTC)
