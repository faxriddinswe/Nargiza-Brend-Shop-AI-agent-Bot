"""Kirish nuqtasi: `python -m bot.main`.

Ishga tushish tartibi: sozlamalar → log → DB tekshiruvi → adminlarni .env bilan moslash →
router'lar → long polling (qaror: docs/ARCHITECTURE.md).
"""

from __future__ import annotations

import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, ErrorEvent, Message
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncEngine

from bot.ai import build_provider
from bot.config import Settings, get_settings
from bot.db.session import make_engine, make_sessionmaker, uow
from bot.handlers.admin import panel as admin_panel
from bot.handlers.common import fallback, start
from bot.handlers.customer import menu as customer_menu
from bot.handlers.staff import agent as staff_agent
from bot.handlers.staff import broadcast as staff_broadcast
from bot.handlers.staff import confirm as staff_confirm
from bot.handlers.staff import ledger as staff_ledger
from bot.handlers.staff import menu as staff_menu
from bot.handlers.staff import notebook as staff_notebook
from bot.logging_setup import safe_frames, setup_logging
from bot.middlewares.auth import UserMiddleware
from bot.scheduler.jobs import setup_scheduler
from bot.services import users as users_svc
from bot.texts import uz_latn as t

log = structlog.get_logger(__name__)


async def check_database(url: URL) -> None:
    engine = make_engine(url)
    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text("SHOW server_version"))).scalar_one()
        log.info("database_ok", server_version=version)
    finally:
        await engine.dispose()


async def on_error(event: ErrorEvent) -> bool:
    """Kutilmagan xato: log + foydalanuvchiga muloyim xabar. Shaxsiy ma'lumot log'ga yozilmaydi."""
    # Exception *messages* can contain personal data (Postgres DETAIL: Key (phone)=(...)), so we log
    # only the type and the code location, never the message.
    log.error(
        "unhandled_error",
        error_type=type(event.exception).__name__,
        frames=safe_frames(event.exception),
    )
    msg: Message | None = event.update.message or (
        event.update.callback_query.message  # type: ignore[assignment]
        if event.update.callback_query
        else None
    )
    if isinstance(msg, Message):
        try:
            await msg.answer(t.GENERIC_ERROR)
        except Exception:
            log.exception("error_reply_failed")
    return True


def build_dispatcher(settings: Settings, engine: AsyncEngine) -> Dispatcher:
    dp = Dispatcher()
    dp["settings"] = settings
    dp["sm"] = make_sessionmaker(engine)
    dp["ai"] = build_provider(settings)  # None until GEMINI_API_KEY/GEMINI_MODEL are set

    user_mw = UserMiddleware()
    dp.message.outer_middleware(user_mw)
    dp.callback_query.outer_middleware(user_mw)
    dp.errors.register(on_error)

    # Tartib muhim: admin → start (FSM) → xodim → mijoz
    dp.include_routers(
        admin_panel.router,
        staff_confirm.router,
        staff_ledger.router,
        staff_broadcast.router,
        staff_notebook.router,
        staff_agent.router,
        start.router,
        staff_menu.router,
        customer_menu.router,
        fallback.router,
    )
    return dp


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info(
        "starting",
        environment=settings.environment,
        admin_phones=len(settings.admin_phones),
        admin_ids=len(settings.admin_telegram_ids),
        ai_configured=build_provider(settings) is not None,
    )
    await check_database(settings.app_database_url)

    engine = make_engine(settings.app_database_url)
    dp = build_dispatcher(settings, engine)

    async with uow(dp["sm"], actor_kind="system") as s:
        promoted, demoted = await users_svc.sync_admins(
            s, admin_phones=settings.admin_phones, admin_telegram_ids=settings.admin_telegram_ids
        )
    if promoted or demoted:
        log.warning("admins_synced", promoted=len(promoted), demoted=len(demoted))

    bot = Bot(token=settings.bot_token.get_secret_value())
    scheduler = setup_scheduler(bot, dp["sm"], settings)
    scheduler.start()
    try:
        me = await bot.get_me()
        await bot.set_my_commands([BotCommand(command="start", description=t.CMD_START)])
        log.info("bot_ready", username=me.username)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
