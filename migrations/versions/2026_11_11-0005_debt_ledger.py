"""Debt ledger: debts, debt_items, payments, payment_allocations (Stage 2).

Design: docs/DATA_MODEL.md (reviewed by architect). Money safety is enforced by the database itself:
- composite FKs keep items/allocations inside one section and one customer (BR-021, BR-025);
- ledger rows are immutable except `active -> cancelled` (corrections = cancel + new record, Q-34);
- deferred constraint triggers check at COMMIT: payment = Σ allocations; Σ active allocations ≤ debt
  total (no overpayment, BR-065, with a row lock so concurrent payments cannot both pass);
  regular manual debt total = Σ(quantity × unit_price);
- a debt with active payments cannot be cancelled (BR-104 💡);
- audit + no-DELETE triggers; the app role gets no UPDATE on items/allocations and no DELETE anywhere.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)
APP_ROLE_SQL = "SELECT rolname FROM pg_roles WHERE rolname = 'nargiza_app'"


def _now(name: str) -> sa.Column[object]:
    return sa.Column(name, TS, server_default=sa.func.now(), nullable=False)


def _cancel_cols(table: str) -> list[sa.Column[object]]:
    return [
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("cancelled_at", TS),
        sa.Column("cancelled_by", sa.BigInteger(), sa.ForeignKey("users.id", name=f"fk_{table}_cancelled_by_users")),
        sa.Column("cancel_reason", sa.Text()),
    ]


IMMUTABLE_FN = r"""
CREATE FUNCTION ledger_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_locked text[] := TG_ARGV;   -- columns that may never change
    v_col    text;
BEGIN
    FOREACH v_col IN ARRAY v_locked LOOP
        IF (to_jsonb(OLD)->v_col) IS DISTINCT FROM (to_jsonb(NEW)->v_col) THEN
            RAISE EXCEPTION 'ledger: %.% o''zgartirilmaydi — bekor qilib, yangisini yozing', TG_TABLE_NAME, v_col;
        END IF;
    END LOOP;
    IF OLD.status = 'cancelled' AND NEW.status <> 'cancelled' THEN
        RAISE EXCEPTION 'ledger: bekor qilingan yozuv qayta faollashtirilmaydi (%)', TG_TABLE_NAME;
    END IF;
    IF TG_TABLE_NAME = 'debts' AND OLD.status = 'active' AND NEW.status = 'cancelled' THEN
        IF EXISTS (
            SELECT 1 FROM payment_allocations pa JOIN payments p ON p.id = pa.payment_id
             WHERE pa.debt_id = OLD.id AND p.status = 'active'
        ) THEN
            RAISE EXCEPTION 'ledger: bu qarzga to''lov bor — avval to''lovni bekor qiling (qarz %)', OLD.id;
        END IF;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END $$;
"""

CHECK_ALLOCATION_FN = r"""
CREATE FUNCTION check_allocation() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_total  bigint;
    v_status text;
    v_paid   bigint;
    v_pstat  text;
BEGIN
    -- Row lock first: a concurrent transaction allocating to the same debt waits here,
    -- and the SUM below (new snapshot per statement in READ COMMITTED) sees its committed rows.
    SELECT total_amount, status INTO v_total, v_status FROM debts WHERE id = NEW.debt_id FOR UPDATE;
    SELECT status INTO v_pstat FROM payments WHERE id = NEW.payment_id;
    IF v_status <> 'active' THEN
        RAISE EXCEPTION 'ledger: bekor qilingan qarzga to''lov taqsimlanmaydi (qarz %)', NEW.debt_id;
    END IF;
    IF v_pstat <> 'active' THEN
        RETURN NULL;  -- cancelled in the same transaction: ignored
    END IF;
    SELECT coalesce(sum(pa.amount), 0) INTO v_paid
      FROM payment_allocations pa JOIN payments p ON p.id = pa.payment_id
     WHERE pa.debt_id = NEW.debt_id AND p.status = 'active';
    IF v_paid > v_total THEN
        RAISE EXCEPTION 'ledger: qarzdan ortiq to''lov (qarz %, jami %, to''langan %)', NEW.debt_id, v_total, v_paid;
    END IF;
    RETURN NULL;
END $$;
"""

CHECK_PAYMENT_SUM_FN = r"""
CREATE FUNCTION check_payment_sum() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_amount bigint;
    v_sum    bigint;
    v_id     bigint;
BEGIN
    -- IF (not CASE): plpgsql only resolves NEW.<field> in the branch that actually runs
    IF TG_TABLE_NAME = 'payments' THEN v_id := NEW.id; ELSE v_id := NEW.payment_id; END IF;
    SELECT amount INTO v_amount FROM payments WHERE id = v_id;
    SELECT coalesce(sum(amount), 0) INTO v_sum FROM payment_allocations WHERE payment_id = v_id;
    IF v_sum <> v_amount THEN
        RAISE EXCEPTION 'ledger: to''lov summasi taqsimotga teng emas (to''lov %, summa %, taqsimot %)', v_id, v_amount, v_sum;
    END IF;
    RETURN NULL;
END $$;
"""

CHECK_DEBT_ITEMS_FN = r"""
CREATE FUNCTION check_debt_items() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_id     bigint;
    v_debt   debts%ROWTYPE;
    v_sum    bigint;
    v_count  int;
BEGIN
    IF TG_TABLE_NAME = 'debts' THEN v_id := NEW.id; ELSE v_id := NEW.debt_id; END IF;
    SELECT * INTO v_debt FROM debts WHERE id = v_id;
    SELECT coalesce(sum(quantity::bigint * unit_price), 0), count(*) INTO v_sum, v_count
      FROM debt_items WHERE debt_id = v_id;
    IF v_debt.kind = 'regular' AND v_debt.source = 'manual' AND v_count = 0 THEN
        RAISE EXCEPTION 'ledger: qarzda tovar yo''q (qarz %)', v_id;
    END IF;
    IF v_debt.kind = 'regular' AND v_count > 0 AND v_sum <> v_debt.total_amount THEN
        RAISE EXCEPTION 'ledger: qarz summasi tovarlar yig''indisiga teng emas (qarz %: % ≠ %)', v_id, v_debt.total_amount, v_sum;
    END IF;
    RETURN NULL;
END $$;
"""


def upgrade() -> None:
    op.create_table(
        "debts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customers.id", name="fk_debts_customer_id_customers"), nullable=False),
        sa.Column("section_id", sa.BigInteger(), sa.ForeignKey("sections.id", name="fk_debts_section_id_sections"), nullable=False),
        sa.Column("kind", sa.Text(), server_default="regular", nullable=False),
        sa.Column("sale_id", sa.BigInteger()),  # FK to sales added in Stage 5
        sa.Column("debt_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("total_amount", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.Text(), server_default="manual", nullable=False),
        sa.Column("import_ref", sa.Text()),
        sa.Column("note", sa.Text()),
        *_cancel_cols("debts"),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_debts_created_by_users")),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint("total_amount > 0", name="ck_debts_amount_positive"),
        sa.CheckConstraint("kind IN ('regular', 'sale_remainder')", name="ck_debts_kind"),
        sa.CheckConstraint("(kind = 'sale_remainder') = (sale_id IS NOT NULL)", name="ck_debts_sale_link"),
        sa.CheckConstraint("source IN ('manual', 'import')", name="ck_debts_source"),
        sa.CheckConstraint("status IN ('active', 'cancelled')", name="ck_debts_status"),
        sa.CheckConstraint("(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="ck_debts_cancel_fields"),
        sa.CheckConstraint("due_date IS NULL OR due_date >= debt_date", name="ck_debts_due_after_date"),
        sa.UniqueConstraint("sale_id", name="uq_debts_sale_id"),
        sa.UniqueConstraint("id", "section_id", name="uq_debts_id_section"),
        sa.UniqueConstraint("id", "section_id", "customer_id", name="uq_debts_id_section_customer"),
    )  # fmt: skip
    op.create_index("uq_debts_import_ref", "debts", ["source", "import_ref"], unique=True, postgresql_where=sa.text("import_ref IS NOT NULL"))
    op.create_index("ix_debts_open_fifo", "debts", ["customer_id", "section_id", "debt_date", "id"], postgresql_where=sa.text("status = 'active'"))
    op.create_index("ix_debts_due", "debts", ["due_date"], postgresql_where=sa.text("status = 'active' AND due_date IS NOT NULL"))
    op.create_index("ix_debts_no_due", "debts", ["customer_id"], postgresql_where=sa.text("status = 'active' AND due_date IS NULL"))

    op.create_table(
        "debt_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("debt_id", sa.BigInteger(), nullable=False),
        sa.Column("section_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.CheckConstraint("quantity > 0", name="ck_debt_items_quantity_positive"),
        sa.CheckConstraint("unit_price > 0", name="ck_debt_items_price_positive"),
        sa.ForeignKeyConstraint(["debt_id", "section_id"], ["debts.id", "debts.section_id"], name="fk_debt_items_debt_section"),
        sa.ForeignKeyConstraint(["category_id", "section_id"], ["categories.id", "categories.section_id"], name="fk_debt_items_category_section"),
    )  # fmt: skip
    op.create_index("ix_debt_items_debt", "debt_items", ["debt_id"])
    op.create_index("ix_debt_items_category", "debt_items", ["category_id", "section_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customers.id", name="fk_payments_customer_id_customers"), nullable=False),
        sa.Column("section_id", sa.BigInteger(), sa.ForeignKey("sections.id", name="fk_payments_section_id_sections"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("method", sa.Text()),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), server_default="manual", nullable=False),
        sa.Column("import_ref", sa.Text()),
        sa.Column("note", sa.Text()),
        *_cancel_cols("payments"),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_payments_created_by_users")),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint("kind IN ('payment', 'write_off')", name="ck_payments_kind"),
        sa.CheckConstraint("(kind = 'payment') = (method IS NOT NULL)", name="ck_payments_method_only_for_cash"),
        sa.CheckConstraint("method IS NULL OR method IN ('cash', 'card')", name="ck_payments_method"),
        sa.CheckConstraint("source IN ('manual', 'import')", name="ck_payments_source"),
        sa.CheckConstraint("status IN ('active', 'cancelled')", name="ck_payments_status"),
        sa.CheckConstraint("(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="ck_payments_cancel_fields"),
        sa.UniqueConstraint("id", "section_id", "customer_id", name="uq_payments_id_section_customer"),
    )  # fmt: skip
    op.create_index("uq_payments_import_ref", "payments", ["source", "import_ref"], unique=True, postgresql_where=sa.text("import_ref IS NOT NULL"))
    op.create_index("ix_payments_customer_open", "payments", ["customer_id", "section_id"], postgresql_where=sa.text("status = 'active'"))
    op.create_index("ix_payments_section_day", "payments", ["section_id", "paid_on"])

    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("payment_id", sa.BigInteger(), nullable=False),
        sa.Column("debt_id", sa.BigInteger(), nullable=False),
        sa.Column("section_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payment_allocations_amount_positive"),
        sa.UniqueConstraint("payment_id", "debt_id", name="uq_payment_allocations_payment_debt"),
        sa.ForeignKeyConstraint(["payment_id", "section_id", "customer_id"], ["payments.id", "payments.section_id", "payments.customer_id"], name="fk_payment_allocations_payment"),
        sa.ForeignKeyConstraint(["debt_id", "section_id", "customer_id"], ["debts.id", "debts.section_id", "debts.customer_id"], name="fk_payment_allocations_debt"),
    )  # fmt: skip
    op.execute("CREATE INDEX ix_payment_allocations_debt ON payment_allocations (debt_id) INCLUDE (payment_id, amount)")

    # --- triggers
    for fn in (IMMUTABLE_FN, CHECK_ALLOCATION_FN, CHECK_PAYMENT_SUM_FN, CHECK_DEBT_ITEMS_FN):
        op.execute(fn)
    op.execute(
        "CREATE TRIGGER trg_debts_immutable BEFORE UPDATE ON debts FOR EACH ROW EXECUTE FUNCTION "
        "ledger_immutable('customer_id','section_id','kind','sale_id','debt_date','total_amount','source','import_ref','created_by','created_at')"
    )
    op.execute(
        "CREATE TRIGGER trg_payments_immutable BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION "
        "ledger_immutable('customer_id','section_id','kind','method','amount','paid_on','source','import_ref','created_by','created_at')"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_allocation_check AFTER INSERT ON payment_allocations "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_allocation()"
    )
    for table in ("payments", "payment_allocations"):
        op.execute(
            f"CREATE CONSTRAINT TRIGGER trg_{table}_sum_check AFTER INSERT ON {table} "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_payment_sum()"
        )
    for table in ("debts", "debt_items"):
        op.execute(
            f"CREATE CONSTRAINT TRIGGER trg_{table}_items_check AFTER INSERT ON {table} "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_debt_items()"
        )
    # Items and allocations are written once and never updated
    for table in ("debt_items", "payment_allocations"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} FOR EACH ROW "
            "EXECUTE FUNCTION forbid_delete()"
        )

    for table in ("debts", "debt_items", "payments", "payment_allocations"):
        op.execute(
            f"CREATE TRIGGER trg_audit_{table} AFTER INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION audit_trigger('id')"
        )
        op.execute(
            f"CREATE TRIGGER trg_no_delete_{table} BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION forbid_delete()"
        )

    # --- grants (default privileges gave SELECT/INSERT/UPDATE; tighten)
    conn = op.get_bind()
    if conn.exec_driver_sql(APP_ROLE_SQL).scalar():
        op.execute("REVOKE UPDATE ON debt_items, payment_allocations FROM nargiza_app")
        op.execute("GRANT SELECT, INSERT, UPDATE ON debts, payments TO nargiza_app")
        op.execute("GRANT SELECT, INSERT ON debt_items, payment_allocations TO nargiza_app")
        op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nargiza_app")


def downgrade() -> None:
    for table in ("payment_allocations", "payments", "debt_items", "debts"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for fn in ("ledger_immutable", "check_allocation", "check_payment_sum", "check_debt_items"):
        op.execute(f"DROP FUNCTION IF EXISTS {fn}()")
