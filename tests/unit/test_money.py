"""Pul summasini o'qish va formatlash (BR-004, BR-076, master 8.4)."""

from __future__ import annotations

import pytest

from bot.utils.money import (
    AmbiguousAmountError,
    AmountParseError,
    ParsedAmount,
    format_amount,
    parse_amount,
)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("450000", 450_000),
        ("450 000", 450_000),
        ("450.000", 450_000),
        ("450,000", 450_000),
        ("1 500 000", 1_500_000),
        ("350 ming", 350_000),
        ("350ming", 350_000),
        ("350k", 350_000),
        ("350 000 so'm", 350_000),
        ("100 ming so'm", 100_000),
        ("1.5 mln", 1_500_000),
        ("1,5 million", 1_500_000),
        ("2 mln", 2_000_000),
        ("yarim million", 500_000),
        ("bir yarim million", 1_500_000),
        ("ikki yarim mln", 2_500_000),
        ("uch yuz ellik ming", 350_000),
        ("yuz ming", 100_000),
        ("yigirma besh ming", 25_000),
        ("to'qson ming", 90_000),
        ("to'rt yuz sakson ming", 480_000),
        ("bir million ikki yuz ming", 1_200_000),
        ("1 mln 200 ming", 1_200_000),
        ("уч юз эллик минг", 350_000),  # kirill
        ("ярим миллион", 500_000),
        ("1,500,000", 1_500_000),
        ("500 minglik", 500_000),
        ("bir million yarim", 1_500_000),
        ("million yarim", 1_500_000),
        ("ikki yuz ellik besh ming", 255_000),
        ("100 ming so'mga", 100_000),
        ("бир ярим миллион", 1_500_000),
        ("3 yuz ming", 300_000),
        ("1 mlrd", 1_000_000_000),
    ],
)
def test_parse_amount_explicit(text: str, value: int) -> None:
    assert parse_amount(text) == ParsedAmount(value, assumed_thousands=False)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("350", 350_000),
        ("50", 50_000),
        ("uch yuz ellik", 350_000),
        ("bir million ikki yuz", 1_200_000),
    ],
)
def test_parse_amount_assumes_thousands_and_flags_it(text: str, value: int) -> None:
    """BR-076: "350" → 350 000, lekin belgi bilan (kartada ko'rinadi)."""
    assert parse_amount(text) == ParsedAmount(value, assumed_thousands=True)


@pytest.mark.parametrize(
    "text",
    [
        "1500", "2500", "9999", "1.5", "yarim", "ming", "5",
        # jim noto'g'ri summa bo'lishi mumkin bo'lgan kirishlar — so'ralishi shart
        "1.500 mln", "1,250 mln", "1.005 mln", "350.000 ming", "1,500 ming",
        "350-400 ming", "300k 50k", "yuz ming besh yuz ming", "500 ming 450",
        "ming ming", "million ming", "-500 ming", "ming besh yuz", "ikki ming yigirma besh",
        "2.5k", "1.25 ming", "+998901234567", "10 000 000 000 000", "1 500 mln",
    ],
)  # fmt: skip
def test_parse_amount_ambiguous(text: str) -> None:
    """BR-076: 1000–9999 va birliksiz kasr — noaniq, bot so'raydi."""
    with pytest.raises(AmbiguousAmountError):
        parse_amount(text)


@pytest.mark.parametrize("text", ["", "salom", "0", "0 ming", "ko'p pul", "yuz yuz", "1.2345 ming"])
def test_parse_amount_rejects_garbage(text: str) -> None:
    with pytest.raises(AmountParseError):
        parse_amount(text)


def test_parse_amount_large_values_are_exact_ints() -> None:
    """float ishlatilmaganini tekshirish: katta summa aniq qoladi."""
    result = parse_amount("999 999 999")
    assert result.value == 999_999_999
    assert isinstance(result.value, int)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (450_000, "450 000 so'm"),
        (0, "0 so'm"),
        (1_500_000, "1 500 000 so'm"),
        (999, "999 so'm"),
        (-2000, "−2 000 so'm"),
    ],
)
def test_format_amount(value: int, text: str) -> None:
    assert format_amount(value) == text


@pytest.mark.parametrize("bad", [450000.0, True])
def test_format_amount_rejects_non_int(bad: object) -> None:
    with pytest.raises(TypeError):
        format_amount(bad)  # type: ignore[arg-type]
