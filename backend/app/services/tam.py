"""TAM (Total Addressable Market) aggregation service."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OutreachStatus
from app.models.icp import ICP
from app.models.lead import Lead
from app.schemas.tam import (
    TAMCell,
    TAMHeatmapResponse,
    TAMWhitespaceResponse,
)
from app.services.icp_scorer import parse_size_bucket


# Rough estimates per industry-size combination for demo purposes.
_DEFAULT_TAM_ESTIMATE = 500


async def build_heatmap(
    icp_id: uuid.UUID,
    db: AsyncSession,
) -> TAMHeatmapResponse:
    """Build a TAM heatmap for the given ICP.

    X-axis: industries from ICP config
    Y-axis: company_sizes from ICP config

    Groups leads by (industry, derived_size_bucket) to produce
    per-cell aggregates without double-counting.
    """
    icp = await db.get(ICP, icp_id)
    if icp is None:
        msg = f"ICP {icp_id} not found"
        raise ValueError(msg)

    config: dict[str, Any] = icp.config or {}
    industries: list[str] = config.get("industries", [])
    size_buckets: list[str] = config.get("company_sizes", [])

    # Defaults if ICP config is sparse
    if not industries:
        industries = ["Other"]
    if not size_buckets:
        size_buckets = ["1-50", "51-200", "201-1000", "1001+"]

    # Build SQL CASE expression that maps company_size → bucket label
    whens: list[tuple] = []
    for bucket in size_buckets:
        parsed = parse_size_bucket(bucket)
        if parsed:
            lo, hi = parsed
            whens.append((Lead.company_size.between(lo, hi), bucket))

    if not whens:
        # No valid size buckets — every lead falls into "Unknown"
        size_bucket_expr = case(else_=None)
    else:
        size_bucket_expr = case(*whens, else_=None)

    # Query: group by (industry, size_bucket) — includes NULL-size leads
    # so we can count excluded rows without a separate query.
    stmt = (
        select(
            Lead.industry,
            size_bucket_expr.label("size_bucket"),
            func.count(Lead.id).label("captured"),
            func.sum(
                case(
                    (Lead.outreach_status == OutreachStatus.IN_SEQUENCE, 1),
                    else_=0,
                ),
            ).label("in_sequence"),
            func.sum(
                case(
                    (Lead.outreach_status == OutreachStatus.REPLIED, 1),
                    else_=0,
                ),
            ).label("replied"),
        )
        .where(Lead.icp_id == icp_id)
        .where(Lead.industry.in_(industries))
        .group_by(Lead.industry, size_bucket_expr)
    )
    result = await db.execute(stmt)

    # Build lookup: (industry, size_bucket) → stats
    # Rows where size_bucket is None are leads with NULL or unbucketable
    # company_size — count them as excluded.
    rows: dict[tuple[str, str], dict[str, int]] = {}
    excluded_no_size = 0
    for r in result:
        if r.size_bucket is None:
            excluded_no_size += r.captured
        else:
            rows[(r.industry, r.size_bucket)] = {
                "captured": r.captured,
                "in_sequence": r.in_sequence or 0,
                "replied": r.replied or 0,
            }

    cells: list[TAMCell] = []
    total_tam = 0
    total_captured = 0

    for ind in industries:
        for size in size_buckets:
            estimate = _DEFAULT_TAM_ESTIMATE
            total_tam += estimate
            stats = rows.get(
                (ind, size),
                {"captured": 0, "in_sequence": 0, "replied": 0},
            )
            captured = stats["captured"]
            total_captured += captured
            coverage = (captured / estimate * 100) if estimate > 0 else 0.0

            cells.append(
                TAMCell(
                    dimension_x=ind,
                    dimension_y=size,
                    total_estimated=estimate,
                    captured=captured,
                    in_sequence=stats["in_sequence"],
                    replied=stats["replied"],
                    coverage_pct=round(coverage, 1),
                ),
            )

    overall = (total_captured / total_tam * 100) if total_tam > 0 else 0.0

    return TAMHeatmapResponse(
        icp_id=icp_id,
        x_dimension="industry",
        y_dimension="company_size",
        cells=cells,
        total_tam_size=total_tam,
        total_captured=total_captured,
        overall_coverage_pct=round(overall, 1),
        excluded_no_size=excluded_no_size,
        tam_estimates_are_defaults=True,
    )


async def get_whitespace(
    icp_id: uuid.UUID,
    db: AsyncSession,
    top_n: int = 10,
) -> TAMWhitespaceResponse:
    """Return the cells with lowest coverage_pct."""
    heatmap = await build_heatmap(icp_id, db)
    sorted_cells = sorted(heatmap.cells, key=lambda c: c.coverage_pct)
    whitespace = sorted_cells[:top_n]
    return TAMWhitespaceResponse(
        icp_id=icp_id,
        cells=whitespace,
        total_whitespace=len(
            [c for c in heatmap.cells if c.coverage_pct == 0],
        ),
    )
