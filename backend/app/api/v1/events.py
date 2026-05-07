"""Unified SSE event stream."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.redis import redis_client
from app.services.event_bus import EVENT_CHANNEL, format_sse

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
async def stream_events(
    request: Request,
    topic: str | None = Query(default=None),
) -> StreamingResponse:
    """Stream typed events over Server-Sent Events."""

    async def event_generator():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(EVENT_CHANNEL)
        try:
            yield "event: worker.status\ndata: {\"type\":\"worker.status\",\"payload\":{\"worker\":\"api\",\"status\":\"running\",\"queue_depth\":0}}\n\n"
            while not await request.is_disconnected():
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=5.0,
                )
                if message is None:
                    yield ": keepalive\n\n"
                    continue
                data = str(message.get("data", ""))
                if _topic_matches(data, topic):
                    yield format_sse(data)
                await asyncio.sleep(0)
        finally:
            await pubsub.unsubscribe(EVENT_CHANNEL)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def _topic_matches(data: str, topic: str | None) -> bool:
    if topic is None:
        return True
    try:
        event_type = json.loads(data).get("type", "")
    except json.JSONDecodeError:
        return False
    if topic == "signals":
        return event_type.startswith("signal.")
    if topic == "inbound":
        return event_type.startswith("inbound.")
    if topic == "drafts":
        return event_type.startswith("draft.")
    if topic == "sequences":
        return event_type.startswith("sequence.")
    return event_type == topic
