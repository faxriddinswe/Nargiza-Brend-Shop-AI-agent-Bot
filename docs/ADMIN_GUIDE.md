# Admin qo'llanmasi

## Admin bo'lish
`.env` dagi `ADMIN_PHONES` da sizning raqamingiz. Botda /start → ro'yxatdan o'tish → raqamni ulashish.
Raqam o'zgarsa — `.env` ni yangilab, `docker compose up -d bot`.

## Admin paneli
Menyuda **🛠 Admin** (yoki `/admin`):

| Tugma | Nima qiladi |
|---|---|
| 👥 Xodimlar | Ro'yxat: ism, telefon, bo'lim egaligi, holati (ulangan / hali ulanmagan / bloklangan) |
| ➕ Xodim qo'shish | Telefon → murojaat ("Nodira opa") → bo'lim egaligi → ✅ Tasdiqlash |
| 📊 Statistika | Adminlar, xodimlar, botdagi va daftardagi mijozlar soni |
| 🖼 Do'kon rasmi | Xush kelibsiz xabari va "Do'kon haqida" uchun rasm |
| 📍 Lokatsiya | "Do'kon haqida" da xarita |

Har bir yozish amali (xodim qo'shish, bloklash, olish) tasdiqlash kartasi orqali. Karta 30 daqiqa amal qiladi.

## Xodim qanday ulanadi
1. Siz uni raqami bilan qo'shasiz.
2. U botda /start → ro'yxatdan o'tish → "📱 Raqamni ulashish". Bot uni avtomatik xodim qiladi.
   (Agar u oldin ro'yxatdan o'tgan bo'lsa — darhol xodim bo'ladi.)

## Xodim raqami yangi akkauntdan kelsa (BR-012a)
Sizga "⚠️ ... yangi Telegram akkauntdan ulashildi" xabari keladi. Eski akkaunt darhol huquqdan mahrum bo'ladi.
Bu haqiqatan o'sha odam bo'lsa (masalan, telefonini almashtirgan) — **✅ Tasdiqlash**. Shubhali bo'lsa — rad eting
va unga qo'ng'iroq qiling.

## Bloklash (telefon yo'qolsa)
👥 Xodimlar → 🚫 Bloklash → ✅ Tasdiqlash. Keyingi xabaridanoq hech narsa qila olmaydi.

## Tizim xabarlari
- Har kuni 03:00: "✅ Backup OK: ..." + shifrlangan fayl. Kelmasa yoki "❌ Backup xato" kelsa — RUNBOOK.md.
- "⚠️ Hajm keskin kamaydi" — ma'lumot o'chirilgan bo'lishi mumkin, darhol tekshiring.
