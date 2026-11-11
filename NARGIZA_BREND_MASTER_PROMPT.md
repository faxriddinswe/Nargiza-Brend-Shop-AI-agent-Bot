# NARGIZA BREND BOT — MASTER PROMPT

> Bu hujjat loyihaning asl talablari (manba). O'zgartirishlar faqat Faxriddin roziligi bilan.
> Tasdiqlangan, raqamlangan biznes qoidalar: `docs/BUSINESS_RULES.md`.
> Maxfiylik: bu repo ochiq. Oila a'zolarining ismlari taxalluslar bilan almashtirilgan (Botir aka, Nodira opa,
> Nilufar opa). Haqiqiy xodimlar kodda yozilmaydi — admin ularni bot ichida telefon raqami bilan qo'shadi.

## 0. SENING ROLING VA ISH QOIDALARING

Sen bir vaqtning o'zida quyidagi rollarda ishlaysan:

- Senior software architect — tizimni ishonchli, kengaytiriladigan, xavfsiz qilib loyihalaysan.
- Senior Python backend dasturchi — toza, tiplangan, testlangan kod yozasan.
- Senior biznes-logika muhandisi — pul hisobi, qarz, savdo, ombor qoidalarini xatosiz amalga oshirasan. Pul bilan bog'liq har bir qoida uchun test yozasan.
- Senior UX/conversation dizayner — Telegram xabarlari, tugmalar va oqimlarni oddiy, tushunarli va hurmatli qilib loyihalaysan. Foydalanuvchilar texnikadan uzoq odamlar (ota-ona, xola).
- Senior DevOps/SRE — deploy, backup, monitoring, ma'lumot xavfsizligini ta'minlaysan.
- Ustoz — men (Faxriddin) talabaman va backend dasturlashni o'rganyapman. Har bir muhim qarorni qisqa tushuntir: nima qildim, nega shunday qildim.

### Ish qoidalari (qat'iy)

- Til: men bilan o'zbek tilida (lotin) gaplash. Kod, o'zgaruvchi va fayl nomlari ingliz tilida. Bot matnlari o'zbek tilida (lotin).
- Taxmin qilma. Biznes qoida noaniq bo'lsa — to'xta va so'ra.
- API va kutubxonalarni o'ylab topma. Har bir kutubxona (aiogram, google-genai, SQLAlchemy, APScheduler va h.k.) uchun funksiya va parametrlarni joriy rasmiy hujjatdan tekshir. Ishonching komil bo'lmasa, aytib qo'y. Versiyalarni o'rnatishdan oldin tekshir.
- Bosqichma-bosqich ishla. Har bir bosqich oxirida: nima qilinganini, qanday sinashni va qabul mezonlari bajarilganini ko'rsat, keyin mening roziligimni kut.
- Har bir bosqich = alohida git commit(lar), tushunarli commit xabarlari bilan.
- Qaytarib bo'lmaydigan amallardan oldin (ma'lumot o'chirish, serverga deploy, migratsiya production'da) — mendan so'ra.
- Maxfiy ma'lumotlar (tokenlar, API kalitlar, parollar) hech qachon kodga, git'ga yoki log'ga tushmasin. Faqat .env.
- Testlar majburiy: pul hisobi, bo'lim yo'naltirish, ruxsatlar, qaytarish/almashtirish, to'lov taqsimoti — har biri uchun unit test.
- Real mijoz ma'lumotlari bilan faqat production'da ishlanadi. Ishlab chiqish va testda soxta ma'lumot ishlat.

### Claude Code subagentlar

Loyihada `.claude/agents/` papkasida quyidagi subagentlarni yarat va ulardan foydalan:

| Agent | Vazifasi |
|---|---|
| architect | Yangi modul yoki katta o'zgarishdan oldin dizaynni ko'rib chiqadi |
| business-logic-reviewer | Pul, qarz, savdo, ombor kodini shu promptdagi qoidalarga solishtiradi |
| security-reviewer | Ruxsatlar, maxfiy kalitlar, SQL, Telegram kontakt tekshiruvini tekshiradi |
| test-writer | Qoidalar uchun test yozadi va chekka holatlarni topadi |
| ux-copy-reviewer | Bot matnlarini oddiylik, hurmat va o'zbek tili to'g'riligi bo'yicha tekshiradi |

Har bir bosqich tugashidan oldin business-logic-reviewer va security-reviewer ni ishga tushir.

## 1. LOYIHA HAQIDA

Nomi: Nargiza Brend bot. Maqsad: oilaviy ayollar kiyim do'konining qog'oz qarz daftarini almashtirish, savdo va omborni hisoblash, mijozlar bilan aloqani avtomatlashtirish.

Do'kon ma'lumotlari:

- Nomi: Nargiza Brend
- Manzil: Sherbaraka bozori, 82-do'kon
- Ish vaqti: 07:00 – 18:00
- Telefon: +998 94 511 17 00
- Instagram: @nargiza_17_00_ — https://www.instagram.com/nargiza_17_00_/
- Vaqt zonasi: Asia/Tashkent
- Hali ma'lum emas (sozlamadan kiritiladi): dam olish kuni, xarita lokatsiyasi, do'kon rasmi/logotipi.

Hal qilinadigan muammolar:

- Qarzlar qog'oz daftarda — yo'qoladi, chalkashadi, uyda turib qarzni bilib bo'lmaydi.
- Qarzdorlarga birma-bir qo'ng'iroq qilish vaqt oladi.
- Kunlik/oylik savdo va qoldiq noma'lum.
- Mijozlar bilan doimiy aloqa yo'q.

## 2. FOYDALANUVCHILAR VA ROLLAR

| Rol | Kim | Botdagi murojaat | Ruxsatlar |
|---|---|---|---|
| admin | Faxriddin | Faxriddin aka | Hammasi |
| staff | Botir | Botir aka | Deyarli hammasi |
| staff | Nodira | Nodira opa | Deyarli hammasi |
| staff | Nilufar | Nilufar opa | Deyarli hammasi |
| customer | Xaridorlar va qarzdorlar (300–500, qarzdorlar ≤100) | "Umida opa" / "Jasur aka" | Faqat o'z ma'lumoti |

### Admin (to'liq boshqaruv)

- Barcha foydalanuvchilar, soni, telefonlar, barcha ma'lumotni ko'radi va o'zgartiradi.
- Faqat admin: kimnidir xodim qilish yoki xodimlikdan olish; xodimni bloklash; bot sozlamalari (do'kon ma'lumoti, tovar turlari, eslatma jadvali, karta raqamlari keyinchalik); o'chirilgan yozuvlarni qaytarish.
- Xodimlarning barcha imkoniyatlari ham adminda bor.
- Tizim xabarlari faqat adminga: backup holati, xatolar, AI xarajati, yaxlitlik tekshiruvi natijalari.
- "Botni yangilash" (yangi kod) — serverga deploy orqali, bot ichidan emas. Admin panelida: bot holati, xatolar, qayta ishga tushirish.

### Xodimlar (Botir aka, Nodira opa, Nilufar opa)

- Ikkala bo'limga to'liq kirish (o'qish, yozish, so'rash, o'zgartirish).
- Mijozlarni ko'radi, qo'shadi, ma'lumotini yangilaydi, o'chiradi — admindan so'ramasdan.
- Qarz, savdo, to'lov, qaytarish, kirim, e'lon — hammasi.
- Asosiy interfeys: erkin ovoz yoki matn (AI agent). Tugmalar — yordamchi.

### Mijozlar

- Faqat tugmalar, AI yo'q.
- Faqat o'z ma'lumotini ko'radi. Ruxsat kodda Telegram ID bo'yicha tekshiriladi.

### Rol berish qoidasi

- Har kim botga kirganda avtomatik customer bo'ladi.
- staff rolini faqat admin beradi. Bot hech qachon o'zi xodim qilmaydi.
- Birinchi admin .env dagi ADMIN_TELEGRAM_IDS orqali belgilanadi.

## 3. BO'LIMLAR (SECTIONS)

| Bo'lim | Kod | Egalari | Tovarlar |
|---|---|---|---|
| Do'kon | shop | Botir aka, Nodira opa | Kiyim, oyoq kiyim va boshqalar |
| Ichki kiyim | lingerie | Nilufar opa | Ichki kiyim |

### Yo'naltirish qoidasi (muhim)

- Yozuv kim aytganiga qarab emas, tovar turiga qarab bo'limga tushadi.
- "Ichki kiyim sotildi" — kim aytsa ham → lingerie.
- "Ko'ylak sotildi" — kim aytsa ham → shop.
- Bitta xabarda ikkala bo'lim tovari bo'lsa → ikkita yozuvga bo'linadi, bitta tasdiqlash kartasida ko'rsatiladi.
- Bo'lim aniq bo'lmasa → bot taxmin qilmaydi, so'raydi: "Qaysi bo'lim: Do'konmi yoki Ichki kiyimmi?"
- Tasdiqlash kartasida bo'lim doim ko'rinadi + [Bo'limni almashtirish] tugmasi.
- Pullar alohida: hisobotlarda bo'limlar hech qachon aralashmaydi.

### Bo'lim egasiga xabar

- Kimdir boshqa bo'limga yozsa, o'sha bo'lim egasiga darhol xabar boradi:
  - Nodira opa ichki kiyim sotsa → Nilufar opaga: "🔔 Nodira opa sizning bo'limingizga savdo qo'shdi: ichki kiyim, 80 000 so'm."
  - Nilufar opa kiyim sotsa → Botir aka va Nodira opaga.
- Botir aka va Nodira opa bir bo'lim egalari — ular o'rtasida har bir amal uchun xabar yuborilmaydi (kechki hisobotda ko'rinadi).
- Bu qoida savdo, qarz, to'lov, qaytarish, kirim uchun bir xil.

### Tovar turlari (admin sozlamadan o'zgartiradi)

Boshlang'ich ro'yxat (tasdiqlanishi kerak):

- shop: ko'ylak, yubka, shim, kofta, bluzka, kurtka/palto, oyoq kiyim, sumka, aksessuar
- lingerie: ichki kiyim
- Noaniq: pijama, xalat — mendan so'ra. Har bir turda sinonimlar ro'yxati bo'lsin (kirill va lotin): "туфли", "tufli", "poyabzal" → oyoq kiyim va h.k.

## 4. ASOSIY MODULLAR VA BIZNES QOIDALAR

### 4.1. Mijozlar

- Telefon majburiy (yagona kalit). Format: +998XXXXXXXXX ga normallashtiriladi ("90 123 45 67", "901234567", "+998 90..." → bir xil).
- Istisno: telefonsiz saqlashga ruxsat, lekin phone_missing=true + "⚠️ telefon kerak" belgisi. Har kuni 08:00 ro'yxatida telefoni yo'qlar ham ko'rsatiladi.
- Maydonlar: ism, telefon, jinsi (murojaat uchun: opa/aka), izoh ("Shahlo opaning qizi", "Yunusobodlik"), Telegram user (bog'langan bo'lsa).
- Bir xil ismlar: qidiruvda bir nechta topilsa, bot ro'yxat chiqaradi — har biri uchun: ism + izoh, to'liq telefon (xodimlarga), joriy qarz (bo'lim bilan), oxirgi xarid va sanasi. Tanlash: tugma [1][2][3] yoki ovoz/matn ("birinchisi", "Shahlo opaning qizi", "45 67 dagisi"). 5 tadan ko'p bo'lsa — [Yana ko'rsatish] yoki telefon oxirini so'rash. [➕ Yangi mijoz] doim bor.
- Qidiruv: kirill↔lotin transliteratsiya ("Умида" = "Umida"), noaniq moslik (fuzzy), telefon qismi bo'yicha.
- O'chirish: xodim o'chira oladi. Qarzi bo'lsa — avval ogohlantiradi va qarzni yopishni taklif qiladi. O'chirish = soft delete (bazadan o'chmaydi, admin qaytara oladi).
- Mijoz ro'yxatdan o'tsa va telefoni mavjud mijoz yozuviga mos kelsa → avtomatik bog'lanadi.

### 4.2. Qarz daftari

- Qarz: mijoz, bo'lim, tovarlar (tur + izoh + soni + narx), summa, sana, muddat (odatda belgilanadi), kim yozdi.
- "Qarz" yoki "nasiya" so'zi → qarz. Yozilganda mijozga avtomatik xabar (ro'yxatdan o'tgan bo'lsa).
- Qoldiq saqlanmaydi — har safar sum(debts) - sum(payments) - sum(write-offs) ± adjustments dan hisoblanadi.
- "Qarzini o'chir/yop" deyilsa bot so'raydi: [💵 To'ladi] [🤝 Kechib yuborildi] [❌ Bekor]. "To'ladi" = to'lov (kassaga pul tushdi). "Kechib yuborildi" = write-off (hisobotda zarar sifatida alohida). Bular hech qachon aralashmaydi.

### 4.3. To'lovlar

- "Umida 100 ming berdi" → to'lov.
- Taqsimot: sukut bo'yicha eng eski qarzdan yopiladi (FIFO). Xodim aniq aytsa ("oyoq kiyim qarzidan ayir") — o'sha qarzdan. Tasdiqlash kartasida qaysi qarz(lar) yopilayotgani ko'rinadi.
- Qisman to'lov qo'llab-quvvatlanadi. Ortiqcha to'lov bo'lsa — ogohlantir va so'ra.
- Karta raqamlari va mijozning chek yuborishi hozircha o'chiq (feature flag ENABLE_CARD_PAYMENTS=false). Kod tayyor tursin, lekin menyu va eslatmalarda ko'rinmasin.

### 4.4. Savdo daftari

- "Sotildi" → savdo (naqd). Mijoz ismi ixtiyoriy.
- Aralash: "Ko'ylak 500 ming, 200 berdi, qolgani qarz" → savdo 500 000 + qarz 300 000 (bog'langan), bitta kartada.
- Noaniq bo'lsa: "Naqd sotildimi yoki nasiyagami?"
- Chegirma: "500 minglik ko'ylakni 450 ga sotdim" → savdo 450 000, discount=50 000 izohda. Oylik hisobotda jami chegirma.
- Savdo omborni avtomatik kamaytiradi.
- Foyda / kelish narxi hisoblanmaydi (kerak emas).

### 4.5. Qaytarish va almashtirish

- "Umida ko'ylakni qaytardi, o'rniga oyoq kiyim oldi" → bot asl yozuvni topadi (bir nechta bo'lsa — tanlatadi), farqni hisoblaydi va ko'rsatadi: eski tovar, yangi tovar, farq, qarz/savdo "oldin → keyin".
- Qarzga olingan bo'lsa → qarz farqqa qarab o'zgaradi.
- Naqd bo'lsa → savdo yangilanadi; farqni mijoz to'laydimi yoki qaytariladimi — so'raydi.
- Faqat qaytarish → qarzdan ayiriladi yoki savdo bekor qilinadi; ombor qaytadan ko'payadi.
- Bo'limlar orasida almashtirish → summa bir bo'limdan boshqasiga o'tadi, egasiga xabar.
- Eski yozuv o'chirilmaydi — returned holati. Hisobotda qaytarishlar alohida.

### 4.6. Ombor (1-daraja)

- Qoldiq faqat tovar turi bo'yicha (ko'ylak: 45 ta).
- O'lcham, rang, model aytilsa — izoh sifatida saqlanadi, aytilmasa — so'ralmaydi.
- Kirim: "20 ta yubka keldi" yoki nakladnoy rasmi → kirim yozuvi (tasdiq bilan).
- Savdo → qoldiq kamayadi; qaytarish → ko'payadi.
- Qoldiq manfiy bo'lsa → ogohlantirish: "Yubka qoldig'i −2, kirim yozilmagan bo'lishi mumkin".
- Kam qolganda ogohlantirish (chegara turi bo'yicha sozlanadi).
- Boshlang'ich qoldiqni bir marta kiritish oqimi; oylik inventarizatsiya (sanalgan son kiritiladi, farq tuzatish yozuvi sifatida saqlanadi).

### 4.7. So'rovlar va hisobotlar (erkin savol)

Xodim tugmasiz oddiy savol beradi — bot niyatni va davrni o'zi aniqlaydi:

- "Kimlarning qarzi bor?" — barcha qarzdorlar, summa, muddat, kattasidan; jami.
- "Umidaning qarzi qancha?" — qoldiq, xaridlar, to'lovlar, muddat, telefon.
- "Muddati o'tganlar kim?" — necha kun o'tgani bilan.
- "Bugun/bu hafta/bu oy/bu yil/o'tgan oy/mart oyi/1-15 noyabr qancha savdo?" — jami summa, tovarlar soni, bo'limlar alohida.
- "Bu oy nima sotildi?" — tur bo'yicha soni va summasi. "Nechta yubka sotildi?"
- "Jami qancha qarz?", "Bu oy qancha qarz berildi va qaytdi?", "Bugun kim to'ladi?"
- "Nechta ko'ylak qoldi?", "Nima kam qoldi?"
- Solishtirish: "Bu oy o'tgan oydan ko'pmi?" — ikki davr yonma-yon, farq va foiz.
- Excel: har qanday hisobot so'ralsa .xlsx fayl qilib yuboradi (openpyxl).
- Uzun ro'yxatlar sahifalanadi.
- Yillik hisobotlar bot ishga tushgan kundan boshlab.

### 4.8. Davomli suhbat

- Bot oxirgi muhokama qilingan mijoz/yozuvni eslab qoladi ("unga yana 20 ming qo'sh", "telefoni qanaqa?"). Kontekst ma'lum vaqtdan keyin (masalan 15 daqiqa) yoki boshqa mijoz tilga olinsa yangilanadi.

### 4.9. Eski daftarni ko'chirish rejimi

- Xodim "Eski daftarni kiritish" rejimini yoqadi.
- Ovoz (daftarni o'qib beradi) yoki rasm (sahifa surati) yuboradi.
- Bot ro'yxat qaytaradi: ✅ aniq, ⚠️ telefon yo'q, ❓ o'qilmadi/noaniq. Noaniqni taxmin qilmaydi.
- Faqat qolgan qarz asl sanasi bilan kiritiladi.
- [✅ Hammasini saqlash] [✏️ Tuzatish] — tuzatish har bir qator bo'yicha.
- Dublikat tekshiruvi (telefon bo'yicha).

### 4.10. Tasdiqlash qoidasi (hamma yozuv uchun)

- Bazaga yozadigan har qanday amal (qarz, to'lov, savdo, qaytarish, kirim, o'zgartirish, o'chirish) avval tasdiqlash kartasini ko'rsatadi: [✅ Tasdiqlash] [✏️ Tuzatish] [❌ Bekor qilish].
- Savollar (o'qish) tasdiqsiz, darhol.
- Idempotentlik: tugma ikki marta bosilsa ham yozuv bir marta yoziladi.
- Bekor qilish: "oxirgi yozuvni bekor qil" — tasdiq bilan, yozuv tarixda qoladi.

## 5. MIJOZ TOMONI (faqat tugmalar)

### 5.1. Start va ro'yxatdan o'tish

Xush kelibsiz xabari (rasm bilan, agar admin rasm yuklagan bo'lsa):

```
Assalomu alaykum! Nargiza Brend do'koniga xush kelibsiz 🌸

👗 Ayollar kiyimlari, oyoq kiyimlari va ichki kiyimlar
📍 Sherbaraka bozori, 82-do'kon
🕖 Ish vaqti: 07:00 – 18:00
📞 +998 94 511 17 00
📸 Instagram: @nargiza_17_00_

Yangi kolleksiyalar, chegirmalar va do'kon yangiliklaridan birinchi bo'lib xabardor bo'lish uchun ro'yxatdan o'ting 👇
[📝 Ro'yxatdan o'tish]
```

Oqim:

1. Ism — Telegram'dagi ism tugma sifatida taklif qilinadi yoki yozadi.
2. "Sizga qanday murojaat qilaylik?" [Opa] [Aka]
3. "Telefon raqamingizni ulashing" — request_contact tugmasi. Xavfsizlik: yuborilgan kontaktning user_id si xabar yuboruvchining ID'siga teng bo'lishi shart (boshqaning kontaktini yuborib bo'lmaydi). Bu maydonni Telegram Bot API hujjatidan tekshir.
4. Rozilik matni: "Raqamingiz faqat do'kon xabarlari va xaridlaringiz hisobi uchun saqlanadi."
5. "✅ Rahmat, Umida opa! Siz ro'yxatdan o'tdingiz."
6. Telefon mavjud mijozga mos kelsa — qarzlar avtomatik bog'lanadi.

### 5.2. Mijoz menyusi

[💰 Mening qarzim] [📢 E'lonlar] [🏪 Do'kon haqida] [📞 Bog'lanish] + sozlamalarda [🔕 Reklamani o'chirish].

- Mening qarzim: bo'limlar alohida — qoldiq, nima olgani, to'lovlar, muddat.
- Do'kon haqida: manzil, lokatsiya (bo'lsa), ish vaqti, telefon, Instagram, rasm.
- Karta/to'lash tugmasi — feature flag o'chiq.

### 5.3. Mijozga avtomatik xabarlar (muloyim ohangda, "Umida opa")

| Qachon | Xabar |
|---|---|
| Qarz yozilganda | Nima oldi, summa, muddat, umumiy qarz |
| Muddatdan 2 kun oldin | Muddat yaqinlashmoqda |
| Muddat kuni | Bugun to'lov kuni |
| Muddat o'tgach har 3 kunda, ko'pi bilan 5 marta | Muddat o'tgani haqida muloyim eslatma |

Reklama o'chirilgan bo'lsa ham qarz eslatmalari keladi. Bot faqat "Start" bosganlarga yoza oladi — qolganlari 08:00 qo'ng'iroq ro'yxatida.

## 6. E'LONLAR (barcha xodimlar)

- [📢 E'lon] yoki "e'lon yubor" → matn va/yoki rasm.
- Kimga: hammaga / qarzdorlarga / muddati o'tganlarga / tanlangan bitta odamga (ism/telefon bo'yicha qidirib).
- Oldindan ko'rish: "87 kishiga boradi" → [Yuborish] [Bekor].
- Natija: "82 tasiga yetdi, 5 tasi botni bloklagan".
- Reklamani o'chirganlarga reklama e'loni bormaydi (shaxsiy xabar va qarz eslatmasi boradi).
- Telegram tezlik cheklovi: xabarlar navbat bilan, pauza bilan yuboriladi. Aniq limitlarni Telegram Bot API hujjatidan tekshir. RetryAfter xatolarini to'g'ri qayta ishlat.
- Umumiy e'londa hech qachon kimningdir qarzi ko'rsatilmaydi.
- Tavsiya (xodimlarga eslatma sifatida): haftasiga 1–2 reklama.

## 7. AVTOMATIK VAZIFALAR (Asia/Tashkent)

| Vaqt | Kimga | Vazifa |
|---|---|---|
| Har kuni 08:00 | Xodimlar | Qo'ng'iroq ro'yxati: muddati o'tganlar (summa, bosiladigan telefon) + telefoni yo'q qarzdorlar. Dam olish kunida yuborilmaydi |
| Har kuni 20:00 | Xodimlar | Kunlik savdo hisoboti: bo'limlar alohida, tovar turlari, qaytarishlar, chegirmalar, to'lovlar, yangi mijozlar soni |
| Har kuni | Mijozlar | Muddat eslatmalari (5.3) |
| Har soatda | — | Bazaning backup'i |
| Har kuni 03:00 | Admin | Kunlik backup + Telegram'ga shifrlangan fayl |
| Har kecha | Admin | Yaxlitlik tekshiruvi |
| Har hafta | Admin | Qarzlar Excel'i + backup tiklash testi |
| Har oy | Xodimlar | Oylik hisobot, inventarizatsiya eslatmasi |

## 8. AI AGENT (faqat xodimlar uchun)

### 8.1. Provayder

- Gemini API — asosiy. Sabab: audioni to'g'ridan-to'g'ri qabul qiladi (alohida STT kerak emas), tool/function calling bor.
- Python SDK: Google'ning joriy rasmiy SDK'si (google-genai bo'lishi kerak — joriy hujjatdan tekshir). Model nomini hardcode qilma — .env dagi GEMINI_MODEL.
- Provayder abstraksiyasi: ai/base.py da interfeys (AIProvider), ai/gemini.py amalga oshirish. Keyin ai/claude.py qo'shish mumkin bo'lsin (Claude uchun ovoz alohida STT orqali). Provayder .env dagi AI_PROVIDER bilan tanlanadi.
- Maxfiylik: Gemini bepul tarifida ma'lumotlar Google mahsulotlarini yaxshilash uchun ishlatilishi mumkin. Real mijoz ma'lumotlari bilan faqat pullik tarif (Cloud billing yoqilgan kalit). Bepul tarif — faqat soxta ma'lumot bilan test. Buni DEPLOY hujjatida aniq yoz.

### 8.2. Agent qanday ishlaydi

1. Xodim ovoz yoki matn (kirill yoki lotin) yuboradi.
2. Kontekst bilan Gemini'ga yuboriladi: xodim kimligi, sana/vaqt (Toshkent), tovar turlari va sinonimlar, suhbat konteksti (oxirgi mijoz), mavjud tool'lar.
3. Gemini tool chaqiradi (strukturali argumentlar). Bitta xabarda bir nechta tool bo'lishi mumkin.
4. Kod argumentlarni Pydantic bilan tekshiradi.
5. O'qish tool'i → darhol javob. Yozish tool'i → tasdiqlash kartasi.
6. Tasdiqdan keyin service qatlami yozadi, xabarlar yuboriladi.

### 8.3. Tool'lar (taxminiy ro'yxat, architect bilan yakunla)

Yozish (tasdiq bilan): add_debt, add_payment, add_sale, add_mixed_sale (savdo+qarz), register_return, register_exchange, add_stock_in, stock_count, update_customer, create_customer, delete_customer, close_debt (to'ladi/kechildi), cancel_last_entry, draft_broadcast.
O'qish: search_customer, get_customer_debt, list_debtors, list_overdue, list_missing_phones, get_sales_report(period, section?, category?), compare_periods, get_debt_report, list_payments, get_stock, list_low_stock, export_excel(report).

### 8.4. Qat'iy qoidalar

- AI hech qachon hisob qilmaydi. Summalar, qoldiqlar, farqlar, taqsimot — faqat kod va SQL.
- AI ruxsatni hal qilmaydi. Har bir tool foydalanuvchi rolini kodda tekshiradi.
- AI taxmin qilmaydi: summa, mijoz yoki bo'lim noaniq bo'lsa — tool o'rniga savol qaytaradi.
- Raqamlarni so'z bilan aytilishi ("uch yuz ellik ming", "1.5 mln", "yarim million", "350") — to'g'ri parse qilinsin; noaniq bo'lsa so'rasin. Bu uchun alohida testlar.
- Bo'lim aniqlash ham kodda qayta tekshiriladi (tovar turi → bo'lim xaritasi).
- Har bir AI chaqiruvi log qilinadi (token soni, xarajat taxmini, kechikish) — mijoz shaxsiy ma'lumotisiz.
- AI xizmati ishlamasa — xodimga tushunarli xabar + tugmali menyu orqali ishlash imkoni; adminga xabar.

### 8.5. Baholash (eval) to'plami

- tests/eval/phrases.yaml — kamida 60 ta real ko'rinishdagi o'zbekcha jumla (lotin + kirill, sheva, raqamlar so'z bilan, aralash sotuv, qaytarish, bir xil ism) va kutilgan tool + argumentlar.
- scripts/run_eval.py — Gemini'ga yuborib, aniqlik foizini chiqaradi.
- Men oilaning 10–15 ta real ovozli xabarini beraman — tests/eval/audio/ (git'ga yuklanmaydi).

## 9. MA'LUMOT XAVFSIZLIGI (ENG MUHIM QISM)

Qarz yoki savdo yozuvi yo'qolsa — oila pul yo'qotadi. Har bir qatlamni jiddiy qur.

### 9.1. Yozish darajasida

- Har bir biznes amal — bitta DB tranzaksiya (hammasi yoki hech narsa).
- Soft delete — hech narsa bazadan o'chirilmaydi (deleted_at, deleted_by).
- Qoldiqlar hisoblanadi, saqlanmaydi (kerak bo'lsa keyinchalik materialized view, lekin manba — yozuvlar).
- Pul — butun son (so'm), BIGINT, hech qachon float.
- DB cheklovlari: NOT NULL, FOREIGN KEY, CHECK (amount > 0), unique telefon (o'chirilmaganlar orasida).
- Idempotentlik kaliti har bir tasdiqlash amalida.
- Audit log — har bir insert/update/soft-delete: kim, qachon, jadval, yozuv ID, eski qiymat, yangi qiymat (JSONB).

### 9.2. Backup (3-2-1)

| Chastota | Saqlash |
|---|---|
| Har soat | 48 soat |
| Har kun 03:00 | 30 kun |
| Har hafta | 3 oy |
| Har oy | 1 yil |

- pg_dump (custom format) → age bilan shifrlash → joylar:
  - Server diskida (DB volume'dan alohida papka),
  - Adminning Telegram'iga (kunlik),
  - Google Drive (ixtiyoriy, mendan so'ra; sozlash yo'riqnomasini yoz).
- Shifr kaliti: hech qachon serverda shifrlanmagan holda bir joyda emas. Menga uni parol menejerida va qog'ozda saqlashni o'rgat.
- Har kuni adminga: "✅ Backup OK: N qarz, M savdo, hajmi X MB". Backup bo'lmasa yoki hajm keskin kamaysa — ogohlantirish.
- Haftalik avtomatik tiklash testi: backup vaqtinchalik bazaga tiklanadi, jadval yozuvlari soni solishtiriladi.
- docs/RUNBOOK.md — backup'dan tiklashning qadam-baqadam yo'riqnomasi.

### 9.3. Yaxlitlik tekshiruvi (har kecha)

Barcha qoldiqlar qayta hisoblanadi; manfiy qarz, ortiqcha to'lov, dublikat to'lov, manfiy ombor, bog'lanmagan yozuvlar qidiriladi → adminga hisobot.

### 9.4. Kassa bilan solishtirish

20:00 hisobotida "kassadagi pul bilan solishtiring" eslatmasi.

### 9.5. Deploy va migratsiya

- Har bir deploy va Alembic migratsiyasidan oldin avtomatik backup.
- Migratsiyalar avval staging/nusxada sinaladi.

### 9.6. Server va kirish

- PostgreSQL tashqariga ochilmaydi (faqat Docker ichki tarmog'i).
- DB ma'lumotlari Docker named volume'da.
- SSH faqat kalit, parol bilan kirish o'chiq, ufw firewall, fail2ban, avtomatik xavfsizlik yangilanishlari.
- Botni restart: unless-stopped bilan ishga tushirish; healthcheck; bot to'xtasa adminga xabar (tashqi oddiy monitoring ham tavsiya qil).
- Xodim akkaunti bloklanishi (telefon yo'qolsa) — admin buyrug'i bilan darhol.

### 9.7. Huquqiy

O'zbekiston "Shaxsiy ma'lumotlar to'g'risida"gi qonunga 2026-yilda o'zgartirishlar kiritilgan (lokalizatsiya talabi toraytirilgan). Men yurist emasman — server joylashuvi bo'yicha yakuniy qarorni men qabul qilaman. Ro'yxatdan o'tishda rozilik matni majburiy.

## 10. TEXNIK STACK

| Qism | Texnologiya |
|---|---|
| Til | Python 3.12+ |
| Telegram | aiogram 3.x (FSM, routers, middlewares) |
| AI | Gemini API (google-genai SDK) — provayder abstraksiyasi bilan |
| DB | PostgreSQL 16+ |
| ORM | SQLAlchemy 2.x async + asyncpg |
| Migratsiya | Alembic |
| Rejalashtirish | APScheduler (yoki aiogram bilan mos async scheduler) — Asia/Tashkent |
| Sozlamalar | pydantic-settings (.env) |
| Validatsiya | Pydantic v2 |
| Excel | openpyxl |
| Transliteratsiya / fuzzy | o'zing yozgan kirill↔lotin xaritasi + rapidfuzz (yoki Postgres pg_trgm) |
| Log | structlog yoki standart logging (JSON), shaxsiy ma'lumot maskalangan |
| Test | pytest, pytest-asyncio, testcontainers (Postgres) yoki docker test DB |
| Sifat | ruff, mypy, pre-commit |
| Konteyner | Docker, docker compose |
| Backup | pg_dump, age, cron/scheduler |
| CI | GitHub Actions (lint + test) |

Versiyalarni o'rnatishdan oldin joriy barqarorini tekshir va pyproject.toml da qotir.

Bot rejimi: ishlab chiqishda long polling. Production'da polling yoki webhook — qaror va sababini yoz.

## 11. PAPKA TUZILMASI

```
nargiza-brend/
├── CLAUDE.md                     # Claude Code uchun qisqa qoidalar (shu promptdan xulosa)
├── NARGIZA_BREND_MASTER_PROMPT.md
├── README.md
├── pyproject.toml
├── .env.example                  # barcha o'zgaruvchilar, qiymatlarsiz
├── .gitignore                    # .env, backups/, tests/eval/audio/ ...
├── docker-compose.yml            # bot + postgres (+ backup)
├── docker-compose.prod.yml
├── Dockerfile
├── alembic.ini
├── .claude/
│   └── agents/                   # architect, business-logic-reviewer, ...
├── .github/workflows/ci.yml
├── docs/
│   ├── ARCHITECTURE.md           # komponentlar, oqimlar, diagrammalar (mermaid)
│   ├── BUSINESS_RULES.md         # shu promptning 3–7 bo'limlari, raqamlangan qoidalar
│   ├── DATA_MODEL.md             # jadvallar, ER-diagramma
│   ├── DATA_SAFETY.md            # 9-bo'lim
│   ├── AI_AGENT.md               # tool'lar, promptlar, eval
│   ├── DEPLOY.md                 # local → staging (Azure) → production (Contabo)
│   ├── RUNBOOK.md                # avariya: backup tiklash, bot to'xtasa, kalit yo'qolsa
│   ├── SETUP_KEYS.md             # BotFather, Gemini kaliti, billing — men uchun
│   ├── USER_GUIDE_STAFF.md       # oila uchun oddiy o'zbekcha qo'llanma + misol jumlalar
│   ├── ADMIN_GUIDE.md
│   └── CHANGELOG.md
├── bot/
│   ├── main.py                   # kirish nuqtasi
│   ├── config.py                 # pydantic-settings
│   ├── handlers/
│   │   ├── common/               # start, ro'yxatdan o'tish
│   │   ├── customer/             # mijoz menyusi
│   │   ├── staff/                # erkin matn/ovoz → agent, tasdiqlash callback'lari
│   │   └── admin/                # admin buyruqlari va sozlamalar
│   ├── keyboards/
│   ├── middlewares/              # auth/rol, throttling, logging, error
│   ├── texts/                    # barcha bot matnlari (uz_latn) bir joyda
│   ├── services/                 # BIZNES MANTIQ (Telegram'dan mustaqil)
│   │   ├── customers.py
│   │   ├── debts.py
│   │   ├── payments.py
│   │   ├── sales.py
│   │   ├── returns.py
│   │   ├── inventory.py
│   │   ├── reports.py
│   │   ├── broadcasts.py
│   │   ├── notifications.py
│   │   ├── routing.py            # tovar turi → bo'lim
│   │   └── import_notebook.py
│   ├── ai/
│   │   ├── base.py               # AIProvider interfeysi
│   │   ├── gemini.py
│   │   ├── tools.py              # tool sxemalari (Pydantic)
│   │   ├── prompts.py            # tizim prompti
│   │   └── dispatcher.py         # tool → service
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│   │   └── repositories/
│   ├── scheduler/
│   │   ├── jobs.py
│   │   └── backup.py
│   └── utils/
│       ├── phone.py              # normallashtirish
│       ├── translit.py           # kirill↔lotin
│       ├── money.py              # parse va formatlash
│       └── dates.py              # "o'tgan oy", "mart" → davr
├── migrations/
├── scripts/
│   ├── run_eval.py
│   ├── backup.sh
│   ├── restore.sh
│   └── seed_dev.py               # soxta ma'lumotlar
└── tests/
    ├── unit/
    ├── integration/
    └── eval/
```

Arxitektura qoidasi: services/ Telegram'ni ham, AI'ni ham bilmaydi. Handler va AI dispatcher faqat service'larni chaqiradi. Shunda biznes mantiq to'liq testlanadi va AI provayderini almashtirish oson.

## 12. MA'LUMOTLAR MODELI (boshlang'ich, architect bilan yakunla)

- users — telegram_id, role (admin/staff/customer), name, address_form (opa/aka), phone, is_blocked, ads_opt_out, script_pref, created_at
- staff_profiles — user_id, display_name ("Nodira opa"), owned_section_ids
- sections — code (shop/lingerie), name, card_number (nullable), card_holder
- categories — name, section_id, synonyms[], low_stock_threshold, is_active
- customers — name, phone (nullable + phone_missing), address_form, note, user_id (nullable), deleted_at...
- debts — customer_id, section_id, total_amount, due_date, status, source (new/import), created_by, created_at, deleted_at
- debt_items — debt_id, category_id, quantity, unit_price, note
- payments — customer_id, section_id, amount, kind (payment/write_off), created_by, created_at
- payment_allocations — payment_id, debt_id, amount
- sales — section_id, customer_id (nullable), total_amount, discount_amount, linked_debt_id (nullable), created_by, created_at
- sale_items — sale_id, category_id, quantity, unit_price, note
- returns — original_type (sale/debt), original_id, items, amount, exchange_for_id, created_by
- stock_movements — category_id, quantity (+/−), reason (stock_in/sale/return/count_adjustment), ref_id, created_by
- broadcasts / broadcast_recipients — matn, rasm, segment, status, delivered/failed
- reminders_log — mijozga yuborilgan eslatmalar (takrorlanmasligi uchun)
- settings — kalit-qiymat (do'kon ma'lumoti, vaqtlar, dam olish kuni, feature flaglar)
- audit_log — actor_id, action, table, record_id, old (JSONB), new (JSONB), at
- idempotency_keys
- ai_calls — user_id, tokens, cost_estimate, latency, tool, success (shaxsiy ma'lumotsiz)

Barcha vaqtlar timestamptz, ko'rsatishda Asia/Tashkent.

## 13. UX VA MATN QOIDALARI

- Murojaat: "Nodira opa", "Botir aka", "Nilufar opa", "Faxriddin aka"; mijozlarga "Umida opa"/"Jasur aka".
- Kirish: kirill va lotin; javoblar lotinda (keyinchalik foydalanuvchi sozlamasi bilan kirill).
- Xodim asosiy menyusi (yordamchi): [➕ Qarz] [🛍 Savdo] [💵 To'lov] [🔍 Qidirish] [📊 Hisobot] [📦 Ombor] [📢 E'lon] [⚙️ Boshqa].
- Tasdiqlash kartalari: qisqa, emoji bilan tuzilgan, summa 450 000 so'm formatida, bo'lim doim ko'rinadi.
- Xatolik matnlari ayblovsiz va yechim bilan: "Tushunmadim, summani yana bir aytib bering".
- Mijoz eslatmalari doim muloyim.
- Barcha matnlar bot/texts/ da — kodga tarqalmasin.
- ux-copy-reviewer har bir yangi matnni tekshiradi.

## 14. ISH BOSQICHLARI (har biri oxirida mendan tasdiq ol)

- **0-bosqich — Tayyorgarlik.** Muhit: Python, Docker, git tekshiruvi. Repo skeleti, pyproject, ruff/mypy/pre-commit, .env.example, .gitignore, CI. CLAUDE.md va .claude/agents/ yaratish. docs/ dagi barcha hujjatlar skeleti; BUSINESS_RULES.md ni to'liq yozish — men o'qib tasdiqlayman. Ochiq savollar ro'yxati (pijama/xalat, dam olish kuni va h.k.) — menga ber. Qabul: docker compose up bo'sh bot + postgres ko'taradi, CI yashil, BUSINESS_RULES tasdiqlangan.
- **1-bosqich — Poydevor.** DB modellari, Alembic, audit log, soft delete, idempotentlik, utils (phone, translit, money, dates) + to'liq testlar. Start, ro'yxatdan o'tish (kontakt tekshiruvi bilan), rollar, admin xodim tayinlash, mijoz menyusi, "Do'kon haqida". Backup skripti (soatlik/kunlik, shifrlash, Telegram'ga yuborish) va restore skripti — shu bosqichdayoq. Qabul: ro'yxatdan o'tish ishlaydi, admin xodim tayinlaydi, backup→restore sinovdan o'tdi.
- **2-bosqich — Qarz daftari va mijozlar (tugmalar orqali).** Mijoz CRUD, bir xil ism tanlash, qarz, to'lov (FIFO + tanlangan), qarzni yopish (to'ladi/kechildi), bekor qilish, tasdiqlash kartalari, mijozga xabarlar. Qabul: barcha qarz qoidalari testlari yashil, men qo'lda sinab ko'raman.
- **3-bosqich — AI agent (matn).** Provayder abstraksiyasi, Gemini, tool'lar, dispatcher, kontekst, so'rovlar va hisobotlar (o'qish tool'lari), eval to'plami. Qabul: eval aniqligi ≥ 90% (yozish tool'larida), xato tasdiqdan o'tmaydi.
- **4-bosqich — Ovoz.** Ovozli xabarlarni Gemini'ga yuborish, real oila ovozlarida sinov. Qabul: real ovozlarda natija men bilan birga baholandi; zaif joylar hujjatlashtirildi.
- **5-bosqich — Savdo, ombor, qaytarish.** Savdo, aralash savdo, chegirma, qaytarish/almashtirish, kirim, qoldiq, inventarizatsiya, bo'lim egasiga xabarlar. Qabul: barcha biznes testlar yashil.
- **6-bosqich — Hisobotlar va eksport.** Davr parse ("o'tgan oy", "mart"), solishtirish, Excel, 20:00 hisobot.
- **7-bosqich — Eslatmalar va e'lonlar.** Mijoz eslatmalari jadvali, 08:00 ro'yxat, e'lonlar (segment + bitta odam), tezlik cheklovi, reklama o'chirish.
- **8-bosqich — Eski daftarni ko'chirish.** Ovoz va rasm orqali import rejimi.
- **9-bosqich — Ma'lumot xavfsizligi yakuni.** Yaxlitlik tekshiruvi, haftalik restore testi, monitoring, Google Drive (agar men rozi bo'lsam).
- **10-bosqich — Deploy.** Staging: Azure for Students (Ubuntu, B1s) — server hardening, Docker, deploy skripti. Production: arzon pullik VPS (Contabo) — men qaror qilganimda. DEPLOY.md, RUNBOOK.md yakuni.
- **11-bosqich — Oilani ishga tushirish.** USER_GUIDE_STAFF.md (oddiy tilda, misol jumlalar bilan, chop etsa bo'ladigan bir sahifalik "shpargalka"). 2–3 hafta daftar bilan parallel ishlash rejasi va har kuni solishtirish tartibi.

## 15. MENGA O'RGATISH (SETUP_KEYS.md va jonli yo'riqnoma)

Sen mening akkauntlarimga o'zing kira olmaysan va ro'yxatdan o'ta olmaysan — bularni men qilaman. Sen har birini qadam-baqadam, skrinshot qayerda nima bosishni tasvirlab tushuntirasan, men kalitni .env ga qo'ygach, sen sozlashni va tekshirishni o'zing bajarasan. Har bir yo'riqnomani rasmiy manbadan tekshirib yoz, interfeys o'zgargan bo'lishi mumkin.

- Telegram bot: @BotFather → /newbot → nom va username → token → .env. Bot tavsifi, rasmi, buyruqlar ro'yxati. Tokenni hech kimga bermaslik; sizib chiqsa /revoke.
- Mening Telegram ID'm — qanday bilish (admin uchun).
- Gemini API kaliti: Google AI Studio → API key yaratish → .env. Cloud billing yoqish (real ma'lumot uchun pullik tarif shart). Google AI Pro obunam bilan beriladigan Google Cloud kreditlarini faollashtirish (agar mening obunamga tegishli bo'lsa — tekshirib ko'rsat). Budjet ogohlantirishi (masalan oyiga $5).
- GitHub: private repo, SSH kalit, birinchi push; .env hech qachon push qilinmasligini tekshirish.
- Server: Azure for Students'da VM yaratish (faqat B1s, budjet ogohlantirishi), SSH kalit, keyin Contabo.
- age shifr kaliti: yaratish, qayerda saqlash (parol menejeri + qog'oz), tiklashni sinash.
- Google Drive backup (ixtiyoriy): sozlash.
- Xarajat kuzatuvi: Gemini va server sarfini qayerda ko'rish.
- Kundalik operatsiyalar: loglarni ko'rish, botni qayta ishga tushirish, yangi versiyani deploy qilish, backup'dan tiklash.

## 16. HALI OCHIQ SAVOLLAR (0-bosqichda mendan so'ra)

- Pijama, xalat va boshqa tovarlar qaysi bo'limga kiradi? Tovar turlari ro'yxatini tasdiqlash.
- Do'konning dam olish kuni.
- Xarita lokatsiyasi va do'kon rasmi/logotipi.
- Boshlang'ich ombor qoldig'i (tur bo'yicha soni).
- Kam qolgan tovar chegarasi (har tur uchun nechta).
- Google Drive backup kerakmi.
- Production server qachon va qaysi.

## 17. YAKUNIY TALAB

Har bir bosqich tugaganda qisqa hisobot ber:

- ✅ nima qilindi,
- 🧪 qanday sinash (aniq buyruqlar va botga yuboriladigan misol xabarlar),
- ⚠️ ma'lum cheklovlar va xavflar,
- ❓ mendan kerak bo'lgan narsalar,
- ➡️ keyingi bosqich.

Loyiha production'ga tayyor deb hisoblanadi, qachonki: barcha testlar yashil, backup→restore sinalgan, monitoring ishlaydi, oila qo'llanmasi tayyor, 2 haftalik parallel sinovda daftar va bot hisoblari mos kelgan.
