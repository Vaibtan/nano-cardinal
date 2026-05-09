"""Personalization draft endpoints."""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import suppress

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.draft import PersonalizationDraft
from app.models.enums import DraftStatus
from app.models.lead import Lead
from app.redis import redis_client
from app.schemas.personalization import (
    PersonalizationBatchRequest,
    PersonalizationDraftPatch,
    PersonalizationDraftRead,
    PersonalizationGenerateRequest,
    PersonalizationPathGenerateRequest,
)
from app.services.event_bus import publish_event
from app.services.personalization import approve_draft, generate_draft

router = APIRouter(prefix="/personalization", tags=["personalization"])
personalize_router = APIRouter(prefix="/personalize", tags=["personalization"])


@router.post(
    "/generate",
    response_model=PersonalizationDraftRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_single(
    body: PersonalizationGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> PersonalizationDraft:
    """Generate one personalization draft."""
    lead = await db.get(Lead, body.lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    return await generate_draft(
        db=db,
        lead=lead,
        sequence_id=body.sequence_id,
        sequence_step_id=body.sequence_step_id,
        enrollment_id=body.enrollment_id,
        signal_id=body.signal_id,
    )


@router.post(
    "/batch",
    response_model=list[PersonalizationDraftRead],
    status_code=status.HTTP_201_CREATED,
)
async def generate_batch(
    body: PersonalizationBatchRequest,
    db: AsyncSession = Depends(get_db),
) -> list[PersonalizationDraft]:
    """Generate drafts for multiple leads."""
    drafts: list[PersonalizationDraft] = []
    for lead_id in body.lead_ids:
        lead = await db.get(Lead, lead_id)
        if lead is not None:
            drafts.append(await generate_draft(db=db, lead=lead))
    return drafts


@router.get("/drafts", response_model=list[PersonalizationDraftRead])
async def list_drafts(
    lead_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> list[PersonalizationDraft]:
    """List personalization drafts."""
    stmt = select(PersonalizationDraft).order_by(
        PersonalizationDraft.created_at.desc(),
    )
    if lead_id:
        stmt = stmt.where(PersonalizationDraft.lead_id == lead_id)
    if status_filter:
        stmt = stmt.where(PersonalizationDraft.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.patch(
    "/drafts/{draft_id}",
    response_model=PersonalizationDraftRead,
)
async def patch_draft(
    draft_id: uuid.UUID,
    body: PersonalizationDraftPatch,
    db: AsyncSession = Depends(get_db),
) -> PersonalizationDraft:
    """Patch editable draft fields."""
    draft = await _get_draft_or_404(db, draft_id)
    if draft.status in {DraftStatus.APPROVED.value, DraftStatus.SENT.value}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approved or sent drafts cannot be edited",
        )
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(draft, key, value)
    await db.flush()
    return draft


@router.post(
    "/drafts/{draft_id}/approve",
    response_model=PersonalizationDraftRead,
)
async def approve(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PersonalizationDraft:
    """Approve a draft and resume linked sequence enrollment."""
    draft = await _get_draft_or_404(db, draft_id)
    return await approve_draft(db, draft)


@router.get("/drafts/{draft_id}/stream")
async def stream_draft(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream draft tokens as typed SSE events."""
    draft = await _get_draft_or_404(db, draft_id)

    async def event_generator():
        channel = f"sse:{draft.id}"
        pubsub = redis_client.pubsub()
        try:
            await pubsub.subscribe(channel)
            pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            try:
                await pool.enqueue_job("stream_draft_tokens", str(draft.id))
            finally:
                await pool.close()
        except Exception:
            text = draft.email_body or draft.linkedin_message or ""
            async for chunk in _fallback_token_stream(draft.id, text):
                yield chunk
            return
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=5.0,
                )
                if message is None:
                    yield ": keepalive\n\n"
                    continue
                data = str(message.get("data", ""))
                if data == "__done__":
                    break
                yield f"event: draft.token\ndata: {data}\n\n"
        finally:
            with suppress(Exception):
                await pubsub.unsubscribe(channel)
                await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


async def _get_draft_or_404(
    db: AsyncSession,
    draft_id: uuid.UUID,
) -> PersonalizationDraft:
    draft = await db.get(PersonalizationDraft, draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )
    return draft


async def _fallback_token_stream(
    draft_id: uuid.UUID,
    text: str,
):
    for token in text.split():
        payload = {"draft_id": str(draft_id), "token": f"{token} "}
        await publish_event("draft.token", payload)
        event = {"type": "draft.token", "payload": payload}
        yield f"event: draft.token\ndata: {json.dumps(event)}\n\n"
        await asyncio.sleep(0.02)


@personalize_router.post(
    "/batch",
    response_model=list[PersonalizationDraftRead],
    status_code=status.HTTP_201_CREATED,
)
async def personalize_batch(
    body: PersonalizationBatchRequest,
    db: AsyncSession = Depends(get_db),
) -> list[PersonalizationDraft]:
    """PRD-compatible batch personalization alias."""
    return await generate_batch(body=body, db=db)


@personalize_router.patch(
    "/drafts/{draft_id}",
    response_model=PersonalizationDraftRead,
)
async def personalize_patch_draft(
    draft_id: uuid.UUID,
    body: PersonalizationDraftPatch,
    db: AsyncSession = Depends(get_db),
) -> PersonalizationDraft:
    """PRD-compatible draft patch alias."""
    return await patch_draft(draft_id=draft_id, body=body, db=db)


@personalize_router.post(
    "/drafts/{draft_id}/approve",
    response_model=PersonalizationDraftRead,
)
async def personalize_approve_draft(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PersonalizationDraft:
    """PRD-compatible draft approval alias."""
    return await approve(draft_id=draft_id, db=db)


@personalize_router.post(
    "/{lead_id}",
    response_model=PersonalizationDraftRead,
    status_code=status.HTTP_201_CREATED,
)
async def personalize_lead(
    lead_id: uuid.UUID,
    body: PersonalizationPathGenerateRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> PersonalizationDraft:
    """PRD-compatible path-param personalization alias."""
    path_body = body or PersonalizationPathGenerateRequest()
    payload = PersonalizationGenerateRequest(
        lead_id=lead_id,
        sequence_id=path_body.sequence_id,
        sequence_step_id=path_body.sequence_step_id,
        enrollment_id=path_body.enrollment_id,
        signal_id=path_body.signal_id,
    )
    return await generate_single(body=payload, db=db)


@personalize_router.get(
    "/{lead_id}/drafts",
    response_model=list[PersonalizationDraftRead],
)
async def list_lead_drafts(
    lead_id: uuid.UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> list[PersonalizationDraft]:
    """PRD-compatible lead draft listing alias."""
    return await list_drafts(
        lead_id=lead_id,
        status_filter=status_filter,
        db=db,
    )
