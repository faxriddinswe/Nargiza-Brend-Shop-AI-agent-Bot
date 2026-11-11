# AI agent

> Holat: skelet. 3-bosqichda to'ldiriladi (google-genai SDK hujjati o'sha paytda tekshiriladi).

## Provayder
- `AI_PROVIDER=gemini`, model — `GEMINI_MODEL` (kodda yozilmaydi).
- `ai/base.py` — `AIProvider` interfeysi; `ai/gemini.py` — amalga oshirish; keyin `ai/claude.py` (ovoz uchun alohida STT).

## Qat'iy qoidalar
- AI hisob qilmaydi va ruxsat hal qilmaydi.
- Noaniq summa/mijoz/bo'lim → savol, tool emas.
- Argumentlar Pydantic bilan tekshiriladi; bo'lim kodda qayta aniqlanadi.
- Yozish tool'lari — tasdiqlash kartasi orqali.
- Har chaqiruv `ai_calls` ga (token, xarajat, kechikish), shaxsiy ma'lumotsiz.
- AI ishlamasa — xodimga tushunarli xabar + tugmali menyu; adminga xabar.

## Tool'lar
_3-bosqichda `architect` bilan yakunlanadi (master prompt 8.3)._

## Tizim prompti
_3-bosqichda._

## Eval
- `tests/eval/phrases.yaml` — ≥ 60 jumla; `scripts/run_eval.py`.
- Qabul: yozish tool'larida aniqlik ≥ 90%.
- Real ovozlar `tests/eval/audio/` — git'ga yuklanmaydi.
