"""Signal scoring, creation, and mock monitoring services."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.icp import ICP
from app.models.lead import Lead
from app.models.signal import Signal
from app.redis import redis_client
from app.services.event_bus import publish_event

logger = logging.getLogger(__name__)

_BASE_SCORES: dict[str, float] = {
    "PRODUCT_SIGNUP": 0.98,
    "WEBSITE_VISIT": 0.95,
    "CONFERENCE_ATTENDANCE": 0.90,
    "FUNDING_ROUND": 0.88,
    "HIRING_SURGE": 0.84,
    "JOB_POSTING_ICP_ROLE": 0.82,
    "LEADERSHIP_HIRE": 0.80,
    "JOB_CHANGE": 0.78,
    "LINKEDIN_POST": 0.74,
    "NEWS_MENTION": 0.70,
    "PRODUCT_LAUNCH": 0.68,
    "TECH_STACK_CHANGE": 0.66,
}

_SIGNAL_RETENTION_DAYS = 90
_DEDUP_TTL_SECONDS = 7 * 24 * 60 * 60


def build_signal_hash(
    lead_id: str,
    signal_type: str,
    title: str,
    body: str | None,
) -> str:
    """Build a deterministic hash for deduplicating signals."""
    raw = "|".join(
        [
            lead_id,
            signal_type,
            title.strip().lower(),
            (body or "").strip().lower(),
        ],
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _keyword_matches(
    icp: ICP | None,
    title: str,
    body: str | None,
) -> bool:
    if icp is None:
        return False
    keywords = (icp.config or {}).get("signal_keywords", [])
    if not keywords:
        return False
    haystack = f"{title} {body or ''}".lower()
    return any(str(keyword).lower() in haystack for keyword in keywords)


def compute_signal_strength(
    lead: Lead,
    signal_type: str,
    title: str,
    body: str | None,
    detected_at: datetime,
    icp: ICP | None = None,
) -> float:
    """Compute final signal strength with the PRD modifiers."""
    score = _BASE_SCORES.get(signal_type, 0.60)
    now = datetime.now(timezone.utc)

    if detected_at >= now - timedelta(hours=48):
        score *= 1.2
    if lead.icp_score is not None and lead.icp_score > 80:
        score *= 1.1
    if (
        lead.last_contacted_at is not None
        and lead.last_contacted_at >= now - timedelta(days=30)
    ):
        score *= 0.8
    if _keyword_matches(icp, title, body):
        score *= 1.05

    return round(min(score, 1.0), 4)


async def _claim_dedup_key(signal_hash: str) -> bool:
    """Return True if this process owns the signal hash for 7 days."""
    key = f"signal-dedup:{signal_hash}"
    try:
        return bool(
            await redis_client.set(
                key,
                "1",
                ex=_DEDUP_TTL_SECONDS,
                nx=True,
            ),
        )
    except Exception:
        logger.debug("Redis signal dedup unavailable", exc_info=True)
        return True


async def create_signal(
    db: AsyncSession,
    lead: Lead,
    signal_type: str,
    title: str,
    body: str | None = None,
    url: str | None = None,
    detected_at: datetime | None = None,
) -> Signal | None:
    """Create a scored signal unless it was recently deduplicated."""
    detected = detected_at or datetime.now(timezone.utc)
    signal_hash = build_signal_hash(
        str(lead.id),
        signal_type,
        title,
        body,
    )
    if not await _claim_dedup_key(signal_hash):
        return None

    icp = await db.get(ICP, lead.icp_id) if lead.icp_id else None
    strength = compute_signal_strength(
        lead,
        signal_type,
        title,
        body,
        detected,
        icp,
    )
    signal = Signal(
        lead_id=lead.id,
        company_domain=lead.company_domain,
        signal_type=signal_type,
        signal_title=title,
        signal_body=body,
        signal_url=url,
        signal_strength=strength,
        signal_hash=signal_hash,
        detected_at=detected,
        expires_at=detected + timedelta(days=_SIGNAL_RETENTION_DAYS),
    )
    try:
        async with db.begin_nested():
            db.add(signal)
            await db.flush()
    except IntegrityError:
        return None

    await publish_event(
        "signal.detected",
        {
            "signal_id": str(signal.id),
            "lead_id": str(lead.id),
            "signal_type": signal.signal_type,
            "signal_title": signal.signal_title,
            "signal_strength": signal.signal_strength or 0.0,
        },
    )
    return signal


async def run_mock_signal_scan(db: AsyncSession) -> int:
    """Create deterministic mock monitor signals for enriched leads."""
    result = await db.execute(
        select(Lead)
        .where(Lead.enrichment_status == "COMPLETE")
        .order_by(Lead.updated_at.desc())
        .limit(100),
    )
    created = 0
    for lead in result.scalars().all():
        signal_type = _pick_mock_signal_type(lead)
        signal = await create_signal(
            db=db,
            lead=lead,
            signal_type=signal_type,
            title=_mock_signal_title(lead, signal_type),
            body=_mock_signal_body(lead, signal_type),
        )
        if signal is not None:
            created += 1
    return created


def _pick_mock_signal_type(lead: Lead) -> str:
    """Pick a stable signal type from lead attributes."""
    seed = str(lead.company_domain or lead.email or lead.id)
    options = [
        "FUNDING_ROUND",
        "HIRING_SURGE",
        "LINKEDIN_POST",
        "NEWS_MENTION",
    ]
    return options[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 4]


def _mock_signal_title(lead: Lead, signal_type: str) -> str:
    company = lead.company_name or lead.company_domain or "Target account"
    titles = {
        "FUNDING_ROUND": f"{company} shows new funding momentum",
        "HIRING_SURGE": f"{company} is hiring for GTM and platform roles",
        "LINKEDIN_POST": f"{company} leader is discussing growth priorities",
        "NEWS_MENTION": f"{company} appeared in market news",
    }
    return titles.get(signal_type, f"{company} has a buying signal")


def _mock_signal_body(lead: Lead, signal_type: str) -> str:
    industry = lead.industry or "their market"
    return (
        f"Mock {signal_type.lower()} signal for "
        f"{lead.company_name or lead.company_domain or 'this account'} "
        f"in {industry}."
    )
