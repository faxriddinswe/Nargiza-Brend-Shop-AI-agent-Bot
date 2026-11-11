"""1-bosqich poydevori: foydalanuvchilar, xodimlar, bo'limlar, tovar turlari, mijozlar,
sozlamalar, tasdiqlash kartalari, audit log + trigger'lar + boshlang'ich ma'lumot.

Revision ID: 0001
Revises:
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHONE_CHECK = r"phone ~ '^\+[0-9]{7,15}$'"
TS = sa.DateTime(timezone=True)


def _ts(name: str) -> sa.Column[object]:
    return sa.Column(name, TS, server_default=sa.func.now(), nullable=False)


# ---------------------------------------------------------------- trigger'lar
AUDIT_FN = r"""
CREATE FUNCTION audit_trigger() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_kind   text := nullif(current_setting('app.actor_kind', true), '');
    v_actor  text := nullif(current_setting('app.actor_id', true), '');
    v_old    jsonb;
    v_new    jsonb;
    v_action text;
    v_id     text;
BEGIN
    -- Kim qilgani noma'lum yozuv — rad etiladi (audit'siz yozish mumkin emas).
    IF v_kind IS NULL THEN
        RAISE EXCEPTION 'audit: app.actor_kind o''rnatilmagan (jadval %)', TG_TABLE_NAME;
    END IF;
    IF v_kind = 'user' AND v_actor IS NULL THEN
        RAISE EXCEPTION 'audit: user aktor uchun app.actor_id kerak (jadval %)', TG_TABLE_NAME;
    END IF;

    IF TG_OP = 'INSERT' THEN
        v_action := 'insert';
        v_new := to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        v_old := to_jsonb(OLD);
        v_new := to_jsonb(NEW);
        IF v_old = v_new THEN
            RETURN NULL;  -- hech narsa o'zgarmadi
        END IF;
        v_action := 'update';
        IF v_new ? 'deleted_at' THEN
            IF v_old->>'deleted_at' IS NULL AND v_new->>'deleted_at' IS NOT NULL THEN
                v_action := 'soft_delete';
            ELSIF v_old->>'deleted_at' IS NOT NULL AND v_new->>'deleted_at' IS NULL THEN
                v_action := 'restore';
            END IF;
        END IF;
    ELSE
        v_action := 'delete';
        v_old := to_jsonb(OLD);
    END IF;

    -- Yozuv kaliti: trigger argumentlarida berilgan ustunlar (kompozit PK uchun "1:2")
    SELECT string_agg(coalesce(v_new, v_old)->>col, ':' ORDER BY ord)
      INTO v_id
      FROM unnest(TG_ARGV) WITH ORDINALITY AS t(col, ord);

    INSERT INTO audit_log (actor_id, actor_kind, action, table_name, record_id, old, new)
    VALUES (v_actor::bigint, v_kind, v_action, TG_TABLE_NAME, v_id, v_old, v_new);
    RETURN NULL;
END $$;
"""

FORBID_DELETE_FN = r"""
CREATE FUNCTION forbid_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% jadvalidan o''chirish taqiqlangan — soft delete (deleted_at) ishlating', TG_TABLE_NAME;
END $$;
"""

AUDIT_IMMUTABLE_FN = r"""
CREATE FUNCTION audit_log_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log o''zgartirilmaydi va o''chirilmaydi';
END $$;
"""

# jadval -> audit kaliti ustunlari
AUDITED: dict[str, tuple[str, ...]] = {
    "users": ("id",),
    "sections": ("id",),
    "staff_profiles": ("id",),
    "staff_section_owners": ("staff_id", "section_id"),
    "categories": ("id",),
    "category_synonyms": ("id",),
    "customers": ("id",),
    "settings": ("key",),
}
# Bu jadvallarda DELETE butunlay taqiqlangan (soft delete yoki is_active ishlatiladi)
NO_DELETE = ("users", "sections", "staff_profiles", "categories", "customers", "settings")


def add_audit_trigger(table: str, key_cols: Sequence[str]) -> None:
    """Keyingi migratsiyalarda yangi jadvallar uchun ham shu helper ishlatiladi."""
    args = ", ".join(f"'{c}'" for c in key_cols)
    op.execute(
        f"CREATE TRIGGER trg_audit_{table} AFTER INSERT OR UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION audit_trigger({args})"
    )


def add_no_delete_trigger(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER trg_no_delete_{table} BEFORE DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION forbid_delete()"
    )


# ------------------------------------------------------- boshlang'ich ma'lumot
SECTIONS = [("shop", "Do'kon"), ("lingerie", "Ichki kiyim")]

# (bo'lim, nomi, sinonimlar — search_key() ko'rinishida: lotin, kichik, apostrofsiz)
CATEGORIES: list[tuple[str, str, list[str]]] = [
    ("shop", "ko'ylak", ["koylak", "platye", "plate"]),
    ("shop", "yubka", ["yubka"]),
    ("shop", "shim", ["shim", "bryuki", "jinsi", "jins"]),
    ("shop", "kofta", ["kofta", "sviter", "jemper"]),
    ("shop", "bluzka", ["bluzka", "bluza"]),
    ("shop", "kurtka/palto", ["kurtka", "palto", "plash", "puxovik"]),
    ("shop", "oyoq kiyim", ["oyoq kiyim", "tufli", "poyabzal", "krossovka", "etik", "botinka", "shippak", "sandal", "tapochka"]),
    ("shop", "sumka", ["sumka", "sumkacha"]),
    ("shop", "aksessuar", ["aksessuar", "hamyon", "kamar", "remen"]),
    ("shop", "pijama", ["pijama", "pijamka"]),
    ("shop", "xalat", ["xalat", "halat"]),
    ("lingerie", "ichki kiyim", ["ichki kiyim", "lifchik", "byustgalter", "trusik", "trusi", "belye"]),
]  # fmt: skip


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.Text(), server_default="customer", nullable=False),
        sa.Column("tg_first_name", sa.Text()),
        sa.Column("phone", sa.Text()),
        sa.Column("phone_verified_at", TS),
        sa.Column("is_blocked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("bot_blocked_at", TS),
        sa.Column("ads_opt_out", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("script_pref", sa.Text(), server_default="latn", nullable=False),
        sa.Column("consent_at", TS),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint("role IN ('admin', 'staff', 'customer')", name="ck_users_role"),
        sa.CheckConstraint("script_pref IN ('latn', 'cyrl')", name="ck_users_script_pref"),
        sa.CheckConstraint(PHONE_CHECK, name="ck_users_phone_format"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
    )

    op.create_table(
        "sections",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("card_number", sa.Text()),
        sa.Column("card_holder", sa.Text()),
        sa.UniqueConstraint("code", name="uq_sections_code"),
    )

    op.create_table(
        "staff_profiles",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="fk_staff_profiles_user_id_users"),
        ),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="fk_staff_profiles_created_by_users"),
        ),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", TS),
        sa.Column(
            "deleted_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="fk_staff_profiles_deleted_by_users"),
        ),
        sa.CheckConstraint(PHONE_CHECK, name="ck_staff_profiles_phone_format"),
        sa.UniqueConstraint("user_id", name="uq_staff_profiles_user_id"),
    )
    op.create_index(
        "uq_staff_profiles_phone_active", "staff_profiles", ["phone"], unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )  # fmt: skip

    op.create_table(
        "staff_section_owners",
        sa.Column("staff_id", sa.BigInteger(), sa.ForeignKey("staff_profiles.id", name="fk_staff_section_owners_staff_id_staff_profiles"), primary_key=True),
        sa.Column("section_id", sa.BigInteger(), sa.ForeignKey("sections.id", name="fk_staff_section_owners_section_id_sections"), primary_key=True),
    )  # fmt: skip

    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("section_id", sa.BigInteger(), sa.ForeignKey("sections.id", name="fk_categories_section_id_sections"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("low_stock_threshold", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.UniqueConstraint("id", "section_id", name="uq_categories_id_section"),
        sa.CheckConstraint("low_stock_threshold IS NULL OR low_stock_threshold >= 0", name="ck_categories_threshold"),
    )  # fmt: skip
    op.create_index("uq_categories_name_lower", "categories", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "category_synonyms",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("category_id", sa.BigInteger(), sa.ForeignKey("categories.id", name="fk_category_synonyms_category_id_categories"), nullable=False),
        sa.Column("synonym", sa.Text(), nullable=False),
        sa.UniqueConstraint("synonym", name="uq_category_synonyms_synonym"),
    )  # fmt: skip

    op.create_table(
        "customers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("search_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text()),
        sa.Column("phone_missing", sa.Boolean(), sa.Computed("phone IS NULL", persisted=True), nullable=False),
        sa.Column("address_form", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_customers_user_id_users")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_customers_created_by_users")),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", TS),
        sa.Column("deleted_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_customers_deleted_by_users")),
        sa.CheckConstraint("address_form IN ('opa', 'aka')", name="ck_customers_address_form"),
        sa.CheckConstraint(PHONE_CHECK, name="ck_customers_phone_format"),
    )  # fmt: skip
    op.create_index(
        "uq_customers_phone_active",
        "customers",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_customers_user_active",
        "customers",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_customers_search_name_trgm", "customers", ["search_name"],
        postgresql_using="gin", postgresql_ops={"search_name": "gin_trgm_ops"},
    )  # fmt: skip

    op.create_table(
        "settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_settings_updated_by_users")),
        _ts("updated_at"),
    )  # fmt: skip

    op.create_table(
        "pending_actions",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_pending_actions_user_id_users"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("result", postgresql.JSONB()),
        _ts("created_at"),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("completed_at", TS),
        sa.CheckConstraint("status IN ('open', 'done', 'cancelled', 'expired')", name="ck_pending_actions_status"),
    )  # fmt: skip

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id", name="fk_audit_log_actor_id_users")),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("record_id", sa.Text(), nullable=False),
        sa.Column("old", postgresql.JSONB()),
        sa.Column("new", postgresql.JSONB()),
        _ts("at"),
        sa.CheckConstraint("action IN ('insert', 'update', 'soft_delete', 'restore', 'delete')", name="ck_audit_log_action"),
        sa.CheckConstraint("actor_kind IN ('user', 'system', 'migration')", name="ck_audit_log_actor_kind"),
    )  # fmt: skip
    op.create_index("ix_audit_log_table_record", "audit_log", ["table_name", "record_id"])
    op.create_index("ix_audit_log_at", "audit_log", ["at"])

    # --- trigger'lar
    op.execute(AUDIT_FN)
    op.execute(FORBID_DELETE_FN)
    op.execute(AUDIT_IMMUTABLE_FN)
    for table, cols in AUDITED.items():
        add_audit_trigger(table, cols)
    for table in NO_DELETE:
        add_no_delete_trigger(table)
    op.execute(
        "CREATE TRIGGER trg_audit_log_immutable BEFORE UPDATE OR DELETE ON audit_log "
        "FOR EACH ROW EXECUTE FUNCTION audit_log_immutable()"
    )
    op.execute(
        "CREATE TRIGGER trg_audit_log_no_truncate BEFORE TRUNCATE ON audit_log "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_log_immutable()"
    )

    # --- boshlang'ich ma'lumot (audit'da actor_kind='migration' bo'lib yoziladi)
    conn = op.get_bind()
    for code, name in SECTIONS:
        conn.execute(
            sa.text("INSERT INTO sections (code, name) VALUES (:c, :n)"), {"c": code, "n": name}
        )
    for section, name, synonyms in CATEGORIES:
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
    # Production'da downgrade ishlatilmaydi (ma'lumot yo'qoladi) — faqat dev/test uchun.
    for table in (
        "audit_log", "pending_actions", "settings", "customers", "category_synonyms",
        "categories", "staff_section_owners", "staff_profiles", "sections", "users",
    ):  # fmt: skip
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for fn in ("audit_trigger", "forbid_delete", "audit_log_immutable"):
        op.execute(f"DROP FUNCTION IF EXISTS {fn}()")
