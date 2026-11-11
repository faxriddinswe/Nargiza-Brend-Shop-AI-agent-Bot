# Security Policy

This bot stores a small business's debt ledger and its customers' phone numbers, so security
reports are taken seriously.

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private
[security advisory](https://github.com/faxriddinswe/Nargiza-Brend-Shop-AI-agent-Bot/security/advisories/new)
form instead. You can expect an acknowledgement within a few days.

## Scope

- Privilege escalation (customer → staff/admin, acting on another customer's data)
- Bypassing the audit log or the soft-delete guarantees
- Leaking secrets, phone numbers or customer data (logs, errors, backups)
- Weaknesses in backup encryption or restore scripts

## What is already in place

- Contact ownership check at registration (`contact.user_id == sender`)
- Roles re-read from the database on every update; blocked users stopped in middleware
- Least-privilege database role for the bot; audit log written by a `SECURITY DEFINER` trigger
- `age`-encrypted backups; the private key never lives on the server
- Secrets only in `.env` (git-ignored); pre-commit hook blocks private keys and tokens
