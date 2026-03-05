"""Sequence, SequenceStep, and LeadSequenceEnrollment models."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Sequence(Base):
    __tablename__ = "sequences"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    icp_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("icps.id"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    auto_enroll: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    auto_enroll_threshold: Mapped[float | None] = mapped_column(
        Float,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    steps = relationship(
        "SequenceStep",
        back_populates="sequence",
        lazy="selectin",
        order_by="SequenceStep.step_number",
    )
    icp = relationship("ICP", lazy="selectin")


class SequenceStep(Base):
    __tablename__ = "sequence_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sequences.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )
    step_type: Mapped[str] = mapped_column(
        String, default="OUTREACH", server_default="OUTREACH",
    )
    channel: Mapped[str] = mapped_column(String, nullable=False)
    delay_days: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )
    template: Mapped[str | None] = mapped_column(Text)
    use_ai_personalization: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    engagement_action: Mapped[str | None] = mapped_column(String)

    sequence = relationship("Sequence", back_populates="steps")

    __table_args__ = (
        UniqueConstraint(
            "sequence_id", "step_number",
            name="uq_sequence_step_number",
        ),
    )


class LeadSequenceEnrollment(Base):
    __tablename__ = "lead_sequence_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("leads.id"), nullable=False,
    )
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sequences.id"), nullable=False,
    )
    current_step: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1",
    )
    status: Mapped[str] = mapped_column(
        String, default="ACTIVE", server_default="ACTIVE",
    )
    next_step_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    reply_received: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    reply_body: Mapped[str | None] = mapped_column(Text)

    lead = relationship("Lead", lazy="selectin")
    sequence = relationship("Sequence", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "lead_id", "sequence_id",
            name="uq_lead_sequence",
        ),
        Index(
            "idx_enrollments_next_step",
            next_step_at,
        ),
    )
