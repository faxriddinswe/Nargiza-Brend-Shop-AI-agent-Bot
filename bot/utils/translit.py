"""O'zbek kirill ↔ lotin transliteratsiyasi va qidiruv kaliti (BR-044).

Qidiruvda hamma narsa bitta ko'rinishga keltiriladi (`search_key`): lotin, kichik harf,
apostrofsiz. Shunda "Умида", "Umida", "UMIDA" bir xil; "O'g'iloy", "Oʻgʻiloy", "Ogiloy" ham.
"""

from __future__ import annotations

import re

# Turli apostrof belgilari: ' ʻ ʼ ` ’ ‘ ´
APOSTROPHES = "'ʻʼ`’‘´"
_APOS_RE = re.compile(f"[{re.escape(APOSTROPHES)}]")

_CYR_TO_LAT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x",
    "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'", "ь": "", "ы": "i",
    "э": "e", "ю": "yu", "я": "ya", "ё": "yo", "ў": "o'", "қ": "q", "ғ": "g'",
    "ҳ": "h",
}  # fmt: skip
_CYR_VOWELS = set("аеёиоуэюяў")


def normalize_apostrophes(text: str) -> str:
    return _APOS_RE.sub("'", text)


def to_latin(text: str) -> str:
    """Kirill matnni lotinga o'giradi. Lotin matn o'zgarmaydi (faqat apostroflar bir xil bo'ladi).

    "е": so'z boshida va unlidan keyin "ye" (Ер → Yer), aks holda "e".
    """
    out: list[str] = []
    prev = ""
    for ch in text:
        low = ch.lower()
        if low == "е":
            lat = "ye" if (not prev.isalpha() or prev.lower() in _CYR_VOWELS) else "e"
        elif low in _CYR_TO_LAT:
            lat = _CYR_TO_LAT[low]
        else:
            out.append(ch)
            prev = ch
            continue
        if ch.isupper() and lat:
            lat = lat[0].upper() + lat[1:]
        out.append(lat)
        prev = ch
    return normalize_apostrophes("".join(out))


_LAT_TO_CYR_MULTI: list[tuple[str, str]] = [
    ("o'", "ў"), ("g'", "ғ"), ("sh", "ш"), ("ch", "ч"),
    ("yo", "ё"), ("yu", "ю"), ("ya", "я"), ("ye", "е"),
]  # fmt: skip
_LAT_TO_CYR_SINGLE: dict[str, str] = {
    "a": "а", "b": "б", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "x": "х", "y": "й", "z": "з", "'": "ъ",
}  # fmt: skip


def to_cyrillic(text: str) -> str:
    """Lotin matnni kirillga (bot javoblarini kirillda ko'rsatish sozlamasi uchun).

    "e" so'z boshida "э" bo'ladi (ekan → экан). Oddiy, lekin ko'p uchraydigan holatlar uchun yetarli.
    """
    src = normalize_apostrophes(text)
    out: list[str] = []
    i = 0
    while i < len(src):
        pair = src[i : i + 2]
        lowpair = pair.lower()
        for lat, cyr in _LAT_TO_CYR_MULTI:
            if lowpair == lat:
                out.append(cyr.upper() if pair[0].isupper() else cyr)
                i += 2
                break
        else:
            ch = src[i]
            low = ch.lower()
            if low == "e" and (i == 0 or not src[i - 1].isalpha()):
                cyr = "э"
            else:
                cyr = _LAT_TO_CYR_SINGLE.get(low, ch)
            out.append(cyr.upper() if ch.isupper() else cyr)
            i += 1
    return "".join(out)


_SPACES = re.compile(r"\s+")


def search_key(text: str) -> str:
    """Qidiruv kaliti: lotin, kichik harf, apostrofsiz, bitta bo'sh joy."""
    latin = to_latin(text).lower()
    latin = _APOS_RE.sub("", latin)
    return _SPACES.sub(" ", latin).strip()
