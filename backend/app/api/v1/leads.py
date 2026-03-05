"""Lead CRUD, import, and search endpoints."""

from __future__ import annotations

import csv
import io
import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.embeddings import generate_mock_embedding
from app.models.enums import LeadSource
from app.models.lead import Lead
from app.models.outreach import OutreachLog
from app.schemas.lead import (
    CSVImportResult,
    LeadCreate,
    LeadRead,
    OutreachLogRead,
    SemanticSearchResult,
    YCImportRequest,
    YCImportResult,
)
from app.services.enrichment import run_enrichment_pipeline
from app.services.yc_import import import_yc_batch

logger = logging.getLogger(__name__)

_MAX_CSV_BYTES = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/leads", tags=["leads"])


# ── Helpers ──────────────────────────────────────────────────


async def _cosine_search(
    db: AsyncSession,
    embedding: list[float],
    top_k: int,
    exclude_id: uuid.UUID | None = None,
) -> list[dict]:
    """Find leads closest to *embedding* by cosine distance."""
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    stmt = (
        select(
            Lead,
            Lead.embedding.cosine_distance(
                text(f"'{vec_str}'::vector"),
            ).label("distance"),
        )
        .where(Lead.embedding.isnot(None))
        .order_by("distance")
        .limit(top_k)
    )
    if exclude_id is not None:
        stmt = stmt.where(Lead.id != exclude_id)
    result = await db.execute(stmt)
    return [
        {
            "lead": row[0],
            "similarity": round(1.0 - float(row[1]), 4),
        }
        for row in result.all()
    ]


# ── CRUD ─────────────────────────────────────────────────────


@router.post(
    "",
    response_model=LeadRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_lead(
    body: LeadCreate,
    db: AsyncSession = Depends(get_db),
) -> Lead:
    """Create a single lead and enqueue enrichment."""
    lead = Lead(**body.model_dump())
    db.add(lead)
    await db.flush()
    await db.refresh(lead)
    return lead


@router.get("", response_model=list[LeadRead])
async def list_leads(
    enrichment_status: str | None = None,
    outreach_status: str | None = None,
    source: str | None = None,
    icp_id: uuid.UUID | None = None,
    min_icp_score: float | None = None,
    max_icp_score: float | None = None,
    industry: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[Lead]:
    """List leads with optional filters and pagination."""
    stmt = select(Lead).order_by(Lead.updated_at.desc())

    if enrichment_status:
        stmt = stmt.where(Lead.enrichment_status == enrichment_status)
    if outreach_status:
        stmt = stmt.where(Lead.outreach_status == outreach_status)
    if source:
        stmt = stmt.where(Lead.source == source)
    if icp_id:
        stmt = stmt.where(Lead.icp_id == icp_id)
    if min_icp_score is not None:
        stmt = stmt.where(Lead.icp_score >= min_icp_score)
    if max_icp_score is not None:
        stmt = stmt.where(Lead.icp_score <= max_icp_score)
    if industry:
        stmt = stmt.where(Lead.industry == industry)

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/search", response_model=list[SemanticSearchResult])
async def search_leads(
    q: str = Query(min_length=1),
    top_k: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Semantic search across all leads using pgvector."""
    if settings.USE_MOCK_ENRICHMENT:
        query_vec = generate_mock_embedding(q)
    else:
        # TODO: Call real embedding API
        raise HTTPException(
            status_code=501,
            detail="Real embedding API not yet implemented",
        )

    return await _cosine_search(db, query_vec, top_k)


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Lead:
    """Get a single lead by ID."""
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    return lead


@router.delete(
    "/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a lead."""
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    await db.delete(lead)


@router.post(
    "/{lead_id}/enrich",
    response_model=LeadRead,
)
async def enrich_lead(
    lead_id: uuid.UUID,
    background: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> Lead:
    """Re-trigger enrichment for a single lead.

    Pass ``background=true`` to dispatch to the ARQ worker instead of
    running synchronously.  Requires a running Redis + ARQ worker.
    """
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    if background:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            pool = await create_pool(
                RedisSettings.from_dsn(settings.REDIS_URL),
            )
            try:
                await pool.enqueue_job("enrich_lead", str(lead_id))
            finally:
                await pool.close()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Background worker unavailable; use sync enrichment",
            ) from exc
        await db.refresh(lead)
        return lead

    try:
        await run_enrichment_pipeline(str(lead_id), db)
    except Exception:
        # Pipeline has set FAILED status and flushed it.
        # Swallow so get_db commits FAILED instead of rolling back.
        logger.warning("Enrichment failed for lead %s (sync path)", lead_id)
    await db.refresh(lead)
    return lead


@router.get(
    "/{lead_id}/similar",
    response_model=list[SemanticSearchResult],
)
async def get_similar_leads(
    lead_id: uuid.UUID,
    top_k: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Find leads most similar to the given lead via pgvector."""
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    if lead.embedding is None:
        return []

    return await _cosine_search(
        db, list(lead.embedding), top_k, exclude_id=lead_id,
    )


@router.get(
    "/{lead_id}/outreach",
    response_model=list[OutreachLogRead],
)
async def get_lead_outreach(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[OutreachLog]:
    """Get outreach history for a lead."""
    # Verify lead exists
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    stmt = (
        select(OutreachLog)
        .where(OutreachLog.lead_id == lead_id)
        .order_by(OutreachLog.sent_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── CSV Import ───────────────────────────────────────────────

_CSV_FIELDS = {
    "first_name",
    "last_name",
    "email",
    "company_name",
    "company_domain",
    "title",
    "linkedin_url",
    "industry",
    "company_size",
}


@router.post(
    "/import/csv",
    response_model=CSVImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Bulk import leads from a CSV file."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a .csv",
        )

    content = await file.read(_MAX_CSV_BYTES + 1)
    if len(content) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"CSV file too large (max {_MAX_CSV_BYTES // 1024 // 1024} MB)",
        )
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))

    imported = 0
    errors: list[dict] = []
    total_rows = 0

    for row_num, row in enumerate(reader, start=2):
        total_rows += 1
        try:
            # Filter to known fields only
            data: dict = {}
            for field in _CSV_FIELDS:
                val = row.get(field, "").strip()
                if val:
                    if field == "company_size":
                        data[field] = int(val)
                    else:
                        data[field] = val

            if not data.get("email") and not data.get("company_name"):
                errors.append({
                    "row": row_num,
                    "error": "Row must have at least email or company_name",
                })
                continue

            lead = Lead(source=LeadSource.CSV_IMPORT, **data)
            db.add(lead)
            imported += 1

        except (ValueError, TypeError) as exc:
            errors.append({"row": row_num, "error": str(exc)})

    if imported > 0:
        await db.flush()

    return {
        "total_rows": total_rows,
        "imported": imported,
        "errors": errors,
    }


# ── YC Import ────────────────────────────────────────────────


@router.post(
    "/import/yc",
    response_model=YCImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_yc(
    body: YCImportRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Import leads from YC directory (mock fixture mode)."""
    raw_leads = await import_yc_batch(
        batch=body.batch, limit=body.limit,
    )

    created: list[Lead] = []
    for raw in raw_leads:
        lead = Lead(**raw.model_dump())
        db.add(lead)
        created.append(lead)

    await db.flush()
    for lead in created:
        await db.refresh(lead)

    return {"imported": len(created), "leads": created}
