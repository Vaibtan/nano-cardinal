"""Outreach Log ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OutreachLog(Base):
    __tablename__ = "outreach_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("leads.id"),
    )
    sequence_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sequences.id"),
    )
    step_number: Mapped[int | None] = mapped_column(Integer)
    step_type: Mapped[str | None] = mapped_column(String)
    channel: Mapped[str | None] = mapped_column(String)
    subject: Mapped[str | None] = mapped_column(String)
    body: Mapped[str | None] = mapped_column(Text)
    engagement_action: Mapped[str | None] = mapped_column(String)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    replied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("personalization_drafts.id"),
    )

    lead = relationship("Lead", lazy="selectin")
    draft = relationship("PersonalizationDraft", lazy="selectin")

    __table_args__ = (
        Index("idx_outreach_logs_lead", lead_id),
    )
