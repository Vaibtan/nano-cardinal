"""Sequence management and execution state machine."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.draft import PersonalizationDraft
from app.models.enums import (
    Channel,
    DeliveryStatus,
    DraftStatus,
    EnrollmentStatus,
    OutreachStatus,
    PausedReason,
    StepType,
)
from app.models.lead import Lead
from app.models.outreach import OutreachLog
from app.models.sequence import (
    LeadSequenceEnrollment,
    Sequence,
    SequenceStep,
)
from app.schemas.sequence import SequenceCreate, SequenceUpdate
from app.services.event_bus import publish_event
from app.services.personalization import generate_draft

_TERMINAL_STATUSES = {
    EnrollmentStatus.BOUNCED.value,
    EnrollmentStatus.REPLIED.value,
    EnrollmentStatus.UNSUBSCRIBED.value,
    EnrollmentStatus.COMPLETED.value,
}


async def create_sequence(
    db: AsyncSession,
    body: SequenceCreate,
) -> Sequence:
    """Create a sequence and ordered steps."""
    sequence = Sequence(
        name=body.name,
        icp_id=body.icp_id,
        is_active=body.is_active,
        auto_enroll=body.auto_enroll,
        auto_enroll_threshold=body.auto_enroll_threshold,
    )
    db.add(sequence)
    await db.flush()
    for step in body.steps:
        db.add(SequenceStep(sequence_id=sequence.id, **step.model_dump()))
    await db.flush()
    return await _load_sequence(db, sequence.id)


async def update_sequence(
    db: AsyncSession,
    sequence: Sequence,
    body: SequenceUpdate,
) -> Sequence:
    """Update sequence metadata, steps, and active-state effects."""
    was_active = sequence.is_active
    data = body.model_dump(exclude_unset=True)
    steps = data.pop("steps", None)
    for key, value in data.items():
        setattr(sequence, key, value)

    if steps is not None:
        await db.execute(
            delete(SequenceStep).where(
                SequenceStep.sequence_id == sequence.id,
            ),
        )
        await db.flush()
        for step in steps:
            step_data = (
                step.model_dump()
                if hasattr(step, "model_dump")
                else dict(step)
            )
            db.add(SequenceStep(sequence_id=sequence.id, **step_data))

    if was_active and sequence.is_active is False:
        await pause_sequence_enrollments(db, sequence.id)
    elif not was_active and sequence.is_active is True:
        await resume_sequence_enrollments(db, sequence.id)

    await db.flush()
    return await _load_sequence(db, sequence.id)


async def pause_sequence_enrollments(
    db: AsyncSession,
    sequence_id: uuid.UUID,
) -> None:
    """Pause active enrollments because their sequence was disabled."""
    result = await db.execute(
        select(LeadSequenceEnrollment)
        .where(LeadSequenceEnrollment.sequence_id == sequence_id)
        .where(LeadSequenceEnrollment.status == EnrollmentStatus.ACTIVE.value),
    )
    now = datetime.now(timezone.utc)
    for enrollment in result.scalars().all():
        enrollment.status = EnrollmentStatus.PAUSED.value
        enrollment.paused_reason = PausedReason.SEQUENCE_DEACTIVATED.value
        enrollment.paused_at = now


async def resume_sequence_enrollments(
    db: AsyncSession,
    sequence_id: uuid.UUID,
) -> None:
    """Resume only rows paused by sequence deactivation."""
    result = await db.execute(
        select(LeadSequenceEnrollment)
        .where(LeadSequenceEnrollment.sequence_id == sequence_id)
        .where(LeadSequenceEnrollment.status == EnrollmentStatus.PAUSED.value)
        .where(
            LeadSequenceEnrollment.paused_reason
            == PausedReason.SEQUENCE_DEACTIVATED.value
        ),
    )
    now = datetime.now(timezone.utc)
    for enrollment in result.scalars().all():
        if enrollment.status in _TERMINAL_STATUSES:
            continue
        enrollment.status = EnrollmentStatus.ACTIVE.value
        enrollment.paused_reason = None
        enrollment.paused_at = None
        enrollment.next_step_at = now


async def enroll_lead(
    db: AsyncSession,
    sequence: Sequence,
    lead: Lead,
) -> LeadSequenceEnrollment:
    """Enroll a lead into a sequence idempotently."""
    result = await db.execute(
        select(LeadSequenceEnrollment)
        .where(LeadSequenceEnrollment.sequence_id == sequence.id)
        .where(LeadSequenceEnrollment.lead_id == lead.id),
    )
    existing = result.scalars().first()
    if existing is not None:
        return existing

    enrollment = LeadSequenceEnrollment(
        lead_id=lead.id,
        sequence_id=sequence.id,
        current_step=1,
        status=EnrollmentStatus.ACTIVE.value,
        next_step_at=datetime.now(timezone.utc),
    )
    lead.outreach_status = OutreachStatus.IN_SEQUENCE.value
    db.add(enrollment)
    await db.flush()
    return enrollment


async def auto_enroll_matching_sequences(
    db: AsyncSession,
    lead: Lead,
) -> list[LeadSequenceEnrollment]:
    """Auto-enroll a lead into active matching sequences."""
    if lead.icp_score is None:
        return []
    result = await db.execute(
        select(Sequence)
        .where(Sequence.is_active.is_(True))
        .where(Sequence.auto_enroll.is_(True)),
    )
    enrollments: list[LeadSequenceEnrollment] = []
    for sequence in result.scalars().all():
        threshold = (
            sequence.auto_enroll_threshold
            if sequence.auto_enroll_threshold is not None
            else settings.AUTO_ENROLL_ICP_THRESHOLD
        )
        if sequence.icp_id is not None and sequence.icp_id != lead.icp_id:
            continue
        if lead.icp_score < threshold:
            continue
        enrollment = await enroll_lead(db, sequence, lead)
        enrollments.append(enrollment)
        await publish_event(
            "inbound.lead.enrolled",
            {
                "lead_id": str(lead.id),
                "sequence_id": str(sequence.id),
                "icp_score": lead.icp_score,
            },
        )
    return enrollments


async def execute_due_enrollments(db: AsyncSession) -> int:
    """Execute due active enrollments once."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(LeadSequenceEnrollment)
        .where(LeadSequenceEnrollment.status == EnrollmentStatus.ACTIVE.value)
        .where(LeadSequenceEnrollment.next_step_at <= now)
        .order_by(LeadSequenceEnrollment.next_step_at)
        .limit(100),
    )
    executed = 0
    for enrollment in result.scalars().all():
        if await execute_enrollment_step(db, enrollment):
            executed += 1
    return executed


async def execute_enrollment_step(
    db: AsyncSession,
    enrollment: LeadSequenceEnrollment,
) -> bool:
    """Execute the current step for one enrollment."""
    lead = await db.get(Lead, enrollment.lead_id)
    if lead is None:
        enrollment.status = EnrollmentStatus.COMPLETED.value
        return False

    step = await _get_current_step(db, enrollment)
    if step is None:
        enrollment.status = EnrollmentStatus.COMPLETED.value
        return False

    draft = await _resolve_draft(db, lead, enrollment, step)
    if step.requires_approval and (
        draft is None or draft.status != DraftStatus.APPROVED.value
    ):
        enrollment.status = EnrollmentStatus.PENDING_APPROVAL.value
        return True

    log = await _write_pending_log(db, lead, enrollment, step, draft)
    outcome = _mock_delivery_outcome(lead, step)
    _apply_delivery_outcome(lead, enrollment, log, draft, outcome)
    if outcome in {
        DeliveryStatus.SENT,
        DeliveryStatus.ENGAGED,
    }:
        await _advance_after_success(db, enrollment, step)

    await publish_event(
        "sequence.step.sent",
        {
            "lead_id": str(lead.id),
            "sequence_id": str(enrollment.sequence_id),
            "step_number": step.step_number,
            "channel": step.channel,
        },
    )
    return True


async def _get_current_step(
    db: AsyncSession,
    enrollment: LeadSequenceEnrollment,
) -> SequenceStep | None:
    result = await db.execute(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == enrollment.sequence_id)
        .where(SequenceStep.step_number == enrollment.current_step),
    )
    return result.scalars().first()


async def _resolve_draft(
    db: AsyncSession,
    lead: Lead,
    enrollment: LeadSequenceEnrollment,
    step: SequenceStep,
) -> PersonalizationDraft | None:
    result = await db.execute(
        select(PersonalizationDraft)
        .where(PersonalizationDraft.enrollment_id == enrollment.id)
        .where(PersonalizationDraft.sequence_step_id == step.id)
        .order_by(PersonalizationDraft.created_at.desc())
        .limit(1),
    )
    draft = result.scalars().first()
    if draft is not None:
        return draft
    if step.use_ai_personalization:
        return await generate_draft(
            db=db,
            lead=lead,
            sequence_id=enrollment.sequence_id,
            sequence_step_id=step.id,
            enrollment_id=enrollment.id,
        )
    return None


async def _write_pending_log(
    db: AsyncSession,
    lead: Lead,
    enrollment: LeadSequenceEnrollment,
    step: SequenceStep,
    draft: PersonalizationDraft | None,
) -> OutreachLog:
    subject = draft.subject_line if draft else None
    if step.step_type == StepType.ENGAGEMENT.value:
        body = None
    elif step.channel == Channel.EMAIL.value:
        body = draft.email_body if draft else step.template
    else:
        body = draft.linkedin_message if draft else step.template

    log = OutreachLog(
        lead_id=lead.id,
        sequence_id=enrollment.sequence_id,
        step_number=step.step_number,
        step_type=step.step_type,
        channel=step.channel,
        subject=subject,
        body=body,
        engagement_action=step.engagement_action,
        draft_id=draft.id if draft else None,
        delivery_status=DeliveryStatus.PENDING.value,
    )
    db.add(log)
    await db.flush()
    return log


def _mock_delivery_outcome(
    lead: Lead,
    step: SequenceStep,
) -> DeliveryStatus:
    if step.channel == Channel.LINKEDIN_ENGAGE.value:
        return DeliveryStatus.ENGAGED
    if step.channel in {
        Channel.LINKEDIN_MESSAGE.value,
        Channel.LINKEDIN_CONNECTION.value,
    }:
        return DeliveryStatus.SENT
    if settings.MOCK_SMTP_MODE == "random":
        return _random_smtp_outcome(lead)

    domain = (lead.email or "").split("@")[-1].lower()
    bounce_domains = _csv_setting(settings.MOCK_SMTP_BOUNCE_DOMAINS)
    reply_domains = _csv_setting(settings.MOCK_SMTP_REPLY_DOMAINS)
    if domain in bounce_domains:
        return DeliveryStatus.BOUNCED
    if domain in reply_domains:
        return DeliveryStatus.REPLIED
    return DeliveryStatus.SENT


def _apply_delivery_outcome(
    lead: Lead,
    enrollment: LeadSequenceEnrollment,
    log: OutreachLog,
    draft: PersonalizationDraft | None,
    outcome: DeliveryStatus,
) -> None:
    now = datetime.now(timezone.utc)
    log.delivery_status = outcome.value
    if outcome in {
        DeliveryStatus.SENT,
        DeliveryStatus.ENGAGED,
        DeliveryStatus.REPLIED,
    }:
        log.sent_at = now
        lead.last_contacted_at = now
        if draft is not None:
            draft.status = DraftStatus.SENT.value

    if outcome == DeliveryStatus.BOUNCED:
        log.error_code = "mock_bounce"
        log.error_message = "Mock SMTP bounced this recipient domain."
        log.bounced_at = now
        enrollment.status = EnrollmentStatus.BOUNCED.value
        lead.outreach_status = OutreachStatus.BOUNCED.value
        return

    if outcome == DeliveryStatus.REPLIED:
        log.replied_at = now
        enrollment.reply_received = True
        enrollment.status = EnrollmentStatus.REPLIED.value
        lead.outreach_status = OutreachStatus.REPLIED.value


async def _advance_after_success(
    db: AsyncSession,
    enrollment: LeadSequenceEnrollment,
    step: SequenceStep,
) -> None:
    result = await db.execute(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == enrollment.sequence_id)
        .where(SequenceStep.step_number > step.step_number)
        .order_by(SequenceStep.step_number)
        .limit(1),
    )
    next_step = result.scalars().first()
    if next_step is None:
        enrollment.status = EnrollmentStatus.COMPLETED.value
        return
    enrollment.current_step = next_step.step_number
    enrollment.next_step_at = (
        datetime.now(timezone.utc)
        + timedelta(days=next_step.delay_days)
    )


def _csv_setting(value: str) -> set[str]:
    return {
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    }


def _random_smtp_outcome(lead: Lead) -> DeliveryStatus:
    seed = f"{settings.MOCK_SMTP_RANDOM_SEED}:{lead.email or lead.id}"
    rng = random.Random(seed)
    sample = rng.random()
    if sample < settings.MOCK_SMTP_BOUNCE_RATE:
        return DeliveryStatus.BOUNCED
    if sample < settings.MOCK_SMTP_BOUNCE_RATE + settings.MOCK_SMTP_REPLY_RATE:
        return DeliveryStatus.REPLIED
    return DeliveryStatus.SENT


async def _load_sequence(
    db: AsyncSession,
    sequence_id: uuid.UUID,
) -> Sequence:
    result = await db.execute(
        select(Sequence)
        .options(selectinload(Sequence.steps))
        .where(Sequence.id == sequence_id),
    )
    return result.scalar_one()
