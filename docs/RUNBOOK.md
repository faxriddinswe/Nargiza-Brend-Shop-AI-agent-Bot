# Runbook — avariya holatlari

> Vahima qilmang. Har bir qadamni ketma-ket bajaring. Hech narsani o'chirmang — avval nusxa oling.
> Holat: 1-bosqich (backup/restore) yakunlangan; server bo'limlari 10-bosqichda to'ldiriladi.

## 0. Holatni ko'rish

```bash
docker compose ps                         # qaysi konteynerlar ishlayapti
docker compose logs --tail=100 bot        # bot loglari
docker compose logs --tail=50 backup      # backup loglari
docker compose exec backup ls -l /backups/daily /backups/hourly   # mavjud backup'lar
```

## 1. Bot javob bermayapti

```bash
docker compose restart bot
docker compose logs --tail=50 bot | grep -E '"bot_ready"|"level": "error"'
```
`bot_ready` chiqsa — ishlayapti. `database` xatosi bo'lsa — 2-bo'limga qarang.

## 2. Baza ishlamayapti / ma'lumot buzilgan

1. Botni to'xtating (yangi yozuvlar tushmasin): `docker compose stop bot`
2. Postgres holatini ko'ring: `docker compose logs --tail=100 postgres`
3. Ma'lumot buzilgan bo'lsa — 3-bo'lim (tiklash).

## 3. Backup'dan tiklash (qadam-baqadam)

**Kerak:** age yopiq kaliti (parol menejeringizda yoki qog'ozda, `AGE-SECRET-KEY-1...`).

1. **Botni to'xtating:**
   ```bash
   docker compose stop bot
   ```
2. **Yopiq kalitni vaqtincha serverga qo'ying** (faqat tiklash vaqtiga):
   ```bash
   C=$(docker compose ps -q backup)
   nano /tmp/key.txt                          # kalitni joylashtiring, saqlang
   docker cp /tmp/key.txt "$C":/tmp/key.txt && shred -u /tmp/key.txt
   ```
3. **Qaysi backup'dan tiklashni tanlang:**
   ```bash
   docker compose exec backup sh -c 'ls -lt /backups/*/*.dump.age | head'
   ```
4. **Avval SINOV bazasiga tiklang** (asosiy bazaga tegmaydi):
   ```bash
   docker compose exec backup restore.sh /backups/daily/<fayl>.dump.age /tmp/key.txt sinov_tiklash
   ```
   Chiqqan sonlarni (mijozlar, foydalanuvchilar) tekshiring. To'g'rimi?
5. **Asosiy bazani almashtirish** (faqat 4-qadam to'g'ri bo'lsa):
   ```bash
   docker compose exec backup restore.sh /backups/daily/<fayl>.dump.age /tmp/key.txt nargiza --replace-main
   ```
   `HA` deb yozing. Eski baza **o'chirilmaydi** — `nargiza_old_<vaqt>` nomi bilan qoladi.
6. **Kalitni serverdan o'chiring:**
   ```bash
   docker compose exec backup sh -c 'shred -u /tmp/key.txt 2>/dev/null || rm -f /tmp/key.txt'
   ```
7. **Botni ishga tushiring:** `docker compose start bot`
8. Botda tekshiring: mijozlar, qarzlar joyidami. Bir necha kundan keyin eski bazani o'chirish:
   ```bash
   docker compose exec postgres psql -U nargiza -d postgres -c 'DROP DATABASE "nargiza_old_<vaqt>"'
   ```
9. Sinov bazasini o'chiring: `... -c 'DROP DATABASE sinov_tiklash'`

### Backup Telegram'dan olingan bo'lsa (server butunlay yo'qolgan)
1. Yangi serverda loyihani o'rnating (DEPLOY.md), `.env` ni tiklang (parol menejeridan: `POSTGRES_*`,
   `POSTGRES_APP_PASSWORD`, `BOT_TOKEN`), `docker compose up -d postgres backup`.
   `restore.sh` ilova rolini (`nargiza_app`) o'zi yaratadi. *(Sinaldi: 2026-11-11, bo'sh Postgres'ga tiklash.)*
2. Bo'sh bazaga migratsiya **qilmang** — tiklash sxemani ham olib keladi.
3. Faylni serverga yuklang: `scp nargiza_daily_....dump.age server:/tmp/`, keyin
   `docker cp /tmp/<fayl> "$C":/backups/` va 3-bo'limning 2–7 qadamlari.

## 4. Backup'ni qo'lda olish
```bash
docker compose exec backup backup.sh daily
```

## 5. Tiklash testini qo'lda o'tkazish
```bash
docker compose exec backup restore_test.sh /tmp/key.txt     # kalit 3.2 qadamdagidek qo'yiladi
```
Har bir jadval uchun ✅ chiqishi kerak. Keyin kalitni o'chiring (3.6).

## 6. age yopiq kaliti yo'qolsa
- Mavjud backup'larni **ochib bo'lmaydi** — shuning uchun kalit ikki joyda (parol menejeri + qog'oz).
- Darhol: yangi kalit yarating (SETUP_KEYS.md 6-bo'lim), `.env` dagi `BACKUP_AGE_RECIPIENT` ni yangilang,
  `docker compose up -d backup`, so'ng `docker compose exec backup backup.sh daily` — yangi kalit bilan backup.
- Eski backup'lar keraksiz bo'lib qoladi; baza o'zi joyida bo'lsa ma'lumot yo'qolmaydi.

## 7. Bot tokeni sizib chiqsa
@BotFather → `/mybots` → bot → *API Token* → *Revoke current token*. Yangi tokenni `.env` ga →
`docker compose up -d bot backup`.

## 8. Xodimning telefoni yo'qolsa
Botda: **🛠 Admin → 👥 Xodimlar → 🚫 Bloklash → ✅ Tasdiqlash**. U keyingi xabaridanoq hech narsa
qila olmaydi. Yangi telefon/akkaunt bilan qaytsa — raqamini ulashadi, sizga tasdiqlash so'rovi keladi.

## 9. Admin raqami o'zgarsa
`.env` dagi `ADMIN_PHONES` ni yangilang → `docker compose up -d bot`. Bot ishga tushganda eski
raqamdagi admin huquqini avtomatik oladi.
