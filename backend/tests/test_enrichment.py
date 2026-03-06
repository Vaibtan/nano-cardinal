"""Unit tests for enrichment step functions (mock mode)."""

import pytest

from app.config import settings
from app.models.lead import Lead
from app.services.enrichment import (
    RealIntegrationNotImplementedError,
    build_embedding_text,
    step_company_enrichment,
    step_email_finder,
    step_embedding_generation,
    step_github_enrichment,
    step_linkedin_enrichment,
)
from app.services.icp_scorer import compute_icp_score


# ── Enrichment step tests ────────────────────────────────────


async def test_step_email_finder() -> None:
    lead = Lead(
        first_name="Alice",
        last_name="Chen",
        company_domain="dataforge.ai",
    )
    result = await step_email_finder(lead, {})
    assert "email_finder" in result
    assert result["email_finder"]["email"] == "alice@dataforge.ai"
    assert result["email_finder"]["confidence"] == 95


async def test_step_linkedin_enrichment() -> None:
    lead = Lead(title="CTO")
    result = await step_linkedin_enrichment(lead, {})
    assert "linkedin" in result
    assert "current_role" in result["linkedin"]
    assert "education" in result["linkedin"]


async def test_step_company_enrichment() -> None:
    lead = Lead(company_size=200, industry="SaaS")
    result = await step_company_enrichment(lead, {})
    assert "company" in result
    assert "headcount" in result["company"]
    assert "funding_rounds" in result["company"]


async def test_step_github_enrichment_with_url() -> None:
    lead = Lead(github_url="https://github.com/alice")
    result = await step_github_enrichment(lead, {})
    assert "github" in result
    assert "building_story" in result["github"]


async def test_step_github_enrichment_without_url() -> None:
    lead = Lead()
    result = await step_github_enrichment(lead, {})
    assert "github" not in result


async def test_real_mode_fails_fast_in_enrichment_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "USE_MOCK_ENRICHMENT", False)
    lead = Lead(
        first_name="Alice",
        company_domain="example.com",
        github_url="https://github.com/alice",
    )

    with pytest.raises(RealIntegrationNotImplementedError):
        await step_email_finder(lead, {})

    with pytest.raises(RealIntegrationNotImplementedError):
        await step_linkedin_enrichment(lead, {})

    with pytest.raises(RealIntegrationNotImplementedError):
        await step_company_enrichment(lead, {})

    with pytest.raises(RealIntegrationNotImplementedError):
        await step_github_enrichment(lead, {})

    with pytest.raises(RealIntegrationNotImplementedError):
        await step_embedding_generation(lead, {}, db=None)


# ── Embedding text builder ───────────────────────────────────


async def test_build_embedding_text() -> None:
    lead = Lead(
        first_name="Jane",
        last_name="Doe",
        title="VP Engineering",
        company_name="Acme",
        industry="SaaS",
        tech_stack=["Python", "React"],
    )
    enriched = {
        "linkedin": {
            "recent_posts": ["Excited about AI"],
            "education": [
                {"degree": "BS CS", "university": "MIT"},
            ],
        },
        "company": {
            "tech_stack": ["Python", "React"],
            "funding_rounds": [{"round": "Series A"}],
        },
    }
    text = build_embedding_text(lead, enriched)
    assert "Jane Doe" in text
    assert "VP Engineering" in text
    assert "Acme" in text
    assert "Python" in text


# ── ICP scoring tests ────────────────────────────────────────


async def test_icp_score_exact_match() -> None:
    lead = Lead(
        industry="SaaS",
        company_size=100,
        title="VP Engineering",
        tech_stack=["Python"],
    )
    config = {
        "industries": ["SaaS"],
        "company_sizes": ["50-200"],
        "titles": ["VP Engineering"],
        "tech_stack": ["Python"],
    }
    weights = {
        "industry": 2.0,
        "company_size": 1.5,
        "title": 1.0,
        "tech_stack": 1.0,
    }
    score, breakdown = compute_icp_score(lead, config, weights)
    assert score > 50.0
    assert breakdown["industry"] == 1.0
    assert breakdown["company_size"] == 1.0
    assert breakdown["title"] == 1.0


async def test_icp_score_no_match() -> None:
    lead = Lead(
        industry="Healthcare",
        company_size=5000,
        title="Nurse",
    )
    config = {
        "industries": ["SaaS"],
        "company_sizes": ["50-200"],
        "titles": ["VP Engineering"],
    }
    weights = {"industry": 1.0, "company_size": 1.0, "title": 1.0}
    score, breakdown = compute_icp_score(lead, config, weights)
    assert score == 0.0
    assert breakdown["industry"] == 0.0


async def test_icp_score_partial_match() -> None:
    lead = Lead(
        industry="SaaS Platform",  # Partial: contains "SaaS"
        company_size=250,  # Close to 50-200 bucket
        title="Director Engineering",
    )
    config = {
        "industries": ["SaaS"],
        "company_sizes": ["50-200"],
        "titles": ["VP Engineering"],
    }
    weights = {"industry": 1.0, "company_size": 1.0, "title": 1.0}
    score, breakdown = compute_icp_score(lead, config, weights)
    assert 0 < score < 100
    assert breakdown["industry"] == 0.5  # Partial match


async def test_icp_score_empty_config() -> None:
    lead = Lead(industry="SaaS")
    score, _ = compute_icp_score(lead, {}, {})
    assert score == 0.0
