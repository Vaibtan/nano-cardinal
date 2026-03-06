"""Tests for Lead CRUD, import, enrichment, and search endpoints."""

import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

_BASE = "/api/v1/leads"


@pytest.fixture
async def sample_lead(client: AsyncClient) -> dict:
    """Create and return a sample lead via the API."""
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        "company_name": "Acme Corp",
        "company_domain": "acme.com",
        "title": "VP Engineering",
        "industry": "SaaS",
        "company_size": 150,
        "tech_stack": ["Python", "React"],
    }
    resp = await client.post(_BASE, json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def sample_icp(client: AsyncClient) -> dict:
    """Create an ICP for scoring/TAM tests."""
    payload = {
        "name": "Mid-market SaaS",
        "config": {
            "industries": ["SaaS"],
            "company_sizes": ["50-200"],
            "titles": ["VP Engineering", "CTO"],
        },
        "weights": {"industry": 2.0, "company_size": 1.5, "title": 1.0},
    }
    resp = await client.post("/api/v1/icps", json=payload)
    assert resp.status_code == 201
    return resp.json()


# ── CRUD ─────────────────────────────────────────────────────


async def test_create_lead(client: AsyncClient) -> None:
    payload = {
        "first_name": "John",
        "last_name": "Smith",
        "company_name": "TestCo",
    }
    resp = await client.post(_BASE, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["first_name"] == "John"
    assert data["enrichment_status"] == "PENDING"
    assert data["source"] == "MANUAL"
    assert "id" in data


async def test_list_leads(
    client: AsyncClient, sample_lead: dict,
) -> None:
    resp = await client.get(_BASE)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["id"] == sample_lead["id"]


async def test_list_leads_filter_by_industry(
    client: AsyncClient, sample_lead: dict,
) -> None:
    resp = await client.get(_BASE, params={"industry": "SaaS"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    resp = await client.get(_BASE, params={"industry": "Healthcare"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


async def test_get_lead(
    client: AsyncClient, sample_lead: dict,
) -> None:
    resp = await client.get(f"{_BASE}/{sample_lead['id']}")
    assert resp.status_code == 200
    assert resp.json()["email"] == "jane@example.com"


async def test_get_lead_not_found(client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"{_BASE}/{fake_id}")
    assert resp.status_code == 404


async def test_delete_lead(
    client: AsyncClient, sample_lead: dict,
) -> None:
    resp = await client.delete(f"{_BASE}/{sample_lead['id']}")
    assert resp.status_code == 204

    resp = await client.get(f"{_BASE}/{sample_lead['id']}")
    assert resp.status_code == 404


# ── Enrichment ───────────────────────────────────────────────


async def test_enrich_lead(
    client: AsyncClient, sample_lead: dict, sample_icp: dict,
) -> None:
    resp = await client.post(f"{_BASE}/{sample_lead['id']}/enrich")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enrichment_status"] == "COMPLETE"
    assert data["enriched_data"] is not None
    assert "email_finder" in data["enriched_data"]
    assert "linkedin" in data["enriched_data"]
    assert "company" in data["enriched_data"]
    assert len(data["enrichment_sources"]) >= 3
    assert data["icp_score"] is not None
    assert data["icp_score"] > 0


async def test_enrich_lead_not_found(client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.post(f"{_BASE}/{fake_id}/enrich")
    assert resp.status_code == 404


# ── Outreach history ─────────────────────────────────────────


async def test_outreach_history_empty(
    client: AsyncClient, sample_lead: dict,
) -> None:
    resp = await client.get(f"{_BASE}/{sample_lead['id']}/outreach")
    assert resp.status_code == 200
    assert resp.json() == []


# ── CSV Import ───────────────────────────────────────────────


async def test_csv_import(client: AsyncClient) -> None:
    csv_content = (
        "first_name,last_name,email,company_name,title\n"
        "Alice,Chen,alice@dataforge.ai,DataForge,CEO\n"
        "Bob,Smith,bob@shipfast.dev,ShipFast,CTO\n"
    )
    files = {
        "file": ("leads.csv", io.BytesIO(csv_content.encode()), "text/csv"),
    }
    resp = await client.post(f"{_BASE}/import/csv", files=files)
    assert resp.status_code == 201
    data = resp.json()
    assert data["imported"] == 2
    assert data["errors"] == []


async def test_csv_import_with_errors(client: AsyncClient) -> None:
    csv_content = (
        "first_name,last_name,email,company_name\n"
        ",,,,\n"  # Missing required fields
        "Valid,Lead,valid@test.com,ValidCo\n"
    )
    files = {
        "file": ("leads.csv", io.BytesIO(csv_content.encode()), "text/csv"),
    }
    resp = await client.post(f"{_BASE}/import/csv", files=files)
    assert resp.status_code == 201
    data = resp.json()
    assert data["imported"] == 1
    assert len(data["errors"]) == 1


async def test_csv_import_non_csv(client: AsyncClient) -> None:
    files = {
        "file": ("data.txt", io.BytesIO(b"not csv"), "text/plain"),
    }
    resp = await client.post(f"{_BASE}/import/csv", files=files)
    assert resp.status_code == 400


# ── YC Import ────────────────────────────────────────────────


async def test_yc_import(client: AsyncClient) -> None:
    resp = await client.post(
        f"{_BASE}/import/yc",
        json={"batch": "W25", "limit": 3},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["imported"] == 3
    assert len(data["leads"]) == 3
    assert data["leads"][0]["source"] == "YC_SCRAPER"


# ── Semantic search & similarity ─────────────────────────────


async def test_semantic_search(
    client: AsyncClient, sample_lead: dict, sample_icp: dict,
) -> None:
    # First enrich so the lead gets an embedding
    await client.post(f"{_BASE}/{sample_lead['id']}/enrich")

    resp = await client.get(f"{_BASE}/search", params={"q": "SaaS engineer"})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert "similarity" in results[0]
    assert results[0]["similarity"] > 0


async def test_similar_leads(
    client: AsyncClient, sample_icp: dict,
) -> None:
    # Create and enrich two leads
    lead1 = await client.post(
        _BASE,
        json={
            "first_name": "A",
            "company_name": "Co1",
            "industry": "SaaS",
            "company_size": 100,
        },
    )
    lead2 = await client.post(
        _BASE,
        json={
            "first_name": "B",
            "company_name": "Co2",
            "industry": "SaaS",
            "company_size": 120,
        },
    )
    lid1 = lead1.json()["id"]
    lid2 = lead2.json()["id"]

    await client.post(f"{_BASE}/{lid1}/enrich")
    await client.post(f"{_BASE}/{lid2}/enrich")

    resp = await client.get(f"{_BASE}/{lid1}/similar")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1


async def test_similar_leads_no_embedding(
    client: AsyncClient, sample_lead: dict,
) -> None:
    # Lead without enrichment has no embedding → empty result
    resp = await client.get(f"{_BASE}/{sample_lead['id']}/similar")
    assert resp.status_code == 200
    assert resp.json() == []


# ── Background enrichment ──────────────────────────────────────


async def test_enrich_lead_background_unavailable(
    client: AsyncClient, sample_lead: dict,
) -> None:
    """background=true with no Redis should return 503."""
    with patch(
        "arq.create_pool", side_effect=ConnectionError("no redis"),
    ):
        resp = await client.post(
            f"{_BASE}/{sample_lead['id']}/enrich",
            params={"background": "true"},
        )
    assert resp.status_code == 503


# ── CSV size limit ─────────────────────────────────────────────


async def test_csv_import_too_large(client: AsyncClient) -> None:
    """CSV exceeding 10 MB limit should return 413."""
    header = b"first_name,email,company_name\n"
    row = b"A,a@b.com,C\n"
    content = header + row * (10 * 1024 * 1024 // len(row) + 1)
    files = {
        "file": ("big.csv", io.BytesIO(content), "text/csv"),
    }
    resp = await client.post(f"{_BASE}/import/csv", files=files)
    assert resp.status_code == 413
