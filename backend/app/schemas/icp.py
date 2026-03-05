"""Pydantic schemas for ICP endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ICPConfigSchema(BaseModel):
    """ICP filter configuration sent by the wizard."""

    industries: list[str] = Field(default_factory=list)
    company_sizes: list[str] = Field(default_factory=list)
    funding_stages: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    seniorities: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)


class ICPWeightsSchema(BaseModel):
    """Weight multipliers for scoring dimensions."""

    industry: float = 1.0
    company_size: float = 1.0
    funding_stage: float = 1.0
    title: float = 1.0
    seniority: float = 1.0
    department: float = 1.0
    tech_stack: float = 1.0
    region: float = 1.0


class ICPCreate(BaseModel):
    """Request body for creating an ICP."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    config: ICPConfigSchema = Field(default_factory=ICPConfigSchema)
    weights: ICPWeightsSchema = Field(
        default_factory=ICPWeightsSchema,
    )
    is_active: bool = True


class ICPUpdate(BaseModel):
    """Request body for updating an ICP (all optional)."""

    name: str | None = Field(
        default=None, min_length=1, max_length=200,
    )
    description: str | None = None
    config: ICPConfigSchema | None = None
    weights: ICPWeightsSchema | None = None
    is_active: bool | None = None


class ICPRead(BaseModel):
    """Response schema for a single ICP."""

    id: uuid.UUID
    name: str
    description: str | None
    config: dict[str, Any]
    weights: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
