# Kalitlar va akkauntlarni sozlash (Faxriddin uchun)

> Akkauntlarga faqat siz kirasiz. Kalitni `.env` ga qo'ygach, sozlash va tekshirishni Claude bajaradi.
> **Qoida:** kalitni hech kimga yubormang, chatga, skrinshotga, git'ga qo'ymang.

## 1. Telegram bot tokeni (0-bosqich uchun kerak)

1. Telegram'da **@BotFather** ni oching (ko'k "verified" belgisi borligini tekshiring).
2. `/newbot` yuboring.
3. Bot **nomi** — ko'rinadigan nom, masalan: `Nargiza Brend`.
4. Bot **username** — oxiri `bot` bilan tugashi shart, masalan: `nargiza_brend_bot`. Band bo'lsa boshqasini sinang.
5. BotFather token yuboradi: `1234567890:AA...` ko'rinishida. Bu — botning paroli.
6. Loyiha papkasida:
   ```bash
   cp .env.example .env
   nano .env        # BOT_TOKEN= qatoriga tokenni qo'ying
   ```
7. `POSTGRES_PASSWORD=` ga uzun tasodifiy parol — ekranga chiqarmasdan to'g'ridan-to'g'ri `.env` ga:
   ```bash
   sed -i "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')#" .env
   ```
   (Dev muhitingizda bu allaqachon qilingan.)

**Sizib chiqsa:** @BotFather → `/mybots` → botni tanlang → *API Token* → *Revoke current token*. Yangi tokenni `.env` ga qo'ying.

Keyinroq (1-bosqichda) BotFather'da: tavsif (`/setdescription`), rasm (`/setuserpic`), buyruqlar (`/setcommands`) — matnlarini tayyorlab beraman.

## 2. Admin raqami (BR-013)

`.env` dagi `ADMIN_PHONES=` ga o'z raqamingizni yozing: `ADMIN_PHONES=+998901234567`.
Botda /start → ro'yxatdan o'tish → "📱 Raqamni ulashish" — bot sizni admin deb taniydi.
Telegram ID'ni bilish shart emas (quyidagi — zaxira yo'l).

## 2a. Telegram ID'ingizni bilish (ixtiyoriy, zaxira yo'l)

Uchinchi tomon botlarisiz, rasmiy Bot API orqali:

1. O'z botingizni Telegram'da oching va unga istalgan xabar yozing (masalan "salom").
   (Bot ishga tushmagan bo'lishi kerak — aks holda xabarni u "yeb qo'yadi". `docker compose stop bot`.)
2. Terminalda (token ekranga ham, shell tarixiga ham tushmasligi uchun `.env` dan,
   qavs ichidagi alohida subshell'da o'qiymiz — buyruq tugagach qiymatlar yo'qoladi):
   ```bash
   ( set -a; . ./.env; curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getUpdates" ) | python3 -m json.tool | grep -A3 '"from"'
   ```
3. `"id": 123456789` — shu raqam sizning ID'ingiz. `.env` dagi `ADMIN_TELEGRAM_IDS=` ga yozing.

## 3. Gemini API kaliti — 3-bosqichda to'ldiriladi

- Google AI Studio → API key yaratish → `GEMINI_API_KEY`.
- **Muhim:** bepul tarifda yuborilgan ma'lumotlar Google mahsulotlarini yaxshilash uchun ishlatilishi mumkin. Real mijoz ma'lumoti faqat billing yoqilgan (pullik) kalit bilan. Bepul kalit — faqat soxta ma'lumotda test.
- Cloud billing, Google AI Pro kreditlari, oylik budjet ogohlantirishi ($5) — yo'riqnoma 3-bosqichda rasmiy hujjatdan tekshirib yoziladi.

## 4. GitHub — 0-bosqich oxirida (sizning roziligingiz bilan)

- Private repo yaratish, SSH kalit, birinchi push. `.env` push qilinmasligini tekshirish.

## 5. Server (Azure for Students, keyin Contabo) — 10-bosqich

## 6. age shifr kaliti (backup'lar uchun) — HOZIR KERAK

**G'oya:** backup ochiq kalit (`age1...`) bilan shifrlanadi — u serverda turadi va hech narsani ocha olmaydi.
Ochish faqat yopiq kalit (`AGE-SECRET-KEY-1...`) bilan mumkin — u **hech qachon serverda turmaydi**.
Server buzib kirilsa ham backup'lar o'qilmaydi. Lekin yopiq kalitni yo'qotsangiz — backup'lar ham yo'qoladi.

1. O'z kompyuteringizda `age` ni o'rnating: `sudo apt install age`
2. Kalit yarating (fayl faqat sizga o'qiladigan bo'lsin):
   ```bash
   umask 077 && age-keygen -o ~/nargiza-backup-key.txt
   ```
   Ekranda `Public key: age1...` chiqadi.
3. **Ochiq kalitni** (`age1...`) `.env` dagi `BACKUP_AGE_RECIPIENT=` ga yozing, so'ng
   `docker compose up -d backup`. (Hozir u yerda Claude qo'ygan **TEST** kaliti turibdi — almashtiring.)
4. **Yopiq kalitni ikki joyga saqlang:**
   - Parol menejeri (Bitwarden, 1Password, KeePassXC): yangi "Secure note" → nomi "Nargiza Brend backup kaliti" →
     `~/nargiza-backup-key.txt` ning to'liq mazmuni.
   - Qog'oz: `AGE-SECRET-KEY-1...` qatorini chop eting (yoki katta harflar bilan aniq ko'chiring; kalitda
     `O`, `I`, `B` harflari va boshidagi `-1` dan keyin `1` raqami uchramaydi — shubhali belgi `0` bo'ladi).
     Konvertga solib, uyda xavfsiz joyda (hujjatlar bilan) saqlang. Ikkinchi nusxa — ishonchli oila a'zosida.
     **Qog'ozdagi nusxadan** qayta yozib, 5-qadamdagi tiklash testini o'tkazing — shunda qog'oz to'g'riligi isbotlanadi.
5. Tiklashni sinang (RUNBOOK.md 5-bo'lim) — kalit haqiqatan ishlashiga ishonch hosil qiling.
6. Sinovdan keyin kompyuterdagi faylni o'chiring: `shred -u ~/nargiza-backup-key.txt`
   (kalit endi faqat parol menejeri va qog'ozda).

## 7. Google Drive backup (ixtiyoriy) — 9-bosqich

## 8. Xarajat kuzatuvi — 3 va 10-bosqich

## 9. Kundalik operatsiyalar — `RUNBOOK.md`
