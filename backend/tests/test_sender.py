"""Tests for Sender Profile endpoints."""

import pytest
from httpx import AsyncClient

_BASE = "/api/v1/sender"


@pytest.fixture
async def sample_sender(client: AsyncClient) -> dict:
    """Create and return a sample sender profile."""
    payload = {
        "name": "Alice Founder",
        "current_title": "CEO",
        "current_company": "Acme Inc",
        "education": ["MIT", "Stanford"],
        "past_employers": ["Google", "Meta"],
        "cities_lived": ["SF", "NYC"],
        "hobbies_and_interests": ["Running", "Chess"],
        "investors": ["a16z"],
        "languages_spoken": ["English", "Spanish"],
        "conferences_attended": ["SaaStr", "Web Summit"],
    }
    resp = await client.post(_BASE, json=payload)
    assert resp.status_code == 201
    return resp.json()


async def test_create_sender(client: AsyncClient) -> None:
    payload = {
        "name": "Bob Sales",
        "current_title": "VP Sales",
    }
    resp = await client.post(_BASE, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Bob Sales"
    assert data["user_id"] == "default"
    assert data["education"] == []


async def test_create_sender_missing_name(
    client: AsyncClient,
) -> None:
    resp = await client.post(_BASE, json={})
    assert resp.status_code == 422


async def test_get_sender(
    client: AsyncClient, sample_sender: dict,
) -> None:
    resp = await client.get(_BASE)
    assert resp.status_code == 200
    assert resp.json()["name"] == sample_sender["name"]


async def test_get_sender_not_found(
    client: AsyncClient,
) -> None:
    resp = await client.get(_BASE)
    assert resp.status_code == 404


async def test_upsert_sender(
    client: AsyncClient, sample_sender: dict,
) -> None:
    """POST again should update (upsert), not create a second."""
    payload = {
        "name": "Alice Updated",
        "current_title": "CTO",
    }
    resp = await client.post(_BASE, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alice Updated"
    # Same id (upserted, not duplicated).
    assert data["id"] == sample_sender["id"]


async def test_patch_sender(
    client: AsyncClient, sample_sender: dict,
) -> None:
    resp = await client.patch(
        f"{_BASE}/{sample_sender['id']}",
        json={"current_company": "NewCo"},
    )
    assert resp.status_code == 200
    assert resp.json()["current_company"] == "NewCo"
    # Unchanged field preserved.
    assert resp.json()["name"] == sample_sender["name"]


async def test_patch_sender_not_found(
    client: AsyncClient,
) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.patch(
        f"{_BASE}/{fake_id}", json={"name": "x"},
    )
    assert resp.status_code == 404
