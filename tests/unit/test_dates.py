"""Davrlarni tushunish (BR-002, BR-123). "Bugun" = 2026-11-11 (chorshanba)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from bot.utils.dates import Period, parse_period, today_tashkent

TODAY = date(2026, 11, 11)  # chorshanba


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("bugun", TODAY, TODAY),
        ("kecha", date(2026, 11, 10), date(2026, 11, 10)),
        ("bu hafta", date(2026, 11, 9), TODAY),  # dushanbadan
        ("o'tgan hafta", date(2026, 11, 2), date(2026, 11, 8)),
        ("bu oy", date(2026, 11, 1), TODAY),
        ("o'tgan oy", date(2026, 10, 1), date(2026, 10, 31)),
        ("bu yil", date(2026, 1, 1), TODAY),
        ("o'tgan yil", date(2025, 1, 1), date(2025, 12, 31)),
        ("mart", date(2026, 3, 1), date(2026, 3, 31)),
        ("mart oyi", date(2026, 3, 1), date(2026, 3, 31)),
        ("dekabr", date(2025, 12, 1), date(2025, 12, 31)),  # kelajakdagi oy → o'tgan yil
        ("noyabr", date(2026, 11, 1), date(2026, 11, 30)),
        ("fevral 2024", date(2024, 2, 1), date(2024, 2, 29)),  # kabisa yil
        ("1-15 noyabr", date(2026, 11, 1), date(2026, 11, 15)),
        ("1 dan 15 gacha noyabr", date(2026, 11, 1), date(2026, 11, 15)),
        ("15 noyabr", date(2026, 11, 15), date(2026, 11, 15)),
        ("15-noyabr", date(2026, 11, 15), date(2026, 11, 15)),
        ("Бугун", TODAY, TODAY),  # kirill
        ("ўтган ой", date(2026, 10, 1), date(2026, 10, 31)),
        ("март", date(2026, 3, 1), date(2026, 3, 31)),
        ("mayda", date(2026, 5, 1), date(2026, 5, 31)),
        ("martdagi", date(2026, 3, 1), date(2026, 3, 31)),
    ],
)
def test_parse_period(text: str, start: date, end: date) -> None:
    p = parse_period(text, TODAY)
    assert p is not None, text
    assert (p.start, p.end) == (start, end)


@pytest.mark.parametrize(
    "text", ["ertaga", "salom", "31 fevral", "15-1 noyabr", "qachondir", "mart 0001", "mart 2099"]
)
def test_parse_period_unknown_returns_none(text: str) -> None:
    """Tushunilmagan davr — taxmin qilinmaydi."""
    assert parse_period(text, TODAY) is None


def test_last_month_in_january_is_december_last_year() -> None:
    p = parse_period("o'tgan oy", date(2027, 1, 5))
    assert p is not None and (p.start, p.end) == (date(2026, 12, 1), date(2026, 12, 31))


def test_utc_range_uses_tashkent_midnight() -> None:
    """BR-002: Toshkent kuni 00:00 (UTC+5) → UTC'da oldingi kun 19:00."""
    lo, hi = Period(TODAY, TODAY, "bugun").to_utc_range()
    assert lo == datetime(2026, 11, 10, 19, 0, tzinfo=UTC)
    assert hi == datetime(2026, 11, 11, 19, 0, tzinfo=UTC)


def test_today_tashkent_crosses_midnight_before_utc() -> None:
    """UTC 20:30 da Toshkentda allaqachon ertangi kun."""
    assert today_tashkent(datetime(2026, 11, 11, 20, 30, tzinfo=UTC)) == date(2026, 11, 12)
    assert today_tashkent(datetime(2026, 11, 11, 18, 59, tzinfo=UTC)) == date(2026, 11, 11)


@pytest.mark.parametrize(
    ("today", "text", "start", "end"),
    [
        (date(2026, 3, 31), "o'tgan oy", date(2026, 2, 1), date(2026, 2, 28)),
        (date(2027, 1, 1), "o'tgan hafta", date(2026, 12, 21), date(2026, 12, 27)),
        (date(2027, 1, 1), "bu hafta", date(2026, 12, 28), date(2027, 1, 1)),
    ],
)
def test_month_and_year_boundaries(today: date, text: str, start: date, end: date) -> None:
    p = parse_period(text, today)
    assert p is not None and (p.start, p.end) == (start, end)


# ---------------------------------------------------------------- due dates (BR-052)
from bot.utils.dates import add_months, due_from_preset, parse_due_date  # noqa: E402


@pytest.mark.parametrize(
    ("preset", "expected"),
    [("1w", date(2026, 11, 18)), ("2w", date(2026, 11, 25)), ("1m", date(2026, 12, 11))],
)
def test_due_presets(preset: str, expected: date) -> None:
    assert due_from_preset(preset, TODAY) == expected


def test_add_months_clamps_to_month_end() -> None:
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("25.12", date(2026, 12, 25)),
        ("25.12.2026", date(2026, 12, 25)),
        ("25/12/26", date(2026, 12, 25)),
        ("25-dekabr", date(2026, 12, 25)),
        ("25 dekabr", date(2026, 12, 25)),
        ("5 yanvar", date(2027, 1, 5)),  # o'tgan oy → keyingi yil
        ("11.11", TODAY),  # bugun ham mumkin
        ("10 mart", date(2027, 3, 10)),
    ],
)
def test_parse_due_date(text: str, expected: date) -> None:
    assert parse_due_date(text, TODAY) == expected


@pytest.mark.parametrize("text", ["10.11.2026", "31.02", "ertaga", "salom", "1.1.2030", "45.12"])
def test_parse_due_date_rejects(text: str) -> None:
    assert parse_due_date(text, TODAY) is None


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("25-dekabrgacha", (True, date(2026, 12, 25))),
        ("bir haftaga", (True, date(2026, 11, 18))),
        ("2 haftagacha", (True, date(2026, 11, 25))),
        ("bir oyga", (True, date(2026, 12, 11))),
        ("muddatsiz", (True, None)),
        ("yo'q", (True, None)),
        ("ertaga bir kun", (False, None)),
    ],
)
def test_parse_due_text_with_case_endings(spoken: str, expected: tuple[bool, date | None]) -> None:
    from bot.utils.dates import parse_due_text

    assert parse_due_text(spoken, TODAY) == expected
