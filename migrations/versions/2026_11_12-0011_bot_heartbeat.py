"""Stage 9: bot_heartbeat — one row the bot refreshes every minute; the separate backup container watches it
and tells the admins if the bot stops (master 9.6). Operational data: no audit trigger (it would log 1440 rows a day).

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bot_heartbeat",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("beat_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_bot_heartbeat_single"),
    )  # fmt: skip
    conn = op.get_bind()
    if conn.exec_driver_sql("SELECT 1 FROM pg_roles WHERE rolname = 'nargiza_app'").scalar():
        op.execute("GRANT SELECT, INSERT, UPDATE ON bot_heartbeat TO nargiza_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bot_heartbeat")
