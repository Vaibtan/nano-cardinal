"""Inbound webhook parsing and idempotent processing."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InboundEventType, LeadSource, SignalType
from app.models.inbound import InboundEvent
from app.models.lead import Lead
from app.services.enrichment import run_enrichment_pipeline
from app.services.event_bus import publish_event
from app.services.signals import create_signal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedInboundEvent:
    """Canonical fields extracted from a source payload."""

    source: str
    event_type: str
    source_event_id: str | None
    event_fingerprint: str | None
    email: str | None
    first_name: str | None
    last_name: str | None
    linkedin_url: str | None
    company_domain: str | None
    company_name: str | None
    raw_payload: dict[str, Any]


def parse_inbound_payload(
    source: str,
    payload: dict[str, Any],
) -> ParsedInboundEvent:
    """Parse a supported inbound source into canonical fields."""
    normalized_source = source.lower()
    parser = _PARSERS.get(normalized_source, _parse_manual)
    parsed = parser(normalized_source, payload)
    return parsed


async def process_inbound_payload(
    db: AsyncSession,
    source: str,
    payload: dict[str, Any],
) -> InboundEvent:
    """Store and process an inbound payload idempotently."""
    parsed = parse_inbound_payload(source, payload)
    existing = await _find_existing_event(db, parsed)
    if existing is not None:
        if not existing.processed:
            await process_inbound_event(db, existing)
        return existing

    event = InboundEvent(
        source=parsed.source,
        event_type=parsed.event_type,
        source_event_id=parsed.source_event_id,
        event_fingerprint=parsed.event_fingerprint,
        email=parsed.email,
        first_name=parsed.first_name,
        last_name=parsed.last_name,
        linkedin_url=parsed.linkedin_url,
        company_domain=parsed.company_domain,
        raw_payload=parsed.raw_payload,
    )
    db.add(event)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing = await _find_existing_event(db, parsed)
        if existing is not None:
            return existing
        raise

    await publish_event(
        "inbound.event.received",
        {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "source": event.source,
            "email": event.email,
        },
    )
    await process_inbound_event(db, event)
    return event


async def process_inbound_event(
    db: AsyncSession,
    event: InboundEvent,
) -> None:
    """Retry-safe inbound worker pipeline for a stored event."""
    if event.created_lead_id is not None:
        event.processed = True
        event.processing_error = None
        event.processed_at = datetime.now(timezone.utc)
        await db.flush()
        return

    parsed = parse_inbound_payload(event.source, event.raw_payload)
    _copy_parsed_fields(event, parsed)

    if (
        parsed.source_event_id is None
        and parsed.event_fingerprint is None
    ):
        event.processed = True
        event.processing_error = "no_stable_identity"
        event.processed_at = datetime.now(timezone.utc)
        await db.flush()
        return

    lead = await _find_existing_lead(db, parsed)
    if lead is None:
        lead = Lead(
            first_name=parsed.first_name,
            last_name=parsed.last_name,
            email=parsed.email,
            linkedin_url=parsed.linkedin_url,
            company_domain=parsed.company_domain,
            company_name=parsed.company_name,
            source=LeadSource.INBOUND.value,
        )
        db.add(lead)
        await db.flush()

    lead.inbound_event_id = event.id
    event.created_lead_id = lead.id
    event.processed = True
    event.processing_error = None
    event.processed_at = datetime.now(timezone.utc)
    await db.flush()

    await _bridge_inbound_signal(db, event, lead)
    try:
        await run_enrichment_pipeline(str(lead.id), db)
    except Exception:
        logger.warning(
            "Inbound-created lead enrichment failed for %s",
            lead.id,
            exc_info=True,
        )
    else:
        from app.services.sequences import auto_enroll_matching_sequences

        await auto_enroll_matching_sequences(db, lead)

    await publish_event(
        "lead.created",
        {
            "lead_id": str(lead.id),
            "source": LeadSource.INBOUND.value,
            "company_name": lead.company_name,
        },
    )


async def _find_existing_event(
    db: AsyncSession,
    parsed: ParsedInboundEvent,
) -> InboundEvent | None:
    clauses = []
    if parsed.source_event_id is not None:
        clauses.append(
            and_(
                InboundEvent.source == parsed.source,
                InboundEvent.source_event_id == parsed.source_event_id,
            ),
        )
    if parsed.event_fingerprint is not None:
        clauses.append(
            InboundEvent.event_fingerprint == parsed.event_fingerprint,
        )
    if not clauses:
        return None
    result = await db.execute(select(InboundEvent).where(or_(*clauses)))
    return result.scalars().first()


async def _find_existing_lead(
    db: AsyncSession,
    parsed: ParsedInboundEvent,
) -> Lead | None:
    clauses = []
    if parsed.email:
        clauses.append(Lead.email == parsed.email)
    if parsed.linkedin_url:
        clauses.append(Lead.linkedin_url == parsed.linkedin_url)
    if parsed.company_domain and parsed.company_name:
        clauses.append(
            and_(
                Lead.company_domain == parsed.company_domain,
                Lead.company_name == parsed.company_name,
            ),
        )
    if not clauses:
        return None
    result = await db.execute(select(Lead).where(or_(*clauses)))
    return result.scalars().first()


async def _bridge_inbound_signal(
    db: AsyncSession,
    event: InboundEvent,
    lead: Lead,
) -> None:
    signal_type = _INBOUND_SIGNAL_MAP.get(event.event_type)
    if signal_type is None:
        return
    await create_signal(
        db=db,
        lead=lead,
        signal_type=signal_type,
        title=f"{event.event_type.replace('_', ' ').title()} detected",
        body=f"{event.source} generated an inbound buying signal.",
    )


def _copy_parsed_fields(
    event: InboundEvent,
    parsed: ParsedInboundEvent,
) -> None:
    event.event_type = parsed.event_type
    event.source_event_id = parsed.source_event_id
    event.event_fingerprint = parsed.event_fingerprint
    event.email = parsed.email
    event.first_name = parsed.first_name
    event.last_name = parsed.last_name
    event.linkedin_url = parsed.linkedin_url
    event.company_domain = parsed.company_domain


def _fingerprint(
    source: str,
    event_type: str,
    keys: list[str | None],
) -> str | None:
    stable = [str(value).strip().lower() for value in keys if value]
    if not stable:
        return None
    raw = "|".join([source, event_type, *stable])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _path(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_clerk(
    source: str,
    payload: dict[str, Any],
) -> ParsedInboundEvent:
    data = payload.get("data", {})
    email = _string(_path(payload, "data.email"))
    addresses = data.get("email_addresses") if isinstance(data, dict) else []
    if not email and addresses:
        email = _string(addresses[0].get("email_address"))
    event_type = _string(payload.get("type")) or InboundEventType.PRODUCT_SIGNUP.value
    source_event_id = _string(data.get("id")) or _string(payload.get("id"))
    fingerprint = _fingerprint(
        source,
        InboundEventType.PRODUCT_SIGNUP.value,
        [data.get("id")],
    )
    return ParsedInboundEvent(
        source=source,
        event_type=InboundEventType.PRODUCT_SIGNUP.value,
        source_event_id=source_event_id,
        event_fingerprint=fingerprint,
        email=email,
        first_name=_string(data.get("first_name")),
        last_name=_string(data.get("last_name")),
        linkedin_url=_string(data.get("linkedin_url")),
        company_domain=_string(data.get("company_domain")),
        company_name=_string(data.get("company_name")),
        raw_payload={**payload, "_source_event_type": event_type},
    )


def _parse_stripe(
    source: str,
    payload: dict[str, Any],
) -> ParsedInboundEvent:
    obj = _path(payload, "data.object") or {}
    metadata = obj.get("metadata", {}) if isinstance(obj, dict) else {}
    event_type = InboundEventType.PRODUCT_SIGNUP.value
    source_event_id = _string(payload.get("id")) or _string(obj.get("id"))
    email = (
        _string(obj.get("customer_email"))
        or _string(obj.get("receipt_email"))
        or _string(metadata.get("email"))
    )
    fingerprint = _fingerprint(
        source,
        event_type,
        [obj.get("id")],
    )
    return ParsedInboundEvent(
        source=source,
        event_type=event_type,
        source_event_id=source_event_id,
        event_fingerprint=fingerprint,
        email=email,
        first_name=_string(metadata.get("first_name")),
        last_name=_string(metadata.get("last_name")),
        linkedin_url=_string(metadata.get("linkedin_url")),
        company_domain=_string(metadata.get("company_domain")),
        company_name=_string(metadata.get("company_name")),
        raw_payload=payload,
    )


def _parse_linkedin_ads(
    source: str,
    payload: dict[str, Any],
) -> ParsedInboundEvent:
    response = payload.get("leadGenFormResponse", payload)
    event_type = InboundEventType.WEBSITE_OPT_IN.value
    email = _string(response.get("email"))
    form_id = _string(response.get("formId"))
    fingerprint = _fingerprint(source, event_type, [form_id, email])
    return ParsedInboundEvent(
        source=source,
        event_type=event_type,
        source_event_id=_string(response.get("id")),
        event_fingerprint=fingerprint,
        email=email,
        first_name=_string(response.get("firstName")),
        last_name=_string(response.get("lastName")),
        linkedin_url=_string(response.get("linkedinUrl")),
        company_domain=_string(response.get("companyDomain")),
        company_name=_string(response.get("companyName")),
        raw_payload=payload,
    )


def _parse_google_ads(
    source: str,
    payload: dict[str, Any],
) -> ParsedInboundEvent:
    user_data = payload.get("user_data", {})
    lead = payload.get("lead", {})
    event_type = InboundEventType.AD_CLICK.value
    gclid = _string(payload.get("gclid"))
    email = _string(user_data.get("email")) or _string(payload.get("email"))
    conversion_action = (
        _string(payload.get("conversion_action"))
        or _string(payload.get("conversionAction"))
    )
    fingerprint = _fingerprint(
        source,
        event_type,
        [conversion_action, gclid or email],
    )
    return ParsedInboundEvent(
        source=source,
        event_type=event_type,
        source_event_id=(
            _string(lead.get("id")) if isinstance(lead, dict) else None
        )
        or gclid
        or _string(payload.get("conversion_id")),
        event_fingerprint=fingerprint,
        email=email,
        first_name=_string(user_data.get("first_name")),
        last_name=_string(user_data.get("last_name")),
        linkedin_url=_string(user_data.get("linkedin_url")),
        company_domain=_string(payload.get("company_domain")),
        company_name=_string(payload.get("company_name")),
        raw_payload=payload,
    )


def _parse_manual(
    source: str,
    payload: dict[str, Any],
) -> ParsedInboundEvent:
    event_type = _string(payload.get("event_type")) or InboundEventType.PRODUCT_SIGNUP.value
    email = _string(payload.get("email"))
    source_event_id = _string(payload.get("id"))
    fingerprint = _fingerprint(
        source,
        event_type,
        [
            email,
            payload.get("linkedin_url"),
            payload.get("company_domain"),
            payload.get("company_name"),
        ],
    )
    return ParsedInboundEvent(
        source=source,
        event_type=event_type,
        source_event_id=source_event_id,
        event_fingerprint=fingerprint,
        email=email,
        first_name=_string(payload.get("first_name")),
        last_name=_string(payload.get("last_name")),
        linkedin_url=_string(payload.get("linkedin_url")),
        company_domain=_string(payload.get("company_domain")),
        company_name=_string(payload.get("company_name")),
        raw_payload=payload,
    )


_PARSERS = {
    "clerk": _parse_clerk,
    "stripe": _parse_stripe,
    "linkedin_ads": _parse_linkedin_ads,
    "google_ads": _parse_google_ads,
    "manual": _parse_manual,
}

_INBOUND_SIGNAL_MAP = {
    InboundEventType.PRODUCT_SIGNUP.value: SignalType.PRODUCT_SIGNUP.value,
    InboundEventType.AD_CLICK.value: SignalType.WEBSITE_VISIT.value,
    InboundEventType.WEBSITE_OPT_IN.value: SignalType.WEBSITE_VISIT.value,
    InboundEventType.CONFERENCE_REGISTRATION.value: (
        SignalType.CONFERENCE_ATTENDANCE.value
    ),
}
