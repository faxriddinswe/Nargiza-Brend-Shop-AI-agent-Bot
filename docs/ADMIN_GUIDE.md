# Admin guide

## Becoming an admin
Your number is listed in `ADMIN_PHONES` in `.env`. In the bot: /start → registration → share your phone number.
If your number changes, update `.env` and run `docker compose up -d bot`.

## Admin panel
In the menu, tap **⚙️ Boshqa** (*More*) (or send `/admin`):

| Button | What it does |
|---|---|
| 👥 Xodimlar (*Staff*) | List: name, phone, department ownership, status (connected / not yet connected / blocked) |
| ➕ Xodim qo'shish (*Add staff member*) | Phone → form of address (e.g. "Nodira opa") → department ownership → ✅ Tasdiqlash (*Confirm*) |
| 📊 Statistika (*Statistics*) | Number of admins, staff members, and customers in the bot and in the notebook |
| 🖼 Do'kon rasmi (*Shop photo*) | Photo for the welcome message and for "Do'kon haqida" (*About the shop*) |
| 📍 Lokatsiya (*Location*) | Map shown in "Do'kon haqida" (*About the shop*) |

Every write action (adding, blocking or removing a staff member) goes through a confirmation card. A card is valid for 30 minutes.

## How a staff member connects
1. You add them by their phone number.
2. They open the bot: /start → registration → "📱 Raqamni ulashish" (*Share phone number*). The bot automatically makes them a staff member.
   (If they had already registered, they become a staff member immediately.)

## A staff member's number arrives from a new account (BR-012a)
You receive a "⚠️ ... yangi Telegram akkauntdan ulashildi" (*... was shared from a new Telegram account*) message. The old account loses its rights immediately.
If it really is the same person (e.g. they changed phones), tap **✅ Tasdiqlash** (*Confirm*). If it looks suspicious, reject it
and give them a call.

## Blocking (if a phone is lost)
**⚙️ Boshqa** (*More*) → **👥 Xodimlar** (*Staff*) → **🚫 Bloklash** (*Block*) → **✅ Tasdiqlash** (*Confirm*). From their very next message they can no longer do anything.

## System messages
- Every day at 03:00: "✅ Backup OK: ..." plus the encrypted file. If it does not arrive, or you get "❌ Backup xato" (*Backup error*), see RUNBOOK.md.
- "⚠️ Hajm keskin kamaydi" (*Size dropped sharply*) — data may have been deleted; check immediately.
