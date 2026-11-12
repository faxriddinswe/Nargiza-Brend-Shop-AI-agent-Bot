from datetime import date

from bot.utils.notebook import parse_line, parse_past_date

T = date(2026, 11, 11)


def test_full_line() -> None:
    r = parse_line("Umida opa, 90 123 45 67, 350 ming, 12-oktabr", T)
    assert (r.name, r.form, r.phone, r.amount, r.debt_date) == (
        "Umida",
        "opa",
        "+998901234567",
        350_000,
        date(2026, 10, 12),
    )
    assert not r.problems and not r.warnings


def test_missing_parts_are_flagged_not_guessed() -> None:
    assert "summa yo'q" in parse_line("Laylo opa", T).problems
    assert "ism yo'q" in parse_line("opa 100 ming", T).problems
    assert "summa noaniq" in parse_line("Malika opa 350-400 ming", T).problems
    assert any("sana" in p for p in parse_line("Gulya opa 100 ming 31.02", T).problems)
    r = parse_line("Laylo opa 200 ming", T)
    assert (
        r.debt_date is None
        and any("sana yo'q" in w for w in r.warnings)
        and any("telefon" in w for w in r.warnings)
    )


def test_past_dates_only() -> None:
    assert parse_past_date("5.10", T) == date(2026, 10, 5)
    assert parse_past_date("25-dekabr", T) == date(2025, 12, 25)  # not yet this year → last year
    assert parse_past_date("12.10.2025", T) == date(2025, 10, 12)
    assert parse_past_date("12.12.2026", T) is None  # future


def test_decimal_amounts_are_not_dates() -> None:
    for text, amount in (
        ("Umida opa 1.5 mln", 1_500_000),
        ("Umida opa 2.5 ming", 2_500),
        ("Umida opa 12.5 mln 5.10", 12_500_000),
    ):
        r = parse_line(text, T)
        assert r.amount == amount, text
    assert parse_line("Umida opa 12.5 mln 5.10", T).debt_date == date(2026, 10, 5)
    r = parse_line(
        "Umida opa 2.5 ming", T
    )  # not a date; the amount itself is ambiguous → unclear, never guessed
    assert r.debt_date is None and "summa noaniq" in r.problems
