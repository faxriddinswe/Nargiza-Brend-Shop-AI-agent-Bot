"""Stage 5a: sales, sale items and the stock ledger.

- sales: total = items_total − discount; paid ≤ total; an unpaid part needs a customer (CHECKs);
  the unpaid part is a linked debt (debts.sale_id, kind 'sale_remainder').
- sale_items: composite FKs keep an item inside its sale's section (BR-021).
- stock_movements: append-only (+/−); stock = Σ quantity per category. Sales, credit goods, returns, stock-in
  and inventory counts all write movements; negative stock is allowed (warned about, BR-093).
- default low-stock threshold 3 (BR-094).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)

CHECK_SALE_ITEMS_FN = r"""
CREATE FUNCTION check_sale_items() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_id    bigint;
    v_total bigint;
    v_sum   bigint;
BEGIN
    IF TG_TABLE_NAME = 'sales' THEN v_id := NEW.id; ELSE v_id := NEW.sale_id; END IF;
    SELECT items_total INTO v_total FROM sales WHERE id = v_id;
    SELECT coalesce(sum(quantity::bigint * unit_price), 0) INTO v_sum FROM sale_items WHERE sale_id = v_id;
    IF v_sum <> v_total THEN
        RAISE EXCEPTION 'sales: tovarlar yig''indisi savdo summasiga teng emas (savdo %: % ≠ %)', v_id, v_total, v_sum;
    END IF;
    RETURN NULL;
END $$;
"""


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("section_id", sa.BigInteger(), sa.ForeignKey("sections.id", name="fk_sales_section_id_sections"), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customers.id", name="fk_sales_customer_id_customers")),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("items_total", sa.BigInteger(), nullable=False),
        sa.Column("discount_amount", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("total_amount", sa.BigInteger(), nullable=False),
        sa.Column("paid_amount", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("cancelled_at", TS),
        sa.Column("cancelled_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_sales_cancelled_by_users")),
        sa.Column("cancel_reason", sa.Text()),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_sales_created_by_users")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("items_total > 0", name="ck_sales_items_positive"),
        sa.CheckConstraint("discount_amount >= 0 AND discount_amount < items_total", name="ck_sales_discount"),
        sa.CheckConstraint("total_amount = items_total - discount_amount", name="ck_sales_total"),
        sa.CheckConstraint("paid_amount >= 0 AND paid_amount <= total_amount", name="ck_sales_paid"),
        sa.CheckConstraint("paid_amount = total_amount OR customer_id IS NOT NULL", name="ck_sales_credit_needs_customer"),
        sa.CheckConstraint("status IN ('active', 'cancelled')", name="ck_sales_status"),
        sa.CheckConstraint("(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="ck_sales_cancel_fields"),
        sa.UniqueConstraint("id", "section_id", name="uq_sales_id_section"),
    )  # fmt: skip
    op.create_index("ix_sales_section_day", "sales", ["section_id", "sale_date"])
    op.create_index("ix_sales_customer", "sales", ["customer_id"], postgresql_where=sa.text("customer_id IS NOT NULL"))

    op.create_table(
        "sale_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("sale_id", sa.BigInteger(), nullable=False),
        sa.Column("section_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.CheckConstraint("quantity > 0", name="ck_sale_items_quantity_positive"),
        sa.CheckConstraint("unit_price > 0", name="ck_sale_items_price_positive"),
        sa.ForeignKeyConstraint(["sale_id", "section_id"], ["sales.id", "sales.section_id"], name="fk_sale_items_sale_section"),
        sa.ForeignKeyConstraint(["category_id", "section_id"], ["categories.id", "categories.section_id"], name="fk_sale_items_category_section"),
    )  # fmt: skip
    op.create_index("ix_sale_items_sale", "sale_items", ["sale_id"])
    op.create_index("ix_sale_items_category", "sale_items", ["category_id", "section_id"])

    op.create_foreign_key("fk_debts_sale_id_sales", "debts", "sales", ["sale_id"], ["id"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("category_id", sa.BigInteger(), sa.ForeignKey("categories.id", name="fk_stock_movements_category_id_categories"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("ref_type", sa.Text()),
        sa.Column("ref_id", sa.BigInteger()),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_stock_movements_created_by_users")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity <> 0", name="ck_stock_movements_nonzero"),
        sa.CheckConstraint(
            "reason IN ('stock_in', 'sale', 'debt', 'return', 'count_adjustment', 'cancel')",
            name="ck_stock_movements_reason",
        ),
    )  # fmt: skip
    op.create_index("ix_stock_movements_category", "stock_movements", ["category_id"])
    op.create_index("ix_stock_movements_ref", "stock_movements", ["ref_type", "ref_id"])

    op.execute(CHECK_SALE_ITEMS_FN)
    op.execute(
        "CREATE TRIGGER trg_sales_immutable BEFORE UPDATE ON sales FOR EACH ROW EXECUTE FUNCTION "
        "ledger_immutable('section_id','customer_id','sale_date','items_total','discount_amount',"
        "'total_amount','paid_amount','created_by','created_at')"
    )
    for table in ("sales", "sale_items"):
        op.execute(
            f"CREATE CONSTRAINT TRIGGER trg_{table}_items_check AFTER INSERT ON {table} "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_sale_items()"
        )
    for table in ("sale_items", "stock_movements"):  # written once, never edited
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} FOR EACH ROW "
            "EXECUTE FUNCTION forbid_delete()"
        )
    for table in ("sales", "sale_items", "stock_movements"):
        op.execute(
            f"CREATE TRIGGER trg_audit_{table} AFTER INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION audit_trigger('id')"
        )
        op.execute(
            f"CREATE TRIGGER trg_no_delete_{table} BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION forbid_delete()"
        )

    op.execute("UPDATE categories SET low_stock_threshold = 3 WHERE low_stock_threshold IS NULL")

    conn = op.get_bind()
    if conn.exec_driver_sql("SELECT 1 FROM pg_roles WHERE rolname = 'nargiza_app'").scalar():
        op.execute("GRANT SELECT, INSERT, UPDATE ON sales TO nargiza_app")
        op.execute("GRANT SELECT, INSERT ON sale_items, stock_movements TO nargiza_app")
        op.execute("REVOKE UPDATE ON sale_items, stock_movements FROM nargiza_app")
        op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nargiza_app")


def downgrade() -> None:
    op.drop_constraint("fk_debts_sale_id_sales", "debts", type_="foreignkey")
    for table in ("stock_movements", "sale_items", "sales"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS check_sale_items()")
