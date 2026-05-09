"""ARQ tasks for personalization streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.draft import PersonalizationDraft
from app.redis import redis_client
from app.services.event_bus import publish_event

logger = logging.getLogger(__name__)

_worker_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)
_worker_session_factory = async_sessionmaker(
    _worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def stream_draft_tokens(ctx: dict, draft_id: str) -> None:
    """Publish draft tokens to the draft-specific SSE channel."""
    try:
        parsed_id = uuid.UUID(draft_id)
    except ValueError:
        logger.warning("Invalid draft id for streaming: %s", draft_id)
        return

    async with _worker_session_factory() as db:
        draft = await db.get(PersonalizationDraft, parsed_id)
        if draft is None:
            logger.warning("Draft %s not found for streaming", draft_id)
            return
        text = draft.email_body or draft.linkedin_message or ""

    channel = f"sse:{draft_id}"
    for token in text.split():
        payload = {"draft_id": draft_id, "token": f"{token} "}
        event = {"type": "draft.token", "payload": payload}
        await publish_event("draft.token", payload)
        await redis_client.publish(channel, json.dumps(event))
        await asyncio.sleep(0.02)
    await redis_client.publish(channel, "__done__")
