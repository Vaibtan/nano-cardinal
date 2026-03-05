"""Tests for ICP CRUD endpoints."""

import pytest
from httpx import AsyncClient

_BASE = "/api/v1/icps"


@pytest.fixture
async def sample_icp(client: AsyncClient) -> dict:
    """Create and return a sample ICP via the API."""
    payload = {
        "name": "Mid-market SaaS",
        "description": "B2B SaaS in 50-500 range",
        "config": {
            "industries": ["SaaS", "Fintech"],
            "company_sizes": ["50-200"],
        },
        "weights": {"industry": 1.5, "company_size": 1.0},
    }
    resp = await client.post(_BASE, json=payload)
    assert resp.status_code == 201
    return resp.json()


async def test_create_icp(client: AsyncClient) -> None:
    payload = {
        "name": "Enterprise",
        "config": {"industries": ["Enterprise"]},
        "weights": {"industry": 2.0},
    }
    resp = await client.post(_BASE, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Enterprise"
    assert data["is_active"] is True
    assert "id" in data


async def test_create_icp_missing_name(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        _BASE, json={"config": {}, "weights": {}},
    )
    assert resp.status_code == 422


async def test_list_icps(
    client: AsyncClient, sample_icp: dict,
) -> None:
    resp = await client.get(_BASE)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["id"] == sample_icp["id"]


async def test_list_icps_active_filter(
    client: AsyncClient, sample_icp: dict,
) -> None:
    # Deactivate the ICP.
    await client.patch(
        f"{_BASE}/{sample_icp['id']}",
        json={"is_active": False},
    )
    resp = await client.get(_BASE, params={"active_only": True})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


async def test_get_icp(
    client: AsyncClient, sample_icp: dict,
) -> None:
    resp = await client.get(f"{_BASE}/{sample_icp['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == sample_icp["name"]


async def test_get_icp_not_found(
    client: AsyncClient,
) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"{_BASE}/{fake_id}")
    assert resp.status_code == 404


async def test_update_icp(
    client: AsyncClient, sample_icp: dict,
) -> None:
    resp = await client.patch(
        f"{_BASE}/{sample_icp['id']}",
        json={"name": "Updated Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


async def test_delete_icp(
    client: AsyncClient, sample_icp: dict,
) -> None:
    resp = await client.delete(f"{_BASE}/{sample_icp['id']}")
    assert resp.status_code == 204

    # Verify it's gone.
    resp = await client.get(f"{_BASE}/{sample_icp['id']}")
    assert resp.status_code == 404
