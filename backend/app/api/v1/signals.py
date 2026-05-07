"""Signal feed endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.icp import ICP
from app.models.lead import Lead
from app.models.signal import Signal
from app.schemas.signal import SignalCreate, SignalRead
from app.services.signals import create_signal, run_mock_signal_scan

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalRead])
async def list_signals(
    icp_id: uuid.UUID | None = None,
    signal_type: str | None = None,
    include_read: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[Signal]:
    """Return default signal feed, excluding read/expired signals."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(Signal)
        .options(selectinload(Signal.lead))
        .where(Signal.expires_at > now)
        .order_by(Signal.detected_at.desc())
    )
    if not include_read:
        stmt = stmt.where(Signal.is_read.is_(False))
    if signal_type:
        stmt = stmt.where(Signal.signal_type == signal_type)
    if icp_id:
        icp = await db.get(ICP, icp_id)
        if icp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ICP not found",
            )
        config = icp.config or {}
        selected = config.get("selected_signal_types", [])
        if selected:
            stmt = stmt.where(Signal.signal_type.in_(selected))
        recency_days = int(config.get("signal_recency_days", 30))
        stmt = stmt.where(
            Signal.detected_at
            >= datetime.now(timezone.utc) - timedelta(days=recency_days),
        )
        min_strength = float(config.get("min_signal_strength", 0.0))
        stmt = stmt.where(Signal.signal_strength >= min_strength)

    result = await db.execute(stmt.offset(offset).limit(limit))
    return list(result.scalars().all())


@router.post(
    "",
    response_model=SignalRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_signal(
    body: SignalCreate,
    db: AsyncSession = Depends(get_db),
) -> Signal:
    """Create a manual signal for demos and tests."""
    lead = await db.get(Lead, body.lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    signal = await create_signal(
        db=db,
        lead=lead,
        signal_type=body.signal_type,
        title=body.signal_title,
        body=body.signal_body,
        url=body.signal_url,
    )
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate signal",
        )
    signal.lead = lead
    return signal


@router.post("/mock-scan")
async def mock_scan(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Run deterministic mock funding/hiring/LinkedIn/news monitors."""
    created = await run_mock_signal_scan(db)
    return {"created": created}


@router.delete(
    "/{signal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def dismiss_signal(
    signal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a signal by marking it read."""
    signal = await db.get(Signal, signal_id)
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )
    signal.is_read = True
