"""Phase 4 LangGraph personalization tests."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.personalization_graph import NEGATIVE_KEYWORDS
from app.models.lead import Lead
from app.models.sender import SenderProfile
from app.models.signal import Signal
from app.services.personalization import generate_draft


async def test_generate_draft_runs_langgraph_quality_contract(
    _db_session: AsyncSession,
) -> None:
    sender = SenderProfile(
        user_id="phase4",
        name="Avery Chen",
        education=["MIT"],
        past_employers=["Stripe"],
    )
    lead = Lead(
        first_name="Maya",
        email="maya@example.com",
        company_name="GrowthLoop",
        company_domain="growthloop.io",
        title="VP Sales",
        industry="SaaS",
        enriched_data={
            "linkedin": {
                "education": [{"university": "MIT"}],
                "past_companies": [],
            },
        },
    )
    _db_session.add_all([sender, lead])
    await _db_session.flush()
    signal = Signal(
        lead_id=lead.id,
        company_domain=lead.company_domain,
        signal_type="FUNDING_ROUND",
        signal_title="GrowthLoop raised a Series A",
        signal_body="Funding round detected.",
        signal_strength=0.9,
        signal_hash="phase4-signal",
    )
    _db_session.add(signal)
    await _db_session.flush()

    draft = await generate_draft(_db_session, lead, signal_id=signal.id)

    assert draft.personalization_hook is not None
    assert draft.hook_type == "commonality"
    assert draft.signal_used == "FUNDING_ROUND"
    assert draft.critique_score is not None
    assert draft.critique_score >= 7.0
    assert set(draft.critique_breakdown or {}) == {
        "specificity",
        "relevance",
        "tone",
        "cta_clarity",
        "subject_line",
    }
    body = (draft.email_body or "").lower()
    assert all(keyword not in body for keyword in NEGATIVE_KEYWORDS)
    assert (draft.token_usage or {}).get("provider") == "mock-langgraph"


async def test_approved_draft_cannot_be_patched(client) -> None:
    lead_resp = await client.post(
        "/api/v1/leads",
        json={
            "first_name": "Tara",
            "email": "tara@example.com",
            "company_name": "Patch Guard",
        },
    )
    assert lead_resp.status_code == 201
    draft_resp = await client.post(
        "/api/v1/personalization/generate",
        json={"lead_id": lead_resp.json()["id"]},
    )
    assert draft_resp.status_code == 201
    draft_id = draft_resp.json()["id"]

    approve_resp = await client.post(
        f"/api/v1/personalization/drafts/{draft_id}/approve",
        json={},
    )
    assert approve_resp.status_code == 200

    patch_resp = await client.patch(
        f"/api/v1/personalization/drafts/{draft_id}",
        json={"subject_line": "Should not change"},
    )
    assert patch_resp.status_code == 409


async def test_path_personalize_alias_persists_draft(client) -> None:
    lead_resp = await client.post(
        "/api/v1/leads",
        json={
            "first_name": "Persist",
            "email": "persist@example.com",
            "company_name": "PersistCo",
        },
    )
    assert lead_resp.status_code == 201
    lead_id = lead_resp.json()["id"]

    draft_resp = await client.post(
        f"/api/v1/personalize/{lead_id}",
        json={},
    )
    assert draft_resp.status_code == 201
    draft_id = draft_resp.json()["id"]

    list_resp = await client.get(
        f"/api/v1/personalize/{lead_id}/drafts",
    )
    assert list_resp.status_code == 200
    assert any(item["id"] == draft_id for item in list_resp.json())
