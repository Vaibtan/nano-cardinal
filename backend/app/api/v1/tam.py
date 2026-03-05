"""TAM (Total Addressable Market) endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.tam import TAMHeatmapResponse, TAMWhitespaceResponse
from app.services.tam import build_heatmap, get_whitespace

router = APIRouter(prefix="/tam", tags=["tam"])


@router.get("/heatmap", response_model=TAMHeatmapResponse)
async def tam_heatmap(
    icp_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> TAMHeatmapResponse:
    """Return TAM coverage heatmap for an ICP."""
    try:
        return await build_heatmap(icp_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/whitespace", response_model=TAMWhitespaceResponse)
async def tam_whitespace(
    icp_id: uuid.UUID = Query(...),
    top_n: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> TAMWhitespaceResponse:
    """Return cells with lowest coverage for whitespace discovery."""
    try:
        return await get_whitespace(icp_id, db, top_n=top_n)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
