"""Pydantic schemas for inbound events."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InboundWebhookResponse(BaseModel):
    """Response from webhook ingestion."""

    event_id: uuid.UUID
    processed: bool
    created_lead_id: uuid.UUID | None = None
    processing_error: str | None = None


class InboundEventRead(BaseModel):
    """Audit view of an inbound event."""

    id: uuid.UUID
    source: str
    event_type: str
    source_event_id: str | None
    event_fingerprint: str | None
    email: str | None
    first_name: str | None
    last_name: str | None
    linkedin_url: str | None
    company_domain: str | None
    raw_payload: dict[str, Any]
    processed: bool
    processing_error: str | None
    created_lead_id: uuid.UUID | None
    received_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class InboundRetryResponse(BaseModel):
    """Response for a retry request."""

    event: InboundEventRead


class InboundStatsResponse(BaseModel):
    """Operational inbound statistics."""

    total_events: int
    processed_events: int
    errored_events: int
    created_leads: int
    by_source: dict[str, int] = Field(default_factory=dict)
    by_event_type: dict[str, int] = Field(default_factory=dict)
