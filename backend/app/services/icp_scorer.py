"""ICP scoring service.

Score = Σ(weight_i × match_i) / Σ(weight_i) × 100

Where match_i ∈ {0, 0.5, 1.0}:
  1.0 = exact match
  0.5 = partial match (industry adjacent, size close, etc.)
  0.0 = no match
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.icp import ICP
from app.models.lead import Lead

logger = logging.getLogger(__name__)

# ── Shared helpers ────────────────────────────────────────────


def parse_size_bucket(bucket: str) -> tuple[int, int] | None:
    """Parse '50-200' → (50, 200) or '1001+' → (1001, 999_999_999)."""
    b = bucket.strip().replace(" ", "")
    if b.endswith("+"):
        try:
            return (int(b[:-1]), 999_999_999)
        except ValueError:
            return None
    parts = b.split("-")
    if len(parts) == 2:
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            return None
    return None


# ── Match helpers ────────────────────────────────────────────


def _list_match(lead_value: str | None, icp_values: list[str]) -> float:
    """Return 1.0 for exact, 0.5 for partial, 0.0 for no match."""
    if not icp_values or not lead_value:
        return 0.0
    lower_val = lead_value.lower()
    lower_list = [v.lower() for v in icp_values]
    if lower_val in lower_list:
        return 1.0
    # Partial: substring match in either direction
    for item in lower_list:
        if item in lower_val or lower_val in item:
            return 0.5
    return 0.0


def _size_match(
    company_size: int | None,
    size_buckets: list[str],
) -> float:
    """Match company size against ICP size buckets like '50-200' or '1001+'."""
    if not company_size or not size_buckets:
        return 0.0
    for bucket in size_buckets:
        parsed = parse_size_bucket(bucket)
        if parsed is None:
            continue
        lo, hi = parsed
        if lo <= company_size <= hi:
            return 1.0
        # Close range (within 50% of bucket span)
        if hi < 999_999_999:
            margin = (hi - lo) * 0.5
        else:
            margin = lo * 0.5
        if lo - margin <= company_size <= hi + margin:
            return 0.5
    return 0.0


# ── Scoring engine ───────────────────────────────────────────


def compute_icp_score(
    lead: Lead,
    config: dict[str, Any],
    weights: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    """Compute weighted ICP score for a lead.

    Returns (score_0_to_100, breakdown_dict).
    """
    dimensions: dict[str, float] = {}

    # Industry
    dimensions["industry"] = _list_match(
        lead.industry, config.get("industries", []),
    )

    # Company size
    dimensions["company_size"] = _size_match(
        lead.company_size, config.get("company_sizes", []),
    )

    # Funding stage
    dimensions["funding_stage"] = _list_match(
        lead.funding_stage, config.get("funding_stages", []),
    )

    # Title
    dimensions["title"] = _list_match(
        lead.title, config.get("titles", []),
    )

    # Seniority
    dimensions["seniority"] = _list_match(
        lead.seniority, config.get("seniorities", []),
    )

    # Department
    dimensions["department"] = _list_match(
        lead.department, config.get("departments", []),
    )

    # Tech stack — average across lead's tech stack items
    icp_tech = config.get("tech_stack", [])
    if icp_tech and lead.tech_stack:
        matches = [_list_match(t, icp_tech) for t in lead.tech_stack]
        dimensions["tech_stack"] = sum(matches) / len(matches)
    else:
        dimensions["tech_stack"] = 0.0

    # Region (not stored on lead yet — default to 0)
    dimensions["region"] = 0.0

    # Compute weighted score
    total_weight = 0.0
    weighted_sum = 0.0
    for dim, match_val in dimensions.items():
        w = float(weights.get(dim, 1.0))
        total_weight += w
        weighted_sum += w * match_val

    if total_weight == 0:
        return 0.0, dimensions

    score = (weighted_sum / total_weight) * 100.0
    return round(score, 2), {k: round(v, 3) for k, v in dimensions.items()}


async def score_lead_against_all_icps(
    lead: Lead,
    db: AsyncSession,
) -> None:
    """Score a lead against all active ICPs, persist best match."""
    stmt = select(ICP).where(ICP.is_active.is_(True))
    result = await db.execute(stmt)
    icps = list(result.scalars().all())

    if not icps:
        return

    best_score = -1.0
    best_icp_id = None
    full_breakdown: dict[str, float] = {}

    for icp in icps:
        score, breakdown = compute_icp_score(
            lead,
            icp.config or {},
            icp.weights or {},
        )
        if score > best_score:
            best_score = score
            best_icp_id = icp.id
            full_breakdown = breakdown

    lead.icp_score = best_score
    lead.icp_id = best_icp_id
    lead.icp_score_breakdown = full_breakdown
