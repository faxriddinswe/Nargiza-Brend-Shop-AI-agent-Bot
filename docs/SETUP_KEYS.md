# Setting up keys and accounts (for the project owner)

> Only you sign in to the accounts. Once a key is in `.env`, Claude handles the configuration and verification.
> **Rule:** never send a key to anyone, and never put it in a chat, a screenshot or git.

## 1. Telegram bot token (required for Stage 0)

1. Open **@BotFather** in Telegram (check that it has the blue "verified" badge).
2. Send `/newbot`.
3. Bot **name** — the display name, e.g. `Nargiza Brend`.
4. Bot **username** — must end in `bot`, e.g. `nargiza_brend_bot`. If it is taken, try another one.
5. BotFather sends you a token that looks like `1234567890:AA...`. This is the bot's password.
6. In the project folder:
   ```bash
   cp .env.example .env
   nano .env        # BOT_TOKEN= qatoriga tokenni qo'ying
   ```
   (Put the token on the `BOT_TOKEN=` line.)
7. Set `POSTGRES_PASSWORD=` to a long random password, written straight into `.env` without ever showing it on screen:
   ```bash
   sed -i "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')#" .env
   ```
   (This has already been done in your dev environment.)

**If it leaks:** @BotFather → `/mybots` → select the bot → *API Token* → *Revoke current token*. Put the new token in `.env`.

Later (in Stage 1), in BotFather: description (`/setdescription`), profile picture (`/setuserpic`), commands (`/setcommands`) — I will prepare the texts for these.

## 2. Admin phone number (BR-013)

Put your own number in `ADMIN_PHONES=` in `.env`: `ADMIN_PHONES=+998901234567`.
In the bot: /start → registration → "📱 Raqamni ulashish" (*Share phone number*) — the bot recognises you as the admin.
You don't need to know your Telegram ID (the method below is only a fallback).

## 2a. Finding your Telegram ID (optional fallback)

Without any third-party bots, using the official Bot API:

1. Open your own bot in Telegram and send it any message (e.g. "salom" — *hello*).
   (The bot must not be running, otherwise it will "swallow" the message: `docker compose stop bot`.)
2. In a terminal (the token is read from `.env` inside a separate subshell in parentheses, so it never appears
   on screen or in shell history, and the values disappear once the command finishes):
   ```bash
   ( set -a; . ./.env; curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getUpdates" ) | python3 -m json.tool | grep -A3 '"from"'
   ```
3. `"id": 123456789` — this number is your ID. Put it in `ADMIN_TELEGRAM_IDS=` in `.env`.

## 3. Gemini API key — to be completed in Stage 3

- Google AI Studio → create an API key → `GEMINI_API_KEY`.
- **Important:** on the free tier, submitted data may be used to improve Google products. Real customer data may only be used with a billing-enabled (paid) key. The free key is for testing with fake data only.
- Cloud billing, Google AI Pro credits, a monthly budget alert ($5) — instructions will be written in Stage 3 after checking the official documentation.

## 4. GitHub — at the end of Stage 0 (with your consent)

- Create the repository, SSH key, first push. Verify that `.env` is not pushed.

## 5. Server (Azure for Students, then Contabo) — Stage 10

## 6. age encryption key (for backups) — NEEDED NOW

**Idea:** backups are encrypted with the public key (`age1...`). It lives on the server and cannot decrypt anything.
Decryption is only possible with the private key (`AGE-SECRET-KEY-1...`), which **never lives on the server**.
Even if the server is compromised, the backups cannot be read. But if you lose the private key, you lose the backups too.

**Current state:** a real key has been generated at `~/nargiza-backup-key.txt` on your computer, and its public key
is already set in `BACKUP_AGE_RECIPIENT=` in `.env`. Steps 1–3 below are therefore done; what remains for you is
**steps 4–6**: copy the private key to a password manager and to paper, run the restore test, then shred the file.

1. Install `age` on your own computer: `sudo apt install age`
2. Generate a key (the file must be readable only by you):
   ```bash
   umask 077 && age-keygen -o ~/nargiza-backup-key.txt
   ```
   The screen shows `Public key: age1...`.
3. Put the **public key** (`age1...`) in `BACKUP_AGE_RECIPIENT=` in `.env`, then run
   `docker compose up -d backup`. *(Already done — the public key of the generated key is in `.env`.)*
4. **Store the private key in two places:**
   - Password manager (Bitwarden, 1Password, KeePassXC): new "Secure note" → name it "Nargiza Brend backup key" →
     paste the full contents of `~/nargiza-backup-key.txt`.
   - Paper: print the `AGE-SECRET-KEY-1...` line (or copy it out clearly in capital letters; the key never contains
     the letters `O`, `I`, `B` or, after the leading `-1`, the digit `1` — so an ambiguous character is a `0`).
     Put it in an envelope and keep it somewhere safe at home (with your documents). Keep a second copy with a trusted family member.
     Type the key back in **from the paper copy** and run the restore test in step 5 — this proves the paper copy is correct.
5. Test a restore (RUNBOOK.md, section 5) to make sure the key really works.
6. After the test, delete the file from your computer: `shred -u ~/nargiza-backup-key.txt`
   (from then on the key exists only in the password manager and on paper).

## 7. Google Drive backup (optional) — Stage 9

## 8. Cost monitoring — Stages 3 and 10

## 9. Day-to-day operations — `RUNBOOK.md`
