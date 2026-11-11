"""Sozlamalar testi: maxfiy qiymatlar yashirin, admin ID'lar to'g'ri o'qiladi."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from bot.config import Settings


def make(**overrides: Any) -> Settings:
    """Soxta qiymatlar bilan Settings; haqiqiy .env o'qilmaydi."""
    base: dict[str, Any] = {
        "bot_token": "123:fake-token",
        "postgres_password": "fake-password",
        "postgres_app_password": "fake-app-password-123",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_admin_ids_parsed_from_comma_string() -> None:
    s = make(admin_telegram_ids="111, 222,333")
    assert s.admin_telegram_ids == [111, 222, 333]


def test_admin_ids_empty_string_is_empty_list() -> None:
    assert make(admin_telegram_ids="").admin_telegram_ids == []


def test_secrets_hidden_in_repr() -> None:
    s = make()
    assert "fake-token" not in repr(s)
    assert "fake-password" not in repr(s)


def test_empty_bot_token_rejected() -> None:
    with pytest.raises(ValidationError):
        make(bot_token="  ")


def test_invalid_timezone_rejected() -> None:
    with pytest.raises(ValidationError):
        make(timezone="Mars/Olympus")


def test_card_payments_disabled_by_default() -> None:
    assert make().enable_card_payments is False


def test_database_url_uses_asyncpg() -> None:
    url = make(postgres_host="localhost").database_url
    assert url.drivername == "postgresql+asyncpg"
    assert (url.host, url.port, url.database) == ("localhost", 5432, "nargiza")


def test_database_url_hides_password_and_escapes_special_chars() -> None:
    url = make(postgres_password="p@ss/w:rd%").database_url
    assert "p@ss" not in str(url)  # str/repr parolni yashiradi
    assert url.password == "p@ss/w:rd%"  # lekin qiymat buzilmagan
    rendered = url.render_as_string(hide_password=False)
    assert "p%40ss%2Fw%3Ard%25" in rendered
