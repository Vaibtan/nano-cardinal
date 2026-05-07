"""Pydantic schemas for sequence management."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import Channel, StepType


def _validate_step_channel(step_type: str, channel: str) -> None:
    """Validate channel/step type combinations."""
    if step_type == StepType.ENGAGEMENT.value:
        if channel != Channel.LINKEDIN_ENGAGE.value:
            raise ValueError(
                "ENGAGEMENT steps must use LINKEDIN_ENGAGE channel",
            )
        return
    if channel not in {
        Channel.EMAIL.value,
        Channel.LINKEDIN_MESSAGE.value,
        Channel.LINKEDIN_CONNECTION.value,
    }:
        raise ValueError(
            "OUTREACH steps must use EMAIL, LINKEDIN_MESSAGE, "
            "or LINKEDIN_CONNECTION",
        )


class SequenceStepCreate(BaseModel):
    """Create a sequence step."""

    step_number: int = Field(ge=1)
    step_type: str = StepType.OUTREACH.value
    channel: str = Channel.EMAIL.value
    delay_days: int = Field(default=0, ge=0, le=365)
    template: str | None = None
    use_ai_personalization: bool = True
    requires_approval: bool = False
    engagement_action: str | None = None

    @model_validator(mode="after")
    def validate_channel(self) -> "SequenceStepCreate":
        _validate_step_channel(self.step_type, self.channel)
        return self


class SequenceStepUpdate(BaseModel):
    """Update a sequence step."""

    step_number: int | None = Field(default=None, ge=1)
    step_type: str | None = None
    channel: str | None = None
    delay_days: int | None = Field(default=None, ge=0, le=365)
    template: str | None = None
    use_ai_personalization: bool | None = None
    requires_approval: bool | None = None
    engagement_action: str | None = None

    @model_validator(mode="after")
    def validate_channel(self) -> "SequenceStepUpdate":
        if self.step_type and self.channel:
            _validate_step_channel(self.step_type, self.channel)
        return self


class SequenceStepRead(BaseModel):
    """Sequence step response."""

    id: uuid.UUID
    sequence_id: uuid.UUID
    step_number: int
    step_type: str
    channel: str
    delay_days: int
    template: str | None
    use_ai_personalization: bool
    requires_approval: bool
    engagement_action: str | None

    model_config = {"from_attributes": True}


class SequenceCreate(BaseModel):
    """Create a sequence and its ordered steps."""

    name: str = Field(min_length=1, max_length=200)
    icp_id: uuid.UUID | None = None
    is_active: bool = True
    auto_enroll: bool = False
    auto_enroll_threshold: float | None = Field(
        default=None, ge=0.0, le=100.0,
    )
    steps: list[SequenceStepCreate] = Field(default_factory=list)


class SequenceUpdate(BaseModel):
    """Update sequence metadata and optionally replace steps."""

    name: str | None = Field(
        default=None, min_length=1, max_length=200,
    )
    icp_id: uuid.UUID | None = None
    is_active: bool | None = None
    auto_enroll: bool | None = None
    auto_enroll_threshold: float | None = Field(
        default=None, ge=0.0, le=100.0,
    )
    steps: list[SequenceStepCreate] | None = None


class SequenceRead(BaseModel):
    """Sequence with steps."""

    id: uuid.UUID
    name: str
    icp_id: uuid.UUID | None
    is_active: bool
    auto_enroll: bool
    auto_enroll_threshold: float | None
    created_at: datetime
    steps: list[SequenceStepRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class EnrollmentCreate(BaseModel):
    """Enroll a lead into a sequence."""

    lead_id: uuid.UUID


class EnrollmentRead(BaseModel):
    """Sequence enrollment response."""

    id: uuid.UUID
    lead_id: uuid.UUID
    sequence_id: uuid.UUID
    current_step: int
    status: str
    next_step_at: datetime
    enrolled_at: datetime
    reply_received: bool
    reply_body: str | None
    paused_reason: str | None
    paused_at: datetime | None

    model_config = {"from_attributes": True}
