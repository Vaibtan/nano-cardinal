"""ICP CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.icp import ICP
from app.schemas.icp import ICPCreate, ICPRead, ICPUpdate

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
