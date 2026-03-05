"""Signal ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_domain: Mapped[str | None] = mapped_column(String)
    signal_type: Mapped[str] = mapped_column(
        String, nullable=False,
    )
    signal_title: Mapped[str] = mapped_column(
        String, nullable=False,
    )
    signal_body: Mapped[str | None] = mapped_column(Text)
    signal_url: Mapped[str | None] = mapped_column(String)
    signal_strength: Mapped[float | None] = mapped_column(Float)
    signal_hash: Mapped[str | None] = mapped_column(
        String, unique=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    triggered_outreach: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    lead = relationship("Lead", lazy="selectin")

    __table_args__ = (
        Index("idx_signals_lead_id", lead_id),
        Index(
            "idx_signals_detected_at", detected_at.desc(),
        ),
        Index("idx_signals_type", signal_type),
        Index(
            "idx_signals_strength", signal_strength.desc(),
        ),
    )
