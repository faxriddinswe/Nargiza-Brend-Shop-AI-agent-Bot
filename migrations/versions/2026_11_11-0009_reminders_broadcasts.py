"""Stage 7: reminders_log (no duplicate reminders, BR-166) and broadcasts (announcement history, BR-170…173).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "reminders_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("debt_id", sa.BigInteger(), sa.ForeignKey("debts.id", name="fk_reminders_log_debt_id_debts"), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customers.id", name="fk_reminders_log_customer_id_customers"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('before', 'due', 'overdue')", name="ck_reminders_log_kind"),
        sa.CheckConstraint("seq BETWEEN 0 AND 5", name="ck_reminders_log_seq"),
        sa.UniqueConstraint("debt_id", "kind", "seq", name="uq_reminders_log_once"),
    )  # fmt: skip
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_broadcasts_created_by_users"), nullable=False),
        sa.Column("segment", sa.Text(), nullable=False),
        sa.Column("has_photo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recipients", sa.Integer(), nullable=False),
        sa.Column("delivered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("segment IN ('all', 'debtors', 'overdue', 'one')", name="ck_broadcasts_segment"),
    )  # fmt: skip
    for table in ("reminders_log", "broadcasts"):
        op.execute(
            f"CREATE TRIGGER trg_audit_{table} AFTER INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION audit_trigger('id')"
        )
        op.execute(
            f"CREATE TRIGGER trg_no_delete_{table} BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION forbid_delete()"
        )
    op.execute("CREATE TRIGGER trg_reminders_log_no_update BEFORE UPDATE ON reminders_log FOR EACH ROW EXECUTE FUNCTION forbid_delete()")
    conn = op.get_bind()
    if conn.exec_driver_sql("SELECT 1 FROM pg_roles WHERE rolname = 'nargiza_app'").scalar():
        op.execute("GRANT SELECT, INSERT ON reminders_log TO nargiza_app")
        op.execute("GRANT SELECT, INSERT, UPDATE ON broadcasts TO nargiza_app")
        op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nargiza_app")


def downgrade() -> None:
    for table in ("broadcasts", "reminders_log"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
