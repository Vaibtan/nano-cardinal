"""Sequence management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.lead import Lead
from app.models.sequence import LeadSequenceEnrollment, Sequence
from app.schemas.sequence import (
    EnrollmentCreate,
    EnrollmentRead,
    SequenceCreate,
    SequenceRead,
    SequenceUpdate,
)
from app.services.sequences import (
    create_sequence,
    enroll_lead,
    execute_due_enrollments,
    update_sequence,
)

router = APIRouter(prefix="/sequences", tags=["sequences"])


@router.post(
    "",
    response_model=SequenceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    body: SequenceCreate,
    db: AsyncSession = Depends(get_db),
) -> Sequence:
    """Create a sequence."""
    return await create_sequence(db, body)


@router.get("", response_model=list[SequenceRead])
async def list_sequences(
    db: AsyncSession = Depends(get_db),
) -> list[Sequence]:
    """List sequences."""
    result = await db.execute(
        select(Sequence)
        .options(selectinload(Sequence.steps))
        .order_by(Sequence.created_at.desc()),
    )
    return list(result.scalars().all())


@router.post("/execute-due")
async def execute_due(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Run one execution pass for due enrollments."""
    executed = await execute_due_enrollments(db)
    return {"executed": executed}


@router.get("/{sequence_id}", response_model=SequenceRead)
async def get_sequence(
    sequence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Sequence:
    """Get sequence detail."""
    return await _get_sequence_or_404(db, sequence_id)


@router.patch("/{sequence_id}", response_model=SequenceRead)
async def patch_sequence(
    sequence_id: uuid.UUID,
    body: SequenceUpdate,
    db: AsyncSession = Depends(get_db),
) -> Sequence:
    """Update sequence metadata or steps."""
    sequence = await _get_sequence_or_404(db, sequence_id)
    return await update_sequence(db, sequence, body)


@router.post(
    "/{sequence_id}/enrollments",
    response_model=EnrollmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def enroll(
    sequence_id: uuid.UUID,
    body: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
) -> LeadSequenceEnrollment:
    """Enroll a lead into a sequence."""
    sequence = await _get_sequence_or_404(db, sequence_id)
    lead = await db.get(Lead, body.lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    return await enroll_lead(db, sequence, lead)


@router.get(
    "/{sequence_id}/enrollments",
    response_model=list[EnrollmentRead],
)
async def list_enrollments(
    sequence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[LeadSequenceEnrollment]:
    """List enrollments for a sequence."""
    await _get_sequence_or_404(db, sequence_id)
    result = await db.execute(
        select(LeadSequenceEnrollment)
        .where(LeadSequenceEnrollment.sequence_id == sequence_id)
        .order_by(LeadSequenceEnrollment.enrolled_at.desc()),
    )
    return list(result.scalars().all())


async def _get_sequence_or_404(
    db: AsyncSession,
    sequence_id: uuid.UUID,
) -> Sequence:
    result = await db.execute(
        select(Sequence)
        .options(selectinload(Sequence.steps))
        .where(Sequence.id == sequence_id),
    )
    sequence = result.scalars().first()
    if sequence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sequence not found",
        )
    return sequence
