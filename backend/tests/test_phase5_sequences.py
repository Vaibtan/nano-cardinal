"""Phase 5 sequence API contract tests."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.schemas.sequence import SequenceStepUpdate


async def test_user_paused_enrollment_does_not_resume_on_sequence_reactivation(
    client,
    _db_session: AsyncSession,
) -> None:
    lead = Lead(
        first_name="User",
        email="user-paused@example.com",
        company_name="PauseCo",
        icp_score=95,
    )
    _db_session.add(lead)
    await _db_session.flush()

    sequence_resp = await client.post(
        "/api/v1/sequences",
        json={
            "name": "Pause semantics",
            "is_active": True,
            "steps": [{"step_number": 1, "channel": "EMAIL"}],
        },
    )
    assert sequence_resp.status_code == 201
    sequence_id = sequence_resp.json()["id"]

    enroll_resp = await client.post(
        f"/api/v1/sequences/{sequence_id}/enrollments",
        json={"lead_id": str(lead.id)},
    )
    assert enroll_resp.status_code == 201
    enrollment_id = enroll_resp.json()["id"]

    pause_resp = await client.patch(
        f"/api/v1/sequences/{sequence_id}/enrollments/{enrollment_id}",
        json={"status": "PAUSED"},
    )
    assert pause_resp.status_code == 200
    assert pause_resp.json()["paused_reason"] == "USER"

    inactive_resp = await client.patch(
        f"/api/v1/sequences/{sequence_id}",
        json={"is_active": False},
    )
    assert inactive_resp.status_code == 200
    active_resp = await client.patch(
        f"/api/v1/sequences/{sequence_id}",
        json={"is_active": True},
    )
    assert active_resp.status_code == 200

    list_resp = await client.get(
        f"/api/v1/sequences/{sequence_id}/enrollments",
    )
    assert list_resp.status_code == 200
    [enrollment] = list_resp.json()
    assert enrollment["status"] == "PAUSED"
    assert enrollment["paused_reason"] == "USER"

    resume_resp = await client.post(
        f"/api/v1/sequences/{sequence_id}/enrollments/{enrollment_id}/resume",
        json={},
    )
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "ACTIVE"
    assert resume_resp.json()["paused_reason"] is None


async def test_batch_enroll_by_min_icp_score(
    client,
    _db_session: AsyncSession,
) -> None:
    high = Lead(
        first_name="High",
        email="high@example.com",
        company_name="HighFit",
        icp_score=91,
    )
    low = Lead(
        first_name="Low",
        email="low@example.com",
        company_name="LowFit",
        icp_score=30,
    )
    _db_session.add_all([high, low])
    await _db_session.flush()

    sequence_resp = await client.post(
        "/api/v1/sequences",
        json={
            "name": "Batch enroll",
            "is_active": True,
            "steps": [{"step_number": 1, "channel": "EMAIL"}],
        },
    )
    assert sequence_resp.status_code == 201
    sequence_id = sequence_resp.json()["id"]

    batch_resp = await client.post(
        f"/api/v1/sequences/{sequence_id}/enroll/batch",
        json={"min_icp_score": 80, "limit": 10},
    )
    assert batch_resp.status_code == 201
    enrollments = batch_resp.json()
    assert len(enrollments) == 1
    assert enrollments[0]["lead_id"] == str(high.id)


def test_sequence_step_partial_channel_validation_rejects_ambiguous_engage():
    try:
        SequenceStepUpdate(channel="LINKEDIN_ENGAGE")
    except ValueError as exc:
        assert "LINKEDIN_ENGAGE" in str(exc)
    else:
        raise AssertionError("Expected validation error")
