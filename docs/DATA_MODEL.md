# Data Model

> Status: phase 1 tables implemented (migration `0001`). Architect recommendations adopted:
> audit — Postgres trigger; synonyms in a separate table; `idempotency_keys` renamed to `pending_actions`; phone CHECK.
> Some parts of the text below reflect the initial plan — the actual schema is in `bot/db/models.py` and the migration.
> Phase 1 creates the **foundation tables**. Debt/payment tables come in phase 2, sales/stock in phase 5,
> announcements/reminders in phase 7 — each with its own Alembic migration, after its rules are approved.

## General rules

- Money: `BIGINT` (so'm), `CHECK (amount > 0)`. `int` in Python.
- Time: `timestamptz`, `now()` on the server side; displayed in `Asia/Tashkent`.
- Soft delete: `deleted_at timestamptz NULL`, `deleted_by → users.id`. `DELETE` is never used.
- Every business table has: `created_at`, `created_by`, `updated_at`.
- Enums are implemented in Postgres as `text + CHECK` (makes adding new values in a migration easy).
- Audit: the Postgres `audit_trigger()` (SECURITY DEFINER) records every insert/update/soft-delete/restore.
  The actor is set at the start of the transaction via `set_config('app.actor_id'/'app.actor_kind', ..., true)` (`bot/db/session.py: uow`).
  Writes without an actor are rejected. Paths outside the ORM (bulk, psql) also go through the audit.
- DB roles: owner (migrations, backups) and `nargiza_app` (the bot): SELECT/INSERT/UPDATE, no DELETE, read-only on audit_log.

## Phase 1 tables

```mermaid
erDiagram
    users ||--o| staff_profiles : "bog'langan (raqam ulashgach)"
    users ||--o| customers : "bog'langan (raqam mos kelsa)"
    staff_profiles ||--o{ staff_section_owners : ""
    sections ||--o{ staff_section_owners : ""
    sections ||--o{ categories : ""
    users ||--o{ audit_log : "actor"
```

*(Diagram labels: "bog'langan (raqam ulashgach)" = linked (once the number is shared); "bog'langan (raqam mos kelsa)" = linked (if the number matches).)*

### users — Telegram users
| Column | Type | Note |
|---|---|---|
| id | bigint PK | |
| telegram_id | bigint UNIQUE NOT NULL | |
| role | text CHECK in (admin, staff, customer) | default `customer` |
| tg_first_name | text | Name in Telegram (used as a suggestion) |
| phone | text NULL UNIQUE | only a contact the user shared themselves and that was verified, `+998XXXXXXXXX` |
| is_blocked | bool | if blocked by the admin — cannot do anything |
| bot_blocked_at | timestamptz NULL | the user has blocked the bot (detected when sending) |
| ads_opt_out | bool | has turned off promotions |
| script_pref | text CHECK in (latn, cyrl) | default `latn` |
| consent_at | timestamptz NULL | when the consent text was shown |
| created_at, updated_at | timestamptz | |

### staff_profiles — staff (added by the admin via phone number)
| Column | Type | Note |
|---|---|---|
| id | bigint PK | |
| phone | text NOT NULL | number entered by the admin |
| user_id | FK users NULL UNIQUE | linked when they share their number |
| display_name | text NOT NULL | "Nodira opa" |
| is_active | bool | `false` when removed from staff |
| created_by, created_at, updated_at, deleted_at, deleted_by | | |

Partial unique: `phone WHERE deleted_at IS NULL`.
The role is stored in `users.role` (single source of truth); `staff_profiles` holds information about the staff member.

### staff_section_owners
`staff_id → staff_profiles`, `section_id → sections`, PK (staff_id, section_id). Used for section-owner notifications (BR-026).

### sections
`id`, `code` UNIQUE (`shop`, `lingerie`), `name`, `card_number` NULL, `card_holder` NULL. Seeded in the migration.

### categories — product categories
| Column | Type | Note |
|---|---|---|
| id | bigint PK | |
| section_id | FK sections NOT NULL | |
| name | text NOT NULL | "ko'ylak" (dress) |
| low_stock_threshold | int NULL CHECK ≥ 0 | |
| is_active | bool | |

Unique: `lower(name)`, `(id, section_id)` (for a composite FK in phase 2). Seed — BUSINESS_RULES 3.1 (pijama, xalat → shop).

### category_synonyms
`id`, `category_id → categories`, `synonym` UNIQUE (in `search_key()` form). A given word belongs to only one category.

### customers — customers (the notebook)
| Column | Type | Note |
|---|---|---|
| id | bigint PK | |
| name | text NOT NULL | "Umida" |
| search_name | text NOT NULL | Latin script, lowercase, apostrophes normalised (for search) |
| phone | text NULL | `+998XXXXXXXXX` |
| phone_missing | bool GENERATED (`phone IS NULL`) STORED | |
| address_form | text CHECK in (opa, aka) | |
| note | text NULL | "Shahlo opaning qizi" (*"Shahlo opa's daughter"*) |
| user_id | FK users NULL | linked after registration |
| created_by, created_at, updated_at, deleted_at, deleted_by | | |

Partial unique: `phone WHERE deleted_at IS NULL`; `user_id WHERE deleted_at IS NULL`.
Index: `pg_trgm` GIN on `search_name` (for fuzzy search, used in phase 2).

### settings — key-value
`key` text PK, `value` jsonb NOT NULL, `updated_by`, `updated_at`. Examples: `shop.photo_file_id`, `shop.location`,
`schedule.weekly_day_off` (null), `reminders.time`.

### audit_log
| Column | Type |
|---|---|
| id | bigint PK |
| actor_id | FK users NULL (NULL = system, e.g. the scheduler) |
| action | text CHECK in (insert, update, soft_delete, restore) |
| table_name | text |
| actor_kind | text CHECK in (user, system, migration) |
| record_id | text (composite key `1:2`) |
| old | jsonb NULL |
| new | jsonb NULL |
| at | timestamptz |

Append-only; the application DB user is not granted UPDATE/DELETE on `audit_log` (in phase 9).

### pending_actions
| Column | Type | Note |
|---|---|---|
| key | text PK | assigned when the confirmation card is created |
| user_id | FK users | |
| action | text | |
| status | text CHECK in (pending, done) | |
| result | jsonb NULL | result (returned again on a repeated press) |
| created_at, completed_at | timestamptz | |

On confirmation: `INSERT ... ON CONFLICT DO NOTHING` + `SELECT ... FOR UPDATE` — a second press waits for the first
to finish and receives the ready result. All of this happens in **a single transaction** together with the business action.

## Later phases (plan)
- 2: `debts`, `debt_items`, `payments` (kind: payment/write_off), `payment_allocations`, `debt_adjustments`.
- 5: `sales`, `sale_items`, `returns`, `stock_movements`.
- 7: `broadcasts`, `broadcast_recipients`, `reminders_log`.
- 3: `ai_calls`.
