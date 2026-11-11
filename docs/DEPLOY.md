# Deploy

> Status: skeleton. To be completed in Stage 10.

## Environments
| Environment | Location | Data |
|---|---|---|
| local (dev) | Developer's computer, `docker compose up` | fake only |
| staging | Azure for Students, Ubuntu, B1s | fake only |
| production | Contabo VPS (❓ Q-25: when) | real |

## ⚠️ Gemini and real data
On the Gemini API **free tier**, submitted data may be used to improve Google products.
**Real customer data may only be used with a key that has billing enabled (paid tier).**
The free key is for dev/staging with fake data only. This is verified before production goes live
(an item on the deploy checklist).

## Starting production
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
_Details in Stage 10 (hardening, deploy script, backup before migrations)._
