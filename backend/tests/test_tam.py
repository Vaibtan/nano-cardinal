"""Tests for TAM aggregation endpoints."""

import pytest
from httpx import AsyncClient

_TAM = "/api/v1/tam"
_LEADS = "/api/v1/leads"
_ICPS = "/api/v1/icps"


@pytest.fixture
async def icp_with_leads(client: AsyncClient) -> dict:
    """Create an ICP and some matching leads."""
    # Create ICP
    icp_resp = await client.post(
        _ICPS,
        json={
            "name": "SaaS ICP",
            "config": {
                "industries": ["SaaS", "Fintech"],
                "company_sizes": ["50-200", "201-1000"],
            },
            "weights": {"industry": 1.0, "company_size": 1.0},
        },
    )
    assert icp_resp.status_code == 201
    icp = icp_resp.json()

    # Create leads and enrich so they get scored against the ICP
    for name, industry, size in [
        ("Lead1", "SaaS", 100),
        ("Lead2", "SaaS", 150),
        ("Lead3", "Fintech", 300),
    ]:
        lead_resp = await client.post(
            _LEADS,
            json={
                "first_name": name,
                "company_name": f"{name}Co",
                "industry": industry,
                "company_size": size,
            },
        )
        assert lead_resp.status_code == 201
        lid = lead_resp.json()["id"]
        await client.post(f"{_LEADS}/{lid}/enrich")

    return icp


async def test_tam_heatmap(
    client: AsyncClient, icp_with_leads: dict,
) -> None:
    icp_id = icp_with_leads["id"]
    resp = await client.get(
        f"{_TAM}/heatmap", params={"icp_id": icp_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["icp_id"] == icp_id
    assert data["x_dimension"] == "industry"
    assert data["y_dimension"] == "company_size"
    assert len(data["cells"]) > 0
    assert data["total_tam_size"] > 0

    # Check cell structure
    cell = data["cells"][0]
    assert "dimension_x" in cell
    assert "dimension_y" in cell
    assert "total_estimated" in cell
    assert "coverage_pct" in cell


async def test_tam_heatmap_not_found(client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(
        f"{_TAM}/heatmap", params={"icp_id": fake_id},
    )
    assert resp.status_code == 404


async def test_tam_heatmap_per_cell(
    client: AsyncClient, icp_with_leads: dict,
) -> None:
    """Verify per-cell aggregates are correct (no double-counting)."""
    icp_id = icp_with_leads["id"]
    resp = await client.get(
        f"{_TAM}/heatmap", params={"icp_id": icp_id},
    )
    assert resp.status_code == 200
    data = resp.json()

    # 2 industries × 2 size buckets = 4 cells
    assert len(data["cells"]) == 4

    cells = {
        (c["dimension_x"], c["dimension_y"]): c for c in data["cells"]
    }

    # Lead1 (SaaS, 100) + Lead2 (SaaS, 150) → bucket "50-200"
    saas_small = cells[("SaaS", "50-200")]
    assert saas_small["captured"] == 2

    # Lead3 (Fintech, 300) → bucket "201-1000"
    fintech_mid = cells[("Fintech", "201-1000")]
    assert fintech_mid["captured"] == 1

    # Empty cells
    assert cells[("SaaS", "201-1000")]["captured"] == 0
    assert cells[("Fintech", "50-200")]["captured"] == 0

    # Total captured must equal exactly 3 (no double-counting)
    assert data["total_captured"] == 3


async def test_tam_whitespace(
    client: AsyncClient, icp_with_leads: dict,
) -> None:
    icp_id = icp_with_leads["id"]
    resp = await client.get(
        f"{_TAM}/whitespace",
        params={"icp_id": icp_id, "top_n": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["icp_id"] == icp_id
    assert "cells" in data
    assert "total_whitespace" in data
    # Whitespace cells should be sorted by coverage (lowest first)
    if len(data["cells"]) >= 2:
        assert data["cells"][0]["coverage_pct"] <= data["cells"][1]["coverage_pct"]
