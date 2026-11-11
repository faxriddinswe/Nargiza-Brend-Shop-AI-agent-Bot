"""Bot ishlatadigan cheklangan DB roli (eng kam huquq): oddiy ish ishlaydi, xavfli amallar yo'q."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, AuditLog, User
from bot.db.session import read_session, uow
from bot.services import users as users_svc

SM = async_sessionmaker[AsyncSession]


async def test_app_role_can_register_and_audit_is_written(app_sm: SM, sm: SM) -> None:
    async with uow(app_sm, actor_kind="system") as s:
        u = await users_svc.get_or_create_user(s, 777, "Umida")
        r = await users_svc.register(
            s,
            u,
            raw_phone="+998900000077",
            name="Umida",
            address_form=AddressForm.OPA,
            admin_phones=set(),
        )
    assert r.customer_created
    async with read_session(sm) as s:
        n = await s.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.table_name == "customers")
        )
    assert n == 1  # audit SECURITY DEFINER orqali yozildi


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER TABLE customers DISABLE TRIGGER ALL",
        "SET session_replication_role = replica",
        "DELETE FROM customers",
        "INSERT INTO audit_log (actor_kind, action, table_name, record_id) VALUES ('system','insert','x','1')",
        "UPDATE audit_log SET action = 'insert'",
        "DROP TABLE customers",
        "CREATE TABLE hack (id int)",
    ],
)
async def test_app_role_cannot_do_dangerous_things(app_sm: SM, sql: str) -> None:
    with pytest.raises(DBAPIError):
        async with uow(app_sm, actor_kind="system") as s:
            await s.execute(text(sql))


async def test_app_role_cannot_pretend_to_be_migration(app_sm: SM) -> None:
    with pytest.raises(DBAPIError, match="migration"):
        async with app_sm() as s, s.begin():
            await s.execute(text("SELECT set_config('app.actor_kind', 'migration', true)"))
            s.add(User(telegram_id=999))
            await s.flush()
