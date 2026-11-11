"""Ilova sozlamalari — faqat muhit o'zgaruvchilari / .env dan o'qiladi.

Maxfiy qiymatlar `SecretStr` turida: tasodifan log'ga yoki repr'ga chiqsa ham
`**********` bo'lib ko'rinadi. Haqiqiy qiymat faqat `.get_secret_value()` bilan olinadi.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL


class Environment(StrEnum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class AIProviderName(StrEnum):
    GEMINI = "gemini"
    CLAUDE = "claude"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.DEV
    log_level: str = "INFO"
    timezone: str = "Asia/Tashkent"

    # Telegram
    bot_token: SecretStr
    # NoDecode: "123,456" ko'rinishini JSON deb emas, oddiy matn deb o'qish uchun
    admin_telegram_ids: Annotated[list[int], NoDecode] = []

    # PostgreSQL
    postgres_user: str = "nargiza"
    postgres_password: SecretStr
    postgres_db: str = "nargiza"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # AI
    ai_provider: AIProviderName = AIProviderName.GEMINI
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None

    # Feature flaglar
    enable_card_payments: bool = False

    # Backup
    backup_age_recipient: str | None = None
    backup_dir: str = "/backups"

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [int(part) for part in value.replace(" ", "").split(",") if part]
        return value

    @field_validator("bot_token", "postgres_password")
    @classmethod
    def _not_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("bo'sh bo'lmasligi kerak — .env faylini to'ldiring")
        return value

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        # ZoneInfoNotFoundError — KeyError turi; pydantic faqat ValueError'ni
        # validatsiya xatosi deb tushunadi, shuning uchun o'giramiz.
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"noma'lum vaqt zonasi: {value}") from exc
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def database_url(self) -> URL:
        """SQLAlchemy async URL obyekti.

        `URL.create` paroldagi maxsus belgilarni (@ / : %) to'g'ri ekranlaydi,
        `repr`/`str` esa parolni `***` bilan yashiradi — log'ga tushsa ham xavfsiz.
        """
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # majburiy qiymatlar .env / muhitdan keladi
