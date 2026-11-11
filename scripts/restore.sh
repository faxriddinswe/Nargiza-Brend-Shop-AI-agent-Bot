#!/usr/bin/env bash
# Backup'dan tiklash. Yo'riqnoma: docs/RUNBOOK.md
#
#   restore.sh <fayl.dump.age> <age-yopiq-kalit-fayli> <maqsad_baza> [--replace-main]
#
# Xavfsizlik:
# - Har doim avval VAQTINCHALIK bazaga tiklanadi. Xato bo'lsa — vaqtinchalik baza o'chiriladi,
#   hech narsa buzilmaydi.
# - Asosiy bazani almashtirish (--replace-main + "HA" tasdig'i): eski baza O'CHIRILMAYDI,
#   `<nom>_old_<vaqt>` deb qayta nomlanadi; tiklangan baza uning o'rniga qo'yiladi.
# - Yopiq kalit faqat tiklash vaqtida kerak; ishdan keyin serverdan o'chiring.
set -Eeuo pipefail

FILE="${1:?backup fayli}"
IDENTITY="${2:?age yopiq kalit fayli}"
TARGET="${3:?maqsad baza nomi}"
MODE="${4:-}"

: "${POSTGRES_HOST:?}" "${POSTGRES_USER:?}" "${POSTGRES_PASSWORD:?}" "${POSTGRES_DB:?}"
export PGPASSWORD="$POSTGRES_PASSWORD"
CONN=(-h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER")
psql_admin() { psql "${CONN[@]}" -d postgres -v ON_ERROR_STOP=1 -qtA "$@"; }

[ -f "$FILE" ] || { echo "Fayl topilmadi: $FILE" >&2; exit 1; }
[ -f "$IDENTITY" ] || { echo "Kalit topilmadi: $IDENTITY" >&2; exit 1; }
[[ "$TARGET" =~ ^[a-z_][a-z0-9_]{0,40}$ ]] || { echo "Baza nomi: kichik lotin harf, raqam, _" >&2; exit 1; }
[[ "$POSTGRES_DB" =~ ^[a-z_][a-z0-9_]{0,40}$ ]] || { echo "POSTGRES_DB nomi noto'g'ri" >&2; exit 1; }

db_exists() { [ -n "$(psql_admin -c "SELECT 1 FROM pg_database WHERE datname='$1'")" ]; }

REPLACE_MAIN=0
if [ "$TARGET" = "$POSTGRES_DB" ]; then
    if [ "$MODE" != "--replace-main" ]; then
        echo "Asosiy bazaga ($POSTGRES_DB) tiklash uchun --replace-main kerak. Avval boshqa nomga tiklab tekshiring." >&2
        exit 1
    fi
    REPLACE_MAIN=1
elif db_exists "$TARGET"; then
    echo "'$TARGET' bazasi allaqachon bor — boshqa nom tanlang." >&2
    exit 1
fi

# 0. Ilova roli (yangi serverda yo'q bo'lishi mumkin — dump'dagi GRANT'lar unga tayanadi)
APP_USER="${POSTGRES_APP_USER:-nargiza_app}"
[[ "$APP_USER" =~ ^[a-z_][a-z0-9_]{0,40}$ ]] || { echo "POSTGRES_APP_USER nomi noto'g'ri" >&2; exit 1; }
if [ -z "$(psql_admin -c "SELECT 1 FROM pg_roles WHERE rolname='$APP_USER'")" ]; then
    : "${POSTGRES_APP_PASSWORD:?yangi serverda POSTGRES_APP_PASSWORD kerak}"
    # :'pw' — psql o'zgaruvchisi xavfsiz tirnoqlanadi (faqat stdin'dagi SQL'da ishlaydi, -c da emas)
    echo "CREATE ROLE \"$APP_USER\" LOGIN PASSWORD :'pw' NOSUPERUSER NOCREATEDB NOCREATEROLE;" \
        | psql "${CONN[@]}" -d postgres -v ON_ERROR_STOP=1 -q -v pw="$POSTGRES_APP_PASSWORD"
    echo "Ilova roli yaratildi: $APP_USER"
fi

# 1. Vaqtinchalik bazaga tiklash
STAGING="restore_tmp_$(date +%s)"
cleanup() { psql_admin -c "DROP DATABASE IF EXISTS \"$STAGING\" WITH (FORCE)" >/dev/null 2>&1 || true; }
trap cleanup EXIT

psql_admin -c "CREATE DATABASE \"$STAGING\""
# --disable-triggers: tiklashda audit trigger'lari qayta ishlamasin (audit_log o'zi tiklanadi).
if ! age -d -i "$IDENTITY" "$FILE" \
    | pg_restore "${CONN[@]}" -d "$STAGING" --no-owner --exit-on-error --disable-triggers; then
    echo "❌ Tiklash muvaffaqiyatsiz (kalit noto'g'ri yoki fayl buzilgan). Hech narsa o'zgarmadi." >&2
    exit 1
fi

# Minimal tekshiruv: asosiy jadvallar bor
for t in users customers audit_log; do
    psql "${CONN[@]}" -d "$STAGING" -v ON_ERROR_STOP=1 -qtAc "SELECT 1 FROM $t LIMIT 1" >/dev/null \
        || { echo "❌ '$t' jadvali tiklanmadi." >&2; exit 1; }
done

# 2. Joyiga qo'yish
if [ "$REPLACE_MAIN" -eq 1 ]; then
    echo "⚠️  DIQQAT: asosiy baza '$POSTGRES_DB' tiklangan nusxa bilan almashtiriladi."
    echo "    Eski baza o'chirilmaydi — '${POSTGRES_DB}_old_<vaqt>' nomi bilan saqlanadi."
    echo "    Bot va backup konteynerlarini avval to'xtating: docker compose stop bot"
    read -r -p "Davom etish uchun HA deb yozing: " answer
    [ "$answer" = "HA" ] || { echo "Bekor qilindi."; exit 1; }
    OLD="${POSTGRES_DB}_old_$(date +%Y%m%d_%H%M%S)"
    psql_admin -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$POSTGRES_DB' AND pid <> pg_backend_pid()" >/dev/null
    psql_admin -c "ALTER DATABASE \"$POSTGRES_DB\" RENAME TO \"$OLD\""
    psql_admin -c "ALTER DATABASE \"$STAGING\" RENAME TO \"$POSTGRES_DB\""
    echo "✅ Asosiy baza tiklandi. Eski nusxa: $OLD (tekshirib bo'lgach, admin qo'lda o'chiradi)."
else
    psql_admin -c "ALTER DATABASE \"$STAGING\" RENAME TO \"$TARGET\""
    echo "✅ Tiklandi: $(basename "$FILE") → $TARGET"
fi
trap - EXIT

FINAL="$TARGET"
psql "${CONN[@]}" -d "$FINAL" -tAc \
    "SELECT 'mijozlar: ' || count(*) FROM customers UNION ALL SELECT 'foydalanuvchilar: ' || count(*) FROM users UNION ALL SELECT 'audit yozuvlari: ' || count(*) FROM audit_log"
