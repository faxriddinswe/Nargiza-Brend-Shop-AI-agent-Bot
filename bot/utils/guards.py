"""Kichik yordamchilar: `assert` o'rniga (assert `python -O` da o'chib ketadi)."""

from __future__ import annotations


def required[T](value: T | None, what: str = "qiymat") -> T:
    if value is None:
        raise RuntimeError(f"{what} topilmadi")
    return value
