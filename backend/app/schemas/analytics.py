"""Pydantic schemas for analytics endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class AnalyticsOverview(BaseModel):
    """Top-line GTM metrics."""

    total_leads: int
    enriched_leads: int
    active_signals: int
    inbound_events_30d: int
    active_sequences: int
    reply_rate: float
    bounce_rate: float


class FunnelStage(BaseModel):
    """One funnel stage."""

    stage: str
    count: int


class AnalyticsFunnel(BaseModel):
    """Lead/outreach funnel."""

    stages: list[FunnelStage]


class AnalyticsTAM(BaseModel):
    """TAM summary metrics."""

    captured_leads: int
    industries: int
    average_icp_score: float | None


class AnalyticsSignals(BaseModel):
    """Signal analytics."""

    total_active: int
    by_type: dict[str, int] = Field(default_factory=dict)
    average_strength: float | None


class AnalyticsInbound(BaseModel):
    """Strategic inbound metrics."""

    total_events: int
    created_leads: int
    conversion_rate: float
    by_source: dict[str, int] = Field(default_factory=dict)


class SequenceAnalytics(BaseModel):
    """Sequence-level analytics."""

    sequence_id: str
    enrollments: int
    active: int
    completed: int
    replied: int
    bounced: int


class PersonalizationAnalytics(BaseModel):
    """Personalization quality metrics."""

    total_drafts: int
    approved_drafts: int
    sent_drafts: int
    average_critique_score: float | None


class AnalyticsDashboard(BaseModel):
    """Aggregated dashboard payload."""

    overview: AnalyticsOverview
    funnel: AnalyticsFunnel
    signals: AnalyticsSignals
    inbound: AnalyticsInbound
    sequence_summaries: list[SequenceAnalytics]
    personalization: PersonalizationAnalytics
    extra: dict[str, Any] = Field(default_factory=dict)
