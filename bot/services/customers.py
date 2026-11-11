"""Customers: create, update, soft delete / restore, search (BR-040…BR-047).

Telegram-agnostic. Permissions are checked here too (staff/admin for writes, admin for restore).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import AddressForm, Customer, Role, User
from bot.utils.phone import normalize_phone
from bot.utils.translit import search_key

STAFF_ROLES = {Role.STAFF.value, Role.ADMIN.value}
SEARCH_LIMIT = 30
FUZZY_THRESHOLD = 0.3


class CustomerError(Exception):
    pass


class NotAllowedError(CustomerError):
    pass


class PhoneTakenError(CustomerError):
    """Another active customer already has this phone (BR-041)."""

    def __init__(self, customer_id: int) -> None:
        super().__init__(customer_id)
        self.customer_id = customer_id


class CustomerNotFoundError(CustomerError):
    pass


def require_staff(actor: User) -> None:
    if actor.role not in STAFF_ROLES or actor.is_blocked:
        raise NotAllowedError


def require_admin(actor: User) -> None:
    if actor.role != Role.ADMIN.value or actor.is_blocked:
        raise NotAllowedError


def clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


async def _phone_owner(
    session: AsyncSession, phone: str, exclude_id: int | None = None
) -> int | None:
    q = select(Customer.id).where(Customer.phone == phone, Customer.deleted_at.is_(None))
    if exclude_id is not None:
        q = q.where(Customer.id != exclude_id)
    return await session.scalar(q)


async def create(
    session: AsyncSession,
    actor: User,
    *,
    name: str,
    address_form: AddressForm,
    raw_phone: str | None,
    note: str | None = None,
) -> Customer:
    """BR-040/042: phone normalized; phone-less customers allowed (phone_missing)."""
    require_staff(actor)
    phone = normalize_phone(raw_phone) if raw_phone else None
    if phone and (owner := await _phone_owner(session, phone)) is not None:
        raise PhoneTakenError(owner)
    customer = Customer(
        name=clean_name(name),
        search_name=search_key(name),
        phone=phone,
        address_form=address_form.value,
        note=clean_name(note) if note else None,
        created_by=actor.id,
    )
    session.add(customer)
    await session.flush()
    await session.refresh(customer)
    return customer


async def get(
    session: AsyncSession, customer_id: int, *, include_deleted: bool = False
) -> Customer:
    c = await session.get(Customer, customer_id)
    if c is None or (c.deleted_at is not None and not include_deleted):
        raise CustomerNotFoundError(customer_id)
    return c


async def update(
    session: AsyncSession,
    actor: User,
    customer_id: int,
    *,
    name: str | None = None,
    address_form: AddressForm | None = None,
    raw_phone: str | None = None,
    clear_phone: bool = False,
    note: str | None = None,
) -> Customer:
    require_staff(actor)
    c = await get(session, customer_id)
    if name is not None:
        c.name = clean_name(name)
        c.search_name = search_key(name)
    if address_form is not None:
        c.address_form = address_form.value
    if clear_phone:
        c.phone = None
        c.user_id = None  # bot link was through the phone
    elif raw_phone is not None:
        phone = normalize_phone(raw_phone)
        if phone != c.phone:
            if (owner := await _phone_owner(session, phone, exclude_id=c.id)) is not None:
                raise PhoneTakenError(owner)
            c.phone = phone
            c.user_id = None  # new number → old Telegram link no longer proven (security review)
    if note is not None:
        c.note = clean_name(note) or None
    await session.flush()
    return c


async def soft_delete(session: AsyncSession, actor: User, customer_id: int) -> Customer:
    """BR-046 ✅: allowed even with debt (the debt stays in reports, Q-33)."""
    require_staff(actor)
    c = await get(session, customer_id)
    c.deleted_at = datetime.now(UTC)
    c.deleted_by = actor.id
    await session.flush()
    return c


async def restore(session: AsyncSession, actor: User, customer_id: int) -> Customer:
    """Admin only. Refused if the phone now belongs to another active customer."""
    require_admin(actor)
    c = await get(session, customer_id, include_deleted=True)
    if c.deleted_at is None:
        return c
    if c.phone and (owner := await _phone_owner(session, c.phone, exclude_id=c.id)) is not None:
        raise PhoneTakenError(owner)
    c.deleted_at = None
    c.deleted_by = None
    await session.flush()
    return c


async def list_deleted(session: AsyncSession, limit: int = 20) -> list[Customer]:
    rows = await session.scalars(
        select(Customer)
        .where(Customer.deleted_at.is_not(None))
        .order_by(Customer.deleted_at.desc())
        .limit(limit)
    )
    return list(rows.all())


@dataclass(frozen=True, slots=True)
class SearchQuery:
    text: str
    digits: str


def _parse_query(raw: str) -> SearchQuery:
    digits = re.sub(r"\D", "", raw)
    text = search_key(re.sub(r"[\d+()\-]", " ", raw))
    return SearchQuery(text=text, digits=digits)


async def search(session: AsyncSession, raw: str, *, limit: int = SEARCH_LIMIT) -> list[Customer]:
    """BR-044: Cyrillic↔Latin, typos (pg_trgm similarity), phone digits ("45 67").

    Order: exact name > prefix > fuzzy score; ties by most recently created.
    """
    q = _parse_query(raw)
    if not q.text and len(q.digits) < 2:
        return []
    conditions = []
    if q.text:
        conditions += [
            Customer.search_name.contains(q.text),
            func.similarity(Customer.search_name, q.text) >= FUZZY_THRESHOLD,
            func.word_similarity(q.text, Customer.search_name) >= 0.5,
        ]
    if len(q.digits) >= 2:
        conditions.append(Customer.phone.endswith(q.digits))
        if len(q.digits) >= 4:
            conditions.append(Customer.phone.contains(q.digits))
    score = (
        func.greatest(
            func.similarity(Customer.search_name, q.text),
            func.word_similarity(q.text, Customer.search_name),
        )
        if q.text
        else literal(0)
    )
    stmt = (
        select(Customer)
        .where(Customer.deleted_at.is_(None), or_(*conditions))
        .order_by(
            (Customer.search_name == q.text).desc() if q.text else Customer.id.desc(),
            score.desc(),
            Customer.created_at.desc(),
        )
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())
