"""Personalization draft services backed by the executable LangGraph graph."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.personalization_graph import (
    seed_winning_snippets,
    run_personalization_graph,
)
from app.models.draft import PersonalizationDraft
from app.models.enums import DraftStatus, EnrollmentStatus
from app.models.lead import Lead
from app.models.sequence import LeadSequenceEnrollment
from app.services.event_bus import publish_event

logger = logging.getLogger(__name__)


async def generate_draft(
    db: AsyncSession,
    lead: Lead,
    sequence_id: uuid.UUID | None = None,
    sequence_step_id: uuid.UUID | None = None,
    enrollment_id: uuid.UUID | None = None,
    signal_id: uuid.UUID | None = None,
) -> PersonalizationDraft:
    """Generate and persist a deterministic personalized draft."""
    state = await run_personalization_graph(db=db, lead=lead, signal_id=signal_id)
    output = state["draft_output"]
    commonality = state["commonality"]
    signal = state.get("selected_signal")
    sender = state.get("sender")

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
        critique_score=state["critique_score"],
        critique_breakdown=state["critique_breakdown"],
        generation_iterations=state.get("iterations", 1),
        token_usage={
            "prompt_tokens": 350,
            "completion_tokens": len(output["email_body"].split()),
            "provider": "mock-langgraph",
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
