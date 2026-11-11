"""Announcements (BR-170…178). Audience rules are decided here, in code:

- everyone: registered customers who did NOT turn promotions off (BR-174);
- debtors / overdue debtors: NOT promotional (owner decision Q-22), so promotions-off does not matter;
- one person: a personal message, always allowed.
Nobody who blocked the bot or is blocked by the shop is included (BR-165). An announcement never contains
anyone's debt (BR-175): the text is written by staff and is sent as is, we add nothing about money.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Broadcast, Customer, Role, User
from bot.services import ledger, users
from bot.services.customers import require_staff

SEGMENTS = ("all", "debtors", "overdue", "one")
MAX_TEXT = 1000


class BroadcastError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Recipient:
    chat_id: int


async def audience(
    session: AsyncSession, segment: str, today: date, *, customer_id: int | None = None
) -> list[Recipient]:
    if segment not in SEGMENTS:
        raise BroadcastError("unknown segment")
    chats: dict[int, None] = {}
    if segment == "all":
        rows = await session.scalars(
            select(User.telegram_id).where(
                User.role == Role.CUSTOMER.value,
                User.consent_at.is_not(None),
                User.is_blocked.is_(False),
                User.bot_blocked_at.is_(None),
                User.ads_opt_out.is_(False),
            )
        )
        chats = dict.fromkeys(rows.all())
    elif segment in ("debtors", "overdue"):
        ids = (
            {r.customer_id for r in await ledger.debtors(session)}
            if segment == "debtors"
            else {r.customer_id for r in await ledger.overdue(session, today)}
        )
        for cid in sorted(ids):
            customer = await session.get(Customer, cid)
            if customer is None or customer.deleted_at is not None:
                continue
            chat = await users.customer_chat_id(session, customer)
            if chat is not None:
                chats[chat] = None
    else:
        if customer_id is None:
            raise BroadcastError("customer required")
        customer = await session.get(Customer, customer_id)
        chat = await users.customer_chat_id(session, customer) if customer else None
        if chat is not None:
            chats[chat] = None
    return [Recipient(c) for c in chats]


def check_text(text: str | None) -> str | None:
    clean = (text or "").strip()
    if len(clean) > MAX_TEXT:
        raise BroadcastError("too long")
    return clean or None


async def start(
    session: AsyncSession, actor: User, *, segment: str, has_photo: bool, recipients: int
) -> int:
    require_staff(actor)
    row = Broadcast(
        created_by=actor.id, segment=segment, has_photo=has_photo, recipients=recipients
    )
    session.add(row)
    await session.flush()
    return row.id


async def finish(session: AsyncSession, broadcast_id: int, *, delivered: int, blocked: int) -> None:
    row = await session.get(Broadcast, broadcast_id)
    if row is not None:
        row.delivered, row.blocked = delivered, blocked
