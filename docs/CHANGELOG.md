# Changelog

## [Unreleased]
- Documentation translated into English.
- Family member names replaced with pseudonyms for the public repository.
- New categories (migration 0004): kostyum (*suit*) → shop; paypoq (*socks*) and kolgotka (*tights*) → lingerie.
- The persistent menu is shown again when a message is not recognised.

## [0.1.0] — Stage 1 (foundation) — 2026-11-11
- Utils: phone numbers, Cyrillic↔Latin, money amounts (including amounts written in words), periods — 138 unit tests.
- DB: 10 foundation tables; auditing via a Postgres trigger (writes without an actor are rejected); DELETE is forbidden; audit_log is immutable.
- Confirmation cards: idempotent (a single record even on concurrent taps), valid for 30 minutes.
- Registration: contact ownership check, phone-based roles (admin/staff), linking to the customer record.
- Admin panel: add/block/remove staff, statistics, shop photo and location.
- Customer menu: my debt, announcements, about the shop, contact, opt out of promotions.
- Backup: separate container, age encryption, 3-2-1 schedule, daily copy to Telegram; restore and restore test.
- Review fixes: strict grammar for the money parser (no silently wrong amounts); restricted DB role for the bot;
  a blocked staff member cannot relink; when a number moves to another account, customer data is not exposed without admin approval;
  restore.sh made safe (restores into a temporary database first) and restoring onto a new server was tested.

## [0.0.1] — Stage 0 (preparation) — 2026-11-11
- Repository skeleton, `pyproject.toml` (pinned versions), ruff/mypy/pytest, pre-commit, CI.
- Docker: bot (Python 3.14) + PostgreSQL 18.
- Minimal bot: settings, JSON logging, DB connection check, /start.
- `CLAUDE.md`, 5 subagents (`.claude/agents/`).
- Draft of `docs/BUSINESS_RULES.md` and skeletons of the other documents.
