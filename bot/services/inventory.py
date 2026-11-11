"""Stock (BR-090…BR-096): per product TYPE only, computed from an append-only movement ledger.

Stock = Σ quantity of `stock_movements`. Sales, credit goods and exchanges take goods out, returns and
cancellations put them back, stock-in adds, an inventory count writes the difference (never overwrites history).
Negative stock is allowed but reported (BR-093).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from sqlalchemy import BigInteger, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, Section, StockMovement, User
from bot.services.customers import require_staff


class InventoryError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class StockRow:
    category_id: int
    name: str
    section_code: str
    qty: int
    threshold: int | None

    @property
    def negative(self) -> bool:
        return self.qty < 0

    @property
    def low(self) -> bool:
        return self.threshold is not None and 0 <= self.qty <= self.threshold


async def add_movement(
    session: AsyncSession,
    *,
    category_id: int,
    quantity: int,
    reason: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
    note: str | None = None,
    actor_id: int | None = None,
) -> None:
    if not isinstance(quantity, int) or quantity == 0:
        raise InventoryError("quantity must be a non-zero int")
    session.add(
        StockMovement(
            category_id=category_id,
            quantity=quantity,
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
            note=note,
            created_by=actor_id,
        )
    )


async def levels(
    session: AsyncSession, category_ids: Collection[int] | None = None, *, active_only: bool = True
) -> list[StockRow]:
    qty = cast(func.coalesce(func.sum(StockMovement.quantity), 0), BigInteger)
    q = (
        select(Category.id, Category.name, Section.code, qty, Category.low_stock_threshold)
        .join(Section, Section.id == Category.section_id)
        .outerjoin(StockMovement, StockMovement.category_id == Category.id)
        .group_by(
            Category.id, Category.name, Section.id, Section.code, Category.low_stock_threshold
        )
        .order_by(Section.id, Category.id)
    )
    if active_only:
        q = q.where(Category.is_active.is_(True))
    if category_ids is not None:
        q = q.where(Category.id.in_(list(category_ids)))
    return [
        StockRow(cid, name, code, int(n), thr)
        for cid, name, code, n, thr in (await session.execute(q)).all()
    ]


async def negative_after(session: AsyncSession, category_ids: Collection[int]) -> list[StockRow]:
    """BR-093: categories that are below zero right now (call after writing movements)."""
    return [r for r in await levels(session, category_ids, active_only=False) if r.negative]


async def stock_in(
    session: AsyncSession, actor: User, category_id: int, quantity: int, note: str | None = None
) -> StockRow:
    require_staff(actor)
    if not 1 <= quantity <= 100_000:
        raise InventoryError("bad quantity")
    await add_movement(
        session,
        category_id=category_id,
        quantity=quantity,
        reason="stock_in",
        note=note,
        actor_id=actor.id,
    )
    await session.flush()
    return (await levels(session, [category_id], active_only=False))[0]


@dataclass(frozen=True, slots=True)
class CountDiff:
    category_id: int
    name: str
    before: int
    counted: int

    @property
    def diff(self) -> int:
        return self.counted - self.before


async def plan_count(session: AsyncSession, counts: Mapping[int, int]) -> list[CountDiff]:
    """What an inventory count would change (preview for the confirmation card)."""
    if any(not isinstance(v, int) or v < 0 or v > 100_000 for v in counts.values()):
        raise InventoryError("bad counted quantity")
    rows = {r.category_id: r for r in await levels(session, list(counts), active_only=False)}
    return [
        CountDiff(cid, rows[cid].name, rows[cid].qty, n) for cid, n in counts.items() if cid in rows
    ]


async def stock_count(
    session: AsyncSession, actor: User, counts: Mapping[int, int]
) -> list[CountDiff]:
    """Monthly inventory / opening stock (BR-095/096): the difference is stored as an adjustment movement."""
    require_staff(actor)
    plan = await plan_count(session, counts)
    for d in plan:
        if d.diff != 0:
            await add_movement(
                session,
                category_id=d.category_id,
                quantity=d.diff,
                reason="count_adjustment",
                note=f"sanoq: {d.before} → {d.counted}",
                actor_id=actor.id,
            )
    await session.flush()
    return plan


async def low_stock(session: AsyncSession) -> list[StockRow]:
    return [r for r in await levels(session) if r.low or r.negative]
