"""Scheduled jobs (master §7). Asia/Tashkent. Idempotent: a restart never sends the same report twice.

- 20:00 every day: daily report to staff + admins, sections separate, with the "compare with the till" reminder.
- 09:00 on the 1st: last month's report + the inventory-count reminder.
Reminders to customers, the 08:00 call list and the backup alerts come in later stages.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Protocol

import structlog
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import Settings
from bot.db.models import Role, User
from bot.db.session import read_session, uow
from bot.services import reports
from bot.services import settings as settings_svc
from bot.services import users as users_svc
from bot.texts import uz_latn as t
from bot.utils.dates import TASHKENT, Period, today_tashkent

log = structlog.get_logger(__name__)
SM = async_sessionmaker[AsyncSession]
SEND_PAUSE = 0.05  # Telegram: stay well below ~30 messages per second


class Sender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> object: ...


async def _claim(sm: SM, key: str, token: str) -> bool:
    """True only the first time `token` is seen for `key` (survives restarts)."""
    async with uow(sm, actor_kind="system") as s:
        if await settings_svc.get(s, key) == token:
            return False
        await settings_svc.set_value(s, key, token, actor_id=None)
        return True


async def _release(sm: SM, key: str) -> None:
    async with uow(sm, actor_kind="system") as s:
        await settings_svc.set_value(s, key, "", actor_id=None)


async def _recipients(sm: SM) -> list[int]:
    async with read_session(sm) as s:
        rows = await s.scalars(
            select(User.telegram_id).where(
                User.role.in_([Role.STAFF.value, Role.ADMIN.value]),
                User.is_blocked.is_(False),
                User.bot_blocked_at.is_(None),
            )
        )
        return list(rows.all())


async def _broadcast(bot: Sender, sm: SM, text: str) -> int:
    sent = 0
    for chat_id in await _recipients(sm):
        try:
            await bot.send_message(chat_id, text)
            sent += 1
        except TelegramForbiddenError:
            async with uow(sm, actor_kind="system") as s:
                await users_svc.mark_bot_blocked(s, chat_id)
        except TelegramRetryAfter as e:
            await asyncio.sleep(min(e.retry_after, 30))
            try:
                await bot.send_message(chat_id, text)
                sent += 1
            except Exception as e2:
                log.warning("report_send_failed", error=type(e2).__name__)
        except Exception as e:
            log.warning("report_send_failed", error=type(e).__name__)
        await asyncio.sleep(SEND_PAUSE)
    return sent


async def daily_report(bot: Sender, sm: SM, *, today: date | None = None) -> int:
    day = today or today_tashkent()
    if not await _claim(sm, "report.daily.last_sent", day.isoformat()):
        return 0
    try:
        async with read_session(sm) as s:
            report = await reports.sales_report(s, Period(day, day, "bugun"))
    except Exception:
        await _release(sm, "report.daily.last_sent")
        raise
    text = f"{t.daily_report_title()}\n\n{t.report_text(report, daily_note=True)}"
    sent = await _broadcast(bot, sm, text)
    if sent == 0 and await _recipients(sm):
        await _release(sm, "report.daily.last_sent")  # nobody received it: allow a retry
        log.error("daily_report_not_delivered")
    log.info("daily_report_sent", recipients=sent)
    return sent


async def monthly_report(bot: Sender, sm: SM, *, today: date | None = None) -> int:
    day = today or today_tashkent()
    first = day.replace(day=1)
    if not await _claim(sm, "report.monthly.last_sent", first.isoformat()):
        return 0
    last_month_end = first - timedelta(days=1)
    period = Period(last_month_end.replace(day=1), last_month_end, "o'tgan oy")
    try:
        async with read_session(sm) as s:
            report = await reports.sales_report(s, period)
    except Exception:
        await _release(sm, "report.monthly.last_sent")
        raise
    sent = await _broadcast(
        bot, sm, f"📅 Oylik hisobot\n\n{t.report_text(report)}{t.monthly_report_extra()}"
    )
    if sent == 0 and await _recipients(sm):
        await _release(sm, "report.monthly.last_sent")
        log.error("monthly_report_not_delivered")
    log.info("monthly_report_sent", recipients=sent)
    return sent


def setup_scheduler(bot: Sender, sm: SM, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    common = {
        "coalesce": True,
        "misfire_grace_time": 6 * 3600,
        "max_instances": 1,
        "replace_existing": True,
    }
    scheduler.add_job(
        daily_report, "cron", hour=20, minute=0, id="daily_report", args=[bot, sm], **common
    )
    scheduler.add_job(
        monthly_report,
        "cron",
        day=1,
        hour=9,
        minute=0,
        id="monthly_report",
        args=[bot, sm],
        **common,
    )
    return scheduler


def now_tashkent() -> datetime:
    return datetime.now(TASHKENT)
