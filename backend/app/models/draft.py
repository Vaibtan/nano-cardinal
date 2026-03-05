"""Personalization Draft ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PersonalizationDraft(Base):
    __tablename__ = "personalization_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sender_profiles.id"),
    )
    sequence_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sequences.id"),
    )
    sequence_step_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sequence_steps.id"),
    )
    enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("lead_sequence_enrollments.id"),
    )
    subject_line: Mapped[str | None] = mapped_column(String)
    email_body: Mapped[str | None] = mapped_column(Text)
    linkedin_message: Mapped[str | None] = mapped_column(Text)
    personalization_hook: Mapped[str | None] = mapped_column(Text)
    hook_type: Mapped[str | None] = mapped_column(String)
    hook_strength: Mapped[float | None] = mapped_column(Float)
    signal_used: Mapped[str | None] = mapped_column(String)
    critique_score: Mapped[float | None] = mapped_column(Float)
    critique_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    generation_iterations: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1",
    )
    token_usage: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String, default="DRAFT", server_default="DRAFT",
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    lead = relationship("Lead", lazy="selectin")
    sender = relationship("SenderProfile", lazy="selectin")

    __table_args__ = (
        Index("idx_drafts_lead_id", lead_id),
        Index("idx_drafts_enrollment_id", enrollment_id),
    )
