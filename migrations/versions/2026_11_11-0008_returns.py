"""Stage 5b: returns and exchanges.

- payments.kind gains 'return': goods returned against a debt reduce it like a payment, but are neither
  cash (kind 'payment') nor a loss (kind 'write_off') — reports keep the three apart.
- returns / return_items: per-item quantities and refund values (discount spread proportionally).
  value = debt_reduction + cash_refund (CHECK). An exchange is a return plus a new sale in one transaction.
- the original record is never edited: returned quantity is derived from active returns.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.drop_constraint("ck_payments_kind", "payments", type_="check")
    op.create_check_constraint("ck_payments_kind", "payments", "kind IN ('payment', 'write_off', 'return')")

    op.create_table(
        "returns",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("section_id", sa.BigInteger(), sa.ForeignKey("sections.id", name="fk_returns_section_id_sections"), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customers.id", name="fk_returns_customer_id_customers")),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("debt_reduction", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("cash_refund", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("return_payment_id", sa.BigInteger(), sa.ForeignKey("payments.id", name="fk_returns_return_payment_id_payments")),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("cancelled_at", TS),
        sa.Column("cancelled_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_returns_cancelled_by_users")),
        sa.Column("cancel_reason", sa.Text()),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_returns_created_by_users")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_type IN ('sale', 'debt')", name="ck_returns_source_type"),
        sa.CheckConstraint("value > 0 AND debt_reduction >= 0 AND cash_refund >= 0", name="ck_returns_amounts"),
        sa.CheckConstraint("value = debt_reduction + cash_refund", name="ck_returns_split"),
        sa.CheckConstraint("(debt_reduction > 0) = (return_payment_id IS NOT NULL)", name="ck_returns_payment_link"),
        sa.CheckConstraint("status IN ('active', 'cancelled')", name="ck_returns_status"),
        sa.CheckConstraint("(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="ck_returns_cancel_fields"),
    )  # fmt: skip
    op.create_index("ix_returns_source", "returns", ["source_type", "source_id"])
    op.create_index("ix_returns_customer", "returns", ["customer_id"], postgresql_where=sa.text("customer_id IS NOT NULL"))

    op.create_table(
        "return_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("return_id", sa.BigInteger(), sa.ForeignKey("returns.id", name="fk_return_items_return_id_returns"), nullable=False),
        sa.Column("source_item_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), sa.ForeignKey("categories.id", name="fk_return_items_category_id_categories"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("quantity > 0 AND value > 0", name="ck_return_items_positive"),
    )  # fmt: skip
    op.create_index("ix_return_items_return", "return_items", ["return_id"])
    op.create_index("ix_return_items_source", "return_items", ["source_item_id"])

    op.execute(
        "CREATE TRIGGER trg_returns_immutable BEFORE UPDATE ON returns FOR EACH ROW EXECUTE FUNCTION "
        "ledger_immutable('section_id','customer_id','source_type','source_id','value','debt_reduction',"
        "'cash_refund','return_payment_id','return_date','created_by','created_at')"
    )
    op.execute(
        "CREATE TRIGGER trg_return_items_no_update BEFORE UPDATE ON return_items FOR EACH ROW "
        "EXECUTE FUNCTION forbid_delete()"
    )
    for table in ("returns", "return_items"):
        op.execute(
            f"CREATE TRIGGER trg_audit_{table} AFTER INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION audit_trigger('id')"
        )
        op.execute(
            f"CREATE TRIGGER trg_no_delete_{table} BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION forbid_delete()"
        )

    conn = op.get_bind()
    if conn.exec_driver_sql("SELECT 1 FROM pg_roles WHERE rolname = 'nargiza_app'").scalar():
        op.execute("GRANT SELECT, INSERT, UPDATE ON returns TO nargiza_app")
        op.execute("GRANT SELECT, INSERT ON return_items TO nargiza_app")
        op.execute("REVOKE UPDATE ON return_items FROM nargiza_app")
        op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nargiza_app")


def downgrade() -> None:
    for table in ("return_items", "returns"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.drop_constraint("ck_payments_kind", "payments", type_="check")
    op.create_check_constraint("ck_payments_kind", "payments", "kind IN ('payment', 'write_off')")
