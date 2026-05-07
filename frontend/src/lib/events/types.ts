export type LeadEnrichmentCompleteEvent = {
  type: "lead.enrichment.complete";
  payload: {
    lead_id: string;
    icp_score: number | null;
    company_name: string | null;
  };
};

export type LeadEnrichmentFailedEvent = {
  type: "lead.enrichment.failed";
  payload: { lead_id: string; error: string };
};

export type SignalDetectedEvent = {
  type: "signal.detected";
  payload: {
    signal_id: string;
    lead_id: string;
    signal_type: string;
    signal_title: string;
    signal_strength: number;
  };
};

export type InboundEventReceivedEvent = {
  type: "inbound.event.received";
  payload: {
    event_id: string;
    event_type: string;
    source: string;
    email: string | null;
  };
};

export type InboundLeadEnrolledEvent = {
  type: "inbound.lead.enrolled";
  payload: { lead_id: string; sequence_id: string; icp_score: number };
};

export type DraftGeneratedEvent = {
  type: "draft.generated";
  payload: {
    lead_id: string;
    draft_id: string;
    critique_score: number | null;
  };
};

export type DraftTokenEvent = {
  type: "draft.token";
  payload: { draft_id: string; token: string };
};

export type SequenceStepSentEvent = {
  type: "sequence.step.sent";
  payload: {
    lead_id: string;
    sequence_id: string;
    step_number: number;
    channel: string;
  };
};

export type LeadCreatedEvent = {
  type: "lead.created";
  payload: { lead_id: string; source: string; company_name: string | null };
};

export type WorkerStatusEvent = {
  type: "worker.status";
  payload: {
    worker: string;
    status: "running" | "idle" | "error";
    queue_depth: number;
  };
};

export type SSEEvent =
  | LeadEnrichmentCompleteEvent
  | LeadEnrichmentFailedEvent
  | SignalDetectedEvent
  | InboundEventReceivedEvent
  | InboundLeadEnrolledEvent
  | DraftGeneratedEvent
  | DraftTokenEvent
  | SequenceStepSentEvent
  | LeadCreatedEvent
  | WorkerStatusEvent;

export type SSEEventType = SSEEvent["type"];

export const SSE_EVENT_TYPES: SSEEventType[] = [
  "lead.enrichment.complete",
  "lead.enrichment.failed",
  "signal.detected",
  "inbound.event.received",
  "inbound.lead.enrolled",
  "draft.generated",
  "draft.token",
  "sequence.step.sent",
  "lead.created",
  "worker.status",
];
