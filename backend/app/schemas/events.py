"""Typed SSE event contracts.

Workers and API streaming endpoints must emit only these event names and
payload shapes.  The frontend mirror lives in
``frontend/src/lib/events/types.ts``.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


class LeadEnrichmentCompletePayload(BaseModel):
    lead_id: str
    icp_score: float | None
    company_name: str | None


class LeadEnrichmentFailedPayload(BaseModel):
    lead_id: str
    error: str


class SignalDetectedPayload(BaseModel):
    signal_id: str
    lead_id: str
    signal_type: str
    signal_title: str
    signal_strength: float


class InboundEventReceivedPayload(BaseModel):
    event_id: str
    event_type: str
    source: str
    email: str | None = None


class InboundLeadEnrolledPayload(BaseModel):
    lead_id: str
    sequence_id: str
    icp_score: float


class DraftGeneratedPayload(BaseModel):
    lead_id: str
    draft_id: str
    critique_score: float | None


class DraftTokenPayload(BaseModel):
    draft_id: str
    token: str


class SequenceStepSentPayload(BaseModel):
    lead_id: str
    sequence_id: str
    step_number: int
    channel: str


class LeadCreatedPayload(BaseModel):
    lead_id: str
    source: str
    company_name: str | None = None


class WorkerStatusPayload(BaseModel):
    worker: str
    status: Literal["running", "idle", "error"]
    queue_depth: int


class LeadEnrichmentCompleteEvent(BaseModel):
    type: Literal["lead.enrichment.complete"]
    payload: LeadEnrichmentCompletePayload


class LeadEnrichmentFailedEvent(BaseModel):
    type: Literal["lead.enrichment.failed"]
    payload: LeadEnrichmentFailedPayload


class SignalDetectedEvent(BaseModel):
    type: Literal["signal.detected"]
    payload: SignalDetectedPayload


class InboundEventReceivedEvent(BaseModel):
    type: Literal["inbound.event.received"]
    payload: InboundEventReceivedPayload


class InboundLeadEnrolledEvent(BaseModel):
    type: Literal["inbound.lead.enrolled"]
    payload: InboundLeadEnrolledPayload


class DraftGeneratedEvent(BaseModel):
    type: Literal["draft.generated"]
    payload: DraftGeneratedPayload


class DraftTokenEvent(BaseModel):
    type: Literal["draft.token"]
    payload: DraftTokenPayload


class SequenceStepSentEvent(BaseModel):
    type: Literal["sequence.step.sent"]
    payload: SequenceStepSentPayload


class LeadCreatedEvent(BaseModel):
    type: Literal["lead.created"]
    payload: LeadCreatedPayload


class WorkerStatusEvent(BaseModel):
    type: Literal["worker.status"]
    payload: WorkerStatusPayload


SSEEvent = Annotated[
    Union[
        LeadEnrichmentCompleteEvent,
        LeadEnrichmentFailedEvent,
        SignalDetectedEvent,
        InboundEventReceivedEvent,
        InboundLeadEnrolledEvent,
        DraftGeneratedEvent,
        DraftTokenEvent,
        SequenceStepSentEvent,
        LeadCreatedEvent,
        WorkerStatusEvent,
    ],
    Field(discriminator="type"),
]

SSE_EVENT_ADAPTER: TypeAdapter[SSEEvent] = TypeAdapter(SSEEvent)
