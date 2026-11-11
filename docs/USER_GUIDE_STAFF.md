# Xodimlar uchun qo'llanma (qarz daftari)

> Bu qo'llanma oila a'zolari uchun — oddiy tilda.
> Botga **tugmalar** bilan ham, **oddiy gap bilan ham** (yozib yoki ovozli xabar yuborib) ishlash mumkin.

## Bosh menyu (pastdagi tugmalar)

| Tugma | Nima qiladi |
|---|---|
| ➕ Qarz | Mijozga qarz yozish |
| 💵 To'lov | Mijoz pul berdi — yozish |
| 🔍 Qidirish | Mijozni topish, qarzini ko'rish |
| ⚙️ Boshqa | Xato yozilgan yozuvni bekor qilish |

> Tugmalar doim pastda turadi. Adashib ketsangiz, `/start` ni bosing.

## 1. Mijozning qarzini ko'rish
1. **🔍 Qidirish** → ismini yozing (kirill yoki lotin, xato yozsangiz ham topadi) yoki telefonining oxirgi raqamlarini (masalan `45 67`).
2. Ro'yxatdan kerakli odamni tanlang. Bir xil ismli bo'lsa, eslatma va telefon bilan ajratasiz.
3. Mijoz kartasi chiqadi: qarzi (bo'limlar alohida), qaysi tovar, muddati.

## 2. Qarz yozish
1. **➕ Qarz** → mijozni toping va tanlang (yo'q bo'lsa **➕ Yangi mijoz**).
2. Tovarni tanlang → nechta → bittasining narxi (masalan `175 ming` yoki `175000`).
3. Rangi/o'lchami bo'lsa yozing, bo'lmasa **⏭ O'tkazib yuborish**.
4. Yana tovar bo'lsa **➕ Yana tovar**, bo'lmasa **✅ Tayyor**.
5. Muddatni tanlang: 1 hafta / 2 hafta / 1 oy / sana / muddatsiz.
6. Bot hammasini ko'rsatadi — to'g'ri bo'lsa **✅ Tasdiqlash**.

Ichki kiyim va boshqa kiyim bir qarzga qo'shilsa, bot o'zi ikki qarzga ajratadi (har biri o'z bo'limida).
Mijoz botga ulangan bo'lsa, unga o'zi xabar boradi.

## 3. To'lov yozish
1. **💵 To'lov** → mijozni tanlang.
2. Ikki bo'limda qarzi bo'lsa — qaysi bo'limdan ekanini tanlang.
3. Qancha berdi: `100 ming`.
4. Bot qaysi qarzdan ayirilishini ko'rsatadi (eng eskisidan). Boshqasidan ayirmoqchi bo'lsangiz **📋 Qarzni tanlash**.
5. **✅ Tasdiqlash**.

Qarzidan **ko'p** summa yozsangiz, bot qabul qilmaydi va qarz qancha ekanini aytadi.

## 4. Kechib yuborish
Mijoz kartasida **🤝 Kechish** → summa (yoki **Hammasini kechish**) → tasdiqlang.
Kechilgan summa kassaga pul tushgani emas — hisobotda alohida ko'rinadi.

## 5. Xato yozdim — bekor qilish
**⚙️ Boshqa** (admin: Admin paneli → **🚫 Yozuvni bekor qilish**) → oxirgi yozuvlardan kerakligini tanlang → tasdiqlang.
Yozuv o'chmaydi, "bekor qilingan" bo'lib tarixda qoladi. Mijozga xato haqida uzr xabari boradi.
To'lovi bor qarzni bekor qilish uchun avval o'sha to'lovni bekor qiling.

## 6. Mijozni o'chirish
Mijoz kartasida **🗑 O'chirish**. Qarzi bo'lsa, bot ogohlantiradi. Mijoz bazadan o'chmaydi — admin uni qaytara oladi.

## Eslatmalar
- Har bir yozuvdan oldin bot **kartani** ko'rsatadi. Tugmani ikki marta bossangiz ham yozuv bir marta yoziladi.
- Karta 30 daqiqadan keyin eskiradi — qaytadan boshlang.
- Boshqa bo'limga yozsangiz (masalan, Nodira opa ichki kiyim qarzi yozsa), o'sha bo'lim egasiga xabar boradi.
- Summani aniq ayting. "350" desangiz bot 350 000 so'm deb tushunadi va kartada ko'rsatadi. "1500" kabi noaniq bo'lsa, qayta so'raydi.


## 🎤 Oddiy gap va ovozli xabar bilan ishlash

Tugma bosmasdan, shunchaki yozing yoki **mikrofon tugmasini bosib gapiring**. Misollar:

| Aytasiz | Bot nima qiladi |
|---|---|
| «Umida 100 ming berdi» | To'lov kartasini ko'rsatadi |
| «Jasur akaga shim 450 ming nasiya, 2 haftaga» | Qarz kartasini ko'rsatadi |
| «Umidaning qarzi qancha?» | Qarzini darhol aytadi |
| «Kimlarning qarzi bor?» / «Muddati o'tganlar kim?» | Ro'yxat beradi |
| «Umida opaning qarzini kechdim» | Kechish kartasini ko'rsatadi |
| «Oxirgi yozuvni bekor qil» | Bekor qilish kartasini ko'rsatadi |
| «Yangi mijoz: Laylo opa, 90 123 45 67» | Yangi mijoz kartasini ko'rsatadi |
| «Unga yana 20 ming qo'sh» | Oxirgi gaplashilgan mijozni eslaydi (15 daqiqagacha) |

Summani qanday aytsangiz ham bo'ladi: «350 ming», «uch yuz ellik ming», «yarim million», «1,5 million».

**Bot tushunmasa, taxmin qilmaydi — so'raydi:**
- bir xil ismli mijoz bo'lsa — tugmalar bilan «qaysi biri?» deb so'raydi;
- ikki bo'limda qarzi bo'lsa — «qaysi bo'lim?»;
- muddat aytilmasa — «1 hafta / 2 hafta / 1 oy / muddatsiz»;
- tovar yoki summani tushunmasa — qisqa savol beradi. Javobni yozing yoki ovoz bilan ayting.

**Muhim:** bot hech narsani o'zi yozmaydi. Har safar kartani ko'rsatadi — tekshirib **✅ Tasdiqlash** bosasiz.
Ovozli xabar 1,5 daqiqagacha bo'lsin. Bot «hozir tinglay olmayapman» desa, pastdagi tugmalardan foydalaning.


## 🛍 Savdo, 📦 ombor va ↩️ qaytarish (yozib yoki gapirib)

| Aytasiz | Bot nima qiladi |
|---|---|
| «Ko'ylak 450 ming sotildi» | Naqd savdo kartasi (mijozsiz) |
| «500 minglik ko'ylakni 450 ga sotdim» | Chegirma bilan: savdo 450 000, chegirma 50 000 |
| «Umidaga ko'ylak 500 ming, 200 berdi, qolgani qarz» | Savdo 500 000: naqd 200 000, nasiya 300 000 (muddatni so'raydi) |
| «20 ta yubka keldi» | Ombor kirimi kartasi |
| «Ko'ylak 45 ta, yubka 30 ta» (sanab chiqqaningizda) | Ombor sanog'i: farq «tuzatish» bo'lib yoziladi |
| «Nechta ko'ylak qoldi?» / «Nima kam qoldi?» | Darhol javob (kam qolish chegarasi — 3 ta) |
| «Umida ko'ylakni qaytardi» | Qaytarish kartasi |
| «Umida ko'ylakni qaytardi, o'rniga oyoq kiyim oldi 280 ming» | Almashtirish: qaytarish + yangi savdo, sof farq kartada |

**Qaytarishda pul qanday hisoblanadi:**
- Qarzga olingan tovar qaytsa — avval **qarzdan ayiriladi**. Qarz yopilgandan keyin ortib qolgan pul **mijozga naqd qaytariladi**.
- Chegirma bilan sotilgan tovarning qiymati chegirma hisobga olingan holda qaytariladi (to'langandan ortiq qaytmaydi).
- Qaysi xariddan ekani aniq bo'lmasa, bot tugmalar bilan so'raydi. Nechtasi qaytgani aytilmasa ham so'raydi.
- Muddat cheklovi yo'q.
- Xato bo'lsa: «⚙️ Boshqa» → **🚫 Yozuvni bekor qilish** — savdo, qaytarish, qarz va to'lov hammasi bekor qilinadi. Qaytarilgan tovari bor savdoni bekor qilish uchun avval qaytarishni bekor qiling. Mijozga allaqachon qaytarib berilgan naqd pulni dastur qaytarib ola olmaydi — buni o'zingiz hal qilasiz.

**Ombor:** 📦 **Ombor** tugmasi hamma qoldiqni ko'rsatadi. Qoldiq manfiy bo'lsa bot ogohlantiradi («kirim yozilmagan bo'lishi mumkin»). Boshlang'ich qoldiqni bir marta sanoq bilan kiriting.


## 📊 Hisobot va Excel

**📊 Hisobot** tugmasi bugungi hisobotni ko'rsatadi. Boshqa davr uchun yozing yoki ayting:

| Aytasiz | Bot nima qiladi |
|---|---|
| «O'tgan oy hisoboti» / «mart» / «1–15 noyabr» | Shu davr hisoboti |
| «Bu oy o'tgan oydan ko'pmi?» | Ikki davrni solishtiradi (farq va foiz bilan) |
| «Bugun kim to'ladi?» | To'lovlar ro'yxati va jami |
| «Qarzdorlarni Excelga ber» / «Hisobotni Excelga ber» / «Ombor Excel» | Excel fayl yuboradi |

- Do'kon va ichki kiyim bo'limlari **alohida** chiqadi, hech qachon qo'shilmaydi.
- «Kassaga kirdi (sof)» = savdodan tushgan naqd + qarz to'lovlari − mijozga qaytarilgan naqd. Kechilgan qarz va qarzdan ayirilgan qaytarish kassaga kirmaydi.
- Har kuni **20:00** da hisobot o'zi keladi — kassadagi pulni shu bilan solishtiring. Har oyning 1-kuni o'tgan oy hisoboti keladi.
- Davr aytilmasa, bot so'raydi (hisobot uchun «bugun» deb olinadi).
- Excel fayl faqat sizga yuboriladi; uni boshqalarga uzatmang (telefon raqamlari bor).
