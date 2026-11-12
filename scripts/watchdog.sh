#!/usr/bin/env bash
# Bot ishlayaptimi? (master 9.6). Backup konteynerida har 5 daqiqada ishlaydi — bot'dan MUSTAQIL.
# Bot har daqiqa bot_heartbeat ni yangilaydi. 10 daqiqadan beri yangilanmasa — adminlarga xabar (bir marta),
# qayta ishga tushsa — "tiklandi" xabari.
set -Eeuo pipefail
: "${POSTGRES_HOST:?}" "${POSTGRES_USER:?}" "${POSTGRES_PASSWORD:?}" "${POSTGRES_DB:?}"
export PGPASSWORD="$POSTGRES_PASSWORD"
PG=(-h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB")
STATE="${BACKUP_DIR:-/backups}/.watchdog_down"

notify() {
    [ -n "${BOT_TOKEN:-}" ] || return 0
    local chat
    for chat in $( { psql "${PG[@]}" -tAc "SELECT telegram_id FROM users WHERE role='admin' AND NOT is_blocked" 2>/dev/null || true
                     tr ',' '\n' <<<"${ADMIN_TELEGRAM_IDS:-}"; } | tr -d ' ' | grep -E '^[0-9]+$' | sort -u); do
        printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$BOT_TOKEN" \
            | curl -sS --max-time 30 -o /dev/null -K - --form-string "chat_id=$chat" --form-string "text=$1" || true
    done
}

AGE="$(psql "${PG[@]}" -tAc "SELECT coalesce(extract(epoch FROM now() - beat_at)::int, 999999) FROM bot_heartbeat WHERE id = 1" 2>/dev/null || echo "")"
if [ -z "$AGE" ]; then AGE=999999; fi   # jadval bo'sh yoki baza javob bermayapti
if [ "$AGE" -gt 600 ]; then
    if [ ! -f "$STATE" ]; then
        date +%s >"$STATE"
        notify "🚨 Bot ishlamayapti (so'nggi signal $((AGE / 60)) daqiqa oldin). Server/Docker'ni tekshiring: docs/RUNBOOK.md"
    fi
elif [ -f "$STATE" ]; then
    rm -f "$STATE"
    notify "✅ Bot yana ishlayapti."
fi
