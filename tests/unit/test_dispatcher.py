"""Smoke test: every router imports and the dispatcher assembles (catches filter/handler typos)."""

from __future__ import annotations

from bot.config import Settings
from bot.db.session import make_engine
from bot.main import build_dispatcher


def test_dispatcher_builds_with_all_routers() -> None:
    settings = Settings(
        _env_file=None,
        bot_token="123:fake-token",
        postgres_password="fake-password",
        postgres_app_password="fake-app-password-123",
    )
    dp = build_dispatcher(settings, make_engine(settings.app_database_url))
    names = [r.name for r in dp.sub_routers]
    assert names == ["admin", "confirm", "staff_ledger", "start", "staff", "customer", "fallback"]
    # the confirmation handler must live in a router open to staff (not only admin)
    confirm = next(r for r in dp.sub_routers if r.name == "confirm")
    assert confirm.callback_query.handlers
