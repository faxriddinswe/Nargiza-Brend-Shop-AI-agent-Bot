"""Xodimlarni boshqarish — faqat admin (BR-012, BR-012a, BR-014, BR-015).

Ruxsat bu yerda ham tekshiriladi (`_require_admin`) — handler filtriga yagona tayanch qilinmaydi.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Role, Section, StaffProfile, StaffSectionOwner, User
from bot.utils.phone import normalize_phone


class StaffError(Exception):
    pass


class NotAdminError(StaffError):
    pass


class StaffExistsError(StaffError):
    pass


class StaffNotFoundError(StaffError):
    pass


def _require_admin(actor: User) -> None:
    if actor.role != Role.ADMIN or actor.is_blocked:
        raise NotAdminError


@dataclass(frozen=True, slots=True)
class StaffView:
    id: int
    display_name: str
    phone: str
    user_id: int | None
    telegram_id: int | None
    is_blocked: bool
    section_codes: tuple[str, ...]


async def add_staff(
    session: AsyncSession,
    actor: User,
    *,
    raw_phone: str,
    display_name: str,
    section_codes: Collection[str],
) -> StaffView:
    """Xodim qo'shish. Shu raqamli foydalanuvchi allaqachon botda bo'lsa — darhol xodim bo'ladi."""
    _require_admin(actor)
    phone = normalize_phone(raw_phone)
    exists = await session.scalar(
        select(StaffProfile.id).where(
            StaffProfile.phone == phone, StaffProfile.deleted_at.is_(None)
        )
    )
    if exists is not None:
        raise StaffExistsError(phone)

    profile = StaffProfile(phone=phone, display_name=display_name.strip(), created_by=actor.id)
    session.add(profile)
    await session.flush()
    await _set_sections(session, profile.id, section_codes)

    user = await session.scalar(select(User).where(User.phone == phone))
    if user is not None:
        profile.user_id = user.id
        if user.role == Role.CUSTOMER:
            user.role = Role.STAFF
    await session.flush()
    return await get_staff(session, profile.id)


async def _set_sections(session: AsyncSession, staff_id: int, codes: Collection[str]) -> None:
    await session.execute(delete(StaffSectionOwner).where(StaffSectionOwner.staff_id == staff_id))
    if codes:
        ids = (await session.scalars(select(Section.id).where(Section.code.in_(list(codes))))).all()
        if len(ids) != len(set(codes)):
            raise StaffError(f"noma'lum bo'lim: {codes}")
        session.add_all(StaffSectionOwner(staff_id=staff_id, section_id=sid) for sid in ids)
    await session.flush()


async def remove_staff(session: AsyncSession, actor: User, staff_id: int) -> None:
    """Xodimlikdan olish: profil soft-delete, foydalanuvchi `customer` ga."""
    _require_admin(actor)
    profile = await _profile(session, staff_id)
    profile.is_active = False
    profile.deleted_at = datetime.now(UTC)
    profile.deleted_by = actor.id
    if profile.user_id is not None:
        user = await session.get(User, profile.user_id)
        if user is not None and user.role == Role.STAFF:
            user.role = Role.CUSTOMER
        profile.user_id = None
    await session.flush()


async def set_blocked(session: AsyncSession, actor: User, staff_id: int, blocked: bool) -> None:
    """BR-015: bloklangan xodim keyingi xabaridan boshlab hech narsa qila olmaydi."""
    _require_admin(actor)
    profile = await _profile(session, staff_id)
    if profile.user_id is None:
        raise StaffError("xodim hali botga ulanmagan")
    user = await session.get(User, profile.user_id)
    if user is None:
        raise StaffNotFoundError(staff_id)
    if user.id == actor.id:
        raise StaffError("o'zingizni bloklay olmaysiz")
    user.is_blocked = blocked
    await session.flush()


async def approve_relink(
    session: AsyncSession, actor: User, staff_id: int, new_user_id: int
) -> None:
    """BR-012a: xodim profilini yangi akkauntga o'tkazish (admin tasdig'i bilan)."""
    _require_admin(actor)
    profile = await _profile(session, staff_id)
    new_user = await session.get(User, new_user_id)
    if new_user is None or new_user.phone != profile.phone:
        raise StaffError("raqam endi mos emas")
    if profile.user_id is not None and profile.user_id != new_user_id:
        old = await session.get(User, profile.user_id)
        if old is not None and old.role == Role.STAFF:
            old.role = Role.CUSTOMER
        profile.user_id = None
        await session.flush()
    profile.user_id = new_user_id
    if new_user.role == Role.CUSTOMER:
        new_user.role = Role.STAFF
    await session.flush()


async def _profile(session: AsyncSession, staff_id: int) -> StaffProfile:
    profile = await session.scalar(
        select(StaffProfile).where(StaffProfile.id == staff_id, StaffProfile.deleted_at.is_(None))
    )
    if profile is None:
        raise StaffNotFoundError(staff_id)
    return profile


async def get_staff(session: AsyncSession, staff_id: int) -> StaffView:
    views = await list_staff(session, only_id=staff_id)
    if not views:
        raise StaffNotFoundError(staff_id)
    return views[0]


async def list_staff(session: AsyncSession, *, only_id: int | None = None) -> list[StaffView]:
    q = (
        select(StaffProfile, User)
        .outerjoin(User, User.id == StaffProfile.user_id)
        .where(StaffProfile.deleted_at.is_(None))
        .order_by(StaffProfile.id)
    )
    if only_id is not None:
        q = q.where(StaffProfile.id == only_id)
    rows = (await session.execute(q)).all()
    owners = (
        await session.execute(
            select(StaffSectionOwner.staff_id, Section.code).join(
                Section, Section.id == StaffSectionOwner.section_id
            )
        )
    ).all()
    by_staff: dict[int, list[str]] = {}
    for sid, code in owners:
        by_staff.setdefault(sid, []).append(code)
    return [
        StaffView(
            id=p.id,
            display_name=p.display_name,
            phone=p.phone,
            user_id=p.user_id,
            telegram_id=u.telegram_id if u else None,
            is_blocked=bool(u and u.is_blocked),
            section_codes=tuple(sorted(by_staff.get(p.id, []))),
        )
        for p, u in rows
    ]


async def section_owner_telegram_ids(session: AsyncSession, section_code: str) -> list[int]:
    """BR-026 uchun: bo'lim egalarining Telegram ID'lari (bloklanmagan, faol)."""
    rows = await session.scalars(
        select(User.telegram_id)
        .join(StaffProfile, StaffProfile.user_id == User.id)
        .join(StaffSectionOwner, StaffSectionOwner.staff_id == StaffProfile.id)
        .join(Section, Section.id == StaffSectionOwner.section_id)
        .where(
            Section.code == section_code,
            StaffProfile.deleted_at.is_(None),
            StaffProfile.is_active.is_(True),
            User.is_blocked.is_(False),
        )
    )
    return list(rows.all())
