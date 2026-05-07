"""Inbound webhook and audit endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.inbound import InboundEvent
from app.schemas.inbound import (
    InboundEventRead,
    InboundRetryResponse,
    InboundStatsResponse,
    InboundWebhookResponse,
)
from app.services.inbound import (
    process_inbound_event,
    process_inbound_payload,
)

router = APIRouter(prefix="/inbound", tags=["inbound"])


@router.post(
    "/webhook/{source}",
    response_model=InboundWebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_webhook(
    source: str,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> InboundWebhookResponse:
    """Receive, store, and process an inbound webhook."""
    if not settings.ENABLE_INBOUND_WEBHOOKS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inbound webhooks are disabled",
        )
    event = await process_inbound_payload(db, source, payload)
    return InboundWebhookResponse(
        event_id=event.id,
        processed=event.processed,
        created_lead_id=event.created_lead_id,
        processing_error=event.processing_error,
    )


@router.get("/events", response_model=list[InboundEventRead])
async def list_events(
    source: str | None = None,
    processed: bool | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[InboundEvent]:
    """List inbound audit events."""
    stmt = select(InboundEvent).order_by(InboundEvent.received_at.desc())
    if source:
        stmt = stmt.where(InboundEvent.source == source)
    if processed is not None:
        stmt = stmt.where(InboundEvent.processed.is_(processed))
    result = await db.execute(stmt.offset(offset).limit(limit))
    return list(result.scalars().all())


@router.get("/events/{event_id}", response_model=InboundEventRead)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InboundEvent:
    """Return one inbound audit event."""
    event = await db.get(InboundEvent, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbound event not found",
        )
    return event


@router.post(
    "/events/{event_id}/retry",
    response_model=InboundRetryResponse,
)
async def retry_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, InboundEvent]:
    """Retry an inbound event without double-creating leads."""
    event = await db.get(InboundEvent, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbound event not found",
        )
    event.processed = False
    event.processing_error = None
    event.processed_at = None
    await process_inbound_event(db, event)
    return {"event": event}


@router.get("/stats", response_model=InboundStatsResponse)
async def get_stats(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> InboundStatsResponse:
    """Return operational inbound stats for the recent window."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    base_filter = InboundEvent.received_at >= since
    total = await _count(db, select(func.count(InboundEvent.id)).where(base_filter))
    processed = await _count(
        db,
        select(func.count(InboundEvent.id)).where(
            base_filter,
            InboundEvent.processed.is_(True),
        ),
    )
    errored = await _count(
        db,
        select(func.count(InboundEvent.id)).where(
            base_filter,
            InboundEvent.processing_error.isnot(None),
        ),
    )
    created = await _count(
        db,
        select(func.count(InboundEvent.id)).where(
            base_filter,
            InboundEvent.created_lead_id.isnot(None),
        ),
    )
    source_rows = await db.execute(
        select(InboundEvent.source, func.count(InboundEvent.id))
        .where(base_filter)
        .group_by(InboundEvent.source),
    )
    type_rows = await db.execute(
        select(InboundEvent.event_type, func.count(InboundEvent.id))
        .where(base_filter)
        .group_by(InboundEvent.event_type),
    )
    return InboundStatsResponse(
        total_events=total,
        processed_events=processed,
        errored_events=errored,
        created_leads=created,
        by_source={str(row[0]): int(row[1]) for row in source_rows.all()},
        by_event_type={str(row[0]): int(row[1]) for row in type_rows.all()},
    )


async def _count(db: AsyncSession, stmt) -> int:
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)
