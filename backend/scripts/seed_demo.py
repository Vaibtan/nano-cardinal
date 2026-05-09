"""Seed a reproducible demo dataset.

Run from ``backend`` after migrations:

    uv run python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.icp import ICP
from app.models.lead import Lead
from app.models.sender import SenderProfile
from app.models.sequence import Sequence
from app.schemas.sequence import SequenceCreate, SequenceStepCreate
from app.services.enrichment import run_enrichment_pipeline
from app.services.inbound import process_inbound_payload
from app.services.personalization import generate_draft, seed_winning_snippets
from app.services.sequences import (
    create_sequence,
    enroll_lead,
    execute_due_enrollments,
)
from app.services.signals import run_mock_signal_scan


async def main() -> None:
    """Seed demo data idempotently."""
    async with async_session_factory() as db:
        sender = await _ensure_sender(db)
        icp = await _ensure_icp(db)
        leads = await _ensure_leads(db)
        await db.flush()

        for lead in leads:
            await run_enrichment_pipeline(str(lead.id), db)

        await run_mock_signal_scan(db)
        await seed_winning_snippets(db)
        sequence = await _ensure_sequence(db, icp)
        await _ensure_inbound_events(db)
        await enroll_lead(db, sequence, leads[0])
        await generate_draft(db, leads[0])
        await execute_due_enrollments(db)

        await db.commit()
        print(
            "Seeded demo data: "
            f"sender={sender.id}, icp={icp.id}, leads={len(leads)}",
        )


async def _ensure_sender(db) -> SenderProfile:
    result = await db.execute(
        select(SenderProfile).where(SenderProfile.user_id == "demo"),
    )
    sender = result.scalars().first()
    if sender:
        return sender
    sender = SenderProfile(
        user_id="demo",
        name="Avery Chen",
        current_title="Founder",
        current_company="Orion",
        education=["MIT", "Stanford"],
        past_employers=["Stripe", "Acme Corp"],
        cities_lived=["San Francisco", "Bangalore"],
        hobbies_and_interests=["developer tools", "trail running"],
        investors=["Sequoia", "a16z"],
        languages_spoken=["English"],
        conferences_attended=["SaaStr Annual", "YC Demo Day"],
    )
    db.add(sender)
    return sender


async def _ensure_icp(db) -> ICP:
    result = await db.execute(select(ICP).where(ICP.name == "Demo SaaS ICP"))
    icp = result.scalars().first()
    if icp:
        return icp
    icp = ICP(
        name="Demo SaaS ICP",
        description="High-growth B2B SaaS companies with active GTM motion.",
        config={
            "industries": ["SaaS", "B2B Software", "Developer Tools"],
            "company_sizes": ["50-200", "201-500", "501-1000"],
            "funding_stages": ["Series A", "Series B"],
            "titles": ["VP Sales", "Founder", "Head of Growth"],
            "seniorities": ["VP", "Founder", "Head"],
            "departments": ["Sales", "Growth", "Revenue"],
            "tech_stack": ["React", "Python", "AWS"],
            "selected_signal_types": [
                "FUNDING_ROUND",
                "HIRING_SURGE",
                "PRODUCT_SIGNUP",
            ],
            "signal_recency_days": 30,
            "min_signal_strength": 0.7,
            "signal_keywords": ["funding", "hiring", "pipeline"],
        },
        weights={
            "industry": 0.18,
            "company_size": 0.15,
            "funding_stage": 0.14,
            "title": 0.18,
            "seniority": 0.12,
            "department": 0.12,
            "tech_stack": 0.08,
            "region": 0.03,
        },
        is_active=True,
    )
    db.add(icp)
    return icp


async def _ensure_leads(db) -> list[Lead]:
    result = await db.execute(
        select(Lead).where(Lead.company_domain.in_(_DEMO_DOMAINS)),
    )
    existing = {lead.company_domain: lead for lead in result.scalars().all()}
    leads: list[Lead] = []
    for row in _DEMO_LEADS:
        lead = existing.get(row["company_domain"])
        if lead is None:
            lead = Lead(**row)
            db.add(lead)
        leads.append(lead)
    return leads


async def _ensure_sequence(db, icp: ICP) -> Sequence:
    result = await db.execute(
        select(Sequence).where(Sequence.name == "Demo high-intent sequence"),
    )
    sequence = result.scalars().first()
    if sequence:
        return sequence
    body = SequenceCreate(
        name="Demo high-intent sequence",
        icp_id=icp.id,
        is_active=True,
        auto_enroll=True,
        auto_enroll_threshold=70,
        steps=[
            SequenceStepCreate(
                step_number=1,
                channel="EMAIL",
                delay_days=0,
                requires_approval=False,
            ),
            SequenceStepCreate(
                step_number=2,
                step_type="ENGAGEMENT",
                channel="LINKEDIN_ENGAGE",
                delay_days=2,
                engagement_action="VIEW_PROFILE",
            ),
        ],
    )
    return await create_sequence(db, body)


async def _ensure_inbound_events(db) -> None:
    """Seed inbound events for analytics and auto-enroll demos."""
    payloads = [
        (
            "manual",
            {
                "id": "demo-inbound-001",
                "event_type": "PRODUCT_SIGNUP",
                "email": "priya@intentcloud.io",
                "first_name": "Priya",
                "last_name": "Menon",
                "company_name": "IntentCloud",
                "company_domain": "intentcloud.io",
            },
        ),
        (
            "google_ads",
            {
                "conversion_action": "demo-request",
                "gclid": "demo-gclid-001",
                "user_data": {
                    "email": "alex@pipelinepilot.ai",
                    "first_name": "Alex",
                    "last_name": "Morgan",
                },
                "company_name": "PipelinePilot",
                "company_domain": "pipelinepilot.ai",
            },
        ),
    ]
    for source, payload in payloads:
        await process_inbound_payload(db, source, payload)


_DEMO_LEADS = [
    {
        "first_name": "Maya",
        "last_name": "Rao",
        "email": "maya@growthloop.io",
        "company_name": "GrowthLoop",
        "company_domain": "growthloop.io",
        "company_size": 180,
        "industry": "SaaS",
        "funding_stage": "Series A",
        "title": "VP Sales",
        "seniority": "VP",
        "department": "Sales",
        "tech_stack": ["React", "Python", "AWS"],
    },
    {
        "first_name": "Noah",
        "last_name": "Kim",
        "email": "noah@devsignal.ai",
        "company_name": "DevSignal",
        "company_domain": "devsignal.ai",
        "company_size": 320,
        "industry": "Developer Tools",
        "funding_stage": "Series B",
        "title": "Founder",
        "seniority": "Founder",
        "department": "Growth",
        "tech_stack": ["TypeScript", "Python", "GCP"],
    },
    {
        "first_name": "Elena",
        "last_name": "Park",
        "email": "elena@reply.test",
        "company_name": "ReplyPath",
        "company_domain": "replypath.com",
        "company_size": 90,
        "industry": "B2B Software",
        "funding_stage": "Series A",
        "title": "Head of Growth",
        "seniority": "Head",
        "department": "Revenue",
        "tech_stack": ["React", "Node.js", "AWS"],
    },
    {
        "first_name": "Ben",
        "last_name": "Stone",
        "email": "ben@bounce.test",
        "company_name": "BounceWorks",
        "company_domain": "bounceworks.com",
        "company_size": 70,
        "industry": "SaaS",
        "funding_stage": "Seed",
        "title": "Founder",
        "seniority": "Founder",
        "department": "Sales",
        "tech_stack": ["Vue", "Python", "AWS"],
    },
]

_DEMO_DOMAINS = [row["company_domain"] for row in _DEMO_LEADS]


if __name__ == "__main__":
    asyncio.run(main())
