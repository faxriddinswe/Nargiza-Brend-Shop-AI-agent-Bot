# Runbook — avariya holatlari

> Holat: skelet. 1-bosqichda (backup tiklash) va 10-bosqichda to'ldiriladi.

## Bot javob bermayapti
```bash
docker compose ps
docker compose logs --tail=100 bot
docker compose restart bot
```

## Backup'dan tiklash
_1-bosqichda: `scripts/restore.sh` bilan qadam-baqadam._

## age yopiq kaliti yo'qolsa
_1-bosqichda._

## Bot tokeni sizib chiqsa
@BotFather → `/mybots` → bot → *API Token* → *Revoke*. Yangi tokenni `.env` ga → `docker compose up -d bot`.

## Xodimning telefoni yo'qolsa
_1-bosqichda: admin buyrug'i bilan darhol bloklash._
