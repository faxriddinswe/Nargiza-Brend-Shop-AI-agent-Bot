"""Parse one line of the old paper notebook typed by staff (BR-140…144).

Accepted shape (order of the name is fixed, the rest is free): ``Umida opa, 90 123 45 67, 350 ming, 12-oktabr``
Commas are optional. Name comes first, then the amount; the phone and the date may be anywhere.
Anything unclear is reported as a problem — NEVER guessed (master rule, BR-141).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from bot.utils.dates import MONTHS
from bot.utils.money import AmbiguousAmountError, AmountParseError, parse_amount
from bot.utils.phone import InvalidPhoneError, normalize_phone
from bot.utils.translit import search_key

_PHONE = re.compile(
    r"(?<!\d)(?:\+?998[\s\-]*)?\(?\d{2}\)?[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"
)
_DATE_NUM = re.compile(r"(?<![\d.])(\d{1,2})[./](\d{1,2})(?:[./](\d{2}|\d{4}))?(?![\d.])")
_DATE_WORD = re.compile(r"(?<!\d)(\d{1,2})[\s\-]*([a-z]+?)(?:da|dagi)?(?:\s+(\d{4}))?(?![a-z\d])")
_FORMS = {"opa": "opa", "aka": "aka", "opaga": "opa", "akaga": "aka"}
_NUMBER_WORDS = {
    "bir", "ikki", "uch", "tort", "besh", "olti", "yetti", "sakkiz", "toqqiz", "on", "yigirma", "ottiz",
    "qirq", "ellik", "oltmish", "yetmish", "sakson", "toqson", "yuz", "ming", "million", "mln", "yarim",
}  # fmt: skip
MAX_AGE_DAYS = 366 * 3


@dataclass(slots=True)
class NotebookLine:
    raw_ok: bool = True
    name: str | None = None
    form: str | None = None  # opa | aka
    phone: str | None = None
    amount: int | None = None
    debt_date: date | None = None
    problems: list[str] = field(default_factory=list)  # ❓ unclear — blocks saving the row
    warnings: list[str] = field(default_factory=list)  # ⚠️ saved, but staff should know


def parse_past_date(text: str, today: date) -> date | None:
    """ "12-oktabr", "12.10", "12.10.2025", "12 oktabr 2025" → a date that is today or earlier (no year: latest past)."""
    t = search_key(text)
    day = month = year = None
    if m := _DATE_NUM.fullmatch(t.strip()):
        day, month = int(m[1]), int(m[2])
        if m[3]:
            year = 2000 + int(m[3]) if len(m[3]) == 2 else int(m[3])
    elif m2 := _DATE_WORD.fullmatch(t.strip()):
        if m2[2] not in MONTHS:
            return None
        day, month = int(m2[1]), MONTHS[m2[2]]
        year = int(m2[3]) if m2[3] else None
    if day is None or month is None:
        return None
    try:
        if year is None:
            cand = date(today.year, month, day)
            if cand > today:
                cand = date(today.year - 1, month, day)
        else:
            cand = date(year, month, day)
    except ValueError:
        return None
    return cand if today - timedelta(days=MAX_AGE_DAYS) <= cand <= today else None


def _take_date(text: str, today: date) -> tuple[str, date | None, bool]:
    """Remove the date from the text (original letters kept). Returns (rest, date, found_but_invalid)."""
    low = text.lower().replace("'", "").replace("\u2019", "").replace("\u02bc", "")
    if len(low) != len(text):  # apostrophes in the name: match on the plain text, cut the same span
        low = text.lower()
    for rx in (_DATE_NUM, _DATE_WORD):
        for m in rx.finditer(low):
            if rx is _DATE_WORD and m[2] not in MONTHS:
                continue
            d = parse_past_date(m[0], today)
            return text[: m.start()] + " " + text[m.end() :], d, d is None
    return text, None, False


def parse_line(line: str, today: date) -> NotebookLine:
    out = NotebookLine()
    text = line.strip()
    if not text:
        out.raw_ok = False
        return out
    # phone
    if m := _PHONE.search(text):
        try:
            out.phone = normalize_phone(m[0])
        except InvalidPhoneError:
            out.problems.append("telefon raqami noto'g'ri")
        text = text[: m.start()] + " " + text[m.end() :]
    # date
    text, out.debt_date, bad_date = _take_date(text, today)
    if bad_date:
        out.problems.append("sana noto'g'ri yoki kelajakda")
    elif out.debt_date is None:
        out.warnings.append("sana yo'q — bugungi sana qo'yiladi")
    # name = leading words, amount = the rest
    words = [w.strip(",;") for w in re.split(r"\s+", text) if w.strip(",;")]
    cut = next(
        (i for i, w in enumerate(words) if re.search(r"\d", w) or search_key(w) in _NUMBER_WORDS),
        len(words),
    )
    name_words, amount_words = words[:cut], words[cut:]
    form = None
    clean: list[str] = []
    for w in name_words:
        if search_key(w) in _FORMS:
            form = _FORMS[search_key(w)]
        else:
            clean.append(w)
    if not clean:
        out.problems.append("ism yo'q")
    else:
        out.name = " ".join(clean)
    out.form = form
    if not amount_words:
        out.problems.append("summa yo'q")
    else:
        try:
            parsed = parse_amount(" ".join(amount_words))
            out.amount = parsed.value
            if parsed.assumed_thousands:
                out.warnings.append(f"«{' '.join(amount_words)}» ming so'm deb olindi")
        except AmbiguousAmountError:
            out.problems.append("summa noaniq")
        except AmountParseError:
            out.problems.append("summani tushunib bo'lmadi")
    if out.phone is None and not any("telefon" in p for p in out.problems):
        out.warnings.append("telefon yo'q")
    return out
