"""Pul summalarini o'qish va formatlash (BR-004, BR-076, master 8.4).

Pul doim `int` (so'm). Ichki hisobda kasr uchun `Fraction` ("1.5 mln"), `float` — hech qachon.

ASOSIY TAMOYIL: shubhali kirish hech qachon "taxminiy" summaga aylanmaydi — xato beriladi va bot
so'raydi. Jim noto'g'ri summa (1000 barobar ko'p yoki ikki son qo'shilgan) — eng xavfli xato.

Grammatika:  [guruh] shkala [guruh] shkala ... [qoldiq]
- shkalalar qat'iy kamayib boradi (mlrd > mln > ming); takrorlanmaydi; ketma-ket kelmaydi
- guruh: raqam ("350", "1.5") yoki so'zlar ("uch yuz ellik", "bir yarim")
- "million yarim" / "bir million yarim" → shkalaning yarmi qo'shiladi

Qabul qilinadi: "450000", "450 000", "450.000", "350 ming", "350k", "500 minglik", "1.5 mln",
"1,5 million", "yarim million", "bir million yarim", "uch yuz ellik ming", "bir million ikki yuz ming",
kirill: "уч юз эллик минг".

So'raladi (`AmbiguousAmountError`):
- "350" → 350 000 qabul qilinadi, lekin `assumed_thousands=True` (kartada ko'rinadi) — BR-076
- "1500" (1000–9999 birliksiz), natija 10 000 so'mdan kam, natija 1 mlrd dan ko'p
- "1.500 mln" (ajratgichmi yoki o'nlik vergulmi — noaniq), "350-400 ming" (oraliq),
  "500 ming 450" (ming dan keyin qoldiq)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from bot.utils.translit import search_key

MIN_AMOUNT = 10_000  # kiyim do'koni uchun bundan kichik summa — ehtimol xato aytilgan
MAX_AMOUNT = 1_000_000_000


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
_SCALES = {
    "ming": 1_000, "minglik": 1_000, "k": 1_000, "tisyach": 1_000,
    "million": 1_000_000, "mln": 1_000_000, "millon": 1_000_000, "milion": 1_000_000,
    "milliard": 10**9, "mlrd": 10**9,
}  # fmt: skip
_IGNORED = {"som", "sum", "sumga", "somga", "somlik", "ga", "lik", "dan", "ni"}

_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_TOKEN = re.compile(r"\d+(?:[.,]\d+)?|[a-z]+|-")
# Minglik guruhlash: "1 500 000", "450.000", "1,500,000" (bitta xil ajratgich)
_GROUPED = re.compile(r"(?<![\d.,])\d{1,3}(?:(?P<sep>[ .,])\d{3})(?:(?P=sep)\d{3})*(?![\d.,]*\d)")


def _is_number(tok: str) -> bool:
    return bool(_NUM.fullmatch(tok))


def _join_groups(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        sep = m.group("sep")
        rest = text[m.end() :].lstrip()
        next_word = re.match(r"[a-z]+", rest)
        if sep in ".," and next_word and next_word.group(0) in _SCALES:
            # "1.500 mln" — 1,5 mlnmi yoki 1500 mlnmi? Taxmin qilmaymiz.
            raise AmbiguousAmountError(text)
        return re.sub(r"[ .,]", "", m.group(0))

    return _GROUPED.sub(repl, text)


def _eval_group(tokens: list[str], original: str) -> Fraction | None:
    """Bitta guruh: "uch yuz ellik", "bir yarim", "350", "1.5", "3 yuz". Bo'sh → None."""
    if not tokens:
        return None
    i, val = 0, Fraction(0)

    def at(k: int) -> str | None:
        return tokens[k] if k < len(tokens) else None

    first = at(0)
    if first is not None and _is_number(first):
        val = Fraction(first.replace(",", "."))
        i = 1
        if at(1) == "yuz":
            val *= 100
            i = 2
    else:
        if first in _ONES and at(1) == "yuz":
            val, i = Fraction(_ONES[first] * 100), 2
        elif first == "yuz":
            val, i = Fraction(100), 1
        tok = at(i)
        if tok in _TENS:
            val += _TENS[tok]
            i += 1
        tok = at(i)
        if tok in _ONES:
            val += _ONES[tok]
            i += 1
    if at(i) == "yarim":
        val += Fraction(1, 2)
        i += 1
    if i != len(tokens):
        raise AmountParseError(original)
    return val


def parse_amount(text: str) -> ParsedAmount:
    """Matndan summani o'qiydi. Tushunilmasa `AmountParseError`, noaniq bo'lsa `AmbiguousAmountError`."""
    norm = search_key(text)
    norm = re.sub(r"(\d)([a-z])", r"\1 \2", norm)  # "350ming", "350k"
    norm = _join_groups(norm)
    tokens = [t for t in _TOKEN.findall(norm) if t not in _IGNORED]
    if not tokens:
        raise AmountParseError(text)
    if "-" in tokens:
        # "-500 ming" (manfiy) yoki "350-400 ming" (oraliq) — summa emas
        raise AmbiguousAmountError(text)

    total = Fraction(0)
    last_scale: int | None = None
    segment: list[str] = []
    for tok in tokens:
        if tok in _SCALES:
            scale = _SCALES[tok]
            if last_scale is not None and scale >= last_scale:
                raise AmbiguousAmountError(text)  # "ming ming", "300k 50k", "million ming"
            group = _eval_group(segment, text)
            if group is None and last_scale is not None:
                raise AmbiguousAmountError(text)  # ketma-ket ikki shkala
            total += (Fraction(1) if group is None else group) * scale
            last_scale, segment = scale, []
        else:
            segment.append(tok)

    assumed = False
    if segment == ["yarim"] and last_scale is not None:
        total += Fraction(last_scale, 2)  # "million yarim" → 1 500 000
    elif segment:
        rest = _eval_group(segment, text)
        if rest is None:  # segment bo'sh emas — bo'lmaydi, lekin xavfsizlik uchun
            raise AmountParseError(text)
        if last_scale is None:
            if rest.denominator != 1:
                raise AmbiguousAmountError(text)  # "1.5" — birliksiz kasr
            if rest < 1000:
                rest *= 1000  # BR-076: "350" → 350 000
                assumed = True
            elif rest < 10_000:
                raise AmbiguousAmountError(text)  # "1500"
        elif last_scale >= 1_000_000 and rest < 1000:
            rest *= 1000  # "bir million ikki yuz" → 1 200 000
            assumed = True
        else:
            raise AmbiguousAmountError(text)  # "500 ming 450"
        total += rest

    if total.denominator != 1:
        raise AmountParseError(text)  # butun so'm bo'lishi shart
    value = int(total)
    if value <= 0:
        raise AmountParseError(text)
    if value < MIN_AMOUNT or value > MAX_AMOUNT:
        raise AmbiguousAmountError(text)
    return ParsedAmount(value, assumed)


def format_amount(value: int) -> str:
    """`450000` → `450 000 so'm` (UX qoidasi: bo'sh joy bilan guruhlash)."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("pul faqat int bo'ladi")
    sign = "−" if value < 0 else ""  # haqiqiy minus belgisi
    return f"{sign}{abs(value):,}".replace(",", " ") + " so'm"
