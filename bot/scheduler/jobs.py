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
from bot.services import integrity, reminders, reports
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


async def send_reminders(bot: Sender, sm: SM, *, today: date | None = None) -> int:
    """10:00: polite debt reminders (BR-161…163). Idempotent through `reminders_log`."""
    day = today or today_tashkent()
    async with read_session(sm) as s:
        due = await reminders.due_reminders(s, day)
    sent = 0
    for r in due:
        try:
            await bot.send_message(r.chat_id, t.reminder_text(r.name, r.form, r.lines))
        except TelegramForbiddenError:
            async with uow(sm, actor_kind="system") as s:
                await users_svc.mark_bot_blocked(s, r.chat_id)  # → call list from now on (BR-165)
            continue
        except Exception as e:
            log.warning("reminder_send_failed", error=type(e).__name__)
            continue
        sent += 1
        try:
            async with uow(sm, actor_kind="system") as s:
                await reminders.mark_sent(s, r)
        except Exception as e:  # the message is out; a failed log must not stop the other customers
            log.error("reminder_log_failed", error=type(e).__name__)
        await asyncio.sleep(SEND_PAUSE)
    log.info("reminders_sent", count=sent)
    return sent


async def morning_call_list(bot: Sender, sm: SM, *, today: date | None = None) -> int:
    """08:00: who to phone today (BR-180). Skipped when there is nothing to do."""
    day = today or today_tashkent()
    if not await _claim(sm, "calllist.last_sent", day.isoformat()):
        return 0
    try:
        async with read_session(sm) as s:
            cl = await reminders.call_list(s, day)
    except Exception:
        await _release(sm, "calllist.last_sent")
        raise
    if cl.empty:
        return 0
    sent = 0
    for chunk in t.split_text(t.call_list_text(cl, day)):
        sent = max(sent, await _broadcast(bot, sm, chunk))
    if sent == 0 and await _recipients(sm):
        await _release(sm, "calllist.last_sent")
    return sent


async def _admin_ids(sm: SM) -> list[int]:
    async with read_session(sm) as s:
        rows = await s.scalars(
            select(User.telegram_id).where(
                User.role == Role.ADMIN.value,
                User.is_blocked.is_(False),
                User.bot_blocked_at.is_(None),
            )
        )
        return list(rows.all())


async def integrity_check(bot: Sender, sm: SM, *, today: date | None = None) -> int:
    """02:00: recompute and look for impossible records (master 9.3). Report goes to admins only."""
    day = today or today_tashkent()
    if not await _claim(sm, "integrity.last_run", day.isoformat()):
        return 0
    try:
        async with read_session(sm) as s:
            rep = await integrity.run_checks(s)
    except Exception:
        await _release(sm, "integrity.last_run")
        raise
    text = t.integrity_text(
        [(p.code, p.count, p.ids) for p in rep.problems], rep.debts, rep.payments
    )
    sent = 0
    for chat_id in await _admin_ids(sm):
        try:
            await bot.send_message(chat_id, text)
            sent += 1
        except Exception as e:
            log.warning("integrity_send_failed", error=type(e).__name__)
        await asyncio.sleep(SEND_PAUSE)
    if not rep.ok:
        log.error("integrity_problems", codes=[p.code for p in rep.problems])
    if sent == 0:
        await _release(sm, "integrity.last_run")  # nobody got it: allow a retry
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
    scheduler.add_job(
        send_reminders, "cron", hour=10, minute=0, id="reminders", args=[bot, sm], **common
    )
    scheduler.add_job(
        morning_call_list, "cron", hour=8, minute=0, id="call_list", args=[bot, sm], **common
    )
    scheduler.add_job(
        integrity_check, "cron", hour=2, minute=0, id="integrity", args=[bot, sm], **common
    )
    return scheduler


def now_tashkent() -> datetime:
    return datetime.now(TASHKENT)
