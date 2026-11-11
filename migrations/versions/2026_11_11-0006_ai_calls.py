"""AI call log: tokens, latency and estimated cost per call — never the message text or any personal data.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_ai_calls_user_id_users"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("cost_micro_usd", sa.BigInteger()),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("tools", sa.Text()),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_type", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('text', 'voice')", name="ck_ai_calls_kind"),
    )  # fmt: skip
    op.create_index("ix_ai_calls_created", "ai_calls", ["created_at"])
    op.execute(
        "CREATE TRIGGER trg_no_delete_ai_calls BEFORE DELETE ON ai_calls "
        "FOR EACH ROW EXECUTE FUNCTION forbid_delete()"
    )
    conn = op.get_bind()
    if conn.exec_driver_sql("SELECT 1 FROM pg_roles WHERE rolname = 'nargiza_app'").scalar():
        op.execute("GRANT SELECT, INSERT ON ai_calls TO nargiza_app")
        op.execute("REVOKE UPDATE ON ai_calls FROM nargiza_app")
        op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nargiza_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_calls CASCADE")
