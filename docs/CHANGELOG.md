# Changelog

## [0.8.0] — Stage 9 (data safety, part 2) — 2026-11-12
- Nightly integrity check at 02:00 (`bot/services/integrity.py`): reports impossible records to admins; read-only.
- Weekly AUTOMATIC restore test with a separate test key (`scripts/restore_test_auto.sh`, Sunday 04:30), result messaged to admins.
- Bot watchdog: `bot_heartbeat` (migration 0011) + `scripts/watchdog.sh` in the backup container.
- Guides (disabled until you create accounts): Google Drive copy, external uptime monitoring — docs/RUNBOOK.md.

## [0.7.0] — Stage 8 (old notebook import, typed) — 2026-11-12
- `/daftar`: typed notebook lines → preview (✅ ⚠️ ❓ 🔁) → fix → one-tap save; duplicate check by phone and by identical earlier import.
- Imported debts: shop section, original date, no goods/stock, excluded from "new debt"/turnover; migration 0010.
- Voice messages are off by default (`VOICE_ENABLED=false`).

## [0.6.0] — Stage 7 (reminders and announcements) — 2026-11-11
- Customer debt reminders at 10:00 (2 days before, due day, every 3 days up to 5 times), one message per customer; `reminders_log` prevents duplicates.
- 08:00 staff call list (overdue, no phone, no due date).
- 📢 E'lon: text/photo, segments (everyone / debtors / overdue / one person), preview count, rate-limited queue (~20/s; Telegram allows ~30/s), result summary; history in `broadcasts`.
- Migration 0009.

## [0.5.0] — Stage 6 (reports, Excel, scheduled reports) — 2026-11-11
- Reports per period and section (sales, cash, credit, write-offs, returns, product types), period comparison, payments list.
- Excel export (sales, debtors, stock) with formula-injection protection; AI tools `get_sales_report`, `compare_periods`, `list_payments`, `export_excel`.
- 20:00 daily and monthly (1st, 09:00) reports, Asia/Tashkent; retried if nobody received them.
- 📊 Hisobot button shows today's report.

## [0.4.0] — Stage 5 (sales, stock, returns) — 2026-11-11
- Sales: cash, mixed (cash + linked credit part), agreed-price discount; sale arithmetic in pure, tested functions.
- Stock ledger: stock-in, inventory count, low-stock (default 3), negative stock warned; credit goods leave the stock too.
- Returns and exchanges: debt reduced first, excess refunded in cash; discount spread exactly; partial returns; cancel
  of sales, returns (with guards); AI tools `add_sale`, `add_stock_in`, `stock_count`, `get_stock`, `list_low_stock`, `register_return`.
- Reviews fixed: exact refund shares (no 1-so'm over-refund), linked debts only cancel with their sale, `return`
  payments only with their return, row locks for customer-less sales, customer-less returns never see other customers' purchases.
- 449 automated tests.

## [0.3.0] — Stage 3/4 (AI agent: text and voice) — 2026-11-11
- `ai/` package: provider-neutral `AIProvider`, 12 Pydantic tool schemas, system prompt, `GeminiProvider`
  (google-genai; audio as `audio/ogg`; function calling forced, automatic calling disabled).
- Dispatcher: resolves customers, products (synonyms, Cyrillic, suffixes, light fuzziness), sections, amounts and
  due dates in code; asks with buttons when anything is unclear; creates the same confirmation cards as the
  button flows; permissions checked in code.
- Staff can write or speak freely; conversation memory (last customer, last 3 exchanges, 15 min).
- Read questions: customer debt, search, debtors list, overdue list.
- `ai_calls` log (tokens, latency, estimated cost; no personal data); admin alert when the AI is down.
- Evaluation set (66 phrases) and `scripts/run_eval.py`.
- 348 automated tests (fake model + exact Gemini request shape).

## [0.2.0] — Stage 2 (debt ledger and customers, button-driven) — 2026-11-11
- Database: `debts`, `debt_items`, `payments`, `payment_allocations` with composite foreign keys (section and
  customer isolation), immutable ledger rows (corrections = cancel + new record), deferred constraint triggers
  (no overpayment even with concurrent payments, payment = sum of allocations, debt total = sum of items).
- Services: FIFO / specific-debt allocation, partial and full write-offs, cancellation, balances computed from
  records, customer search (Cyrillic ↔ Latin, typos, phone tail), soft delete and admin restore.
- Telegram: find customer, new customer, write a debt (category → quantity → price → note → due date),
  record a payment or write-off, cancel recent records, delete / restore customers. Every write ends in a
  confirmation card.
- Notifications: the customer is told about debts, payments and corrections (if linked); the section owner is
  told when someone else writes into their section.
- Customer menu "💰 Mening qarzim" now shows real balances per section.
- Fix: balances were `Decimal` (Postgres `SUM`) — money is now always `int`.
- Fix: shop phone corrected to +998 94 511 17 00.

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
