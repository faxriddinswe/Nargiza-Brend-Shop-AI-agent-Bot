"""BR-044: kirill ↔ lotin va qidiruv kaliti."""

from __future__ import annotations

import pytest

from bot.utils.translit import normalize_apostrophes, search_key, to_cyrillic, to_latin


@pytest.mark.parametrize(
    ("cyr", "lat"),
    [
        ("Умида", "Umida"),
        ("Шаҳло", "Shahlo"),
        ("Ўғилой", "O'g'iloy"),
        ("Нилуфар", "Nilufar"),
        ("Елена", "Yelena"),  # so'z boshidagi е → ye
        ("Бахриддин", "Baxriddin"),
        ("кўйлак", "ko'ylak"),
        ("қарз", "qarz"),
        ("туфли", "tufli"),
        ("Юлдуз", "Yulduz"),
        ("Ёқутхон", "Yoqutxon"),
        ("ички кийим", "ichki kiyim"),
    ],
)
def test_to_latin(cyr: str, lat: str) -> None:
    assert to_latin(cyr) == lat


def test_to_latin_leaves_latin_unchanged() -> None:
    assert to_latin("Umida opa") == "Umida opa"


@pytest.mark.parametrize(
    ("lat", "cyr"),
    [
        ("Umida", "Умида"),
        ("Shahlo", "Шаҳло"),
        ("O'g'iloy", "Ўғилой"),
        ("ko'ylak", "кўйлак"),
        ("ekan", "экан"),
    ],
)
def test_to_cyrillic(lat: str, cyr: str) -> None:
    assert to_cyrillic(lat) == cyr


@pytest.mark.parametrize(
    "variant",
    ["O'g'iloy", "Oʻgʻiloy", "Oʼgʼiloy", "O`g`iloy", "O’g’iloy", "Ogiloy", "Ўғилой", "OGILOY"],
)
def test_search_key_unifies_all_spellings(variant: str) -> None:
    """BR-044: "Умида" = "Umida", apostrof variantlari bir xil."""
    assert search_key(variant) == "ogiloy"


def test_search_key_collapses_spaces() -> None:
    assert search_key("  Umida   opa ") == "umida opa"
    assert search_key("Умида") == search_key("umida")


def test_normalize_apostrophes() -> None:
    assert normalize_apostrophes("oʻgʻil") == "o'g'il"
