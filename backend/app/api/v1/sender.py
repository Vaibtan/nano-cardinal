"""Sender Profile endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.sender import SenderProfile
from app.schemas.sender import (
    SenderProfileCreate,
    SenderProfileRead,
    SenderProfileUpdate,
)

router = APIRouter(prefix="/sender", tags=["sender"])


@router.post(
    "",
    response_model=SenderProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_sender_profile(
    body: SenderProfileCreate,
    db: AsyncSession = Depends(get_db),
) -> SenderProfile:
    """Create or replace the sender profile (atomic upsert)."""
    values = {**body.model_dump(), "user_id": "default"}
    stmt = (
        pg_insert(SenderProfile)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={k: v for k, v in values.items() if k != "user_id"},
        )
        .returning(SenderProfile)
    )
    result = await db.execute(stmt)
    profile = result.scalar_one()
    return profile


@router.get("", response_model=SenderProfileRead | None)
async def get_sender_profile(
    db: AsyncSession = Depends(get_db),
) -> SenderProfile | None:
    """Get the current sender profile."""
    stmt = select(SenderProfile).where(
        SenderProfile.user_id == "default",
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender profile not found",
        )
    return profile


@router.patch("/{profile_id}", response_model=SenderProfileRead)
async def update_sender_profile(
    profile_id: uuid.UUID,
    body: SenderProfileUpdate,
    db: AsyncSession = Depends(get_db),
) -> SenderProfile:
    """Partially update the sender profile."""
    profile = await db.get(SenderProfile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender profile not found",
        )
    for field, value in body.model_dump(
        exclude_unset=True,
    ).items():
        setattr(profile, field, value)
    await db.flush()
    await db.refresh(profile)
    return profile
