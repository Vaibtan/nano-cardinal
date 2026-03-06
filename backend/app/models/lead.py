"""Lead ORM model."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.embeddings import VECTOR_DIMENSION


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )

    # Identity
    first_name: Mapped[str | None] = mapped_column(String)
    last_name: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    linkedin_url: Mapped[str | None] = mapped_column(String)
    github_url: Mapped[str | None] = mapped_column(String)
    twitter_url: Mapped[str | None] = mapped_column(String)

    # Company
    company_name: Mapped[str | None] = mapped_column(String)
    company_domain: Mapped[str | None] = mapped_column(String)
    company_linkedin_url: Mapped[str | None] = mapped_column(
        String,
    )
    company_size: Mapped[int | None] = mapped_column(Integer)
    industry: Mapped[str | None] = mapped_column(String)
    funding_stage: Mapped[str | None] = mapped_column(String)
    total_funding_usd: Mapped[int | None] = mapped_column(
        BigInteger,
    )
    tech_stack: Mapped[list] = mapped_column(
        JSONB, default=list,
    )

    # Persona
    title: Mapped[str | None] = mapped_column(String)
    seniority: Mapped[str | None] = mapped_column(String)
    department: Mapped[str | None] = mapped_column(String)

    # Enrichment metadata
    enriched_data: Mapped[dict | None] = mapped_column(JSONB)
    enrichment_status: Mapped[str] = mapped_column(
        String, default="PENDING", server_default="PENDING",
    )
    enrichment_sources: Mapped[list] = mapped_column(
        JSONB, default=list,
    )
    enrichment_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    # Scoring
    icp_score: Mapped[float | None] = mapped_column(Float)
    icp_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("icps.id"),
    )
    icp_score_breakdown: Mapped[dict | None] = mapped_column(JSONB)

    # Outreach
    outreach_status: Mapped[str] = mapped_column(
        String, default="UNTOUCHED", server_default="UNTOUCHED",
    )

    # Embedding (pgvector)
    embedding = mapped_column(
        Vector(VECTOR_DIMENSION), nullable=True,
    )

    # Source tracking
    source: Mapped[str] = mapped_column(
        String, default="MANUAL", server_default="MANUAL",
    )
    # Circular FK — use_alter defers the constraint; post_update
    # on the relationship breaks the dependency cycle.
    inbound_event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "inbound_events.id",
            use_alter=True,
            name="fk_leads_inbound_event_id",
        ),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    icp = relationship("ICP", lazy="selectin")
    inbound_event = relationship(
        "InboundEvent",
        foreign_keys=[inbound_event_id],
        post_update=True,
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_leads_icp_score", icp_score.desc()),
        Index("idx_leads_enrichment_status", enrichment_status),
        Index("idx_leads_source", source),
        Index("idx_leads_outreach_status", outreach_status),
        Index("idx_leads_updated_at", updated_at.desc()),
    )
