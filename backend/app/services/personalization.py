"""Deterministic personalization agent and draft services."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.embeddings import VECTOR_DIMENSION, generate_mock_embedding
from app.models.draft import PersonalizationDraft
from app.models.enums import DraftStatus, EnrollmentStatus, HookType
from app.models.lead import Lead
from app.models.sender import SenderProfile
from app.models.sequence import LeadSequenceEnrollment
from app.models.signal import Signal
from app.models.snippet import WinningSnippet
from app.services.event_bus import publish_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommonalityResult:
    """Strongest sender/lead commonality."""

    strongest_hook: str | None
    hook_type: str
    hook_strength: float


async def seed_winning_snippets(db: AsyncSession) -> int:
    """Seed deterministic snippet fixtures if none exist."""
    existing = await db.execute(select(WinningSnippet.id).limit(1))
    if existing.scalar_one_or_none() is not None:
        return 0

    fixtures = [
        (
            "Funding trigger",
            "Congrats on the recent raise. Teams usually revisit "
            "pipeline coverage right after funding closes.",
            "SaaS",
            "Founder",
            "EMAIL",
            0.31,
        ),
        (
            "Hiring trigger",
            "Your open GTM roles suggest demand is outpacing the "
            "current outbound motion.",
            "B2B Software",
            "Revenue",
            "EMAIL",
            0.27,
        ),
        (
            "Technical peer hook",
            "I noticed your team ships with a similar Python and "
            "TypeScript stack, so I kept this concrete.",
            "Developer Tools",
            "Engineering",
            "LINKEDIN_MESSAGE",
            0.24,
        ),
    ]
    for title, body, industry, persona, channel, win_rate in fixtures:
        db.add(
            WinningSnippet(
                title=title,
                body=body,
                industry=industry,
                persona=persona,
                channel=channel,
                win_rate=win_rate,
                embedding=generate_mock_embedding(f"{title}. {body}"),
            ),
        )
    await db.flush()
    return len(fixtures)


async def generate_draft(
    db: AsyncSession,
    lead: Lead,
    sequence_id: uuid.UUID | None = None,
    sequence_step_id: uuid.UUID | None = None,
    enrollment_id: uuid.UUID | None = None,
    signal_id: uuid.UUID | None = None,
) -> PersonalizationDraft:
    """Generate and persist a deterministic personalized draft."""
    sender = await _get_sender(db)
    signal = await _get_signal(db, signal_id, lead)
    commonality = _match_commonality(sender, lead)
    snippets = await _retrieve_snippets(db, lead, signal)
    output = _compose_output(lead, commonality, signal, snippets)
    critique_score, critique = _critique_output(output)
    iterations = 1

    while (
        critique_score < settings.CRITIQUE_REWRITE_THRESHOLD
        and iterations < 3
    ):
        output["email_body"] = (
            f"{output['email_body']}\n\n"
            "To make this concrete, I can share a short account map "
            "for your current ICP."
        )
        critique_score, critique = _critique_output(output)
        iterations += 1

    draft = PersonalizationDraft(
        lead_id=lead.id,
        sender_id=sender.id if sender else None,
        sequence_id=sequence_id,
        sequence_step_id=sequence_step_id,
        enrollment_id=enrollment_id,
        subject_line=output["subject_line"],
        email_body=output["email_body"],
        linkedin_message=output["linkedin_message"],
        personalization_hook=commonality.strongest_hook,
        hook_type=commonality.hook_type,
        hook_strength=commonality.hook_strength,
        signal_used=signal.signal_type if signal else None,
        critique_score=critique_score,
        critique_breakdown=critique,
        generation_iterations=iterations,
        token_usage={
            "prompt_tokens": 350,
            "completion_tokens": len(output["email_body"].split()),
            "provider": "mock",
        },
    )
    db.add(draft)
    await db.flush()
    await publish_event(
        "draft.generated",
        {
            "lead_id": str(lead.id),
            "draft_id": str(draft.id),
            "critique_score": draft.critique_score,
        },
    )
    return draft


async def approve_draft(
    db: AsyncSession,
    draft: PersonalizationDraft,
) -> PersonalizationDraft:
    """Approve a draft and resume linked approval-paused enrollment."""
    draft.status = DraftStatus.APPROVED.value
    draft.approved_at = datetime.now(timezone.utc)
    if draft.enrollment_id:
        enrollment = await db.get(
            LeadSequenceEnrollment,
            draft.enrollment_id,
        )
        if (
            enrollment
            and enrollment.status == EnrollmentStatus.PENDING_APPROVAL.value
        ):
            enrollment.status = EnrollmentStatus.ACTIVE.value
            enrollment.next_step_at = datetime.now(timezone.utc)
    await db.flush()
    return draft


async def _get_sender(db: AsyncSession) -> SenderProfile | None:
    result = await db.execute(select(SenderProfile).limit(1))
    return result.scalars().first()


async def _get_signal(
    db: AsyncSession,
    signal_id: uuid.UUID | None,
    lead: Lead,
) -> Signal | None:
    if signal_id is not None:
        return await db.get(Signal, signal_id)
    result = await db.execute(
        select(Signal)
        .where(Signal.lead_id == lead.id)
        .where(Signal.is_read.is_(False))
        .order_by(Signal.signal_strength.desc().nullslast())
        .limit(1),
    )
    return result.scalars().first()


def _match_commonality(
    sender: SenderProfile | None,
    lead: Lead,
) -> CommonalityResult:
    """Find strict commonality JSON-equivalent from sender profile."""
    if sender is None:
        return CommonalityResult(None, HookType.NONE, 0.0)

    enriched = lead.enriched_data or {}
    linkedin = enriched.get("linkedin", {})
    education = linkedin.get("education", [])
    universities = {
        str(item.get("university")).lower()
        for item in education
        if item.get("university")
    }
    sender_education = {item.lower() for item in sender.education or []}
    overlap = universities & sender_education
    if overlap:
        school = sorted(overlap)[0]
        return CommonalityResult(
            f"We both have a connection to {school.title()}.",
            HookType.COMMONALITY,
            0.92,
        )

    sender_employers = {item.lower() for item in sender.past_employers or []}
    past_companies = {
        str(item).lower()
        for item in linkedin.get("past_companies", [])
    }
    overlap = sender_employers & past_companies
    if overlap:
        company = sorted(overlap)[0]
        return CommonalityResult(
            f"We have both crossed paths with {company.title()}.",
            HookType.COMMONALITY,
            0.86,
        )

    return CommonalityResult(None, HookType.NONE, 0.0)


async def _retrieve_snippets(
    db: AsyncSession,
    lead: Lead,
    signal: Signal | None,
) -> list[WinningSnippet]:
    await seed_winning_snippets(db)
    query_text = " ".join(
        [
            lead.industry or "",
            lead.title or "",
            signal.signal_title if signal else "",
        ],
    )
    embedding_param = bindparam(
        "query_embedding",
        value=generate_mock_embedding(query_text),
        type_=Vector(VECTOR_DIMENSION),
    )
    result = await db.execute(
        select(WinningSnippet)
        .where(WinningSnippet.embedding.isnot(None))
        .order_by(
            WinningSnippet.embedding.cosine_distance(embedding_param),
        )
        .limit(2),
    )
    return list(result.scalars().all())


def _compose_output(
    lead: Lead,
    commonality: CommonalityResult,
    signal: Signal | None,
    snippets: list[WinningSnippet],
) -> dict[str, str]:
    name = lead.first_name or "there"
    company = lead.company_name or lead.company_domain or "your team"
    hook = commonality.strongest_hook
    if hook is None and signal is not None:
        hook = signal.signal_title
    if hook is None:
        hook = f"I was looking at {company}'s current GTM motion"

    snippet = snippets[0].body if snippets else (
        "Teams usually benefit from a tighter account-priority loop "
        "when buying signals start moving."
    )
    email_body = (
        f"Hi {name},\n\n"
        f"{hook}\n\n"
        f"{snippet}\n\n"
        "Orion helps surface the right accounts, explain why now, "
        "and draft outreach grounded in the signal behind the account.\n\n"
        "Worth comparing notes for 15 minutes?"
    )
    linkedin_message = (
        f"Hi {name}, noticed {hook.lower()} Orion helps teams turn "
        "that kind of account signal into precise outbound."
    )
    return {
        "subject_line": f"Signal around {company}",
        "email_body": email_body,
        "linkedin_message": linkedin_message,
    }


def _critique_output(output: dict[str, str]) -> tuple[float, dict[str, float]]:
    body = output["email_body"]
    length_score = 2.0 if 60 <= len(body.split()) <= 150 else 1.2
    specificity = 2.5 if "signal" in body.lower() else 1.5
    clarity = 2.0 if "15 minutes" in body else 1.0
    brevity = 1.5 if len(body) < 900 else 0.8
    total = round(length_score + specificity + clarity + brevity, 2)
    return min(total, 10.0), {
        "length": length_score,
        "specificity": specificity,
        "clarity": clarity,
        "brevity": brevity,
    }
