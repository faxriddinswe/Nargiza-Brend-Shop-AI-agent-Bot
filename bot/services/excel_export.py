"""Excel (.xlsx) exports with openpyxl (BR-128). Pure functions: data in, bytes out. Sections on separate sheets."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.worksheet import Worksheet

from bot.services.inventory import StockRow
from bot.services.ledger import DebtorRow
from bot.services.reports import PeriodReport
from bot.texts import uz_latn as t

MONEY = '#,##0" so\'m"'


def _header(ws: Worksheet, row: int, labels: Sequence[str]) -> None:
    for col, text in enumerate(labels, 1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", wrap_text=True)


def _widths(ws: Worksheet, widths: Sequence[int]) -> None:
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w


def _to_bytes(wb: Workbook) -> bytes:
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def sales_workbook(r: PeriodReport) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for code, s in r.sections.items():
        ws = wb.create_sheet(t.SECTION_NAMES[code])
        ws["A1"] = f"{t.SECTION_NAMES[code]} — {r.period.label} ({r.period.start} – {r.period.end})"
        ws["A1"].font = Font(bold=True, size=13)
        _header(ws, 3, ["Ko'rsatkich", "Qiymat"])
        rows = [
            ("Savdo (naqd/aralash), so'm", s.sales_total), ("  shundan naqd tushgan", s.sales_cash),
            ("  shundan nasiyaga", s.sales_on_credit), ("Chegirma", s.discount_total),
            ("To'liq nasiya (tovar)", s.credit_goods_total), ("Jami tovar aylanmasi", s.turnover),
            ("Qarz to'lovlari (naqd)", s.payments_cash), ("Kechilgan qarz", s.write_offs),
            ("Qaytarilgan tovar", s.returns_value), ("  qarzdan ayirilgan", s.returns_debt_reduction),
            ("  naqd qaytarilgan", s.returns_cash_refund), ("Kassaga kirdi (sof)", s.net_cash),
            ("Yangi qarz berildi", s.debt_given),
        ]  # fmt: skip
        for i, (label, value) in enumerate(rows, 4):
            ws.cell(row=i, column=1, value=label)
            c = ws.cell(row=i, column=2, value=value)
            c.number_format = MONEY
        start = 4 + len(rows) + 1
        _header(ws, start, ["Tovar turi", "Soni", "Summa (ro'yxat narxida)"])
        for i, line in enumerate(s.categories, start + 1):
            ws.cell(row=i, column=1, value=line.name.capitalize())
            ws.cell(row=i, column=2, value=line.quantity)
            ws.cell(row=i, column=3, value=line.amount).number_format = MONEY
        _widths(ws, [38, 20, 26])
    return _to_bytes(wb)


def debtors_workbook(
    rows: Sequence[DebtorRow], phones: dict[int, str | None], codes: dict[int, str]
) -> bytes:
    """One sheet per section; biggest debt first."""
    wb = Workbook()
    wb.remove(wb.active)
    by_section: dict[str, list[DebtorRow]] = {}
    for r in rows:
        by_section.setdefault(codes[r.section_id], []).append(r)
    for code in codes.values():
        ws = wb.create_sheet(t.SECTION_NAMES[code])
        _header(ws, 1, ["№", "Mijoz", "Telefon", "Qarz", "Eng yaqin muddat"])
        items = by_section.get(code, [])
        for i, r in enumerate(items, 1):
            ws.cell(row=i + 1, column=1, value=i)
            ws.cell(row=i + 1, column=2, value=f"{r.name} {r.form}")
            ws.cell(row=i + 1, column=3, value=phones.get(r.customer_id) or "⚠️ telefon kerak")
            ws.cell(row=i + 1, column=4, value=r.owed).number_format = MONEY
            ws.cell(
                row=i + 1, column=5, value=r.next_due.isoformat() if r.next_due else "muddatsiz"
            )
        ws.cell(row=len(items) + 3, column=3, value="Jami").font = Font(bold=True)
        total = ws.cell(row=len(items) + 3, column=4, value=sum(r.owed for r in items))
        total.number_format = MONEY
        total.font = Font(bold=True)
        _widths(ws, [5, 28, 20, 18, 18])
    return _to_bytes(wb)


def stock_workbook(rows: Sequence[StockRow]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for code in dict.fromkeys(r.section_code for r in rows):
        ws = wb.create_sheet(t.SECTION_NAMES[code])
        _header(ws, 1, ["Tovar turi", "Qoldiq", "Kam qolish chegarasi", "Holat"])
        for i, r in enumerate((x for x in rows if x.section_code == code), 2):
            ws.cell(row=i, column=1, value=r.name.capitalize())
            ws.cell(row=i, column=2, value=r.qty)
            ws.cell(row=i, column=3, value=r.threshold)
            ws.cell(
                row=i, column=4, value="manfiy" if r.negative else ("kam" if r.low else "yetarli")
            )
        _widths(ws, [24, 12, 22, 14])
    return _to_bytes(wb)
