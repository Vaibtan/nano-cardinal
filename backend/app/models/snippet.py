"""Winning outbound snippet storage for RAG retrieval."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.embeddings import VECTOR_DIMENSION


class WinningSnippet(Base):
    __tablename__ = "winning_snippets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    subject_line: Mapped[str | None] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    industry: Mapped[str | None] = mapped_column(String)
    persona: Mapped[str | None] = mapped_column(String)
    hook_type: Mapped[str | None] = mapped_column(String)
    role_seniority: Mapped[str | None] = mapped_column(String)
    channel: Mapped[str | None] = mapped_column(String)
    reply_rate: Mapped[float | None] = mapped_column(Float)
    embedding = mapped_column(Vector(VECTOR_DIMENSION), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_winning_snippets_industry", industry),
        Index("idx_winning_snippets_persona", persona),
    )
