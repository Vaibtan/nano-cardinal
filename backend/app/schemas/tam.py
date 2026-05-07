"""Pydantic schemas for TAM endpoints."""

import uuid

from pydantic import BaseModel


class TAMCell(BaseModel):
    """A single cell in the TAM heatmap."""

    dimension_x: str
    dimension_y: str
    total_estimated: int
    captured: int
    in_sequence: int
    replied: int
    coverage_pct: float


class TAMHeatmapResponse(BaseModel):
    """Full TAM heatmap response."""

    icp_id: uuid.UUID
    x_dimension: str
    y_dimension: str
    cells: list[TAMCell]
    total_tam_size: int
    total_captured: int
    overall_coverage_pct: float
    excluded_no_size: int = 0
    tam_estimates_are_defaults: bool = True


class TAMWhitespaceResponse(BaseModel):
    """Whitespace cells with lowest coverage."""

    icp_id: uuid.UUID
    cells: list[TAMCell]
    total_whitespace: int
