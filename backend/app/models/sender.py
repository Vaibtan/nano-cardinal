"""Sender Profile ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SenderProfile(Base):
    __tablename__ = "sender_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, default="default",
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    current_title: Mapped[str | None] = mapped_column(String)
    current_company: Mapped[str | None] = mapped_column(String)
    education: Mapped[list] = mapped_column(
        JSONB, default=list,
    )
    past_employers: Mapped[list] = mapped_column(
        JSONB, default=list,
    )
    cities_lived: Mapped[list] = mapped_column(
        JSONB, default=list,
    )
    hobbies_and_interests: Mapped[list] = mapped_column(
        JSONB, default=list,
    )
    investors: Mapped[list] = mapped_column(
        JSONB, default=list,
    )
    languages_spoken: Mapped[list] = mapped_column(
        JSONB, default=list,
    )
    conferences_attended: Mapped[list] = mapped_column(
        JSONB, default=list,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
