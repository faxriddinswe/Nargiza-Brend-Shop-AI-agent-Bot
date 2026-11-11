"""Kirish nuqtasi: `python -m bot.main`.

0-bosqich: sozlamalarni o'qiydi, bazaga ulanishni tekshiradi va long polling bilan
ishga tushadi. /start ga vaqtinchalik javob beradi. Haqiqiy handlerlar 1-bosqichda.
"""

from __future__ import annotations

import asyncio

import structlog
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import create_async_engine

from bot.config import get_settings
from bot.logging_setup import setup_logging
from bot.texts import uz_latn as t

log = structlog.get_logger(__name__)

router = Router(name="stage0")


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(t.STAGE0_START)


async def check_database(url: URL) -> None:
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text("SHOW server_version"))).scalar_one()
        log.info("database_ok", server_version=version)
    finally:
        await engine.dispose()


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info("starting", environment=settings.environment, admins=len(settings.admin_telegram_ids))

    await check_database(settings.database_url)

    bot = Bot(token=settings.bot_token.get_secret_value())
    dp = Dispatcher()
    dp.include_router(router)

    try:
        # get_me tokenni tekshiradi; xato bo'lsa ham HTTP sessiya finally'da yopiladi.
        me = await bot.get_me()
        log.info("bot_ready", username=me.username)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
