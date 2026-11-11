"""BR-040: telefon normallashtirish. Faqat soxta raqamlar."""

from __future__ import annotations

import pytest

from bot.utils.phone import (
    InvalidPhoneError,
    format_phone,
    mask_phone,
    normalize_contact_phone,
    normalize_phone,
    phone_tail_matches,
)


@pytest.mark.parametrize(
    "raw",
    [
        "90 123 45 67",
        "901234567",
        "+998 90 123 45 67",
        "+998901234567",
        "998901234567",
        "+998 (90) 123-45-67",
        "(90) 123-45-67",
        " 90-123-45-67 ",
    ],
)
def test_normalize_phone_variants_give_same_key(raw: str) -> None:
    """BR-040"""
    assert normalize_phone(raw) == "+998901234567"


@pytest.mark.parametrize(
    "raw", ["", "12345", "9012345678", "+7 912 345 67 89", "abc", "99890123456"]
)
def test_normalize_phone_rejects_invalid(raw: str) -> None:
    with pytest.raises(InvalidPhoneError):
        normalize_phone(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("998901234567", "+998901234567"),  # Telegram ko'pincha + siz yuboradi
        ("+998901234567", "+998901234567"),
        ("79123456789", "+79123456789"),  # xorijiy raqam ham saqlanadi
    ],
)
def test_normalize_contact_phone(raw: str, expected: str) -> None:
    assert normalize_contact_phone(raw) == expected


def test_format_phone() -> None:
    assert format_phone("+998901234567") == "+998 90 123 45 67"


def test_mask_phone_hides_middle_digits() -> None:
    masked = mask_phone("+998901234567")
    assert masked == "+99890*****67"
    assert "1234" not in masked
    assert mask_phone(None) == "-"


@pytest.mark.parametrize(
    ("tail", "ok"), [("4567", True), ("45 67", True), ("67", True), ("1111", False), ("", False)]
)
def test_phone_tail_matches(tail: str, ok: bool) -> None:
    assert phone_tail_matches("+998901234567", tail) is ok
