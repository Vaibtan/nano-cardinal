"""ICP CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.icp import ICP
from app.models.lead import Lead
from app.schemas.icp import (
    ICPCreate,
    ICPMatchPreviewRequest,
    ICPMatchPreviewResponse,
    ICPRead,
    ICPUpdate,
)
from app.services.icp_scorer import parse_size_bucket

router = APIRouter(prefix="/icps", tags=["icps"])


@router.post(
    "",
    response_model=ICPRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_icp(
    body: ICPCreate,
    db: AsyncSession = Depends(get_db),
) -> ICP:
    """Create a new Ideal Customer Profile."""
    icp = ICP(**body.model_dump())
    db.add(icp)
    await db.flush()
    await db.refresh(icp)
    return icp


@router.get("", response_model=list[ICPRead])
async def list_icps(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[ICP]:
    """List all ICPs, optionally filtered to active only."""
    stmt = select(ICP).order_by(ICP.created_at.desc())
    if active_only:
        stmt = stmt.where(ICP.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/match-count", response_model=ICPMatchPreviewResponse)
async def preview_match_count(
    body: ICPMatchPreviewRequest,
    db: AsyncSession = Depends(get_db),
) -> ICPMatchPreviewResponse:
    """Return a live count of leads matching an unsaved ICP config."""
    config = body.config
    stmt = select(func.count()).select_from(Lead)

    if config.industries:
        stmt = stmt.where(Lead.industry.in_(config.industries))
    if config.funding_stages:
        stmt = stmt.where(Lead.funding_stage.in_(config.funding_stages))
    if config.titles:
        stmt = stmt.where(Lead.title.in_(config.titles))
    if config.seniorities:
        stmt = stmt.where(Lead.seniority.in_(config.seniorities))
    if config.departments:
        stmt = stmt.where(Lead.department.in_(config.departments))
    if config.company_sizes:
        size_clauses = []
        for bucket in config.company_sizes:
            parsed = parse_size_bucket(bucket)
            if parsed is None:
                continue
            lo, hi = parsed
            size_clauses.append(
                (Lead.company_size >= lo) & (Lead.company_size <= hi),
            )
        if size_clauses:
            stmt = stmt.where(or_(*size_clauses))
    if config.tech_stack:
        tech_clauses = [
            Lead.tech_stack.contains([tech])
            for tech in config.tech_stack
            if tech
        ]
        if tech_clauses:
            stmt = stmt.where(or_(*tech_clauses))

    matching = await db.scalar(stmt)
    total = await db.scalar(select(func.count()).select_from(Lead))
    return ICPMatchPreviewResponse(
        matching_count=int(matching or 0),
        total_leads=int(total or 0),
    )


@router.get("/{icp_id}", response_model=ICPRead)
async def get_icp(
    icp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ICP:
    """Get a single ICP by id."""
    icp = await db.get(ICP, icp_id)
    if icp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ICP not found",
        )
    return icp


@router.patch("/{icp_id}", response_model=ICPRead)
async def update_icp(
    icp_id: uuid.UUID,
    body: ICPUpdate,
    db: AsyncSession = Depends(get_db),
) -> ICP:
    """Partially update an ICP."""
    icp = await db.get(ICP, icp_id)
    if icp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ICP not found",
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(icp, field, value)
    await db.flush()
    await db.refresh(icp)
    return icp


@router.delete(
    "/{icp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_icp(
    icp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an ICP."""
    icp = await db.get(ICP, icp_id)
    if icp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ICP not found",
        )
    await db.delete(icp)
