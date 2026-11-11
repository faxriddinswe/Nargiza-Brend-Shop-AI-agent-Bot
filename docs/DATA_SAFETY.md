# Data Safety

> If a debt or sale record is lost, the family loses money. Source: master prompt, section 9.
> Status: part 1 (write level, backup, restore) is working; integrity checks and monitoring — phase 9.

## 1. At the write level
- Each business action is a single transaction.
- Soft delete; balances are computed; money stored as `BIGINT`.
- DB constraints: NOT NULL, FK, CHECK, partial unique.
- An idempotency key on every confirmation.
- Audit log (old/new values as JSONB) — written inside the same transaction.

## 2. Backup (3-2-1)

| Frequency | Retention |
|---|---|
| Hourly | 48 hours |
| Daily 03:00 | 30 days |
| Weekly | 3 months |
| Monthly | 1 year |

`pg_dump -Fc` → encrypted with `age` (public key on the server, private key **only** in a password manager and on paper) →
server disk (separate from the DB volume) + the admin's Telegram (daily) + Google Drive (optional, ❓ Q-24).

Daily to the admin: "✅ Backup OK: N qarz, M savdo, hajmi X MB" (*"✅ Backup OK: N debts, M sales, size X MB"*). If a backup is missing or its size has dropped sharply — a warning.
Weekly restore test — `scripts/restore_test.sh` (each table's row count is compared with the `.counts` taken at backup time).

### Implementation (phase 1)
- A separate `backup` container (postgres:18.6-alpine + age + crond): keeps running even if the bot stops; `pg_dump` matches the server version.
- `pg_dump -Fc | age -r <public key>` — an unencrypted dump is never written to disk. Files are `600`, owned by root.
- Schedule: hourly (:05), daily 03:00, weekly Sunday 03:30, monthly on the 1st at 04:00 (Tashkent time).
- `restore.sh` first restores into a temporary database; when swapping the main database, the old database is not deleted (`_old_<timestamp>`).
- Tested (2026-11-11): backup → restore, row counts of all 10 tables matched; a wrong key was rejected; main-database swap.

### ⚠️ Open issue: weekly AUTOMATIC restore test
Restoring requires the private key, but by rule the private key is not kept on the server. These two requirements conflict.
For now: the test is manual (the admin temporarily places the key, RUNBOOK 5). Options will be reviewed in phase 9
(e.g. an additional layer of encryption with a separate key pair used only for testing).

## 3. Integrity check (nightly)
Negative debt, overpayment, duplicate payment, negative stock, orphaned records → report to the admin.

## 4. Reconciliation with the till
A reminder in the 20:00 report.

## 5. Deployment and migrations
An automatic backup before every deployment/migration; migrations run on staging first.

## 6. Server
Postgres is not exposed externally; named volume; SSH key-only; ufw; fail2ban; automatic security updates; `unless-stopped` + healthcheck; the admin is notified if the bot stops.

## 7. Legal
Consent text is mandatory. Final decision on server location — Faxriddin (legal advice recommended).
