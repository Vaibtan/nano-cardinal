"""Typed Redis Pub/Sub event publishing."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.redis import redis_client
from app.schemas.events import SSE_EVENT_ADAPTER

logger = logging.getLogger(__name__)

EVENT_CHANNEL = "orion:sse"


async def publish_event(
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Publish a typed SSE event if Redis is available."""
    event = SSE_EVENT_ADAPTER.validate_python(
        {"type": event_type, "payload": payload},
    )
    data = event.model_dump_json()
    try:
        await redis_client.publish(EVENT_CHANNEL, data)
    except Exception:
        logger.debug(
            "Skipping SSE publish because Redis is unavailable",
            exc_info=True,
        )


def format_sse(data: str) -> str:
    """Format a serialized event envelope for EventSource."""
    try:
        payload = json.loads(data)
        event_name = payload.get("type", "message")
    except json.JSONDecodeError:
        event_name = "message"
    return f"event: {event_name}\ndata: {data}\n\n"
