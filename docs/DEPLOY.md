# Deploy

> Holat: skelet. 10-bosqichda yakunlanadi.

## Muhitlar
| Muhit | Joy | Ma'lumot |
|---|---|---|
| local (dev) | Faxriddinning kompyuteri, `docker compose up` | faqat soxta |
| staging | Azure for Students, Ubuntu, B1s | faqat soxta |
| production | Contabo VPS (❓ Q-25: qachon) | real |

## ⚠️ Gemini va real ma'lumot
Gemini API **bepul tarifida** yuborilgan ma'lumotlar Google mahsulotlarini yaxshilash uchun ishlatilishi mumkin.
**Real mijoz ma'lumotlari bilan faqat billing yoqilgan (pullik tarif) kalit ishlatiladi.**
Bepul kalit — faqat dev/staging'da soxta ma'lumot bilan. Production'ni ishga tushirishdan oldin bu tekshiriladi
(deploy checklist bandi).

## Production ishga tushirish
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
_Batafsil: 10-bosqichda (hardening, deploy skripti, migratsiyadan oldingi backup)._
