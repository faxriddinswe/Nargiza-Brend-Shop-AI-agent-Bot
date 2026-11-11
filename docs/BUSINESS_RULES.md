# Biznes qoidalar

> **Holat:** QORALAMA — Faxriddin tasdiqlashi kerak (0-bosqich qabul mezoni).
> Manba: `NARGIZA_BREND_MASTER_PROMPT.md`, 2–7 va 13-bo'limlar.
> Har bir qoida raqamlangan (`BR-xxx`) — kod, test va review'larda shu raqamga havola qilinadi.
> `❓ Q-n` — hali hal qilinmagan savol (oxiridagi ro'yxatga qarang). Javobsiz qoida kodga yozilmaydi.
> `💡` — master promptda yo'q, Claude taklif qilgan qoida. Tasdiqlang yoki o'zgartiring.

---

## 1. Do'kon ma'lumotlari

- **BR-001** Nomi: Nargiza Brend. Manzil: Sherbaraka bozori, 82-do'kon. Ish vaqti: 07:00–18:00. Telefon: +998 95 511 17 00. Instagram: @nargiza_17_00_.
- **BR-002** Vaqt zonasi — `Asia/Tashkent`. "Bugun", "bu oy" va boshqa barcha davrlar Toshkent vaqti bo'yicha (kun 00:00 da boshlanadi). DB'da vaqt `timestamptz`.
- **BR-003** Dam olish kuni, xarita lokatsiyasi, do'kon rasmi/logotipi — admin sozlamadan kiritadi. ❓ Q-2, Q-3
- **BR-004** Barcha pul — butun so'm. Tiyin yo'q, kasr yo'q.

## 2. Foydalanuvchilar va rollar

- **BR-010** Rollar: `admin`, `staff`, `customer`.
- **BR-011** Botga kirgan har bir kishi avtomatik `customer` bo'ladi.
- **BR-012** `staff` rolini faqat admin beradi va oladi. Bot hech qachon o'zi xodim qilmaydi.
- **BR-013** Birinchi admin(lar) `.env` dagi `ADMIN_TELEGRAM_IDS` dan olinadi.
- **BR-014** Admin barcha foydalanuvchilarni, ularning sonini, telefonlarini va barcha ma'lumotni ko'radi va o'zgartiradi. Admin xodimning barcha imkoniyatlariga ega. Faqat adminga: xodim tayinlash/olish, xodimni bloklash, bot sozlamalari, o'chirilgan yozuvlarni qaytarish.
- **BR-015** Bloklangan xodim (masalan telefoni yo'qolsa) darhol hech qanday amal bajara olmaydi — 💡 keyingi xabaridan boshlab.
- **BR-016a** Admin paneli: bot holati, xatolar, qayta ishga tushirish. Botni yangilash (yangi kod) — faqat serverga deploy orqali, bot ichidan emas.
- **BR-016** Tizim xabarlari (backup, xatolar, AI xarajati, yaxlitlik tekshiruvi) faqat adminga boradi.
- **BR-017** Xodimlar ikkala bo'limda to'liq ishlaydi: o'qish, yozish, o'zgartirish, mijoz qo'shish/o'chirish, e'lon — admindan so'ramasdan.
- **BR-018** Mijoz faqat o'z ma'lumotini ko'radi. Tekshiruv kodda, Telegram ID bo'yicha. Mijoz uchun AI yo'q — faqat tugmalar.
- **BR-019** Xodimlarga murojaat: Faxriddin aka, Botir aka, Nodira opa, Nilufar opa. Mijozlarga: "<Ism> opa" / "<Ism> aka".
- **BR-019a** Xodimlar kirill yoki lotinda yozishi mumkin; bot javoblari lotinda (keyinchalik foydalanuvchi sozlamasi bilan kirill).

## 3. Bo'limlar va yo'naltirish

- **BR-020** Ikki bo'lim: `shop` (Do'kon; egalari: Botir aka, Nodira opa) va `lingerie` (Ichki kiyim; egasi: Nilufar opa).
- **BR-021** Yozuv bo'limi **tovar turiga** qarab aniqlanadi, kim aytganiga qarab emas.
- **BR-022** Bitta xabarda ikkala bo'lim tovari bo'lsa — ikkita alohida yozuv, bitta tasdiqlash kartasida.
- **BR-023** Bo'lim aniq bo'lmasa (tovar turi noma'lum) — bot so'raydi: "Qaysi bo'lim: Do'konmi yoki Ichki kiyimmi?" Taxmin qilmaydi.
- **BR-024** Tasdiqlash kartasida bo'lim doim ko'rinadi va [Bo'limni almashtirish] tugmasi bor.
- **BR-025** Bo'limlar puli alohida. Hisobotlarda doim bo'lim bo'yicha ko'rsatiladi; umumiy "jami" faqat aniq "ikkala bo'lim jami" deb belgilangan qatorda.
- **BR-026** Bo'lim egasiga xabar: kimdir (egasi bo'lmagan xodim) bo'limga savdo, qarz, to'lov, qaytarish yoki kirim yozsa — o'sha bo'lim egalariga darhol xabar boradi.
  Misol: Nodira opa ichki kiyim sotsa → Nilufar opaga: "🔔 Nodira opa sizning bo'limingizga savdo qo'shdi: ichki kiyim, 80 000 so'm."
- **BR-027** Bir bo'limning egalari o'rtasida (Botir aka ↔ Nodira opa) har bir amal uchun xabar yuborilmaydi — kechki hisobotda ko'rinadi.
- **BR-028** 💡 Admin (Faxriddin aka) yozsa ham BR-026 ishlaydi (admin hech bir bo'lim egasi emas). ❓ Q-7: adminga ham bo'lim xabarlari kelsinmi?

### 3.1. Tovar turlari (boshlang'ich, admin o'zgartiradi)

| Bo'lim | Turlar |
|---|---|
| shop | ko'ylak, yubka, shim, kofta, bluzka, kurtka/palto, oyoq kiyim, sumka, aksessuar |
| lingerie | ichki kiyim |
| ❓ Q-1 | pijama, xalat |

- **BR-030** Har bir turda sinonimlar ro'yxati (lotin va kirill): masalan "туфли", "tufli", "poyabzal", "tufli", "krossovka" → oyoq kiyim. Sinonimlarni admin to'ldiradi.
- **BR-031** 💡 Tur o'chirilsa (`is_active=false`) eski yozuvlar saqlanadi, yangi yozuvda tanlanmaydi.

## 4. Mijozlar

- **BR-040** Telefon — mijozning yagona kaliti. Format `+998XXXXXXXXX` ga keltiriladi: "90 123 45 67", "901234567", "+998 90 123-45-67", "998901234567" → `+998901234567`.
- **BR-041** O'chirilmagan mijozlar orasida telefon takrorlanmaydi.
- **BR-042** Telefonsiz saqlash mumkin, lekin `phone_missing=true` va "⚠️ telefon kerak" belgisi bilan. Har kungi 08:00 ro'yxatida ko'rinadi. ❓ Q-35: barcha telefonsiz mijozlarmi (master 4.1) yoki faqat telefonsiz qarzdorlarmi (master 7)?
- **BR-043** Maydonlar: ism, telefon, murojaat (opa/aka), izoh ("Shahlo opaning qizi"), bog'langan Telegram foydalanuvchi.
- **BR-044** Qidiruv: kirill↔lotin ("Умида" = "Umida"), noaniq moslik (fuzzy), telefonning bir qismi bo'yicha.
- **BR-045** Bir nechta mos mijoz bo'lsa — ro'yxat: ism + izoh, to'liq telefon (faqat xodimlarga), joriy qarz (bo'lim bilan), oxirgi xarid va sanasi. Tanlash: tugma [1][2][3] yoki matn/ovoz ("birinchisi", "Shahlo opaning qizi", "45 67 dagisi"). 5 tadan ko'p bo'lsa — [Yana ko'rsatish] yoki telefon oxirini so'rash. [➕ Yangi mijoz] doim bor.
- **BR-046** Mijozni xodim o'chira oladi. Qarzi bo'lsa — avval ogohlantiradi va qarzni yopishni taklif qiladi. O'chirish = soft delete; admin qaytara oladi. ❓ Q-8: qarzi bor mijozni qarz yopilmasdan o'chirishga ruxsatmi?
- **BR-047** Mijoz botda ro'yxatdan o'tsa va telefoni mavjud mijoz yozuviga mos kelsa — avtomatik bog'lanadi va qarzlarini ko'radi.

## 5. Qarz daftari

- **BR-050** Qarz: mijoz (majburiy), bo'lim, tovarlar (tur + izoh + soni + narx), summa, sana, muddat, kim yozdi.
- **BR-051** "qarz", "nasiya" so'zlari → qarz yozuvi.
- **BR-052** Muddat odatda belgilanadi. ❓ Q-4: muddat aytilmasa — sukut nechchi kun (masalan 30)? Yoki muddatsiz qarz bo'lishi mumkinmi?
- **BR-053** 💡 Oddiy qarz summasi = tovarlar (soni × narx) yig'indisi. Istisno: aralash savdodagi bog'langan qarz (BR-071) — summasi to'lanmagan qoldiq, tovarlar savdo yozuvida. Summa > 0.
- **BR-054** Qarz yozilganda mijozga avtomatik xabar (agar botda ro'yxatdan o'tgan bo'lsa): nima oldi, summa, muddat, umumiy qarz.
- **BR-055** Qoldiq saqlanmaydi. Har safar hisoblanadi: `qarzlar − to'lovlar − kechilganlar ± tuzatishlar` (o'chirilgan va bekor qilingan yozuvlarsiz).
- **BR-056** Qoldiq har bir bo'lim uchun alohida hisoblanadi.
- **BR-057** "Qarzini o'chir/yop" deyilsa bot so'raydi: [💵 To'ladi] [🤝 Kechib yuborildi] [❌ Bekor].
  - "To'ladi" = to'lov (kassaga pul tushdi).
  - "Kechib yuborildi" = write-off (hisobotda zarar sifatida alohida).
  - Bu ikki tur hech qachon aralashmaydi. ❓ Q-9: kechib yuborishni har qanday xodim qila oladimi yoki faqat admin?

## 6. To'lovlar

- **BR-060** "Umida 100 ming berdi" → to'lov.
- **BR-061** Taqsimot sukut bo'yicha FIFO — eng eski qarzdan boshlab yopiladi. 💡 Bir xil vaqtdagi qarzlar — ID tartibida (barqaror). ❓ Q-27: "eng eski" — yozilgan sana bo'yichami yoki muddat bo'yicha?
- **BR-062** Xodim aniq qarzni aytsa ("oyoq kiyim qarzidan ayir") — o'sha qarzdan.
- **BR-063** Tasdiqlash kartasida qaysi qarz(lar)dan qancha yopilayotgani ko'rinadi.
- **BR-064** Qisman to'lov mumkin.
- **BR-065** To'lov qoldiqdan ko'p bo'lsa — ogohlantirish va so'rash. ❓ Q-5: ortiqcha qismi nima bo'ladi — (a) rad etiladi, faqat qoldiqqa teng qabul qilinadi; (b) mijoz avansi sifatida saqlanadi?
- **BR-066** ❓ Q-6: Mijozning ikkala bo'limda qarzi bo'lsa va xodim bo'lim aytmasa ("Umida 100 ming berdi") — (a) bot so'raydi "Qaysi bo'lim qarzidan?"; (b) ikkala bo'lim bo'yicha umumiy FIFO?
- **BR-067** Karta raqamlari va chek yuborish — `ENABLE_CARD_PAYMENTS=false`. Kod tayyor, menyu va eslatmalarda ko'rinmaydi.

## 7. Savdo

- **BR-070** "sotildi" → naqd savdo. Mijoz ismi ixtiyoriy.
- **BR-071** Aralash savdo: "Ko'ylak 500 ming, 200 berdi, qolgani qarz" → savdo 500 000 + bog'langan qarz 300 000, bitta kartada. 💡 Aralash savdoda mijoz majburiy (qarz uchun).
  ❓ Q-10: aralash savdoda kassaga 200 000 tushdi. Hisobotda "savdo" 500 000 deb ko'rsatilsinmi (tovar narxi), "kassaga tushgan" esa alohida 200 000 bo'lsinmi? (Taklif: ha — savdo 500 000, naqd tushum 200 000, qarzga 300 000; keyin qarz to'lansa — to'lov sifatida.)
- **BR-072** To'lov turi noaniq bo'lsa: "Naqd sotildimi yoki nasiyagami?"
- **BR-073** Chegirma: "500 minglik ko'ylakni 450 ga sotdim" → savdo 450 000, chegirma 50 000 alohida maydonda saqlanadi (master: "izohda"; 💡 alohida maydon — hisobotda jamlash uchun). Oylik hisobotda jami chegirma.
- **BR-074** Savdo omborni avtomatik kamaytiradi.
- **BR-075** Kelish narxi va foyda hisoblanmaydi.

## 8. Qaytarish va almashtirish

- **BR-080** Bot asl yozuvni topadi; bir nechta bo'lsa — tanlatadi.
- **BR-081** Kartada: eski tovar, yangi tovar, farq, qarz/savdo "oldin → keyin".
- **BR-082** Qarzga olingan tovar almashtirilsa — qarz farqqa qarab o'zgaradi (💡 tuzatish yozuvi bilan; asl qarz o'zgartirilmaydi. Tuzatishlar jadvali — 1-bosqichda architect bilan).
- **BR-083** Naqd savdo almashtirilsa — farqni mijoz to'laydimi yoki unga qaytariladimi — bot so'raydi.
- **BR-084** Faqat qaytarish: qarzga olingan bo'lsa — qarzdan ayiriladi; naqd bo'lsa — savdo bekor qilinadi (qaytarish yozuvi). Ombor ko'payadi.
  ❓ Q-11: qarzning bir qismi allaqachon to'langan bo'lsa va tovar qaytarilsa (masalan qarz 300 000, 200 000 to'langan, 300 000 lik tovar qaytdi) — mijozga 100 000 naqd qaytariladimi?
- **BR-085** Bo'limlararo almashtirish (ko'ylak → ichki kiyim) — summa bir bo'limdan chiqib boshqasiga kiradi; tegishli bo'lim egasiga xabar (BR-026).
- **BR-086** Asl yozuv o'chirilmaydi — `returned` holatiga o'tadi. Hisobotda qaytarishlar alohida.
- **BR-087** ❓ Q-12: qaytarishga muddat cheklovi bormi (masalan 14 kun)?

## 9. Ombor (1-daraja)

- **BR-090** Qoldiq faqat tovar turi bo'yicha (ko'ylak: 45 ta). O'lcham, rang, model — izoh sifatida; aytilmasa so'ralmaydi.
- **BR-091** Kirim: "20 ta yubka keldi" yoki nakladnoy rasmi → kirim yozuvi (tasdiq bilan).
- **BR-092** Savdo → qoldiq kamayadi; qaytarish → ko'payadi.
- **BR-093** Qoldiq manfiy bo'lsa — 💡 yozuv saqlanadi, lekin ogohlantirish: "Yubka qoldig'i −2, kirim yozilmagan bo'lishi mumkin".
- **BR-094** Kam qolganda ogohlantirish; chegara har tur uchun alohida. ❓ Q-13
- **BR-095** Boshlang'ich qoldiq bir marta kiritiladi. ❓ Q-14
- **BR-096** Oylik inventarizatsiya: sanalgan son kiritiladi, farq tuzatish yozuvi sifatida saqlanadi.

## 10. Tasdiqlash va bekor qilish (barcha yozuvlar)

- **BR-100** Bazaga yozadigan har qanday amal avval tasdiqlash kartasini ko'rsatadi: [✅ Tasdiqlash] [✏️ Tuzatish] [❌ Bekor qilish].
- **BR-101** Savollar (o'qish) tasdiqsiz, darhol.
- **BR-102** Idempotentlik: tugma ikki marta bosilsa ham yozuv bir marta yoziladi.
- **BR-103** ❓ Q-15: Tasdiqlash kartasi qancha vaqt amal qiladi (masalan 30 daqiqa, keyin "eskirdi")?
- **BR-104** "Oxirgi yozuvni bekor qil" — tasdiq bilan; yozuv o'chirilmaydi, `cancelled` holatiga o'tadi va tarixda qoladi. ❓ Q-16: xodim faqat o'zi yozganini bekor qila oladimi? Vaqt chegarasi bormi?
- **BR-105** Har bir biznes amal — bitta tranzaksiya: hammasi yoziladi yoki hech narsa.
- **BR-106** Har bir yozish, o'zgartirish, o'chirish audit log'ga tushadi (kim, qachon, eski, yangi).

## 11. Davomli suhbat (xodimlar)

- **BR-110** Bot oxirgi muhokama qilingan mijoz/yozuvni eslaydi ("unga yana 20 ming qo'sh").
- **BR-111** Kontekst ma'lum vaqt jimlikdan keyin (masalan 15 daqiqa, sozlanadi) yoki boshqa mijoz tilga olinsa yangilanadi.

## 12. So'rovlar va hisobotlar

- **BR-120** Qarzdorlar ro'yxati: summa, muddat, kattasidan kichigiga; jami (bo'lim bo'yicha).
- **BR-121** Mijoz qarzi: qoldiq, xaridlar, to'lovlar, muddat, telefon.
- **BR-122** Muddati o'tganlar: necha kun o'tgani bilan.
- **BR-123** Savdo hisoboti davr bo'yicha (bugun, bu hafta, bu oy, bu yil, o'tgan oy, "mart", "1–15 noyabr"): jami summa, tovar soni, bo'limlar alohida.
  ❓ Q-17: "Bu hafta" — dushanbadan boshlanadimi?
  ❓ Q-18: "mart" deyilsa va hozir noyabr bo'lsa — joriy yilning marti (o'tgan) deb olinsinmi?
- **BR-124** Tur bo'yicha savdo: soni va summasi.
- **BR-125** Qarz statistikasi: jami qarz; davrda berilgan va qaytgan; kim to'ladi.
- **BR-126** Ombor: tur qoldig'i; kam qolganlar.
- **BR-127** Solishtirish: ikki davr yonma-yon, farq (so'm) va foiz.
- **BR-128** Har qanday hisobot Excel ko'rinishida so'ralsa — .xlsx fayl yuboriladi.
- **BR-129** Uzun ro'yxatlar sahifalanadi. Yillik hisobot — bot ishga tushgan kundan.
- **BR-130** Hisobotda kategoriyalar: savdo, qaytarishlar, chegirmalar, to'lovlar, kechilgan qarzlar — har biri alohida, hech qachon aralashmaydi.

## 13. Eski daftarni ko'chirish

- **BR-140** Xodim "Eski daftarni kiritish" rejimini yoqadi; ovoz yoki sahifa rasmi yuboradi.
- **BR-141** Natija: ✅ aniq, ⚠️ telefon yo'q, ❓ o'qilmadi/noaniq. Noaniq taxmin qilinmaydi.
- **BR-142** Faqat qolgan qarz, asl sanasi bilan kiritiladi (`source=import`).
- **BR-143** [✅ Hammasini saqlash] [✏️ Tuzatish] — tuzatish har bir qator bo'yicha.
- **BR-144** Dublikat tekshiruvi telefon bo'yicha. ❓ Q-19: import qilingan qarzlar uchun bo'lim qanday aniqlanadi, agar daftarda tovar turi yozilmagan bo'lsa? (Daftar bo'limlar bo'yicha alohidami?)

## 14. Mijoz tomoni

- **BR-150** /start → xush kelibsiz xabari (rasm bilan, agar yuklangan bo'lsa) + [📝 Ro'yxatdan o'tish].
- **BR-151** Ro'yxatdan o'tish: ism (Telegram ismi tugma sifatida taklif) → murojaat [Opa]/[Aka] → telefon (faqat "kontakt ulashish" tugmasi) → rozilik matni → "✅ Rahmat, Umida opa! Siz ro'yxatdan o'tdingiz."
- **BR-152** Xavfsizlik: yuborilgan kontaktning `user_id` si yuboruvchining ID'siga teng bo'lishi shart. Aks holda rad etiladi.
- **BR-153** Rozilik matni majburiy: "Raqamingiz faqat do'kon xabarlari va xaridlaringiz hisobi uchun saqlanadi."
- **BR-154** Mijoz menyusi: [💰 Mening qarzim] [📢 E'lonlar] [🏪 Do'kon haqida] [📞 Bog'lanish]; sozlamalarda [🔕 Reklamani o'chirish].
- **BR-154a** "Do'kon haqida": manzil, lokatsiya (bo'lsa), ish vaqti, telefon, Instagram, rasm (bo'lsa).
- **BR-155** "Mening qarzim": bo'limlar alohida — qoldiq, nima olgani, to'lovlar, muddat.

### 14.1. Mijozga avtomatik xabarlar

- **BR-160** Qarz yozilganda — darhol (BR-054).
- **BR-161** Muddatdan 2 kun oldin — "muddat yaqinlashmoqda".
- **BR-162** Muddat kuni — "bugun to'lov kuni".
- **BR-163** Muddat o'tgach har 3 kunda, ko'pi bilan 5 marta — muloyim eslatma.
- **BR-164** Reklama o'chirilgan bo'lsa ham qarz eslatmalari keladi.
- **BR-165** Bot faqat /start bosganlarga yoza oladi; qolganlari 08:00 qo'ng'iroq ro'yxatida.
- **BR-166** Har bir eslatma `reminders_log` ga yoziladi — takrorlanmaydi.
- **BR-167** ❓ Q-20: eslatmalar soat nechada yuboriladi (taklif: 10:00)? Dam olish kunida ham yuborilsinmi?
- **BR-168** ❓ Q-21: mijozning ikkala bo'limda qarzi bo'lsa — bitta xabarda (bo'limlar alohida qatorda) yuborilsinmi?

## 15. E'lonlar

- **BR-170** Har qanday xodim e'lon yubora oladi: matn va/yoki rasm.
- **BR-171** Kimga: hammaga / qarzdorlarga / muddati o'tganlarga / bitta tanlangan odamga.
- **BR-172** Oldindan ko'rish: "87 kishiga boradi" → [Yuborish] [Bekor].
- **BR-173** Natija: "82 tasiga yetdi, 5 tasi botni bloklagan".
- **BR-174** Reklamani o'chirganlarga reklama e'loni bormaydi; shaxsiy xabar va qarz eslatmasi boradi.
- **BR-175** Umumiy e'londa hech qachon kimningdir qarzi ko'rsatilmaydi.
- **BR-176** Xabarlar Telegram tezlik cheklovi doirasida navbat bilan yuboriladi (limitlar 7-bosqichda rasmiy hujjatdan tekshiriladi).
- **BR-177** Xodimlarga tavsiya: haftasiga 1–2 reklama.
- **BR-178** ❓ Q-22: "qarzdorlarga" / "muddati o'tganlarga" e'loni reklama hisoblanadimi (reklamani o'chirganlarga boradimi)?

## 16. Avtomatik vazifalar (Asia/Tashkent)

| Qoida | Vaqt | Kimga | Vazifa |
|---|---|---|---|
| BR-180 | Har kuni 08:00 | Xodimlar | Qo'ng'iroq ro'yxati: muddati o'tganlar (summa, bosiladigan telefon) + telefoni yo'q qarzdorlar. Dam olish kunida yuborilmaydi |
| BR-181 | Har kuni 20:00 | Xodimlar | Kunlik hisobot: bo'limlar alohida, tovar turlari, qaytarishlar, chegirmalar, to'lovlar, yangi mijozlar soni + "kassadagi pul bilan solishtiring" |
| BR-182 | Har kuni | Mijozlar | Muddat eslatmalari (BR-161…163) |
| BR-183 | Har soat | — | Backup (48 soat saqlanadi) |
| BR-184 | Har kuni 03:00 | Admin | Kunlik backup + Telegram'ga shifrlangan fayl (30 kun) |
| BR-185 | Har kecha | Admin | Yaxlitlik tekshiruvi |
| BR-186 | Har hafta | Admin | Qarzlar Excel'i + backup tiklash testi |
| BR-187 | Har oy | Xodimlar | Oylik hisobot, inventarizatsiya eslatmasi |

- **BR-188** ❓ Q-23: 20:00 hisoboti dam olish kunida ham yuborilsinmi? Haftalik/oylik vazifalar qaysi kun va soatda (taklif: haftalik — dushanba 09:00, oylik — oyning 1-kuni 09:00)?

---

## ❓ Ochiq savollar

| # | Savol | Qoida |
|---|---|---|
| Q-1 | Pijama, xalat qaysi bo'limga? Tovar turlari ro'yxati to'g'rimi, nimadir qo'shilsinmi (masalan: kostyum, sharf/ro'mol, paypoq, kolgotka)? | 3.1 |
| Q-2 | Dam olish kuni qaysi kun (yoki yo'q)? | BR-003 |
| Q-3 | Xarita lokatsiyasi va do'kon rasmi/logotipi bormi? | BR-003 |
| Q-4 | Qarz muddati aytilmasa — sukut necha kun? Muddatsiz qarz bo'ladimi? | BR-052 |
| Q-5 | Ortiqcha to'lov: rad etilsinmi yoki avans sifatida saqlansinmi? | BR-065 |
| Q-6 | Ikkala bo'limda qarz bo'lsa, bo'lim aytilmagan to'lov qanday taqsimlanadi? | BR-066 |
| Q-7 | Adminga ham bo'lim xabarlari (🔔) kelsinmi? | BR-028 |
| Q-8 | Qarzi bor mijozni qarz yopilmasdan o'chirish mumkinmi? | BR-046 |
| Q-9 | Qarzni kechib yuborish — har qanday xodimmi yoki faqat admin? | BR-057 |
| Q-10 | Aralash savdo hisobotda qanday ko'rinadi (savdo 500 000 / naqd 200 000 / qarz 300 000)? | BR-071 |
| Q-11 | Qisman to'langan qarzli tovar qaytsa, ortiqcha pul mijozga qaytariladimi? | BR-084 |
| Q-12 | Qaytarishga muddat cheklovi bormi? | BR-087 |
| Q-13 | Har bir tur uchun "kam qoldi" chegarasi | BR-094 |
| Q-14 | Boshlang'ich ombor qoldig'i (tur bo'yicha) | BR-095 |
| Q-15 | Tasdiqlash kartasi necha daqiqada eskiradi? | BR-103 |
| Q-16 | "Oxirgi yozuvni bekor qil" — faqat o'zinikimi, vaqt chegarasi bormi? | BR-104 |
| Q-17 | "Bu hafta" dushanbadan boshlanadimi? | BR-123 |
| Q-18 | "Mart" — joriy yilning o'tgan marti deb olinsinmi? | BR-123 |
| Q-19 | Eski daftar importida bo'lim qanday aniqlanadi? | BR-144 |
| Q-20 | Mijoz eslatmalari soati va dam olish kunida yuborilishi | BR-167 |
| Q-21 | Ikkala bo'lim qarzi — bitta eslatmadami? | BR-168 |
| Q-22 | Qarzdorlarga e'lon reklama hisoblanadimi? | BR-178 |
| Q-23 | 20:00 hisoboti dam olish kunida; haftalik/oylik vazifalar vaqti | BR-188 |
| Q-24 | Google Drive backup kerakmi? | DATA_SAFETY |
| Q-25 | Production server qachon va qaysi? | DEPLOY |
| Q-26 | Sof nasiya ("ko'ylak oldi, nasiyaga") omborni kamaytiradimi? Savdo hisobotida ko'rinadimi (masalan "nasiyaga sotilgan" qatori)? | BR-050, BR-074 |
| Q-27 | FIFO'da "eng eski" — yozilgan sanami yoki muddatmi? Import qarzlarida asl sana hisobga olinadimi? | BR-061 |
| Q-28 | Kechib yuborish: butun qoldiqmi yoki qisman summa? Bitta qarzmi yoki bo'limdagi hamma qarz? | BR-057 |
| Q-29 | Bir nechta tovarli yozuvdan bitta tovar qaytsa (qisman qaytarish) — qolganlari o'z holicha qoladimi? | BR-084 |
| Q-30 | Bo'limlararo almashtirishda eski qarzga avval tushgan to'lovlar yangi bo'lim qarziga o'tadimi? | BR-085 |
| Q-31 | Qarzga ham chegirma bo'ladimi ("500 lik ko'ylakni 450 ga nasiyaga berdim")? | BR-073 |
| Q-32 | Eslatmalar har bir qarz uchunmi yoki mijoz uchun? Muddat uzaytirilsa 5 martalik hisoblagich qaytadan boshlanadimi? | BR-163 |
| Q-33 | O'chirilgan mijozning qarzi "jami qarz" hisobotida qoladimi? (Taklif: ha — pul yo'qolmasligi uchun) | BR-046, BR-055 |
| Q-34 | To'lov bekor qilinsa yoki tahrirlansa, taqsimot qanday qayta hisoblanadi? (Taklif: eski to'lov `cancelled`, yangi to'lov qaytadan taqsimlanadi) | BR-104 |
| Q-35 | 08:00 ro'yxatida — barcha telefonsiz mijozlarmi yoki faqat telefonsiz qarzdorlarmi? | BR-042 |
