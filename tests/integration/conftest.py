"""Integration testlar: haqiqiy PostgreSQL 18 (testcontainers, Docker kerak).

- Sessiya boshida bitta konteyner ko'tariladi va `nb_template` bazasiga migratsiyalar qo'llanadi.
- Har bir test `CREATE DATABASE ... TEMPLATE nb_template` bilan o'zining toza bazasini oladi
  (DELETE trigger'lar bilan taqiqlangani uchun "tozalash" o'rniga yangi baza — tez va ishonchli).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from bot.db.session import make_engine, make_sessionmaker

ROOT = Path(__file__).resolve().parents[2]
PG_IMAGE = "postgres:18.6-alpine"
TEMPLATE_DB = "nb_template"
APP_USER = "nargiza_app"
APP_PASSWORD = "test-only-app-password"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/integration" in str(item.path):
            item.add_marker(pytest.mark.integration)


@dataclass(frozen=True)
class PgServer:
    host: str
    port: int
    user: str
    password: str

    def url(self, database: str) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database,
        )

    async def admin_conn(self) -> asyncpg.Connection:
        return await asyncpg.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database="postgres",
        )


@pytest.fixture(scope="session")
def pg_server() -> Iterator[PgServer]:
    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:  # pragma: no cover
        pytest.skip("testcontainers o'rnatilmagan")

    container = PostgresContainer(
        PG_IMAGE, username="test", password="test-only-password", dbname="postgres", driver=None
    )
    try:
        container.start()
    except Exception as exc:  # Docker yo'q
        pytest.skip(f"Docker mavjud emas: {exc}")
    try:
        server = PgServer(
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(5432)),
            user="test",
            password="test-only-password",
        )
        _create_template(server)
        yield server
    finally:
        container.stop()


def _create_template(server: PgServer) -> None:
    import asyncio

    async def create() -> None:
        conn = await server.admin_conn()
        try:
            await conn.execute(f'CREATE DATABASE "{TEMPLATE_DB}"')
        finally:
            await conn.close()

    asyncio.run(create())

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["db_url"] = server.url(TEMPLATE_DB)
    cfg.attributes["configure_logger"] = False
    cfg.attributes["app_role"] = (APP_USER, APP_PASSWORD)
    command.upgrade(cfg, "head")


@pytest.fixture
async def engine(pg_server: PgServer) -> AsyncIterator[AsyncEngine]:
    name = f"t_{uuid.uuid4().hex[:12]}"
    conn = await pg_server.admin_conn()
    try:
        await conn.execute(f'CREATE DATABASE "{name}" TEMPLATE "{TEMPLATE_DB}"')
    finally:
        await conn.close()

    eng = make_engine(pg_server.url(name))
    try:
        yield eng
    finally:
        await eng.dispose()
        conn = await pg_server.admin_conn()
        try:
            await conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        finally:
            await conn.close()


@pytest.fixture
def sm(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return make_sessionmaker(engine)


@pytest.fixture
async def app_sm(
    engine: AsyncEngine, pg_server: PgServer
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Bot ishlatadigan cheklangan rol bilan ulanish (shu testning bazasiga)."""
    db = engine.url.database
    assert db is not None
    url = URL.create(
        "postgresql+asyncpg",
        username=APP_USER,
        password=APP_PASSWORD,
        host=pg_server.host,
        port=pg_server.port,
        database=db,
    )
    eng = make_engine(url)
    try:
        yield make_sessionmaker(eng)
    finally:
        await eng.dispose()
