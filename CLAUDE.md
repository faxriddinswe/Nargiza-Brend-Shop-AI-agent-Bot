# CLAUDE.md — Nargiza Brend bot

Full requirements (Uzbek): `NARGIZA_BREND_MASTER_PROMPT.md`. Approved rules: `docs/BUSINESS_RULES.md` (rule IDs `BR-xxx`).

## Communication
- Talk to the owner (Faxriddin) in **Uzbek (Latin script)**. Code, identifiers, file names and repo docs — English.
  Bot texts — Uzbek (Latin), only inside `bot/texts/`. `docs/USER_GUIDE_STAFF.md` stays in Uzbek (it is for the family).
- The owner is learning backend development: briefly explain every important decision (what and why).
- If a business rule is ambiguous — stop and ask. Never guess.

## Workflow
- Work stage by stage (master prompt §14). End each stage with a report (✅ 🧪 ⚠️ ❓ ➡️) and wait for approval.
- One stage = separate commit(s). Before finishing a stage run the `business-logic-reviewer` and `security-reviewer` agents.
- Never invent library APIs — check the official docs or the installed source.
- Ask before irreversible actions (deleting data, deploying, production migrations, force pushes, history rewrites).

## Privacy (public repo)
- Never commit real names of family members, phone numbers, emails or customer data. Docs use pseudonyms
  (Botir aka, Nodira opa, Nilufar opa). Real staff are entered in the bot by the admin.
- Secrets only in `.env`. Tests and dev use fake data only.

## Hard technical rules
- Money is an integer (so'm): `BIGINT` / `int`. Never `float`.
- Balances are computed from records, never stored.
- Nothing is deleted: soft delete (`deleted_at`, `deleted_by`). `DELETE` is blocked by triggers.
- Every business action = one transaction (`bot/db/session.py: uow`) with an actor; audit is written by a trigger.
- The section of a record is determined by the product category, not by who wrote it.
- AI never calculates and never decides permissions — code does.
- `services/` never imports aiogram or AI code. Handlers and the AI dispatcher only call services.
- No tokens, passwords, phone numbers or customer names in logs (`mask_phone`, `hide_parameters=True`).
- Times are `timestamptz` (UTC) in the DB, displayed in `Asia/Tashkent`.
- The bot connects as the restricted `nargiza_app` role; migrations and backups use the owner role.

## Commands
```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy bot tests
.venv/bin/pytest                                   # needs Docker for integration tests
docker compose run --rm bot alembic upgrade head   # migrations (owner role)
docker compose up -d --build                       # bot + postgres + backup
```

## Versions
Python 3.14 (Docker and local), PostgreSQL 18.6. Libraries pinned in `pyproject.toml`.
aiogram 3.31 requires pydantic `<2.14` (hence 2.13.5). Dev Postgres is exposed on `127.0.0.1:5433`.
