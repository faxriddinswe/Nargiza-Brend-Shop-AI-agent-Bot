# Nargiza Brend bot

Oilaviy ayollar kiyim do'koni (Sherbaraka bozori, 82-do'kon) uchun Telegram bot:
qarz daftari, savdo, ombor hisobi va mijozlar bilan aloqa.

## Tez boshlash (dev)

```bash
cp .env.example .env          # qiymatlarni to'ldiring — docs/SETUP_KEYS.md
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pre-commit install
docker compose up --build     # bot + postgres
```

## Tekshiruvlar

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy bot tests
.venv/bin/pytest
```

## Hujjatlar

| Hujjat | Mazmuni |
|---|---|
| [docs/BUSINESS_RULES.md](docs/BUSINESS_RULES.md) | Raqamlangan biznes qoidalar |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Komponentlar va oqimlar |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Jadvallar |
| [docs/DATA_SAFETY.md](docs/DATA_SAFETY.md) | Backup, audit, yaxlitlik |
| [docs/AI_AGENT.md](docs/AI_AGENT.md) | AI tool'lar va eval |
| [docs/SETUP_KEYS.md](docs/SETUP_KEYS.md) | Kalitlarni olish yo'riqnomasi |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Deploy |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Avariya holatlari |
| [docs/USER_GUIDE_STAFF.md](docs/USER_GUIDE_STAFF.md) | Oila uchun qo'llanma |
| [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) | Admin qo'llanmasi |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | O'zgarishlar tarixi |
