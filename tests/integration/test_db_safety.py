"""Ma'lumot xavfsizligi qatlami (master 9.1, BR-105, BR-106): audit, soft delete, cheklovlar."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AuditLog, Category, CategorySynonym, Customer, Section, User
from bot.db.session import read_session, uow

SM = async_sessionmaker[AsyncSession]


async def _make_user(sm: SM, telegram_id: int = 1001) -> int:
    async with uow(sm, actor_kind="system") as s:
        user = User(telegram_id=telegram_id, role="staff")
        s.add(user)
        await s.flush()
        return user.id


async def _make_customer(sm: SM, actor: int, phone: str | None = "+998900000001") -> int:
    async with uow(sm, actor_id=actor) as s:
        c = Customer(name="Umida Test", search_name="umida test", phone=phone, address_form="opa")
        s.add(c)
        await s.flush()
        return c.id


async def test_seed_sections_and_categories(sm: SM) -> None:
    async with read_session(sm) as s:
        codes = set((await s.scalars(select(Section.code))).all())
        assert codes == {"shop", "lingerie"}
        pijama_section = await s.scalar(
            select(Section.code).join(Category).where(Category.name == "pijama")
        )
        assert pijama_section == "shop"  # Q-1 javobi
        lingerie = await s.scalar(
            select(Section.code)
            .join(Category)
            .join(CategorySynonym)
            .where(CategorySynonym.synonym == "lifchik")
        )
        assert lingerie == "lingerie"


async def test_write_without_actor_is_rejected(sm: SM) -> None:
    """Aktorsiz yozuv audit trigger'i tomonidan rad etiladi — audit'siz yozib bo'lmaydi."""
    with pytest.raises(DBAPIError, match="actor_kind"):
        async with read_session(sm) as s:
            s.add(User(telegram_id=5))
            await s.flush()


async def test_insert_is_audited_with_actor(sm: SM) -> None:
    actor = await _make_user(sm)
    cid = await _make_customer(sm, actor)
    async with read_session(sm) as s:
        row = (
            await s.scalars(
                select(AuditLog).where(
                    AuditLog.table_name == "customers", AuditLog.record_id == str(cid)
                )
            )
        ).one()
    assert (row.action, row.actor_id, row.actor_kind) == ("insert", actor, "user")
    assert row.new is not None and row.new["name"] == "Umida Test"
    assert row.old is None


async def test_update_soft_delete_and_restore_are_audited(sm: SM) -> None:
    actor = await _make_user(sm)
    cid = await _make_customer(sm, actor)
    async with uow(sm, actor_id=actor) as s:
        await s.execute(update(Customer).where(Customer.id == cid).values(note="Yunusobodlik"))
    async with uow(sm, actor_id=actor) as s:
        await s.execute(
            update(Customer)
            .where(Customer.id == cid)
            .values(deleted_at=func.now(), deleted_by=actor)
        )
    async with uow(sm, actor_id=actor) as s:
        await s.execute(
            update(Customer).where(Customer.id == cid).values(deleted_at=None, deleted_by=None)
        )
    async with read_session(sm) as s:
        actions = (
            await s.scalars(
                select(AuditLog.action)
                .where(AuditLog.table_name == "customers", AuditLog.record_id == str(cid))
                .order_by(AuditLog.id)
            )
        ).all()
    # bulk update (ORM'siz) ham audit'dan o'tdi
    assert actions == ["insert", "update", "soft_delete", "restore"]


async def test_hard_delete_is_forbidden(sm: SM) -> None:
    """9.1: hech narsa bazadan o'chirilmaydi."""
    actor = await _make_user(sm)
    cid = await _make_customer(sm, actor)
    with pytest.raises(DBAPIError, match="soft delete"):
        async with uow(sm, actor_id=actor) as s:
            await s.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})


async def test_audit_log_is_immutable(sm: SM) -> None:
    actor = await _make_user(sm)
    for sql in (
        "UPDATE audit_log SET action = 'insert'",
        "DELETE FROM audit_log",
        "TRUNCATE audit_log",
    ):
        with pytest.raises(DBAPIError, match="audit_log"):
            async with uow(sm, actor_id=actor) as s:
                await s.execute(text(sql))


async def test_failed_transaction_leaves_nothing(sm: SM) -> None:
    """BR-105: hammasi yoki hech narsa — xato bo'lsa audit ham yozilmaydi."""
    actor = await _make_user(sm)
    async with read_session(sm) as s:
        before = await s.scalar(select(func.count()).select_from(AuditLog))
    with pytest.raises(IntegrityError):
        async with uow(sm, actor_id=actor) as s:
            s.add(Customer(name="A", search_name="a", phone="+998900000009", address_form="opa"))
            await s.flush()
            s.add(Customer(name="B", search_name="b", phone="+998900000009", address_form="opa"))
            await s.flush()  # dublikat telefon
    async with read_session(sm) as s:
        assert await s.scalar(select(func.count()).select_from(Customer)) == 0
        assert await s.scalar(select(func.count()).select_from(AuditLog)) == before


async def test_phone_unique_only_among_active_customers(sm: SM) -> None:
    """BR-041: o'chirilgan mijozning raqami yangisiga berilishi mumkin."""
    actor = await _make_user(sm)
    cid = await _make_customer(sm, actor, phone="+998900000002")
    async with uow(sm, actor_id=actor) as s:
        await s.execute(
            update(Customer)
            .where(Customer.id == cid)
            .values(deleted_at=func.now(), deleted_by=actor)
        )
    await _make_customer(sm, actor, phone="+998900000002")  # xato bermaydi


async def test_phone_missing_is_computed(sm: SM) -> None:
    """BR-042"""
    actor = await _make_user(sm)
    cid = await _make_customer(sm, actor, phone=None)
    async with read_session(sm) as s:
        assert await s.scalar(select(Customer.phone_missing).where(Customer.id == cid)) is True


@pytest.mark.parametrize("bad_phone", ["901234567", "+99890 123", "abc", "+"])
async def test_phone_format_check(sm: SM, bad_phone: str) -> None:
    actor = await _make_user(sm)
    with pytest.raises(IntegrityError, match="phone_format"):
        await _make_customer(sm, actor, phone=bad_phone)


async def test_synonym_belongs_to_one_category_only(sm: SM) -> None:
    """BR-021/030: bitta so'z ikki turga tegishli bo'la olmaydi."""
    async with read_session(sm) as s:
        other = await s.scalar(select(Category.id).where(Category.name == "yubka"))
    with pytest.raises(IntegrityError):
        async with uow(sm, actor_kind="system") as s:
            s.add(CategorySynonym(category_id=other, synonym="tufli"))
            await s.flush()
