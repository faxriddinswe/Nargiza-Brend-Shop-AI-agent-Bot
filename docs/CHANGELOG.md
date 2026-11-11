# O'zgarishlar tarixi

## [0.1.0] — 1-bosqich (poydevor) — 2026-11-11
- Utils: telefon, kirill↔lotin, pul summasi (so'z bilan ham), davrlar — 138 unit test.
- DB: 10 ta poydevor jadvali; audit Postgres trigger'i bilan (aktorsiz yozuv rad); DELETE taqiqlangan; audit_log o'zgarmas.
- Tasdiqlash kartalari: idempotent (parallel bosishda ham bitta yozuv), 30 daqiqa.
- Ro'yxatdan o'tish: kontakt egasi tekshiruvi, telefon orqali rollar (admin/xodim), mijoz yozuviga bog'lash.
- Admin paneli: xodim qo'shish/bloklash/olish, statistika, do'kon rasmi va lokatsiyasi.
- Mijoz menyusi: qarzim, e'lonlar, do'kon haqida, bog'lanish, reklamani o'chirish.
- Backup: alohida konteyner, age shifrlash, 3-2-1 jadvali, Telegram'ga kunlik; restore va tiklash testi.
- Review tuzatishlari: pul parseri qat'iy grammatika (jim noto'g'ri summa yo'q); bot uchun cheklangan DB roli;
  bloklangan xodim relink qila olmaydi; raqam ko'chganda mijoz ma'lumoti admin tasdig'isiz ochilmaydi;
  restore.sh xavfsiz (avval vaqtinchalik baza) va yangi serverga tiklash sinaldi.

## [0.0.1] — 0-bosqich (tayyorgarlik) — 2026-11-11
- Repo skeleti, `pyproject.toml` (versiyalar qotirilgan), ruff/mypy/pytest, pre-commit, CI.
- Docker: bot (Python 3.14) + PostgreSQL 18.
- Minimal bot: sozlamalar, JSON log, DB ulanish tekshiruvi, /start.
- `CLAUDE.md`, 5 ta subagent (`.claude/agents/`).
- `docs/BUSINESS_RULES.md` qoralamasi va boshqa hujjatlar skeleti.
