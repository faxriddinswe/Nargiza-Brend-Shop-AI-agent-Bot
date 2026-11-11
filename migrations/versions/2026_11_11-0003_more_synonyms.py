"""Kirill sinonimlari search_key() ko'rinishida yetishmagan: "бельё" → belyo, "трусики" → trusiki.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW = [("ichki kiyim", ["belyo", "trusiki", "byusgalter"])]


def upgrade() -> None:
    conn = op.get_bind()
    for category, synonyms in NEW:
        for syn in synonyms:
            conn.execute(
                sa.text(
                    "INSERT INTO category_synonyms (category_id, synonym) "
                    "SELECT id, :s FROM categories WHERE name = :c "
                    "ON CONFLICT (synonym) DO NOTHING"
                ),
                {"s": syn, "c": category},
            )


def downgrade() -> None:
    conn = op.get_bind()
    for _, synonyms in NEW:
        for syn in synonyms:
            conn.execute(sa.text("DELETE FROM category_synonyms WHERE synonym = :s"), {"s": syn})
