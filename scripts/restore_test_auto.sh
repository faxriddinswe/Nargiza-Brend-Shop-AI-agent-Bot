#!/usr/bin/env bash
# Haftalik AVTOMATIK tiklash testi (master 9.2). Cron: yakshanba 04:30.
# Haftalik backup bilan birga yaratilgan test nusxasi (alohida test kaliti) vaqtinchalik bazaga tiklanadi,
# jadval yozuvlari soni solishtiriladi, natija adminga yuboriladi. Asosiy yopiq kalitga TEGMAYDI.
set -Eeuo pipefail
BASE="${BACKUP_DIR:-/backups}/restore-test"
SELF="$(cd "$(dirname "$0")" && pwd)"
: "${POSTGRES_HOST:?}" "${POSTGRES_USER:?}" "${POSTGRES_PASSWORD:?}" "${POSTGRES_DB:?}"
export PGPASSWORD="$POSTGRES_PASSWORD"
PG=(-h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB")

admin_chats() {
    {
        psql "${PG[@]}" -tAc "SELECT telegram_id FROM users WHERE role='admin' AND NOT is_blocked" 2>/dev/null || true
        tr ',' '\n' <<<"${ADMIN_TELEGRAM_IDS:-}"
    } | tr -d ' ' | grep -E '^[0-9]+$' | sort -u
}
notify() {
    [ -n "${BOT_TOKEN:-}" ] || return 0
    local chat
    for chat in $(admin_chats); do
        printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$BOT_TOKEN" \
            | curl -sS --max-time 60 -o /dev/null -K - --form-string "chat_id=$chat" --form-string "text=$1" || true
    done
}

if [ ! -f "$BASE/latest.dump.age" ] || [ ! -f "$BASE/test.key" ]; then
    notify "⚠️ Haftalik tiklash testi: test nusxasi topilmadi (haftalik backup ishlaganmi?). docs/RUNBOOK.md"
    exit 1
fi
AGE_DAYS=$(( ( $(date +%s) - $(stat -c %Y "$BASE/latest.dump.age") ) / 86400 ))
if [ "$AGE_DAYS" -gt 8 ]; then
    notify "⚠️ Haftalik tiklash testi: test nusxasi $AGE_DAYS kunlik — haftalik backup to'xtab qolgan bo'lishi mumkin."
    exit 1
fi
if OUT="$("$SELF/restore_test.sh" "$BASE/test.key" "$BASE/latest.dump.age" 2>&1)"; then
    notify "✅ Haftalik tiklash testi o'tdi: backup bazaga to'liq tiklandi, jadval yozuvlari soni mos."
else
    notify "❌ Haftalik tiklash testi MUVAFFAQIYATSIZ. Backup'ga ishonib bo'lmaydi! docs/RUNBOOK.md"$'\n'"$(printf '%s' "$OUT" | grep '❌' | head -5)"
    exit 1
fi
