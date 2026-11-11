"""Alembic muhiti (rasmiy async shablon asosida).

DB manzili `.env` dan (bot.config) olinadi — alembic.ini da parol yo'q.
Har bir migratsiya tranzaksiyasida `app.actor_kind = 'migration'` — audit trigger'i
ma'lumot migratsiyalarini ham "migration" deb yozadi.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from bot.db.models import Base

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> object:
    # Testlar URL'ni config.attributes orqali beradi; aks holda .env
    url = config.attributes.get("db_url")
    if url is not None:
        return url
    from bot.config import get_settings

    return get_settings().database_url


def run_migrations_offline() -> None:
    raise SystemExit("Offline (SQL fayl) rejim ishlatilmaydi — `alembic upgrade head` ishlating.")


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        connection.execute(text("SELECT set_config('app.actor_kind', 'migration', true)"))
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(_url(), poolclass=pool.NullPool)  # type: ignore[arg-type]
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:  # testlardan: tayyor ulanish berilgan
        do_run_migrations(connection)
        return
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
