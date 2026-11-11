# Ma'lumotlar modeli

> Holat: skelet. 1-bosqichda `architect` bilan yakunlanadi va ER-diagramma qo'shiladi.
> Boshlang'ich ro'yxat — master prompt 12-bo'lim.

## Umumiy qoidalar

- Pul: `BIGINT` (so'm), `CHECK (amount > 0)`.
- Vaqt: `timestamptz`, UTC'da saqlanadi, `Asia/Tashkent` da ko'rsatiladi.
- Soft delete: `deleted_at`, `deleted_by` — hech narsa `DELETE` qilinmaydi.
- Qoldiqlar saqlanmaydi — yozuvlardan hisoblanadi.
- Telefon: o'chirilmaganlar orasida unique (partial unique index `WHERE deleted_at IS NULL`).
- Har bir jadvalda `created_at`, `created_by`.

## Jadvallar (reja)

`users`, `staff_profiles`, `sections`, `categories`, `customers`, `debts`, `debt_items`,
`payments`, `payment_allocations`, `sales`, `sale_items`, `returns`, `stock_movements`,
`broadcasts`, `broadcast_recipients`, `reminders_log`, `settings`, `audit_log`,
`idempotency_keys`, `ai_calls`.

## ER-diagramma

_1-bosqichda._
