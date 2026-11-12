#!/usr/bin/env bash
# Shifrlangan backup (master 9.2). Ishlatish: backup.sh hourly|daily|weekly|monthly
#
# pg_dump (custom format) → to'g'ridan-to'g'ri age bilan shifrlanadi (diskka ochiq dump yozilmaydi).
# Ochiq kalit (BACKUP_AGE_RECIPIENT) serverda; yopiq kalit — FAQAT adminning parol menejeri va qog'ozida.
#
# Kerakli muhit: POSTGRES_HOST POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB BACKUP_AGE_RECIPIENT
# Ixtiyoriy: BACKUP_DIR (/backups), BOT_TOKEN (Telegram xabari), ADMIN_TELEGRAM_IDS
set -Eeuo pipefail
umask 077

KIND="${1:?ishlatish: backup.sh hourly|daily|weekly|monthly}"
case "$KIND" in hourly|daily|weekly|monthly) ;; *) echo "noma'lum tur: $KIND" >&2; exit 2 ;; esac

: "${POSTGRES_HOST:?}" "${POSTGRES_USER:?}" "${POSTGRES_PASSWORD:?}" "${POSTGRES_DB:?}"
: "${BACKUP_AGE_RECIPIENT:?.env faylida BACKUP_AGE_RECIPIENT (age1...) kerak}"

BASE="${BACKUP_DIR:-/backups}"
DIR="$BASE/$KIND"
mkdir -p "$DIR"
TS="$(date +%Y-%m-%d_%H%M%S)"
OUT="$DIR/nargiza_${KIND}_${TS}.dump.age"
TMP="$OUT.partial"

export PGPASSWORD="$POSTGRES_PASSWORD"
PG=(-h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB")

log() { echo "$(date -Iseconds) backup[$KIND] $*"; }

admin_chats() {
    # Bloklanmagan adminlar (bazadan) + zaxira ADMIN_TELEGRAM_IDS
    {
        psql "${PG[@]}" -tAc "SELECT telegram_id FROM users WHERE role='admin' AND NOT is_blocked" 2>/dev/null || true
        tr ',' '\n' <<<"${ADMIN_TELEGRAM_IDS:-}"
    } | tr -d ' ' | grep -E '^[0-9]+$' | sort -u
}

# Token argv'da ko'rinmasligi uchun URL curl'ga stdin (config) orqali beriladi.
tg() {
    local method="$1"; shift
    [ -n "${BOT_TOKEN:-}" ] || return 0
    printf 'url = "https://api.telegram.org/bot%s/%s"\n' "$BOT_TOKEN" "$method" \
        | curl -sS --max-time 120 -o /dev/null -K - "$@" || log "telegram $method xato"
}

notify() {
    local chat
    for chat in $(admin_chats); do
        tg sendMessage --form-string "chat_id=$chat" --form-string "text=$1"
    done
}

fail() {
    trap - ERR
    log "XATO: $1"
    rm -f "$TMP"
    notify "❌ Backup xato ($KIND): $1. Iltimos, tekshiring: docs/RUNBOOK.md"
    exit 1
}
trap 'fail "kutilmagan xato (qator $LINENO)"' ERR

count_of() {
    local exists
    exists="$(psql "${PG[@]}" -tAc "SELECT to_regclass('public.$1') IS NOT NULL")"
    if [ "$exists" = "t" ]; then psql "${PG[@]}" -tAc "SELECT count(*) FROM $1"; else echo "-"; fi
}

# --- 1. Dump + shifrlash (oqim) -------------------------------------------------
log "boshlandi"
pg_dump "${PG[@]}" --format=custom --no-owner | age -r "$BACKUP_AGE_RECIPIENT" -o "$TMP" \
    || fail "pg_dump yoki age ishlamadi"
mv "$TMP" "$OUT"

# --- 2. Tekshiruvlar ------------------------------------------------------------
SIZE="$(stat -c %s "$OUT")"
[ "$SIZE" -gt 100 ] || fail "fayl juda kichik ($SIZE bayt)"

# Jadval yozuvlari soni — tiklash testida solishtirish uchun (shaxsiy ma'lumot emas)
TABLES="$(psql "${PG[@]}" -tAc "SELECT string_agg(tablename, ' ' ORDER BY tablename) FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'")"
: >"$OUT.counts"
for t in $TABLES; do echo "$t $(count_of "$t")" >>"$OUT.counts"; done

WARN=""
PREV="$(find "$DIR" -name '*.dump.age' ! -path "$OUT" -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
if [ -n "$PREV" ]; then
    PREV_SIZE="$(stat -c %s "$PREV")"
    if [ $((SIZE * 2)) -lt "$PREV_SIZE" ]; then
        WARN="⚠️ Hajm keskin kamaydi: $((PREV_SIZE / 1024)) KB → $((SIZE / 1024)) KB. Ma'lumot o'chganmi — tekshiring!"
        log "$WARN"
    fi
fi

# --- 2b. Haftalik: avtomatik tiklash testi uchun ALOHIDA nusxa (faqat serverda, alohida test kaliti bilan) ---
# Asosiy yopiq kalit serverda bo'lmaydi, shuning uchun test uchun alohida kalit juftligi ishlatiladi (docs/DATA_SAFETY.md).
# Bu nusxa serverda bo'lgan ma'lumotning o'zi: jonli bazadan ortiq narsani oshkor qilmaydi; Telegram/Drive'ga YUBORILMAYDI.
if [ "$KIND" = "weekly" ]; then
    TESTDIR="$BASE/restore-test"
    mkdir -p "$TESTDIR"
    if [ ! -f "$TESTDIR/test.key" ]; then
        age-keygen -o "$TESTDIR/test.key" 2>/dev/null
    fi
    TEST_RECIPIENT="$(age-keygen -y "$TESTDIR/test.key")"
    pg_dump "${PG[@]}" --format=custom --no-owner | age -r "$TEST_RECIPIENT" -o "$TESTDIR/latest.dump.age.partial" \
        && mv "$TESTDIR/latest.dump.age.partial" "$TESTDIR/latest.dump.age" \
        && cp "$OUT.counts" "$TESTDIR/latest.dump.age.counts" \
        || log "OGOHLANTIRISH: test nusxasi yaratilmadi"
fi

# --- 3. Eski backup'larni tozalash (3-2-1 jadvali) ------------------------------
case "$KIND" in
    hourly)  KEEP_MIN=$((48 * 60)) ;;       # 48 soat
    daily)   KEEP_MIN=$((30 * 24 * 60)) ;;  # 30 kun
    weekly)  KEEP_MIN=$((92 * 24 * 60)) ;;  # ~3 oy
    monthly) KEEP_MIN=$((366 * 24 * 60)) ;; # 1 yil
esac
find "$DIR" -name 'nargiza_*' -type f -mmin +"$KEEP_MIN" -print -delete | sed 's/^/o'"'"'chirildi: /' || true

log "OK $OUT ($SIZE bayt)"

# --- 4. Kunlik: adminga hisobot + shifrlangan fayl --------------------------------
if [ "$KIND" = "daily" ] || [ -n "$WARN" ]; then
    SIZE_MB="$(awk "BEGIN { printf \"%.2f\", $SIZE / 1048576 }")"
    MSG="✅ Backup OK ($KIND): $(count_of customers) mijoz, $(count_of debts) qarz, $(count_of sales) savdo, hajmi $SIZE_MB MB"
    [ -n "$WARN" ] && MSG="$MSG"$'\n'"$WARN"
    notify "$MSG"
fi
if [ "$KIND" = "daily" ]; then
    # Telegram bot fayl chegarasi — 50 MB
    if [ "$SIZE" -lt $((49 * 1024 * 1024)) ]; then
        for chat in $(admin_chats); do
            tg sendDocument -F "chat_id=$chat" -F "document=@$OUT" --form-string "caption=🔐 Shifrlangan backup: $(basename "$OUT")"
        done
    else
        notify "⚠️ Backup Telegram uchun juda katta ($SIZE bayt) — faqat serverda saqlandi."
    fi
fi
