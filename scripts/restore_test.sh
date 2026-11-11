#!/usr/bin/env bash
# Tiklash testi (master 9.2): backup vaqtinchalik bazaga tiklanadi va har bir jadval yozuvlari
# soni backup paytida yozib qo'yilgan son (.counts) bilan solishtiriladi. Keyin vaqtinchalik baza o'chiriladi.
#
#   restore_test.sh <age-yopiq-kalit-fayli> [backup-fayli]
# Fayl berilmasa — eng oxirgi kunlik (yo'q bo'lsa — eng oxirgi istalgan) backup.
set -Eeuo pipefail

IDENTITY="${1:?age yopiq kalit fayli}"
BASE="${BACKUP_DIR:-/backups}"
FILE="${2:-}"
if [ -z "$FILE" ]; then
    FILE="$(find "$BASE/daily" -name '*.dump.age' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)"
    [ -n "$FILE" ] || FILE="$(find "$BASE" -name '*.dump.age' -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
fi
[ -n "$FILE" ] && [ -f "$FILE" ] || { echo "Backup topilmadi" >&2; exit 1; }
[ -f "$FILE.counts" ] || { echo "$FILE.counts yo'q — solishtirib bo'lmaydi" >&2; exit 1; }

: "${POSTGRES_HOST:?}" "${POSTGRES_USER:?}" "${POSTGRES_PASSWORD:?}"
export PGPASSWORD="$POSTGRES_PASSWORD"
CONN=(-h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER")
TMPDB="restore_check_$(date +%s)"

cleanup() { psql "${CONN[@]}" -d postgres -qc "DROP DATABASE IF EXISTS \"$TMPDB\" WITH (FORCE)" >/dev/null 2>&1 || true; }
trap cleanup EXIT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/restore.sh" "$FILE" "$IDENTITY" "$TMPDB" >/dev/null

FAIL=0
while read -r table expected; do
    [ "$expected" = "-" ] && continue
    actual="$(psql "${CONN[@]}" -d "$TMPDB" -tAc "SELECT count(*) FROM \"$table\"")"
    if [ "$actual" = "$expected" ]; then
        echo "✅ $table: $actual"
    else
        echo "❌ $table: kutilgan $expected, tiklangan $actual"
        FAIL=1
    fi
done <"$FILE.counts"

if [ "$FAIL" -eq 0 ]; then
    echo "✅ Tiklash testi muvaffaqiyatli: $(basename "$FILE")"
else
    echo "❌ Tiklash testida farq bor: $(basename "$FILE")"
    exit 1
fi
