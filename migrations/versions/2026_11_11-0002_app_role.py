"""Ilova uchun alohida, cheklangan DB roli (eng kam huquq tamoyili).

- Migratsiya/backup — egasi (superuser) roli; bot — `POSTGRES_APP_USER` (sukut: nargiza_app).
- Ilova roli: faqat SELECT/INSERT/UPDATE (DELETE faqat bog'lovchi jadvallarda). Trigger'larni
  o'chira olmaydi (jadval egasi emas), audit_log ga to'g'ridan-to'g'ri yoza olmaydi.
- audit_trigger() SECURITY DEFINER — audit_log ga egasi nomidan yozadi.
- actor_kind='migration' faqat superuser sessiyasida ruxsat (ilova o'zini "migratsiya" deb ko'rsata olmaydi).

Parol `.env` dagi POSTGRES_APP_PASSWORD dan olinadi (migratsiya har safar sinxronlaydi).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11
"""

import re
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

READ_WRITE = ("users", "sections", "staff_profiles", "categories", "customers", "settings", "pending_actions")
READ_WRITE_DELETE = ("staff_section_owners", "category_synonyms")
READ_ONLY = ("audit_log", "alembic_version")

AUDIT_FN_SECURE = r"""
CREATE OR REPLACE FUNCTION audit_trigger() RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_kind   text := nullif(current_setting('app.actor_kind', true), '');
    v_actor  text := nullif(current_setting('app.actor_id', true), '');
    v_old    jsonb;
    v_new    jsonb;
    v_action text;
    v_id     text;
BEGIN
    IF v_kind IS NULL THEN
        RAISE EXCEPTION 'audit: app.actor_kind o''rnatilmagan (jadval %)', TG_TABLE_NAME;
    END IF;
    IF v_kind NOT IN ('user', 'system', 'migration') THEN
        RAISE EXCEPTION 'audit: noma''lum actor_kind %', v_kind;
    END IF;
    -- SECURITY DEFINER ichida current_user = egasi; haqiqiy ulangan rol — session_user
    IF v_kind = 'migration' AND NOT (SELECT rolsuper FROM pg_roles WHERE rolname = session_user) THEN
        RAISE EXCEPTION 'audit: migration aktori faqat migratsiya sessiyasida';
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
            RETURN NULL;
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

    SELECT string_agg(coalesce(v_new, v_old)->>col, ':' ORDER BY ord)
      INTO v_id
      FROM unnest(TG_ARGV) WITH ORDINALITY AS t(col, ord);

    INSERT INTO audit_log (actor_id, actor_kind, action, table_name, record_id, old, new)
    VALUES (v_actor::bigint, v_kind, v_action, TG_TABLE_NAME, v_id, v_old, v_new);
    RETURN NULL;
END $$;
"""


def _app_role() -> tuple[str, str]:
    # Testlar config.attributes orqali beradi; aks holda .env (bot.config)
    given = op.get_context().config.attributes.get("app_role")  # type: ignore[union-attr]
    if given is not None:
        user, password = given
    else:
        from bot.config import get_settings

        s = get_settings()
        user, password = s.postgres_app_user, s.postgres_app_password.get_secret_value()
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,40}", user):
        raise RuntimeError("POSTGRES_APP_USER nomi noto'g'ri")
    if len(password) < 16:
        raise RuntimeError("POSTGRES_APP_PASSWORD .env da bo'lishi kerak (kamida 16 belgi)")
    return user, password


def upgrade() -> None:
    user, password = _app_role()
    pw = password.replace("'", "''")
    conn = op.get_bind()
    exists = conn.exec_driver_sql(f"SELECT 1 FROM pg_roles WHERE rolname = '{user}'").scalar()
    verb = "ALTER" if exists else "CREATE"
    conn.exec_driver_sql(
        f"{verb} ROLE {user} LOGIN PASSWORD '{pw}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
    )

    op.execute(f"GRANT CONNECT ON DATABASE {conn.engine.url.database} TO {user}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {user}")
    for t in READ_WRITE:
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {t} TO {user}")
    for t in READ_WRITE_DELETE:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {t} TO {user}")
    for t in READ_ONLY:
        op.execute(f"GRANT SELECT ON {t} TO {user}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {user}")
    # Keyingi migratsiyalardagi yangi jadvallar uchun sukut (DELETE yo'q; maxsus jadvallar qo'lda)
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO {user}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {user}")

    op.execute(AUDIT_FN_SECURE)
    op.execute("REVOKE ALL ON FUNCTION audit_trigger() FROM PUBLIC")


def downgrade() -> None:
    user, _ = _app_role()
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {user}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {user}")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {user}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {user}")
    op.execute(f"REVOKE ALL ON SCHEMA public FROM {user}")
    op.execute("ALTER FUNCTION audit_trigger() SECURITY INVOKER")
