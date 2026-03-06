"""Lead enrichment pipeline — 6-step process.

Each step populates a portion of the lead's ``enriched_data`` JSONB.
When ``USE_MOCK_ENRICHMENT=true`` (default), all external API calls
return deterministic fixture data so the system runs without keys.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, NoReturn

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.enums import EnrichmentStatus
from app.models.lead import Lead

logger = logging.getLogger(__name__)


class RealIntegrationNotImplementedError(RuntimeError):
    """Raised when real enrichment is requested but not implemented."""


def _require_real_integration(step_name: str) -> NoReturn:
    """Fail fast instead of silently falling back to mock data."""
    raise RealIntegrationNotImplementedError(
        f"{step_name} integration is not implemented. "
        "Keep USE_MOCK_ENRICHMENT=true until the real provider is wired.",
    )


# ── Mock fixtures ────────────────────────────────────────────


def _mock_email(lead: Lead) -> dict[str, Any]:
    domain = lead.company_domain or "example.com"
    first = (lead.first_name or "contact").lower()
    return {"email": f"{first}@{domain}", "confidence": 95}


def _mock_linkedin(lead: Lead) -> dict[str, Any]:
    return {
        "current_role": lead.title or "Software Engineer",
        "tenure_months": 18,
        "past_companies": ["Acme Corp", "Globex Inc"],
        "education": [
            {
                "university": "MIT",
                "degree": "BS Computer Science",
                "year": 2018,
            },
        ],
        "skills": ["Python", "Machine Learning", "Leadership"],
        "recent_posts": [
            "Excited to announce our Series B!",
            "Great insights at SaaStr Annual.",
        ],
    }


def _mock_company(lead: Lead) -> dict[str, Any]:
    return {
        "headcount": lead.company_size or 150,
        "headcount_growth_3m": 0.12,
        "funding_rounds": [
            {
                "round": lead.funding_stage or "Series A",
                "amount_usd": lead.total_funding_usd or 5_000_000,
                "date": "2025-06-15",
                "investors": ["Sequoia", "a16z"],
            },
        ],
        "tech_stack": lead.tech_stack or ["React", "Node.js", "AWS"],
        "news_mentions": [
            "Company featured in TechCrunch for AI innovation.",
        ],
    }


def _mock_github(lead: Lead) -> dict[str, Any]:
    return {
        "repos": 12,
        "primary_languages": ["Python", "TypeScript"],
        "recent_commits": 45,
        "building_story": (
            "Active open-source contributor focused on ML tooling. "
            "Maintains 3 popular Python libraries."
        ),
    }


# ── Enrichment steps ────────────────────────────────────────


async def step_email_finder(
    lead: Lead,
    enriched: dict[str, Any],
) -> dict[str, Any]:
    """Step 1: Find work email from name + domain."""
    if settings.USE_MOCK_ENRICHMENT:
        result = _mock_email(lead)
    else:
        _require_real_integration("Hunter.io email finder")

    enriched["email_finder"] = result
    if not lead.email and result.get("email"):
        enriched["_set_email"] = result["email"]
    return enriched


async def step_linkedin_enrichment(
    lead: Lead,
    enriched: dict[str, Any],
) -> dict[str, Any]:
    """Step 2: Enrich from LinkedIn via Proxycurl."""
    if settings.USE_MOCK_ENRICHMENT:
        result = _mock_linkedin(lead)
    else:
        _require_real_integration("Proxycurl LinkedIn enrichment")

    enriched["linkedin"] = result
    return enriched


async def step_company_enrichment(
    lead: Lead,
    enriched: dict[str, Any],
) -> dict[str, Any]:
    """Step 3: Enrich company data via Clearbit/BuiltWith."""
    if settings.USE_MOCK_ENRICHMENT:
        result = _mock_company(lead)
    else:
        _require_real_integration("Clearbit/BuiltWith company enrichment")

    enriched["company"] = result
    return enriched


async def step_github_enrichment(
    lead: Lead,
    enriched: dict[str, Any],
) -> dict[str, Any]:
    """Step 4: Enrich from GitHub (only if github_url present)."""
    if not lead.github_url:
        return enriched

    if settings.USE_MOCK_ENRICHMENT:
        result = _mock_github(lead)
    else:
        _require_real_integration("GitHub enrichment")

    enriched["github"] = result
    return enriched


def build_embedding_text(lead: Lead, enriched: dict[str, Any]) -> str:
    """Step 5a: Build structured text blob for embedding generation."""
    parts: list[str] = []

    name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()
    if name:
        parts.append(f"{name} is {lead.title or 'professional'}")
    if lead.company_name:
        parts.append(f"at {lead.company_name}")

    tech = enriched.get("company", {}).get("tech_stack", lead.tech_stack)
    if tech:
        parts.append(f"Company uses {', '.join(tech[:10])}")

    linkedin = enriched.get("linkedin", {})
    posts = linkedin.get("recent_posts", [])
    if posts:
        parts.append(f"They recently posted: {posts[0]}")

    funding = enriched.get("company", {}).get("funding_rounds", [])
    if funding:
        latest = funding[0]
        parts.append(
            f"Company raised {latest.get('round', 'funding')} "
            f"in {lead.industry or 'technology'}",
        )

    education = linkedin.get("education", [])
    if education:
        edu = education[0]
        parts.append(
            f"Education: {edu.get('degree', '')} "
            f"from {edu.get('university', '')}",
        )

    github = enriched.get("github", {})
    story = github.get("building_story")
    if story:
        parts.append(f"GitHub: {story}")

    return ". ".join(parts)


async def step_embedding_generation(
    lead: Lead,
    enriched: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    """Step 5: Generate embedding and store in pgvector column."""
    text = build_embedding_text(lead, enriched)
    enriched["_embedding_text"] = text

    # Generate embedding (mock: deterministic hash-based vector)
    if settings.USE_MOCK_ENRICHMENT:
        from app.embeddings import generate_mock_embedding

        enriched["_embedding"] = generate_mock_embedding(text)
    else:
        _require_real_integration("Embedding provider")

    return enriched


# ── Main pipeline ────────────────────────────────────────────


async def run_enrichment_pipeline(
    lead_id: str,
    db: AsyncSession,
) -> None:
    """Execute the full 6-step enrichment pipeline for a lead."""
    from app.services.icp_scorer import score_lead_against_all_icps

    lead = await db.get(Lead, lead_id)
    if lead is None:
        logger.warning("Lead %s not found, skipping enrichment", lead_id)
        return

    # Mark as running
    lead.enrichment_status = EnrichmentStatus.RUNNING
    await db.flush()

    enriched: dict[str, Any] = dict(lead.enriched_data or {})
    sources: list[str] = []

    try:
        # Steps 1-4: Data enrichment
        enriched = await step_email_finder(lead, enriched)
        sources.append("hunter")

        enriched = await step_linkedin_enrichment(lead, enriched)
        sources.append("proxycurl")

        enriched = await step_company_enrichment(lead, enriched)
        sources.extend(["clearbit", "builtwith"])

        enriched = await step_github_enrichment(lead, enriched)
        if lead.github_url:
            sources.append("github")

        # Apply discovered email
        if enriched.pop("_set_email", None) and not lead.email:
            lead.email = enriched["email_finder"]["email"]

        # Step 5: Embedding
        enriched = await step_embedding_generation(lead, enriched, db)
        embedding = enriched.pop("_embedding", None)
        enriched.pop("_embedding_text", None)

        if embedding is not None:
            lead.embedding = embedding

        # Persist enrichment data
        lead.enriched_data = enriched
        lead.enrichment_sources = sources
        lead.enrichment_at = datetime.now(timezone.utc)

        # Step 6: ICP scoring
        await score_lead_against_all_icps(lead, db)

        lead.enrichment_status = EnrichmentStatus.COMPLETE
        lead.updated_at = datetime.now(timezone.utc)

    except Exception:
        logger.exception("Enrichment failed for lead %s", lead_id)
        lead.enrichment_status = EnrichmentStatus.FAILED
        lead.updated_at = datetime.now(timezone.utc)
        raise
    finally:
        await db.flush()
