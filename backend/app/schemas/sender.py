"""Pydantic schemas for Sender Profile endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SenderProfileCreate(BaseModel):
    """Request body for creating a sender profile."""

    name: str = Field(min_length=1, max_length=200)
    current_title: str | None = None
    current_company: str | None = None
    education: list[str] = Field(default_factory=list)
    past_employers: list[str] = Field(default_factory=list)
    cities_lived: list[str] = Field(default_factory=list)
    hobbies_and_interests: list[str] = Field(default_factory=list)
    investors: list[str] = Field(default_factory=list)
    languages_spoken: list[str] = Field(default_factory=list)
    conferences_attended: list[str] = Field(default_factory=list)


class SenderProfileUpdate(BaseModel):
    """Request body for updating a sender profile (all optional)."""

    name: str | None = Field(
        default=None, min_length=1, max_length=200,
    )
    current_title: str | None = None
    current_company: str | None = None
    education: list[str] | None = None
    past_employers: list[str] | None = None
    cities_lived: list[str] | None = None
    hobbies_and_interests: list[str] | None = None
    investors: list[str] | None = None
    languages_spoken: list[str] | None = None
    conferences_attended: list[str] | None = None


class SenderProfileRead(BaseModel):
    """Response schema for a sender profile."""

    id: uuid.UUID
    user_id: str
    name: str
    current_title: str | None
    current_company: str | None
    education: list[str]
    past_employers: list[str]
    cities_lived: list[str]
    hobbies_and_interests: list[str]
    investors: list[str]
    languages_spoken: list[str]
    conferences_attended: list[str]
    updated_at: datetime

    model_config = {"from_attributes": True}
