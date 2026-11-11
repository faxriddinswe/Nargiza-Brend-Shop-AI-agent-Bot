"""Pul summalarini o'qish va formatlash (BR-004, master 8.4).

Pul doim `int` (so'm). Ichki hisobda kasr uchun `Fraction` ishlatiladi ("1.5 mln"),
`float` — hech qachon (0.1 + 0.2 != 0.3 muammosi).

Qo'llab-quvvatlanadi: "450000", "450 000", "450.000", "350 ming", "350k", "1.5 mln",
"1,5 million", "yarim million", "bir yarim million", "uch yuz ellik ming",
"bir million ikki yuz ming", kirill: "уч юз эллик минг".

Bozor odati: birliksiz kichik son ("350") — ming deb olinadi, lekin `assumed_thousands=True`
belgisi qo'yiladi, tasdiqlash kartasida aniq ko'rinadi. 1000–9999 oralig'idagi birliksiz son
("1500" — 1 500 so'mmi yoki 1,5 mln?) — noaniq, `AmbiguousAmountError` (bot so'raydi).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from bot.utils.translit import search_key


class AmountParseError(ValueError):
    """Summani tushunib bo'lmadi."""


class AmbiguousAmountError(AmountParseError):
    """Summa noaniq — foydalanuvchidan aniqlashtirish kerak."""


@dataclass(frozen=True, slots=True)
class ParsedAmount:
    value: int
    assumed_thousands: bool = False


_ONES = {
    "bir": 1, "ikki": 2, "uch": 3, "tort": 4, "besh": 5,
    "olti": 6, "yetti": 7, "sakkiz": 8, "toqqiz": 9,
}  # fmt: skip
_TENS = {
    "on": 10, "yigirma": 20, "ottiz": 30, "qirq": 40, "ellik": 50,
    "oltmish": 60, "yetmish": 70, "sakson": 80, "toqson": 90,
}  # fmt: skip
_THOUSAND = {"ming", "k", "tisyach", "tis"}
_MILLION = {"million", "mln", "millon", "milion"}
_BILLION = {"milliard", "mlrd"}
_HALF = {"yarim"}
_CURRENCY = {"som", "sum", "sumga", "somga", "somlik", "minglik", "ga", "lik"}

# "1 500 000", "450.000", "450,000" — minglik ajratgichlar
_GROUPED = re.compile(r"\b\d{1,3}(?:[ .,]\d{3})+\b")
_TOKEN = re.compile(r"\d+(?:[.,]\d+)?|[a-z]+")


def _strip_group_separators(text: str) -> str:
    return _GROUPED.sub(lambda m: re.sub(r"[ .,]", "", m.group(0)), text)


def parse_amount(text: str) -> ParsedAmount:
    """Matndan summani o'qiydi. Tushunilmasa `AmountParseError`, noaniq bo'lsa `AmbiguousAmountError`."""
    norm = search_key(text)
    # "350ming", "350k" kabi qo'shib yozilganlarni ajratish
    norm = re.sub(r"(\d)([a-z])", r"\1 \2", norm)
    norm = _strip_group_separators(norm)
    tokens = _TOKEN.findall(norm)
    if not tokens:
        raise AmountParseError(text)

    total = Fraction(0)
    current = Fraction(0)
    has_current = False
    last_scale = 0

    for tok in tokens:
        if tok[0].isdigit():
            current += Fraction(tok.replace(",", "."))
            has_current = True
        elif tok in _ONES:
            current += _ONES[tok]
            has_current = True
        elif tok in _TENS:
            current += _TENS[tok]
            has_current = True
        elif tok in _HALF:
            current += Fraction(1, 2)
            has_current = True
        elif tok == "yuz":
            current = (current if has_current else Fraction(1)) * 100
            has_current = True
        elif tok in _THOUSAND or tok in _MILLION or tok in _BILLION:
            scale = 1_000 if tok in _THOUSAND else 1_000_000 if tok in _MILLION else 10**9
            total += (current if has_current else Fraction(1)) * scale
            current, has_current, last_scale = Fraction(0), False, scale
        elif tok in _CURRENCY:
            continue
        else:
            raise AmountParseError(text)

    assumed = False
    if has_current:
        if last_scale >= 1_000_000 and current < 1000:
            # "bir million ikki yuz" → 1 200 000 (so'zlashuvda ming tushib qoladi)
            current *= 1000
            assumed = True
        elif last_scale == 0:
            if current.denominator != 1:
                raise AmbiguousAmountError(text)  # "1.5" — birliksiz kasr
            if current < 1000:
                current *= 1000
                assumed = True
            elif current < 10_000:
                raise AmbiguousAmountError(text)
        total += current

    if total.denominator != 1:
        raise AmountParseError(text)  # natija butun so'm bo'lishi shart
    if total <= 0:
        raise AmountParseError(text)
    return ParsedAmount(int(total), assumed)


def format_amount(value: int) -> str:
    """`450000` → `450 000 so'm` (UX qoidasi: bo'sh joy bilan guruhlash)."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("pul faqat int bo'ladi")
    sign = "−" if value < 0 else ""
    return f"{sign}{abs(value):,}".replace(",", " ") + " so'm"
