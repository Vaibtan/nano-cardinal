"""Inbound Event ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InboundEvent(Base):
    __tablename__ = "inbound_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(
        String, nullable=False,
    )
    email: Mapped[str | None] = mapped_column(String)
    first_name: Mapped[str | None] = mapped_column(String)
    last_name: Mapped[str | None] = mapped_column(String)
    linkedin_url: Mapped[str | None] = mapped_column(String)
    company_domain: Mapped[str | None] = mapped_column(String)
    raw_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    processed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    created_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("leads.id"),
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    created_lead = relationship(
        "Lead",
        foreign_keys=[created_lead_id],
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_inbound_events_processed", processed),
        Index(
            "idx_inbound_events_received",
            received_at.desc(),
        ),
        Index("idx_inbound_events_email", email),
    )
