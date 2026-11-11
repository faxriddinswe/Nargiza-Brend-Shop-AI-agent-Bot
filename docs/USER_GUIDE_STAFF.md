# Xodimlar uchun qo'llanma (qarz daftari)

> Bu qo'llanma oila a'zolari uchun — oddiy tilda. Bot hozir **tugmalar** bilan ishlaydi.
> Keyingi bosqichda shunchaki gapirasiz yoki yozasiz ("Umida 100 ming berdi"), bot o'zi tushunadi.

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
