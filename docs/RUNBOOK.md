# Runbook — emergency procedures

> Don't panic. Follow each step in order. Don't delete anything — make a copy first.
> Status: Stage 1 (backup/restore) is complete; the server sections will be filled in during Stage 10.

## 0. Checking the current state

```bash
docker compose ps                         # qaysi konteynerlar ishlayapti
docker compose logs --tail=100 bot        # bot loglari
docker compose logs --tail=50 backup      # backup loglari
docker compose exec backup ls -l /backups/daily /backups/hourly   # mavjud backup'lar
```

(In order: which containers are running; bot logs; backup logs; available backups.)

## 1. The bot is not responding

```bash
docker compose restart bot
docker compose logs --tail=50 bot | grep -E '"bot_ready"|"level": "error"'
```
If `bot_ready` appears, the bot is running. If you see a `database` error, go to section 2.

## 2. The database is down / data is corrupted

1. Stop the bot (so that no new records are written): `docker compose stop bot`
2. Check the Postgres status: `docker compose logs --tail=100 postgres`
3. If the data is corrupted, go to section 3 (restore).

## 3. Restoring from a backup (step by step)

**You will need:** the age private key (in your password manager or on paper, `AGE-SECRET-KEY-1...`).

1. **Stop the bot:**
   ```bash
   docker compose stop bot
   ```
2. **Place the private key on the server temporarily** (only for the duration of the restore):
   ```bash
   C=$(docker compose ps -q backup)
   nano /tmp/key.txt                          # kalitni joylashtiring, saqlang
   docker cp /tmp/key.txt "$C":/tmp/key.txt && shred -u /tmp/key.txt
   ```
   (In `nano`, paste the key and save.)
3. **Choose which backup to restore from:**
   ```bash
   docker compose exec backup sh -c 'ls -lt /backups/*/*.dump.age | head'
   ```
4. **Restore into a TEST database first** (the main database is not touched):
   ```bash
   docker compose exec backup restore.sh /backups/daily/<fayl>.dump.age /tmp/key.txt sinov_tiklash
   ```
   (`<fayl>` = the file name.) Check the counts it prints (customers, users). Do they look right?
5. **Replace the main database** (only if step 4 looked right):
   ```bash
   docker compose exec backup restore.sh /backups/daily/<fayl>.dump.age /tmp/key.txt nargiza --replace-main
   ```
   Type `HA` (*yes*). The old database is **not deleted** — it is kept under the name `nargiza_old_<vaqt>` (`<vaqt>` = timestamp).
6. **Remove the key from the server:**
   ```bash
   docker compose exec backup sh -c 'shred -u /tmp/key.txt 2>/dev/null || rm -f /tmp/key.txt'
   ```
7. **Start the bot:** `docker compose start bot`
8. Check in the bot that customers and debts are all in place. After a few days, delete the old database:
   ```bash
   docker compose exec postgres psql -U nargiza -d postgres -c 'DROP DATABASE "nargiza_old_<vaqt>"'
   ```
9. Delete the test database: `... -c 'DROP DATABASE sinov_tiklash'`

### If the backup came from Telegram (the server is completely lost)
1. Install the project on a new server (DEPLOY.md), restore `.env` (from the password manager: `POSTGRES_*`,
   `POSTGRES_APP_PASSWORD`, `BOT_TOKEN`), then run `docker compose up -d postgres backup`.
   `restore.sh` creates the application role (`nargiza_app`) by itself. *(Tested 2026-11-11: restore into an empty Postgres.)*
2. **Do not** run migrations on the empty database — the restore brings the schema with it.
3. Upload the file to the server: `scp nargiza_daily_....dump.age server:/tmp/`, then
   `docker cp /tmp/<fayl> "$C":/backups/`, and follow steps 2–7 of section 3.

## 4. Taking a backup manually
```bash
docker compose exec backup backup.sh daily
```

## 5. Running the restore test manually
```bash
docker compose exec backup restore_test.sh /tmp/key.txt     # kalit 3.2 qadamdagidek qo'yiladi
```
(Place the key as in step 3.2.) Every table should show ✅. Afterwards, remove the key (step 3.6).

## 6. If the age private key is lost
- Existing backups **cannot be opened** — this is why the key is kept in two places (password manager + paper).
- Immediately: generate a new key (SETUP_KEYS.md, section 6), update `BACKUP_AGE_RECIPIENT` in `.env`,
  run `docker compose up -d backup`, then `docker compose exec backup backup.sh daily` to take a backup with the new key.
- The old backups become useless; as long as the database itself is intact, no data is lost.

## 7. If the bot token leaks
@BotFather → `/mybots` → your bot → *API Token* → *Revoke current token*. Put the new token in `.env` →
`docker compose up -d bot backup`.

## 8. If a staff member loses their phone
In the bot: **⚙️ Boshqa** (*More*) (or `/admin`) → **👥 Xodimlar** (*Staff*) → **🚫 Bloklash** (*Block*) → **✅ Tasdiqlash** (*Confirm*).
From their very next message they can no longer do anything. If they come back with a new phone/account, they share
their number and you receive a confirmation request.

## 9. If the admin's phone number changes
Update `ADMIN_PHONES` in `.env` → `docker compose up -d bot`. On startup, the bot automatically revokes admin
rights from the old number.
