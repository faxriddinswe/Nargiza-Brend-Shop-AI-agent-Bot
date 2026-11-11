"""Stage 8: technical category 'eski daftar' (inactive) for debts imported from the paper notebook.

The notebook does not record what was bought, so an imported debt has ONE item of this category (Q-19: all imported
debts go to the shop section). The category is inactive: it is never offered to staff, never counted in stock or reports.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO categories (section_id, name, is_active) "
            "SELECT id, 'eski daftar', false FROM sections WHERE code = 'shop'"
        )
    )


def downgrade() -> None:
    op.execute("UPDATE categories SET is_active = false WHERE name = 'eski daftar'")
