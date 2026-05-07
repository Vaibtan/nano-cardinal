"""Pydantic schemas for signal feed endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.lead import LeadRead


class SignalRead(BaseModel):
    """Signal feed item."""

    id: uuid.UUID
    lead_id: uuid.UUID
    company_domain: str | None
    signal_type: str
    signal_title: str
    signal_body: str | None
    signal_url: str | None
    signal_strength: float | None
    signal_hash: str | None
    is_read: bool
    triggered_outreach: bool
    detected_at: datetime
    expires_at: datetime
    lead: LeadRead | None = None

    model_config = {"from_attributes": True}


class SignalCreate(BaseModel):
    """Manual or mock signal creation request."""

    lead_id: uuid.UUID
    signal_type: str
    signal_title: str
    signal_body: str | None = None
    signal_url: str | None = None
