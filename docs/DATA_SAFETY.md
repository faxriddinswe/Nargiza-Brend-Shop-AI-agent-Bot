# Ma'lumot xavfsizligi

> Qarz yoki savdo yozuvi yo'qolsa — oila pul yo'qotadi. Manba: master prompt 9-bo'lim.
> Holat: reja. Amalga oshirish: 1-bosqich (backup/restore), 9-bosqich (yaxlitlik, monitoring).

## 1. Yozish darajasida
- Har bir biznes amal — bitta tranzaksiya.
- Soft delete; qoldiqlar hisoblanadi; pul `BIGINT`.
- DB cheklovlari: NOT NULL, FK, CHECK, partial unique.
- Idempotentlik kaliti har bir tasdiqlashda.
- Audit log (JSONB eski/yangi qiymat) — o'sha tranzaksiya ichida.

## 2. Backup (3-2-1)

| Chastota | Saqlash |
|---|---|
| Har soat | 48 soat |
| Har kun 03:00 | 30 kun |
| Har hafta | 3 oy |
| Har oy | 1 yil |

`pg_dump -Fc` → `age` bilan shifrlash (ochiq kalit serverda, yopiq kalit **faqat** parol menejeri va qog'ozda) →
server diski (DB volume'dan alohida) + adminning Telegram'i (kunlik) + Google Drive (ixtiyoriy, ❓ Q-24).

Har kuni adminga: "✅ Backup OK: N qarz, M savdo, hajmi X MB". Backup yo'q yoki hajm keskin kamaygan — ogohlantirish.
Haftalik avtomatik tiklash testi.

## 3. Yaxlitlik tekshiruvi (har kecha)
Manfiy qarz, ortiqcha to'lov, dublikat to'lov, manfiy ombor, bog'lanmagan yozuvlar → adminga hisobot.

## 4. Kassa bilan solishtirish
20:00 hisobotida eslatma.

## 5. Deploy va migratsiya
Har deploy/migratsiyadan oldin avtomatik backup; migratsiya avval staging'da.

## 6. Server
Postgres tashqariga ochilmaydi; named volume; SSH faqat kalit; ufw; fail2ban; avtomatik xavfsizlik yangilanishlari; `unless-stopped` + healthcheck; bot to'xtasa adminga xabar.

## 7. Huquqiy
Rozilik matni majburiy. Server joylashuvi bo'yicha yakuniy qaror — Faxriddin (yurist maslahati tavsiya etiladi).
