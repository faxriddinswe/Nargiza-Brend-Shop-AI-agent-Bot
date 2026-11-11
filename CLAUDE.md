# CLAUDE.md — Nargiza Brend bot

To'liq talablar: `NARGIZA_BREND_MASTER_PROMPT.md`. Tasdiqlangan qoidalar: `docs/BUSINESS_RULES.md` (qoida raqamlari: BR-xxx).

## Muloqot
- Faxriddin bilan o'zbek tilida (lotin). Kod, o'zgaruvchi, fayl nomlari — ingliz tilida. Bot matnlari — o'zbek (lotin), faqat `bot/texts/` ichida.
- Faxriddin o'rganyapti: har bir muhim qarorni qisqa tushuntir (nima va nega).
- Biznes qoida noaniq bo'lsa — taxmin qilma, to'xta va so'ra.

## Ish tartibi
- Bosqichma-bosqich (master prompt 14-bo'lim). Bosqich oxirida hisobot: ✅ 🧪 ⚠️ ❓ ➡️ — va tasdiqni kut.
- Har bosqich = alohida commit(lar). Bosqich tugashidan oldin `business-logic-reviewer` va `security-reviewer` agentlarini ishga tushir.
- Kutubxona API'larini o'ylab topma — joriy rasmiy hujjat yoki o'rnatilgan kod manbasidan tekshir.
- Qaytarib bo'lmaydigan amallar (ma'lumot o'chirish, deploy, prod migratsiya) — avval so'ra.

## Qat'iy texnik qoidalar
- Pul — butun son (so'm), `BIGINT`/`int`. Hech qachon `float`.
- Qoldiqlar saqlanmaydi — yozuvlardan hisoblanadi.
- Hech narsa o'chirilmaydi: soft delete (`deleted_at`, `deleted_by`).
- Har bir biznes amal — bitta tranzaksiya + audit log + idempotentlik kaliti.
- Yozuv bo'limi tovar turiga qarab aniqlanadi, kim aytganiga qarab emas (`services/routing.py`).
- AI hisob qilmaydi va ruxsat hal qilmaydi — faqat kod.
- `services/` Telegram va AI'ni bilmaydi. Handler va AI dispatcher faqat service'larni chaqiradi.
- Maxfiy qiymatlar faqat `.env` da; log'ga token, parol, telefon, mijoz ismi tushmaydi.
- Dev/test — faqat soxta ma'lumot.
- Vaqtlar `timestamptz` (UTC), ko'rsatishda `Asia/Tashkent`.

## Buyruqlar
```bash
.venv/bin/pip install -e ".[dev]"      # o'rnatish
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy bot tests
.venv/bin/pytest
docker compose up --build              # bot + postgres
```

## Versiyalar
Python 3.14 (Docker va lokal), Postgres 18. Kutubxonalar `pyproject.toml` da qotirilgan.
aiogram 3.31 → pydantic `<2.14` (shuning uchun 2.13.5).
