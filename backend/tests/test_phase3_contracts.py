"""Phase 3 inbound and schema contract tests."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inbound import parse_inbound_payload


async def test_event_fingerprint_unique_index_is_partial(
    _db_session: AsyncSession,
) -> None:
    result = await _db_session.execute(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE tablename = 'inbound_events'
              AND indexname = 'uq_inbound_events_fingerprint'
            """,
        ),
    )
    indexdef = result.scalar_one()
    assert "UNIQUE INDEX" in indexdef
    assert "WHERE (event_fingerprint IS NOT NULL)" in indexdef


def test_source_specific_fingerprints_are_stable() -> None:
    clerk = parse_inbound_payload(
        "clerk",
        {
            "id": "evt_changed",
            "type": "user.created",
            "data": {
                "id": "user_123",
                "email": "first@example.com",
            },
        },
    )
    clerk_retry = parse_inbound_payload(
        "clerk",
        {
            "id": "evt_changed_again",
            "type": "user.created",
            "data": {
                "id": "user_123",
                "email": "second@example.com",
            },
        },
    )
    assert clerk.event_fingerprint == clerk_retry.event_fingerprint

    google = parse_inbound_payload(
        "google_ads",
        {
            "conversion_action": "demo-request",
            "gclid": "gclid_123",
            "user_data": {"email": "a@example.com"},
        },
    )
    google_other_action = parse_inbound_payload(
        "google_ads",
        {
            "conversion_action": "pricing-page",
            "gclid": "gclid_123",
            "user_data": {"email": "a@example.com"},
        },
    )
    assert google.event_fingerprint != google_other_action.event_fingerprint

    linkedin = parse_inbound_payload(
        "linkedin_ads",
        {
            "leadGenFormResponse": {
                "formId": "form_1",
                "email": "BUYER@EXAMPLE.COM",
            },
        },
    )
    linkedin_retry = parse_inbound_payload(
        "linkedin_ads",
        {
            "leadGenFormResponse": {
                "formId": "form_1",
                "email": "buyer@example.com",
            },
        },
    )
    assert linkedin.event_fingerprint == linkedin_retry.event_fingerprint
