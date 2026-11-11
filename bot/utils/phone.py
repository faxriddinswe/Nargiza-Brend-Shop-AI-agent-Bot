"""Telefon raqamlarini normallashtirish, formatlash va maskalash (BR-040).

Yagona saqlash formati: `+998XXXXXXXXX` (O'zbekiston). Telegram kontaktidan kelgan
xorijiy raqamlar E.164 ko'rinishida (`+<raqamlar>`) saqlanadi.
"""

from __future__ import annotations

import re

UZ_CODE = "998"
_NON_DIGIT = re.compile(r"\D")


class InvalidPhoneError(ValueError):
    """Raqamni O'zbekiston formatiga keltirib bo'lmadi."""


def _digits(raw: str) -> str:
    return _NON_DIGIT.sub("", raw)


def normalize_phone(raw: str) -> str:
    """Xodim yozgan O'zbekiston raqamini `+998XXXXXXXXX` ga keltiradi.

    Qabul qilinadi: "90 123 45 67", "901234567", "+998 90 123-45-67", "998901234567",
    "(90) 123-45-67". Boshqa uzunlikdagi raqam — `InvalidPhoneError`.
    """
    digits = _digits(raw)
    if len(digits) == 9:
        return f"+{UZ_CODE}{digits}"
    if len(digits) == 12 and digits.startswith(UZ_CODE):
        return f"+{digits}"
    raise InvalidPhoneError(raw)


def normalize_contact_phone(raw: str) -> str:
    """Telegram kontaktidagi raqam (Telegram tasdiqlagan, xalqaro format).

    Telegram ba'zan `+` siz yuboradi ("998901234567"). O'zbek raqami bo'lsa — standart
    formatga, aks holda E.164 (`+` va 7–15 raqam).
    """
    digits = _digits(raw)
    if len(digits) == 12 and digits.startswith(UZ_CODE):
        return f"+{digits}"
    if 7 <= len(digits) <= 15:
        return f"+{digits}"
    raise InvalidPhoneError(raw)


def format_phone(phone: str) -> str:
    """Ko'rsatish uchun: `+998901234567` → `+998 90 123 45 67`."""
    d = _digits(phone)
    if len(d) == 12 and d.startswith(UZ_CODE):
        return f"+{d[:3]} {d[3:5]} {d[5:8]} {d[8:10]} {d[10:]}"
    return phone


def mask_phone(phone: str | None) -> str:
    """Log uchun: `+998901234567` → `+99890*****67`. Raqamni log'ga faqat shunday yozing."""
    if not phone:
        return "-"
    d = _digits(phone)
    if len(d) < 6:
        return "***"
    return f"+{d[:5]}{'*' * (len(d) - 7)}{d[-2:]}"


def phone_tail_matches(phone: str | None, tail: str) -> bool:
    """ "45 67 dagisi" kabi qisman qidiruv: raqam shu raqamlar bilan tugaydimi."""
    t = _digits(tail)
    return bool(phone) and bool(t) and _digits(phone or "").endswith(t)
