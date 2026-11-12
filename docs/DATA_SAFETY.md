# Data Safety

> If a debt or sale record is lost, the family loses money. Source: master prompt, section 9.
> Status: write level, backup, restore, nightly integrity check, weekly restore test and watchdog are implemented (phase 9).
> Not enabled by code: Google Drive copy (needs the owner's Google account — guide in RUNBOOK) and external uptime monitoring (needs an account).

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

### Weekly AUTOMATIC restore test (phase 9)
The main private key is never on the server, so the automatic test uses a SEPARATE key pair that exists only for it:
- Every Sunday 03:30 the weekly backup also writes `backups/restore-test/latest.dump.age`, encrypted to a test key
  (`backups/restore-test/test.key`, created automatically on the first weekly run, mode 600). This copy is NOT sent to Telegram/Drive.
- Sunday 04:30 `restore_test_auto.sh` restores it into a temporary database, compares every table's row count with the counts taken at
  dump time and messages the admins: ✅ passed / ❌ failed / ⚠️ copy missing or older than 8 days.
- Why this is acceptable: the copy holds the same data the live database already holds on that server, so it reveals nothing more
  to someone who has the server. The offsite copies (Telegram, Drive) still need the main key, which stays in the password manager and on paper.
- What it proves: the dump is complete, readable and restorable by the same scripts. It does NOT prove that the main private key still works —
  the admin should do a manual restore with the real key (RUNBOOK) at least twice a year.

### Bot watchdog
The bot refreshes `bot_heartbeat` every minute. `watchdog.sh` (backup container, every 5 min, independent of the bot) messages the admins
once if there has been no beat for 10 minutes ("🚨 Bot ishlamayapti") and once when it is back. If the whole server is down nothing can message
you — add a free external uptime check (see RUNBOOK, "External monitoring").

## 3. Integrity check (nightly)
Implemented (`bot/services/integrity.py`, job at 02:00, admins only, once per day). It only reports ids, never changes data:
overpaid debt, payment allocations ≠ amount, payment allocated to a cancelled debt, possible duplicate payment (same customer/amount/day within 60 s),
negative stock, regular debt without items, imported debt total ≠ items, active remainder debt of a cancelled sale.

## 4. Reconciliation with the till
A reminder in the 20:00 report.

## 5. Deployment and migrations
An automatic backup before every deployment/migration; migrations run on staging first.

## 6. Server
Postgres is not exposed externally; named volume; SSH key-only; ufw; fail2ban; automatic security updates; `unless-stopped` + healthcheck; the admin is notified if the bot stops.

## 7. Legal
Consent text is mandatory. Final decision on server location — Faxriddin (legal advice recommended).
