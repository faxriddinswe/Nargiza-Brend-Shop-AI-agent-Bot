"""New product categories confirmed by the owner (2026-11-11).

- kostyum (suit) -> shop
- paypoq (socks), kolgotka (tights) -> lingerie
- ro'mol (headscarf) is not sold -> not added

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (section, name, synonyms in search_key() form: latin, lowercase, no apostrophes)
NEW: list[tuple[str, str, list[str]]] = [
    ("shop", "kostyum", ["kostyum", "kostum", "kostyumcha"]),
    ("lingerie", "paypoq", ["paypoq", "noski", "nosok", "golfi"]),
    ("lingerie", "kolgotka", ["kolgotka", "kolgotki", "kalgotka"]),
]


def upgrade() -> None:
    conn = op.get_bind()
    for section, name, synonyms in NEW:
        cat_id = conn.execute(
            sa.text(
                "INSERT INTO categories (section_id, name) "
                "SELECT id, :n FROM sections WHERE code = :s RETURNING id"
            ),
            {"n": name, "s": section},
        ).scalar_one()
        for syn in synonyms:
            conn.execute(
                sa.text("INSERT INTO category_synonyms (category_id, synonym) VALUES (:c, :s)"),
                {"c": cat_id, "s": syn},
            )


def downgrade() -> None:
    # Categories are deactivated, never deleted (records may reference them).
    conn = op.get_bind()
    for _, name, _ in NEW:
        conn.execute(sa.text("UPDATE categories SET is_active = false WHERE name = :n"), {"n": name})
