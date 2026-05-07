"""Analytics aggregation service."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.draft import PersonalizationDraft
from app.models.enums import DeliveryStatus, DraftStatus
from app.models.inbound import InboundEvent
from app.models.lead import Lead
from app.models.outreach import OutreachLog
from app.models.sequence import LeadSequenceEnrollment, Sequence
from app.models.signal import Signal
from app.schemas.analytics import (
    AnalyticsDashboard,
    AnalyticsFunnel,
    AnalyticsInbound,
    AnalyticsOverview,
    AnalyticsSignals,
    AnalyticsTAM,
    FunnelStage,
    PersonalizationAnalytics,
    SequenceAnalytics,
)


async def build_overview(db: AsyncSession) -> AnalyticsOverview:
    """Build top-line dashboard metrics."""
    now = datetime.now(timezone.utc)
    total_leads = await _scalar_count(db, select(func.count(Lead.id)))
    enriched = await _scalar_count(
        db,
        select(func.count(Lead.id)).where(
            Lead.enrichment_status == "COMPLETE",
        ),
    )
    active_signals = await _scalar_count(
        db,
        select(func.count(Signal.id))
        .where(Signal.is_read.is_(False))
        .where(Signal.expires_at > now),
    )
    inbound_30d = await _scalar_count(
        db,
        select(func.count(InboundEvent.id)).where(
            InboundEvent.received_at >= now - timedelta(days=30),
        ),
    )
    active_sequences = await _scalar_count(
        db,
        select(func.count(Sequence.id)).where(Sequence.is_active.is_(True)),
    )
    sent_logs = await _scalar_count(
        db,
        select(func.count(OutreachLog.id)).where(
            OutreachLog.delivery_status.in_(
                [
                    DeliveryStatus.SENT.value,
                    DeliveryStatus.REPLIED.value,
                    DeliveryStatus.BOUNCED.value,
                    DeliveryStatus.ENGAGED.value,
                ],
            ),
        ),
    )
    replies = await _scalar_count(
        db,
        select(func.count(OutreachLog.id)).where(
            OutreachLog.delivery_status == DeliveryStatus.REPLIED.value,
        ),
    )
    bounces = await _scalar_count(
        db,
        select(func.count(OutreachLog.id)).where(
            OutreachLog.delivery_status == DeliveryStatus.BOUNCED.value,
        ),
    )
    return AnalyticsOverview(
        total_leads=total_leads,
        enriched_leads=enriched,
        active_signals=active_signals,
        inbound_events_30d=inbound_30d,
        active_sequences=active_sequences,
        reply_rate=_safe_rate(replies, sent_logs),
        bounce_rate=_safe_rate(bounces, sent_logs),
    )


async def build_funnel(db: AsyncSession) -> AnalyticsFunnel:
    """Build the core GTM funnel."""
    total = await _scalar_count(db, select(func.count(Lead.id)))
    enriched = await _scalar_count(
        db,
        select(func.count(Lead.id)).where(
            Lead.enrichment_status == "COMPLETE",
        ),
    )
    signaled = await _scalar_count(
        db,
        select(func.count(distinct(Signal.lead_id))),
    )
    sequenced = await _scalar_count(
        db,
        select(func.count(distinct(LeadSequenceEnrollment.lead_id))),
    )
    replied = await _scalar_count(
        db,
        select(func.count(Lead.id)).where(Lead.outreach_status == "REPLIED"),
    )
    return AnalyticsFunnel(
        stages=[
            FunnelStage(stage="Leads", count=total),
            FunnelStage(stage="Enriched", count=enriched),
            FunnelStage(stage="Signaled", count=signaled),
            FunnelStage(stage="Sequenced", count=sequenced),
            FunnelStage(stage="Replied", count=replied),
        ],
    )


async def build_tam_summary(db: AsyncSession) -> AnalyticsTAM:
    """Build TAM summary metrics."""
    captured = await _scalar_count(db, select(func.count(Lead.id)))
    industries = await _scalar_count(
        db,
        select(func.count(distinct(Lead.industry))).where(
            Lead.industry.isnot(None),
        ),
    )
    result = await db.execute(select(func.avg(Lead.icp_score)))
    avg_score = result.scalar_one()
    return AnalyticsTAM(
        captured_leads=captured,
        industries=industries,
        average_icp_score=round(float(avg_score), 2)
        if avg_score is not None
        else None,
    )


async def build_signal_analytics(db: AsyncSession) -> AnalyticsSignals:
    """Build active signal analytics."""
    now = datetime.now(timezone.utc)
    base = (
        select(Signal)
        .where(Signal.is_read.is_(False))
        .where(Signal.expires_at > now)
        .subquery()
    )
    total = await _scalar_count(db, select(func.count(base.c.id)))
    rows = await db.execute(
        select(base.c.signal_type, func.count(base.c.id))
        .group_by(base.c.signal_type),
    )
    avg_result = await db.execute(select(func.avg(base.c.signal_strength)))
    avg_strength = avg_result.scalar_one()
    return AnalyticsSignals(
        total_active=total,
        by_type={str(row[0]): int(row[1]) for row in rows.all()},
        average_strength=round(float(avg_strength), 4)
        if avg_strength is not None
        else None,
    )


async def build_inbound_analytics(db: AsyncSession) -> AnalyticsInbound:
    """Build strategic inbound analytics."""
    total = await _scalar_count(db, select(func.count(InboundEvent.id)))
    created = await _scalar_count(
        db,
        select(func.count(InboundEvent.id)).where(
            InboundEvent.created_lead_id.isnot(None),
        ),
    )
    rows = await db.execute(
        select(InboundEvent.source, func.count(InboundEvent.id))
        .group_by(InboundEvent.source),
    )
    return AnalyticsInbound(
        total_events=total,
        created_leads=created,
        conversion_rate=_safe_rate(created, total),
        by_source={str(row[0]): int(row[1]) for row in rows.all()},
    )


async def build_sequence_analytics(
    db: AsyncSession,
    sequence_id: uuid.UUID | None = None,
) -> list[SequenceAnalytics]:
    """Build sequence performance rows."""
    status_counts = [
        func.count(LeadSequenceEnrollment.id).label("enrollments"),
        func.sum(
            case(
                (LeadSequenceEnrollment.status == "ACTIVE", 1),
                else_=0,
            ),
        ).label("active"),
        func.sum(
            case(
                (LeadSequenceEnrollment.status == "COMPLETED", 1),
                else_=0,
            ),
        ).label("completed"),
        func.sum(
            case(
                (LeadSequenceEnrollment.status == "REPLIED", 1),
                else_=0,
            ),
        ).label("replied"),
        func.sum(
            case(
                (LeadSequenceEnrollment.status == "BOUNCED", 1),
                else_=0,
            ),
        ).label("bounced"),
    ]
    stmt = (
        select(LeadSequenceEnrollment.sequence_id, *status_counts)
        .group_by(LeadSequenceEnrollment.sequence_id)
    )
    if sequence_id is not None:
        stmt = stmt.where(
            LeadSequenceEnrollment.sequence_id == sequence_id,
        )
    rows = await db.execute(stmt)
    return [
        SequenceAnalytics(
            sequence_id=str(row.sequence_id),
            enrollments=int(row.enrollments or 0),
            active=int(row.active or 0),
            completed=int(row.completed or 0),
            replied=int(row.replied or 0),
            bounced=int(row.bounced or 0),
        )
        for row in rows.all()
    ]


async def build_personalization_analytics(
    db: AsyncSession,
) -> PersonalizationAnalytics:
    """Build personalization quality analytics."""
    total = await _scalar_count(
        db,
        select(func.count(PersonalizationDraft.id)),
    )
    approved = await _scalar_count(
        db,
        select(func.count(PersonalizationDraft.id)).where(
            PersonalizationDraft.status == DraftStatus.APPROVED.value,
        ),
    )
    sent = await _scalar_count(
        db,
        select(func.count(PersonalizationDraft.id)).where(
            PersonalizationDraft.status == DraftStatus.SENT.value,
        ),
    )
    result = await db.execute(
        select(func.avg(PersonalizationDraft.critique_score)),
    )
    avg_score = result.scalar_one()
    return PersonalizationAnalytics(
        total_drafts=total,
        approved_drafts=approved,
        sent_drafts=sent,
        average_critique_score=round(float(avg_score), 2)
        if avg_score is not None
        else None,
    )


async def build_dashboard(db: AsyncSession) -> AnalyticsDashboard:
    """Build all analytics payloads for the frontend dashboard."""
    return AnalyticsDashboard(
        overview=await build_overview(db),
        funnel=await build_funnel(db),
        signals=await build_signal_analytics(db),
        inbound=await build_inbound_analytics(db),
        sequence_summaries=await build_sequence_analytics(db),
        personalization=await build_personalization_analytics(db),
    )


async def _scalar_count(db: AsyncSession, stmt) -> int:
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)
