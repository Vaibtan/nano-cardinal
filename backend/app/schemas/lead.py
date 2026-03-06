"""Pydantic schemas for Lead endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import LeadSource


class LeadCreate(BaseModel):
    """Request body for creating a single lead."""

    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    twitter_url: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    company_linkedin_url: str | None = None
    company_size: int | None = None
    industry: str | None = None
    funding_stage: str | None = None
    total_funding_usd: int | None = None
    tech_stack: list[str] = Field(default_factory=list)
    title: str | None = None
    seniority: str | None = None
    department: str | None = None
    source: str = LeadSource.MANUAL


class LeadRead(BaseModel):
    """Response schema for a single lead."""

    id: uuid.UUID
    first_name: str | None
    last_name: str | None
    email: str | None
    linkedin_url: str | None
    github_url: str | None
    twitter_url: str | None
    company_name: str | None
    company_domain: str | None
    company_linkedin_url: str | None
    company_size: int | None
    industry: str | None
    funding_stage: str | None
    total_funding_usd: int | None
    tech_stack: list[str]
    title: str | None
    seniority: str | None
    department: str | None
    enriched_data: dict[str, Any] | None
    enrichment_status: str
    enrichment_sources: list[str]
    enrichment_at: datetime | None
    icp_score: float | None
    icp_id: uuid.UUID | None
    icp_score_breakdown: dict[str, float] | None
    outreach_status: str
    source: str
    inbound_event_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CSVImportResult(BaseModel):
    """Result of a CSV import operation."""

    total_rows: int
    imported: int
    errors: list[dict[str, Any]]


class YCImportRequest(BaseModel):
    """Request body for YC import."""

    batch: str = "W25"
    limit: int = Field(default=50, ge=1, le=500)


class YCImportResult(BaseModel):
    """Result of a YC import operation."""

    imported: int
    leads: list[LeadRead]


class SemanticSearchResult(BaseModel):
    """A single semantic search result."""

    lead: LeadRead
    similarity: float


class OutreachLogRead(BaseModel):
    """Response schema for an outreach log entry."""

    id: uuid.UUID
    lead_id: uuid.UUID | None
    sequence_id: uuid.UUID | None
    step_number: int | None
    step_type: str | None
    channel: str | None
    subject: str | None
    body: str | None
    engagement_action: str | None
    sent_at: datetime | None
    opened_at: datetime | None
    replied_at: datetime | None
    draft_id: uuid.UUID | None

    model_config = {"from_attributes": True}
