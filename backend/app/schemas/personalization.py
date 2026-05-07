"""Pydantic schemas for personalization drafts."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PersonalizationGenerateRequest(BaseModel):
    """Generate one draft for a lead."""

    lead_id: uuid.UUID
    sequence_id: uuid.UUID | None = None
    sequence_step_id: uuid.UUID | None = None
    enrollment_id: uuid.UUID | None = None
    signal_id: uuid.UUID | None = None


class PersonalizationBatchRequest(BaseModel):
    """Generate drafts for several leads."""

    lead_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class PersonalizationDraftPatch(BaseModel):
    """Editable draft fields."""

    subject_line: str | None = None
    email_body: str | None = None
    linkedin_message: str | None = None


class PersonalizationDraftRead(BaseModel):
    """Persisted personalization draft."""

    id: uuid.UUID
    lead_id: uuid.UUID
    sender_id: uuid.UUID | None
    sequence_id: uuid.UUID | None
    sequence_step_id: uuid.UUID | None
    enrollment_id: uuid.UUID | None
    subject_line: str | None
    email_body: str | None
    linkedin_message: str | None
    personalization_hook: str | None
    hook_type: str | None
    hook_strength: float | None
    signal_used: str | None
    critique_score: float | None
    critique_breakdown: dict[str, Any] | None
    generation_iterations: int
    token_usage: dict[str, Any] | None
    status: str
    approved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
