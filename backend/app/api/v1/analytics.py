"""Analytics endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.analytics import (
    AnalyticsDashboard,
    AnalyticsFunnel,
    AnalyticsInbound,
    AnalyticsOverview,
    AnalyticsSignals,
    AnalyticsTAM,
    PersonalizationAnalytics,
    SequenceAnalytics,
)
from app.services.analytics import (
    build_dashboard,
    build_funnel,
    build_inbound_analytics,
    build_overview,
    build_personalization_analytics,
    build_sequence_analytics,
    build_signal_analytics,
    build_tam_summary,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=AnalyticsDashboard)
async def dashboard(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsDashboard:
    """Return all dashboard metrics."""
    return await build_dashboard(db)


@router.get("/overview", response_model=AnalyticsOverview)
async def overview(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsOverview:
    """Return top-line metrics."""
    return await build_overview(db)


@router.get("/funnel", response_model=AnalyticsFunnel)
async def funnel(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsFunnel:
    """Return funnel metrics."""
    return await build_funnel(db)


@router.get("/tam", response_model=AnalyticsTAM)
async def tam(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsTAM:
    """Return TAM summary metrics."""
    return await build_tam_summary(db)


@router.get("/signals", response_model=AnalyticsSignals)
async def signals(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSignals:
    """Return signal metrics."""
    return await build_signal_analytics(db)


@router.get("/inbound", response_model=AnalyticsInbound)
async def inbound(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsInbound:
    """Return strategic inbound metrics."""
    return await build_inbound_analytics(db)


@router.get("/sequences", response_model=list[SequenceAnalytics])
async def sequences(
    db: AsyncSession = Depends(get_db),
) -> list[SequenceAnalytics]:
    """Return analytics for every sequence."""
    return await build_sequence_analytics(db)


@router.get("/sequences/{sequence_id}", response_model=list[SequenceAnalytics])
async def sequence_detail(
    sequence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[SequenceAnalytics]:
    """Return analytics for one sequence."""
    return await build_sequence_analytics(db, sequence_id)


@router.get(
    "/personalization",
    response_model=PersonalizationAnalytics,
)
async def personalization(
    db: AsyncSession = Depends(get_db),
) -> PersonalizationAnalytics:
    """Return personalization quality metrics."""
    return await build_personalization_analytics(db)
