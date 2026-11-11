"""Davrlarni tushunish: "bugun", "o'tgan oy", "mart", "1-15 noyabr" → sana oralig'i (BR-002, BR-123).

Qoidalar:
- Barcha davrlar `Asia/Tashkent` kunlari bo'yicha; DB so'rovi uchun `to_utc_range()` [start, end) beradi.
- Hafta dushanbadan boshlanadi.
- Yilsiz oy nomi ("mart") — eng yaqin o'tgan (yoki joriy) shu oy. Kelajakdagi oy o'tgan yilniki.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from bot.utils.translit import search_key

TASHKENT = ZoneInfo("Asia/Tashkent")

MONTHS: dict[str, int] = {
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5, "iyun": 6,
    "iyul": 7, "avgust": 8, "sentabr": 9, "sentyabr": 9, "oktabr": 10,
    "oktyabr": 10, "noyabr": 11, "dekabr": 12,
}  # fmt: skip
MONTH_NAMES_UZ = (
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class Period:
    start: date  # shu kun kiradi
    end: date  # shu kun ham kiradi
    label: str

    def to_utc_range(self, tz: ZoneInfo = TASHKENT) -> tuple[datetime, datetime]:
        """DB uchun yarim ochiq oraliq [start 00:00, end+1 00:00) — UTC'da."""
        lo = datetime.combine(self.start, time.min, tz).astimezone(UTC)
        hi = datetime.combine(self.end + timedelta(days=1), time.min, tz).astimezone(UTC)
        return lo, hi


def today_tashkent(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(TASHKENT).date()


def _month_end(year: int, month: int) -> date:
    first_next = date(year + (month == 12), month % 12 + 1, 1)
    return first_next - timedelta(days=1)


def _month_period(year: int, month: int) -> Period:
    return Period(
        date(year, month, 1), _month_end(year, month), f"{year}-yil {MONTH_NAMES_UZ[month - 1]}"
    )


class _BadYearError(ValueError):
    pass


def _resolve_month_year(month: int, today: date, explicit_year: int | None) -> int:
    if explicit_year is not None:
        # Bot 2026 da ishga tushdi; juda eski yoki kelajakdagi yil — xato aytilgan
        if not 2020 <= explicit_year <= today.year:
            raise _BadYearError(explicit_year)
        return explicit_year
    return today.year if month <= today.month else today.year - 1


_RANGE_RE = re.compile(
    r"^(\d{1,2})\s*(?:-|dan|gacha|\s)\s*(\d{1,2})\s*(?:gacha)?\s*([a-z]+)(?:\s+(\d{4}))?$"
)
_DAY_RE = re.compile(r"^(\d{1,2})\s*([a-z]+)(?:\s+(\d{4}))?$")
_MONTH_RE = re.compile(r"^([a-z]+)(?:\s+oyi)?(?:\s+(\d{4}))?$")


def parse_period(text: str, today: date) -> Period | None:
    """Matndan davr. Tushunilmasa `None` (bot so'raydi — taxmin qilmaydi)."""
    try:
        return _parse_period(text, today)
    except _BadYearError:
        return None


def _parse_period(text: str, today: date) -> Period | None:
    t = search_key(text)
    t = re.sub(r"\b(da|dagi|uchun|oydagi)\b", "", t).strip()
    t = re.sub(r"(\d)-?(chi|inchi|i)\b", r"\1", t)  # "15-chi" → "15"
    t = re.sub(r"(\d)-([a-z])", r"\1 \2", t)  # "15-noyabr" → "15 noyabr"
    # "mayda", "martdagi" → "may", "mart"
    t = re.sub(r"\b([a-z]+?)(da|dagi)\b", lambda m: m[1] if m[1] in MONTHS else m[0], t)
    t = re.sub(r"\s+", " ", t)

    if t == "bugun":
        return Period(today, today, "bugun")
    if t == "kecha":
        d = today - timedelta(days=1)
        return Period(d, d, "kecha")
    if t in {"bu hafta", "shu hafta"}:
        start = today - timedelta(days=today.weekday())
        return Period(start, today, "bu hafta")
    if t == "otgan hafta":
        start = today - timedelta(days=today.weekday() + 7)
        return Period(start, start + timedelta(days=6), "o'tgan hafta")
    if t in {"bu oy", "shu oy"}:
        return Period(today.replace(day=1), today, "bu oy")
    if t == "otgan oy":
        last = today.replace(day=1) - timedelta(days=1)
        p = _month_period(last.year, last.month)
        return Period(p.start, p.end, "o'tgan oy")
    if t in {"bu yil", "shu yil"}:
        return Period(date(today.year, 1, 1), today, "bu yil")
    if t == "otgan yil":
        y = today.year - 1
        return Period(date(y, 1, 1), date(y, 12, 31), "o'tgan yil")

    if m := _RANGE_RE.match(t):
        d1, d2, mon, yr = int(m[1]), int(m[2]), MONTHS.get(m[3]), m[4]
        if mon is None or d1 > d2:
            return None
        year = _resolve_month_year(mon, today, int(yr) if yr else None)
        try:
            return Period(
                date(year, mon, d1), date(year, mon, d2), f"{d1}–{d2} {MONTH_NAMES_UZ[mon - 1]}"
            )
        except ValueError:
            return None
    if m := _DAY_RE.match(t):
        day_num, mon, yr = int(m[1]), MONTHS.get(m[2]), m[3]
        if mon is None:
            return None
        year = _resolve_month_year(mon, today, int(yr) if yr else None)
        try:
            day = date(year, mon, day_num)
        except ValueError:
            return None
        return Period(day, day, f"{day_num}-{MONTH_NAMES_UZ[mon - 1]}")
    if (m := _MONTH_RE.match(t)) and m[1] in MONTHS:
        mon = MONTHS[m[1]]
        year = _resolve_month_year(mon, today, int(m[2]) if m[2] else None)
        return _month_period(year, mon)
    return None


def format_date(d: date) -> str:
    """`2026-11-12` → `12-noyabr` (joriy yil bo'lmasa — `12-noyabr 2025`)."""
    base = f"{d.day}-{MONTH_NAMES_UZ[d.month - 1]}"
    return base if d.year == today_tashkent().year else f"{base} {d.year}"
