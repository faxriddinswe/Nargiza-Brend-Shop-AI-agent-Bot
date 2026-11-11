"""Scheduled reports: sent once per day even if the job fires twice (restart), sections separate."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import User
from bot.db.session import uow
from bot.scheduler import jobs

SM = async_sessionmaker[AsyncSession]


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


async def test_daily_report_is_sent_once(sm: SM) -> None:
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=11, role="staff"))
        s.add(User(telegram_id=12, role="admin"))
        s.add(User(telegram_id=13, role="customer"))
    bot = FakeBot()
    day = date(2026, 11, 11)
    assert await jobs.daily_report(bot, sm, today=day) == 2
    assert await jobs.daily_report(bot, sm, today=day) == 0  # restart / double fire
    assert {c for c, _ in bot.sent} == {11, 12}
    assert "Hisobot" in bot.sent[0][1]
    assert await jobs.daily_report(bot, sm, today=date(2026, 11, 12)) == 2  # next day works


async def test_monthly_report_once_per_month(sm: SM) -> None:
    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=21, role="staff"))
    bot = FakeBot()
    assert await jobs.monthly_report(bot, sm, today=date(2026, 12, 1)) == 1
    assert await jobs.monthly_report(bot, sm, today=date(2026, 12, 1)) == 0
    assert "ombor sanog" in bot.sent[0][1]


async def test_failed_delivery_is_retried(sm: SM) -> None:
    class Down:
        async def send_message(self, chat_id: int, text: str) -> None:
            raise RuntimeError("network")

    async with uow(sm, actor_kind="system") as s:
        s.add(User(telegram_id=31, role="staff"))
    day = date(2026, 11, 11)
    assert await jobs.daily_report(Down(), sm, today=day) == 0
    assert await jobs.daily_report(FakeBot(), sm, today=day) == 1  # not lost: claim was released


def test_payments_total_counts_all_rows() -> None:
    from bot.texts import uz_latn as t
    from bot.utils.money import format_amount

    rows = [(date(2026, 11, 11), "A opa", "shop", 10_000, "payment")] * 45
    text = t.payments_list(rows, "bugun")
    assert format_amount(450_000) in text.splitlines()[-1]
