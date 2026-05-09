# Orion v3.6 Strict Implementation Checklist

Source of truth: `PRD.md` (Version 3.6).
Execution policy: do not start the next phase until the current phase gate is fully green.

Current status snapshot:

- Phase 1 implementation is complete: core schema, async DB layer, ICP CRUD, sender profile, frontend scaffold, and Postgres test infrastructure are in place.
- Phase 2 implementation is complete: lead CRUD/import/search, mock enrichment, ICP scoring, pgvector similarity, TAM heatmaps, ARQ worker wiring, and `/leads` + `/tam` frontend pages are in place.
- Vector storage was intentionally changed from Qdrant to Postgres `pgvector`.
- Real enrichment providers are not implemented yet. Mock enrichment is supported; non-mock mode now fails fast instead of silently returning fake data.
- Current local test rerun uses Docker Postgres/pgvector with test DB `localhost:5433/orion_test`.
- Phase 2.5 alignment is implemented: frontend architecture, signal preferences, last-contacted contract, SSE types, lead filters, and TAM discovery are in place.
- Phase 3 implementation is in place for the demo path: inbound webhooks/audit/retry/stats, idempotency fields, source-specific fingerprints, signal scoring/feed/retention/dismissal, deterministic mock signal monitor, Redis dedup, and unified SSE exist.
- Phase 4 implementation is in place for the demo path: executable LangGraph draft generation, commonality matching, snippet RAG storage, 5-axis critique, tone adaptation, negative-keyword filtering, approval, worker-backed token streaming, and `/compose` exist.
- Phase 5 implementation is in place for the demo path: sequence CRUD/enrollment, user and sequence pause/resume semantics, deterministic mock delivery outcomes, execution worker, outreach transitions, batch enrollment, and `/sequences` exist.
- Phase 6 implementation is in place for the demo path: analytics endpoints/page, demo seed script with inbound events, README runbook, Docker validation, and regression tests exist.
- Local runtime gates still require your Postgres/Redis/browser environment.
- Current branch is `lead-pipeline`; this work is not merged into `main` yet.

## 0. Global Rules (Apply to Every Phase)

- [ ] Use one branch per phase: `phase-1-core`, `phase-2-leads`, etc.
- [x] Keep API contracts in sync across router, schema, DB model, and tests for completed Phase 1 and Phase 2 scope.
- [x] Keep Phase 3-6 API contracts in sync across router, schema, DB model, frontend clients, and tests for the implemented demo surfaces.
- [x] Keep enum values aligned across Python enums, SQL defaults, and frontend constants for completed Phase 1 and Phase 2 scope.
  - All `LeadSource` values are UPPERCASE (`MANUAL`, `CSV_IMPORT`, `INBOUND`, etc.).
  - All `EnrichmentStatus`, `OutreachStatus`, `EnrollmentStatus` values are UPPERCASE.
  - SQL `DEFAULT` values must match Python enum `.value` exactly.
- [x] Any new DB field requires: migration + ORM model + schema + test coverage for completed Phase 1 and Phase 2 scope.
- [ ] Phase 3-6 DB fields require matching test coverage. Current migrations/models exist, but service/worker/schema drift tests are not complete.
- [x] Any new endpoint requires: request schema, response schema, success test, failure test for completed Phase 1 and Phase 2 scope.
- [ ] Phase 3-6 endpoints require success/failure tests before release readiness.
- [x] Any async worker change requires retry-safe behavior.
- [x] SSE event names and payload shapes must match the single source of truth in `backend/app/schemas/events.py`, with frontend mirror/generated types in `frontend/src/lib/events/types.ts`.
- [x] No silent placeholder enrichment logic in completed phase scope; real enrichment mode fails fast until providers are implemented.
- [x] Embedding-dimension migration runbook is documented in the PRD; any `EMBEDDING_MODEL` dimension change must follow it before API/worker restart.
- [x] `pytest -q` must pass before phase close. Current pass: Docker Postgres/pgvector + Redis.
- [x] Frontend `npm run lint` and `npm run build` must pass before phase close.
- [x] Circular FK between `leads ↔ inbound_events` handled via SQLAlchemy `relationship(post_update=True)`.

## 1. Definition of Done (Per Phase)

- [ ] All checklist items in the phase are complete.
- [ ] Phase-specific tests pass.
- [ ] API surface for that phase is documented in OpenAPI and matches PRD.
- [ ] Developer runbook for that phase is updated (commands + env vars).
- [ ] Demo path for that phase works locally via Docker Compose.

## 2. Phase 1 - Core Data Layer + Sender Profile (Week 1)

### Build Checklist

- [x] Docker Compose services defined for local stack: `postgres`, `redis`, `backend`, `worker`, `frontend`.
- [x] Qdrant removed from implementation plan; vectors use Postgres `pgvector`.
- [x] Docker Compose has no deprecated `version` key.
- [x] Health endpoint exists.
- [x] SQLAlchemy async setup complete.
- [x] Write-aware `get_db` session dependency implemented.
- [x] Alembic baseline migration created.
- [x] Postgres + pgvector extension enabled in migration.
- [x] Core schema implemented with v3.2 corrected fields:
  - [x] `leads.company_name` nullable.
  - [x] `leads.icp_score_breakdown` JSONB.
  - [x] `leads.updated_at` TIMESTAMPTZ DEFAULT NOW().
  - [x] `leads.source` DEFAULT `'MANUAL'` (uppercase, matching `LeadSource.MANUAL` enum value).
  - [x] `sequence_steps.requires_approval` boolean.
  - [x] `lead_sequence_enrollments.next_step_at` not null default `NOW()`.
  - [x] `personalization_drafts.sequence_id`, `sequence_step_id`, `enrollment_id` + FK constraints.
  - [x] Circular FK `leads.inbound_event_id -> inbound_events(id)` created via ALTER TABLE.
  - [x] Circular FK note in ORM: use `relationship(post_update=True)`.
- [x] Phase 1 indexes applied, including `idx_leads_updated_at`.
- [x] FastAPI app scaffold with router registration and CORS.
- [x] `config.py` includes embedding, enrichment, LLM, Redis, and threshold env vars.
- [x] ICP CRUD endpoints complete.
- [x] Sender profile create/update/get endpoints complete.
- [x] Sender upsert uses Postgres `ON CONFLICT`.
- [x] Frontend Next.js App Router scaffold complete.
- [x] `/icp` page implemented.
- [x] `/sender` page implemented.

### Phase 1 Test Gate

- [ ] `docker compose up -d` succeeds with all services healthy. Needs current local rerun.
- [x] `alembic upgrade head` is used by test setup instead of ORM metadata creation.
- [x] Test DB safety guard prevents destructive reset unless DB name contains `test`.
- [x] API tests exist for ICP and sender routes.
- [x] Verify: `leads.source` SQL default matches `LeadSource.MANUAL` Python enum value (both UPPERCASE).
- [x] `pytest -q` passes in current shell with Docker Postgres/pgvector + Redis.
- [x] `npm run lint` passes in current shell.
- [x] `npm run build` passes in current shell.

## 3. Phase 2 - Lead Pipeline + TAM Mapping (Week 2)

### Build Checklist

- [x] Lead CRUD endpoints implemented (create, list, get, delete).
- [x] `GET /api/v1/leads/{id}/outreach` endpoint returns outreach history from `outreach_logs`.
- [x] CSV import endpoint implemented with validation and row-level error reporting.
- [x] CSV import size capped at 10 MB with HTTP 413 response.
- [x] YC import endpoint implemented (mock fixture mode supported).
- [x] `GET /api/v1/leads/search?q=` semantic search endpoint implemented.
- [x] `GET /api/v1/leads/{id}/similar` pgvector similarity endpoint implemented.
- [x] Vector search uses bound pgvector parameter, not raw f-string SQL interpolation.
- [x] ARQ worker configuration implemented (`WorkerSettings`, queue wiring).
- [x] Background enrichment enqueue supported with `background=true`.
- [x] ARQ pool is closed in `finally` after enqueue attempt.
- [x] Enrichment pipeline implemented in mock mode.
- [x] Non-mock enrichment mode fails fast because real providers are not wired yet.
- [x] Enrichment status lifecycle enforced: `PENDING -> RUNNING -> COMPLETE/FAILED`.
- [x] Worker commits `FAILED` state before re-raising retryable failures.
- [x] `leads.updated_at` set on enrichment/scoring update.
- [x] pgvector column implemented on `leads.embedding`.
- [x] HNSW vector index added via forward migration `002_add_hnsw_vector_index.py`.
- [x] Mock embedding generation is deterministic and matches fixed vector dimension.
- [x] Real embedding provider integration implemented for gemini/openai/ollama with dimension validation and mock fallback.
- [x] ICP scoring computes against all active ICPs.
- [x] ICP scoring supports both `50-200` and `1001+` company-size bucket formats.
- [x] Best ICP persisted to `leads.icp_id` + `leads.icp_score`.
- [x] Score breakdown persisted to `leads.icp_score_breakdown`.
- [x] TAM heatmap endpoint implemented.
- [x] TAM heatmap groups by `(industry, size_bucket)` without double-counting.
- [x] TAM heatmap reports `excluded_no_size` and flags default TAM estimates.
- [x] TAM whitespace endpoint implemented.
- [x] `/leads` page implemented with filtering and status badges.
- [x] `/leads` frontend avoids sending `"all"` as a backend filter value.
- [x] `/tam` page implemented with ICP selector, summary cards, and heatmap grid.
- [x] `excalidraw.log` removed from tracking and added to `.gitignore`.

### Phase 2 Test Gate

- [x] Unit tests for enrichment step functions (mock mode).
- [x] Test confirms non-mock enrichment mode fails fast instead of silently using mock data.
- [x] Integration tests for lead import and enrichment path.
- [x] Background enqueue unavailable path tested with HTTP 503.
- [x] CSV too-large path tested with HTTP 413.
- [x] TAM aggregation tests with deterministic fixtures.
- [x] TAM per-cell test confirms exact captured counts and no double-counting.
- [x] Semantic similarity endpoint test (`/api/v1/leads/{id}/similar`).
- [x] Semantic search endpoint test (`/api/v1/leads/search?q=`).
- [x] `pytest -q` passes against Docker Postgres/pgvector + Redis.
- [x] `npm run lint` passes in current shell.
- [x] `npm run build` passes in current shell.

## 4. Phase 2.5 - Frontend + Contract Alignment (Before Phase 3)

### Build Checklist

- [x] Install frontend foundations required by PRD: TanStack Query v5, React Hook Form, Zod, Recharts.
- [x] Add typed SSE/EventSource helper module for Phase 3 and Phase 4 streaming workflows.
- [x] Create SSE event contract source of truth in `backend/app/schemas/events.py` and frontend mirror/generated types in `frontend/src/lib/events/types.ts`.
- [x] Decide whether Zustand is needed for cross-page UI/session state; add it only if there is state that does not belong in URL params or TanStack Query cache. Decision: not needed for Phase 2.5.
- [x] Refactor `/icp` wizard order to Firmographics -> Persona -> Signals -> Weighting.
- [x] Move ICP `name` and `description` into metadata/header fields instead of a wizard step.
- [x] Extend ICP config schema and frontend form with signal preferences:
  - [x] `selected_signal_types`.
  - [x] `signal_recency_days`.
  - [x] `min_signal_strength`.
  - [x] `signal_keywords`.
- [x] Migration adds `leads.last_contacted_at TIMESTAMPTZ` + `idx_leads_last_contacted_at`; ORM + schemas updated.
- [x] Signal scorer treats `leads.last_contacted_at=NULL` as "never contacted."
- [x] Add slider-based ICP weight controls.
- [x] Auto-normalize displayed ICP weights to sum to 1.0 before save.
- [x] Add live matching lead count preview for ICP criteria.
- [x] Add backend support for matching lead count preview if current list endpoint is insufficient.
- [x] Upgrade `/leads` filters with ICP score range and signal type.
- [x] Scaffold `/leads` drawer sections for enriched profile, signal timeline, commonality hooks, drafts, and sequence position.
- [x] Render stable empty states for P3/P4/P5 drawer sections until data exists.
- [x] Make zero/low-coverage `/tam` cells clickable.
- [x] Implement TAM Discover Leads action panel with selected industry/company-size criteria prefilled.
- [x] Add frontend tests or smoke coverage for ICP wizard order, weight normalization, lead filters, drawer sections, and TAM cell click behavior. Smoke coverage: `npm run lint` + `npm run build`.
- [x] Update PRD/checklist again if any frontend library is intentionally cut from scope. No library was cut; Zustand deferred by explicit Phase 2.5 decision.

### Phase 2.5 Test Gate

- [x] Frontend `npm run lint` passes.
- [x] Frontend `npm run build` passes.
- [x] Backend tests for new preview/schema behavior pass against Docker Postgres/pgvector.
- [x] Backend migration/model/schema test verifies `leads.last_contacted_at` exists before Phase 3 starts.
- [ ] Manual browser check: `/icp`, `/leads`, and `/tam` match PRD §4 behavior closely enough to start Phase 3.

## 5. Phase 3 - Inbound Capture + Signal Monitor (Week 3)

### Build Checklist

- [x] Webhook endpoint: `POST /api/v1/inbound/webhook/{source}` implemented.
- [ ] Source parsers implemented and tested for: `clerk`, `stripe`, `linkedin_ads`, `google_ads`, `manual`. Parsers exist, but automated parser coverage is missing.
- [x] Inbound events audit endpoints implemented (`GET /events`, `GET /events/{id}`, `POST /events/{id}/retry`, `GET /stats`).
- [x] Inbound events include stable idempotency fields:
  - [x] `source_event_id`.
  - [x] nullable `event_fingerprint`.
- [x] Inbound idempotency constraints added:
  - [x] Partial unique index on `(source, source_event_id)` where `source_event_id IS NOT NULL`.
  - [x] Partial unique `event_fingerprint` where `event_fingerprint IS NOT NULL`.
- [x] Source-specific `event_fingerprint` builders implemented per PRD table; volatile timestamps are excluded from hashes.
- [x] Irreducible inbound events with no stable `source_event_id` or `event_fingerprint` are stored as audit rows with `event_fingerprint=NULL`, `processed=true`, `processing_error='no_stable_identity'`, and no lead creation.
- [x] Inbound worker pipeline implemented (Steps 1-5):
  - [x] store event → extract identity → dedup → lead create/link → enrichment trigger.
- [x] Inbound retry contract implemented:
  - [x] Retry reuses `created_lead_id` when present.
  - [x] Retry dedups by email, LinkedIn URL, company domain + name, then non-null `event_fingerprint`.
  - [x] No-email events use stable `source_event_id` or `event_fingerprint` when available; irreducible events follow the `no_stable_identity` path.
  - [x] Partial failure after lead creation does not double-create on retry.
- [x] Lead creation from inbound sets `source='INBOUND'` and `inbound_event_id`.
- [x] Inbound auto-routing (Step 6) implemented as graceful no-op when no matching sequences exist.
  - [x] Queries sequences with `auto_enroll=true AND icp_id matching`.
  - [ ] Full end-to-end auto-routing tested in Phase 5 when Sequence CRUD is built.
- [ ] Signal workers implemented: Funding, Hiring, LinkedIn, News. Current implementation is one deterministic mock scanner that emits these signal categories; real source-specific polling workers are not implemented.
- [x] Signal strength scoring formula implemented (base score + modifiers):
  - [x] Base scores per signal type (PRODUCT_SIGNUP: 0.98, WEBSITE_VISIT: 0.95, etc.).
  - [x] Recency boost (×1.2 if within 48h).
  - [x] ICP score boost (×1.1 if icp_score > 80).
  - [x] Cool-off penalty (×0.8 if `lead.last_contacted_at` is within last 30 days).
  - [x] Keyword relevance boost (×1.05 if signal title/body matches `icp.signal_keywords`).
  - [x] Final score capped at 1.0.
- [x] ICP-scoped signal queries apply `icp.signal_recency_days` before scoring.
- [x] ICP-scoped feeds and auto-personalization triggers exclude signals below `icp.min_signal_strength` after final score calculation.
- [x] Signal implementation keeps `signal_recency_days`, 48h recency boost, and `expires_at` retention as independent concepts.
- [x] Signal scoring avoids N+1 outreach log lookups by reading denormalized `leads.last_contacted_at`.
- [x] Inbound-to-signal bridge mappings implemented:
  - [x] `PRODUCT_SIGNUP` → `PRODUCT_SIGNUP`.
  - [x] `AD_CLICK` / `WEBSITE_OPT_IN` → `WEBSITE_VISIT`.
  - [x] `CONFERENCE_REGISTRATION` → `CONFERENCE_ATTENDANCE`.
- [x] Redis dedup implemented with SHA256 hash + 7-day TTL.
- [x] Signals table includes `expires_at` + `idx_signals_expires_at` for feed retention.
- [x] Unified SSE endpoint implemented: `GET /api/v1/events/stream` with Redis Pub/Sub bridge.
- [x] Signals filtered view supported: `GET /api/v1/events/stream?topic=signals`.
- [x] Signal dismiss endpoint (`DELETE /api/v1/signals/{id}`) is soft-delete (sets `is_read=true`, excluded from feed).
- [x] Signal retention implemented: default `expires_at = detected_at + 90 days`; default feed excludes `is_read=true` and expired signals.
- [x] `/feed` page implemented with inbound + signal cards and live updates.

### Phase 3 Test Gate

- [x] Targeted parser/fingerprint coverage tests for Clerk, LinkedIn Ads, and Google Ads source-specific contracts.
- [ ] Idempotency tests for inbound retry and signal dedup.
- [ ] Concurrent duplicate webhook test verifies partial unique `(source, source_event_id)` constraint prevents duplicate inbound rows.
- [ ] Partial-failure retry test: event creates/links a lead, crashes before `processed=true`, retry resumes without duplicate lead.
- [ ] No-email event test covers both stable-key retry and irreducible `no_stable_identity` handling.
- [ ] Signal strength scoring formula tests (base + all 4 modifiers + cap at 1.0).
- [ ] Signal query tests verify `icp.signal_recency_days` and `icp.min_signal_strength` are applied without changing `expires_at` retention semantics.
- [ ] Signal scoring test verifies cool-off uses `lead.last_contacted_at`.
- [ ] Signal retention tests verify expired/read signals are hidden from the default feed.
- [ ] SSE contract tests verify backend `backend/app/schemas/events.py` event union matches frontend types and emitted payloads.
- [ ] End-to-end test: inbound webhook → lead enriched (auto-routing is no-op without sequences).
- [x] `pytest -q`, `npm run lint`, and `npm run build` all pass.

## 6. Phase 4 - Commonalities Engine + LangGraph Agent (Week 4)

### Build Checklist

- [x] LangGraph `StateGraph` implemented with executable nodes 1, 1.5, 2, 3, 4, 5, 6 and invoked by `generate_draft`.
- [x] Deterministic commonality matcher exists in executable LangGraph node path.
- [x] Node 1.5 commonality matcher returns strict structured output from the executed LangGraph node.
- [x] Node 1.5 gracefully skips when no SenderProfile exists (returns `strongest_hook=null`, `hook_strength=0`).
- [x] Node 3-style RAG retrieval implemented against Postgres/pgvector `winning_snippets` storage in the graph path.
- [x] Node 3 RAG query includes `{strongest_hook} + {selected_signal_title} + {lead_title} at {lead_industry}` context.
- [x] `winning_snippets` pgvector storage matches PRD schema with `subject_line`, `hook_type`, `role_seniority`, and `reply_rate`.
- [x] Seed job for `winning_snippets` fixture implemented and covered through personalization tests.
- [x] Node 4 draft output contract matches v3.2:
  - [x] `subject_line`, `email_body`, `linkedin_message`.
- [x] Node 4 negative-keyword enforcement implemented for banned phrases in PRD.
- [x] Node 5 critique uses PRD's 5 dimensions: Specificity, Relevance, Tone, CTA Clarity, Subject Line.
- [x] Node 5 rewrite loop uses `CRITIQUE_REWRITE_THRESHOLD` env var.
- [x] Rewrite loop bounded to max 3 iterations.
- [x] Node 6 tone adapter implemented for seniority/industry/channel rules.
- [x] Personalization endpoints implemented:
  - [x] single generate, batch generate, list drafts, patch draft, approve draft.
- [x] Add PRD-compatible `/api/v1/personalize/...` route aliases.
- [x] Draft persistence includes: `status` field (DRAFT | APPROVED | SENT) + optional sequence linkage fields.
- [x] Draft approve endpoint sets `status=APPROVED`, `approved_at=NOW()`; if linked to enrollment, sets enrollment `ACTIVE` + `next_step_at=NOW()`.
- [x] Draft patch endpoint prevents editing APPROVED/SENT drafts unless explicitly reopened.
- [x] Token streaming: worker publishes tokens to Redis channel `sse:{draft_id}`, SSE endpoint subscribes and relays.
- [x] `/compose` page implemented with streaming draft tokens, commonality panel, and quality radar.
- [x] `/compose` page includes signal selector, editable draft mode, scalable lead search/autocomplete, and approve feedback.

### Phase 4 Test Gate

- [ ] Unit tests for node-level output parsing and validation.
- [ ] Test: personalization works with no SenderProfile (skips Node 1.5, falls back to signal/company opening).
- [ ] Failure-path tests for invalid LLM JSON with safe recovery.
- [x] Token usage and critique score persistence tests.
- [ ] SSE `draft.token` and `draft.generated` event tests (including Redis Pub/Sub bridge).
- [x] `pytest -q`, `npm run lint`, and `npm run build` all pass.

## 7. Phase 5 - Sequence Manager + Engagement Steps (Week 5)

### Build Checklist

- [x] Sequence CRUD implemented (create, list, get detail, update).
- [x] Add PRD-compatible `PUT /api/v1/sequences/{id}` alias.
- [x] `lead_sequence_enrollments` pause tracking added via migration + ORM + schemas:
  - [x] `paused_reason VARCHAR` with values `USER | SEQUENCE_DEACTIVATED`.
  - [x] `paused_at TIMESTAMPTZ`.
  - [x] Partial/indexed query support for `(sequence_id, paused_reason)` where `status='PAUSED'`.
- [x] Sequence active-state semantics implemented:
  - [x] Setting `is_active=false` pauses ACTIVE enrollments for that sequence.
  - [x] Sequence deactivation sets `paused_reason='SEQUENCE_DEACTIVATED'` and `paused_at=NOW()`.
  - [x] Reactivating resumes only enrollments where `status='PAUSED' AND paused_reason='SEQUENCE_DEACTIVATED'`, then clears `paused_reason` and `paused_at`.
  - [x] User-paused enrollments use `paused_reason='USER'` and remain PAUSED after sequence reactivation.
  - [x] Terminal enrollments (`BOUNCED`, `REPLIED`, `UNSUBSCRIBED`, `COMPLETED`) never resume on sequence reactivation.
  - [ ] Pause invariant enforced in service/tests: `paused_reason` and `paused_at` are NULL unless `status='PAUSED'`; every PAUSED row has a non-null `paused_reason`. Not yet covered by tests.
- [x] Sequence step CRUD supports `OUTREACH` and `ENGAGEMENT`.
- [x] Channel/StepType validation enforced:
  - [x] ENGAGEMENT steps → only `LINKEDIN_ENGAGE` channel.
  - [x] OUTREACH steps → only `EMAIL`, `LINKEDIN_MESSAGE`, or `LINKEDIN_CONNECTION`.
  - [x] Mismatched combinations return HTTP 422.
  - [x] Partial update validation rejects ambiguous PATCH payloads with only `channel=LINKEDIN_ENGAGE` or only `step_type=ENGAGEMENT`.
- [x] `LINKEDIN_ENGAGE` channel behavior implemented: log `step_type=ENGAGEMENT`, `channel=LINKEDIN_ENGAGE`, `engagement_action=<value>`, `delivery_status=ENGAGED`, no message body.
- [x] Execution worker cron runs every 15 minutes.
- [x] Enrollment scheduler query uses `status='ACTIVE' AND next_step_at <= NOW()`.
- [x] Approval flow implemented end-to-end:
  - [x] AI draft generated with `enrollment_id + sequence_id + sequence_step_id`.
  - [x] if `requires_approval=true`, enrollment moves to `PENDING_APPROVAL`.
  - [x] approve endpoint sets draft approved and resumes enrollment (`ACTIVE`, `next_step_at=NOW()`).
  - [x] worker prefers approved draft for same enrollment+step (no regeneration).
- [x] Mock SMTP send logging implemented.
- [x] Mock deterministic outcome rules implemented:
  - [x] `MOCK_SMTP_MODE=deterministic`.
  - [x] EMAIL recipients in `MOCK_SMTP_BOUNCE_DOMAINS` produce BOUNCED outcomes.
  - [x] EMAIL recipients in `MOCK_SMTP_REPLY_DOMAINS` produce REPLIED outcomes.
  - [x] All other EMAIL recipients produce SENT outcomes.
  - [x] `LINKEDIN_MESSAGE` and `LINKEDIN_CONNECTION` produce SENT outcomes in mock mode.
  - [x] `LINKEDIN_ENGAGE` produces ENGAGED outcomes in mock mode.
- [x] Optional seeded random mock SMTP mode implemented only if deterministic tests remain stable:
  - [x] `MOCK_SMTP_BOUNCE_RATE`.
  - [x] `MOCK_SMTP_REPLY_RATE`.
  - [x] `MOCK_SMTP_RANDOM_SEED`.
- [x] Mock LinkedIn action logging implemented.
- [x] `outreach_logs` delivery outcome fields added via migration + ORM + schema:
  - [x] `delivery_status`.
  - [x] `error_code`.
  - [x] `error_message`.
  - [x] `bounced_at`.
- [x] `outreach_logs.delivery_status` defaults to `PENDING`; worker sets final outcome before commit.
- [x] `outreach_logs.sent_at` is set only after final `SENT` / `ENGAGED` / `REPLIED` outcome is known.
- [x] `lead.outreach_status` transitions implemented:
  - [x] UNTOUCHED → IN_SEQUENCE on enrollment creation.
  - [x] IN_SEQUENCE → REPLIED on reply.
  - [x] IN_SEQUENCE → BOUNCED on send failure.
- [x] Bounced send sets `enrollment.status=BOUNCED` terminal and does not advance to the next step.
- [x] Successful send/engagement updates `leads.last_contacted_at`.
- [x] Successful outreach log write marks linked draft as `SENT`.
- [x] Document that REPLIED also marks linked draft as `SENT`, because a reply implies the message was successfully sent.
- [x] Bounced/failed/skipped sends do not mark drafts `SENT`.
- [x] Auto-enroll logic uses sequence threshold + global fallback.
- [x] Add `PATCH /api/v1/sequences/{id}/enrollments/{eid}` for user pause/update.
- [x] Add `POST /api/v1/sequences/{id}/enrollments/{eid}/resume`.
- [x] Add `POST /api/v1/sequences/{id}/enroll/batch` for bulk enroll by min ICP score.
- [x] Inbound auto-routing (Phase 3 Step 6) activated in service code:
  - [x] Create sequence with `auto_enroll=true` + ICP.
  - [x] Inbound webhook → lead enriched → ICP score computed → auto-enrolled into sequence when threshold criteria match.
  - [x] SSE `inbound.lead.enrolled` event emitted.
- [x] `/sequences` page implemented with `dnd-kit` reordering and step config UI.
- [ ] `/sequences` page shows per-step enrollment metrics overlay.
- [x] Sequence executor drains due enrollments in bounded batches rather than stopping at the first 100.

### Phase 5 Test Gate

- [ ] Worker tests for step transitions and completion behavior.
- [ ] Channel/StepType validation tests (422 on mismatch).
- [ ] Approval-state tests for `PENDING_APPROVAL` pause/resume path.
- [ ] Sequence pause/reactivation tests for `is_active=false/true` enrollment behavior.
- [x] Sequence pause/reactivation tests verify `paused_reason='SEQUENCE_DEACTIVATED'` rows resume and `paused_reason='USER'` rows do not.
- [ ] Sequence reactivation test verifies terminal `BOUNCED`, `REPLIED`, `UNSUBSCRIBED`, and `COMPLETED` enrollments are not resumed.
- [ ] Reply-stop tests (enrollment halts on reply).
- [ ] Mock SMTP deterministic outcome tests for SENT, REPLIED, and BOUNCED.
- [ ] Mock LinkedIn outcome tests verify `LINKEDIN_MESSAGE`/`LINKEDIN_CONNECTION` -> SENT and `LINKEDIN_ENGAGE` -> ENGAGED.
- [ ] Delivery-status safety test verifies no committed outreach log remains `PENDING` after worker success/failure handling.
- [ ] Draft `SENT` transition test after successful outreach log write.
- [ ] Bounce test verifies outreach log error fields, `bounced_at`, `lead.outreach_status=BOUNCED`, and `enrollment.status=BOUNCED`.
- [ ] `last_contacted_at` update test after successful send/engagement.
- [ ] Engagement step tests verify `delivery_status=ENGAGED`, `engagement_action`, no message body, and `last_contacted_at` update.
- [ ] Outreach status transition tests (UNTOUCHED → IN_SEQUENCE → REPLIED).
- [ ] Auto-routing end-to-end test: inbound webhook → lead enriched → auto-enrolled → SSE event.
- [x] `pytest -q`, `npm run lint`, and `npm run build` all pass.

## 8. Phase 6 - Analytics + Polish (Week 6)

### Build Checklist

- [x] Full `AnalyticsMetrics` aggregation service implemented.
- [x] Analytics endpoints complete:
  - [x] overview, funnel, tam, signals, inbound, sequence detail, personalization.
- [x] Clarify overlapping endpoint scopes:
  - [x] `/api/v1/inbound/stats` → operational view (last 30d counts by source/type).
  - [x] `/api/v1/analytics/inbound` → strategic view (includes reply rates, conversion rates).
  - [x] `/api/v1/tam/heatmap` → full cell-level breakdown.
  - [x] `/api/v1/analytics/tam` → summary metrics only.
- [x] `/analytics` page implemented with dashboard/funnel/signal/inbound/sequence/personalization basics plus TAM summary, ICP score histogram, token/cost tracker, and personalization quality trend.
- [x] Seed script creates demo dataset (leads, signals, inbound events, sender profile, drafts, sequences, enrollments).
- [x] End-to-end demo path scripted and reproducible via Docker runbook; backend, frontend build, seed, health, analytics, personalization, and streaming checks validated.
- [x] README updated with architecture diagram and local runbook.
- [ ] Broader pytest coverage added for every service + worker edge case. Targeted Phase 3-5 regression tests now exist; exhaustive worker tests are still useful.
- [x] Playwright smoke tests for all 9 pages.

### Phase 6 Test Gate

- [x] `pytest -q` full suite green.
- [ ] `playwright test` smoke suite green.
- [x] `npm run lint` and `npm run build` green.
- [ ] `docker compose up` demo flow runs without manual patching.
- [ ] Demo checklist validated:
  - [ ] YC import → enrichment → signal → personalization → sequence progression.
  - [ ] Inbound webhook → auto-routing → sequence progression.

## 9. Release Readiness Gate (Must Be Green)

- [ ] All phase gates complete.
- [ ] No schema drift between Alembic head and actual models.
- [ ] No endpoint drift between OpenAPI and frontend clients.
- [ ] No enum value drift between Python enums, SQL defaults, and frontend constants.
- [ ] No blocker-severity bugs in backlog.
- [ ] Worker env vars match backend env vars (all thresholds, API keys, feature flags present).
- [ ] Local setup from clean machine succeeds using README only.
- [ ] Final demo run recorded and repeatable.

## 10. Suggested Daily Execution Cadence

- [ ] Start day: choose one checklist section and define exact acceptance tests first.
- [ ] Mid day: merge only when tests for touched scope are green.
- [ ] End day: update checklist status and note blockers with owner + next action.

## 11. Phase 7 — LLM Rebuild + v1 Reconciliation (Post-merge of `lead-pipeline`)

Source: design-grill conversation (2026-05). 14 decisions resolved, summarized in `memory/MEMORY.md` under "Decisions (2026-05)" — read that index before starting.

This phase converts the deterministic personalization scaffold into a real Gemini-backed LLM agent, reconciles PRD/code drift, closes load-bearing test gates, and polishes the codebase for senior-reviewer scrutiny. PRs are sequenced for a clean critical path: PR 1 unblocks everything; PRs 2 and 3a can run in parallel once PR 1 lands; PRs 3b–3e stack on 3a.

### Phase 7 Conventions (apply to every PR in this section)

- [ ] Branch ≤ 500 net lines or ≤ 5 days of work, whichever is smaller.
- [ ] PR title is one sentence stating user-visible outcome.
- [ ] PR description references the checklist section being closed.
- [ ] Branch off `main`; merge back to `main` after CI green.
- [ ] No silent fallbacks for LLM/safety errors — fail loud, surface in UI as truthful error class.
- [ ] PRD authoritative for interfaces (schemas, endpoints, enums, file structure, agent topology); code authoritative for tuning constants (signal scores, thresholds, retention windows). Source of Truth Index in this checklist Section 0.5 maps tuning constants to file paths.

### PR 1 — Reconciliation + scaffolding (≈ 2 days)

**Goal:** fix known bugs, align PRD to the source-of-truth discipline, scaffold the agent module structure so PRs 3a–3e have somewhere to land.

#### Code fixes
- [ ] Revert `_BASE_SCORES` in `app/services/signals.py` to PRD §3.4.4 values (FUNDING_ROUND=0.90, JOB_CHANGE=0.85, LEADERSHIP_HIRE=0.80, PRODUCT_LAUNCH=0.75, HIRING_SURGE=0.70, JOB_POSTING_ICP_ROLE=0.65, NEWS_MENTION=0.60, TECH_STACK_CHANGE=0.55, LINKEDIN_POST=0.50, CONFERENCE_ATTENDANCE=0.50; PRODUCT_SIGNUP=0.98, WEBSITE_VISIT=0.95 unchanged).
- [ ] Fix `MOCK_SMTP_MODE == "random"` → `"seeded_random"` in `app/services/sequences.py:417`.
- [ ] Reconcile `NEGATIVE_KEYWORDS` constant to PRD §3.5.3 Node 4 list (10 phrases): "I came across your profile", "hope this finds you well", "I wanted to reach out", "synergy", "quick call", "touch base", "circle back", "leverage", "at the end of the day", "game changer".
- [ ] Decouple embedding generation from `USE_MOCK_ENRICHMENT` in `app/services/enrichment.py:208` — embedding provider is independent; route via `EMBEDDING_PROVIDER` only.
- [ ] Migrate `SenderProfile` JSONB shapes from `list[str]` to `list[dict]` per PRD §3.5.1 (`education: list[{school, degree, grad_year}]`, `past_employers: list[{company, role, from_year, to_year}]`). Update model, schema, frontend `/sender` form, seed.
- [ ] Replace hardcoded enum strings (`"COMPLETE"`, `"REPLIED"`) with enum-value references across `app/services/analytics.py`, `app/services/signals.py`.

#### Agent module scaffolding
- [ ] Create `app/agents/golden_snippet/` with skeleton files: `graph.py`, `nodes.py`, `state.py`, `schemas.py`, `prompts.py`, `gemini_client.py`. Existing `app/agents/personalization_graph.py` stays for now; PR 3a swaps the import.
- [ ] `prompts.py` populated with `NEGATIVE_KEYWORDS` constant only; prompt templates land in PR 3b–3d.

#### Doc edits
- [ ] Add **Section 0.5 — Source of Truth Index** at top of this checklist mapping tuning constants to file paths. Required entries: signal base scores → `app/services/signals.py:_BASE_SCORES`, negative keywords → `app/agents/golden_snippet/prompts.py:NEGATIVE_KEYWORDS`, mock SMTP outcomes → `app/services/sequences.py:_mock_delivery_outcome`, enrichment thresholds → `app/config.py`.
- [ ] Edit PRD §3.4.4: replace base-score table with paragraph pointing at `app/services/signals.py:_BASE_SCORES`.
- [ ] Edit PRD §3.5.3 Node 4: replace negative-keyword list with pointer to `app/agents/golden_snippet/prompts.py:NEGATIVE_KEYWORDS`.
- [ ] Edit PRD §3.6.2: replace mock outcome rules with pointer to `app/services/sequences.py:_mock_delivery_outcome`; values `deterministic | seeded_random` remain authoritative as the interface.
- [ ] Edit PRD §6 file structure: replace `agents/golden_snippet/{graph,nodes,commonalities,state,prompts}.py` with `{graph, nodes, state, schemas, prompts, gemini_client}.py`. Remove `commonalities.py` (Node 1.5 is one function, lives in `nodes.py`).
- [ ] Edit PRD §4.3.1: extend SSE event union with 5 agent events (`agent.node.start`, `agent.node.complete`, `agent.commonality.found`, `agent.signal.selected`, `agent.critique.complete`).

#### Tests
- [ ] SSE contract test — assert `backend/app/schemas/events.py` event union exactly matches `frontend/src/lib/events/types.ts`. Test fails if either drifts.
- [ ] Unit test for `_mock_delivery_outcome` covering both `deterministic` and `seeded_random` modes (catches the regression that was just fixed).
- [ ] Audit-fix any test that currently asserts the old signal-score values.

#### Acceptance gate
- [ ] `pytest -q` green.
- [ ] `npm run lint` and `npm run build` green.
- [ ] PRD diff is reviewable on its own (no value duplication, all pointers resolve).
- [ ] Seed script runs without error against the new `SenderProfile` shape.

### PR 2 — Demo seed redesign (≈ 2 days, parallel with PR 1)

**Goal:** replace the placeholder seed with a three-tier curated dataset that gives the LLM real material to reason about during the live demo.

- [ ] **Tier A — 3 hand-crafted demo leads.** Maya Rao @ GrowthLoop (primary; past at Stripe 2019-2021, MIT MBA 2018, hand-crafted `enriched_data`). Noah Kim @ DevSignal (commonality via YC Demo Day W23 conference). Elena Park @ ReplyPath (commonality via SF + trail running).
- [ ] **Sender Avery Chen** rewritten with PRD's `list[dict]` shape: education `[{school: MIT, degree: BS CS, grad_year: 2015}]`; past_employers `[{company: Stripe, role: Software Engineer, from_year: 2019, to_year: 2021}]`; conferences `[{name: "YC Demo Day", batch: "W23"}]`; cities/hobbies populated to overlap with each demo lead on a distinct axis.
- [ ] **Hand-crafted signals for Tier A leads** — bypass `run_mock_signal_scan` for these. Maya: `FUNDING_ROUND` "GrowthLoop raised $24M Series B led by Sequoia" with body referencing infrastructure scaling. Noah: `LEADERSHIP_HIRE` "DevSignal hires former Datadog VP". Elena: `HIRING_SURGE` "ReplyPath opens 8 GTM roles".
- [ ] **Tier B — 30-50 filler leads.** Generated from a name corpus + seeded random. Industry distribution covers 8-12 TAM heatmap cells. Mock-enriched as today.
- [ ] **Tier C — 3-5 outcome leads.** Pre-populate `outreach_logs` with realistic timestamps so analytics page shows non-zero reply rate (~20%), bounce rate (~5%), and step-distribution histogram. Rename `bounce.test`/`reply.test` to `nonexistent-domain.example`/`mock-replier.example` so the leads don't read as obvious fixtures.
- [ ] **Mock signal scanner** updated to emit all 12 `SignalType` values, not just 4 — round-robin or hash-based across the type list.
- [ ] **Eval-harness fixture** (used by PR 4) extracted from this seed: 10 leads (3 Tier A + 7 representative Tier B) with metadata declaring expected commonality axis per lead.

#### Acceptance gate
- [ ] `uv run python scripts/seed_demo.py` produces deterministic output (re-running yields no new rows).
- [ ] TAM heatmap shows ≥ 8 populated cells.
- [ ] Analytics page shows non-zero reply rate, bounce rate, and a 5-7 step funnel.
- [ ] No URL-like or quoted-block content > 30 chars in any Tier A `enriched_data` (avoids tripping output guards in PR 3d).

### PR 3a — Pydantic schemas + Gemini client + USE_MOCK_LLM toggle (≈ 2 days)

**Goal:** establish the type contract and provider boundary that PRs 3b–3e build on.

- [ ] `app/agents/golden_snippet/schemas.py`: Pydantic models `CommonalityOutput`, `DraftMetadata` (Node 4a), `DraftBody` (Node 4b), `DraftOutput` (assembled), `CritiqueOutput`. Field-level descriptions encode PRD strength rubrics.
- [ ] `app/agents/golden_snippet/gemini_client.py`: async wrapper around `google-genai` SDK. Methods: `generate_structured(model, prompt, schema)` returns Pydantic instance; `stream_text(model, prompt, max_tokens)` async iterator over text chunks. Honors `USE_MOCK_LLM` env var.
- [ ] Random-nonce delimiter helper: `wrap_user_data(payload: str) -> tuple[str, str]` returns `(wrapped, nonce)`. System prompts reference the nonce literally.
- [ ] Per-call timeouts: 2.5s for Nodes 1.5/4a/5; 5s for Node 4b streaming.
- [ ] Error class hierarchy: `LLMTimeout`, `LLMSafetyBlocked`, `LLMSchemaInvalid`. Surfaced unchanged to UI per the fail-loud rule.
- [ ] Configuration additions to `app/config.py`: `USE_MOCK_LLM` (default false in prod, true in tests), `LLM_JUDGE_MODEL` (gemini-2.5-pro for eval).
- [ ] `app/agents/golden_snippet/state.py`: `PersonalizationState` TypedDict using the Pydantic types from `schemas.py`. Replaces the loosely-typed dict in current `personalization_graph.py`.
- [ ] Deterministic stubs (one per LLM node) returning Pydantic instances of the right shape. Activated when `USE_MOCK_LLM=true`. CI uses these.

#### Tests
- [ ] Unit test: each schema accepts valid examples + rejects invalid ones (extra keys, wrong types).
- [ ] Unit test: `gemini_client.stream_text` propagates timeouts as `LLMTimeout`.
- [ ] Unit test: `wrap_user_data` produces unguessable nonces (>= 8 chars, alphanumeric, distinct across calls).

### PR 3b — Node 1.5 commonality matcher LLM (≈ 1.5 days)

- [ ] Replace deterministic `match_commonality` set-intersection with Gemini call using `CommonalityOutput` schema.
- [ ] System prompt in `prompts.py:COMMONALITY_SYSTEM` includes PRD §3.5.3's "non-trivial" guidance and the random-nonce delimiter pattern.
- [ ] Node skips gracefully when `SenderProfile` is None (returns `CommonalityOutput(strongest_hook=None, hook_strength=0.0)`).
- [ ] Fires `agent.commonality.found` SSE event when `hook_strength >= 6`.
- [ ] Tests: deterministic fixture for Maya produces hook mentioning Stripe; no-sender path returns null hook.

### PR 3c — Node 4 split (4a + 4b) with Redis Pub/Sub streaming (≈ 3 days)

- [ ] Node 4a: `gemini_client.generate_structured(DraftMetadata)` for `subject_line` + `linkedin_message`.
- [ ] Node 4b: `gemini_client.stream_text` for `email_body`. Worker publishes each chunk to Redis channel `sse:{draft_id}` as `draft.partial` event.
- [ ] SSE endpoint `GET /api/v1/events/stream` subscribes to Redis Pub/Sub for connected drafts and relays.
- [ ] Rewrite-loop reruns Node 4b only; 4a output cached in graph state.
- [ ] Negative-keyword enforcement runs on assembled `DraftOutput` post-stream.
- [ ] `/compose` page: subject + linkedin appear after 4a; body textarea fills word-by-word from `draft.partial` events.

### PR 3d — Node 5 critique LLM + output guards (≈ 2 days)

- [ ] Node 5: `gemini_client.generate_structured(CritiqueOutput)` with PRD's 5 dimensions.
- [ ] Rewrite cap reduced from 3 to 2 in `_should_rewrite`.
- [ ] Output safety guard: scan assembled draft for URLs not in sender allowlist, quoted blocks > 30 chars from `lead.enriched_data`, known-bad-domain references. On guard fire: raise `OutputGuardFired` (new error class), surface in UI as "draft blocked by safety guard."
- [ ] Tests: critique returns valid 5-axis scores; rewrite triggers when avg < 7.0; rewrite cap 2; guard fires on synthetic injection payloads (URL in body, sender-data exfil pattern).

### PR 3e — Per-node SSE progress events + /compose UI sidebar (≈ 1.5 days)

- [ ] Each LangGraph node emits `agent.node.start` and `agent.node.complete` to `sse:{draft_id}` with elapsed_ms + summary.
- [ ] Node 1.5 also emits `agent.commonality.found` with hook + strength.
- [ ] Node 2 emits `agent.signal.selected` with signal_id + title.
- [ ] Node 5 emits `agent.critique.complete` with score + breakdown + iteration.
- [ ] `/compose` page: right-side panel renders a step-list with checkmarks, elapsed times, and the "moat moment" callout when `agent.commonality.found` fires.
- [ ] Error UI states distinguishing `LLMTimeout` / `LLMSafetyBlocked` / `LLMSchemaInvalid` / `OutputGuardFired` with class-specific copy and retry affordance.

### PR 4 — Eval harness (≈ 2 days)

- [ ] `eval/fixtures.py` — 10 leads (3 Tier A + 7 Tier B from PR 2 seed) with expected commonality-axis metadata.
- [ ] `eval/assertions.py` — per-lead must-pass checks. Maya: draft body mentions "Stripe" and "Series B" or "funding". Noah: mentions "YC". Elena: mentions "trail" or "running". Tier B: looser checks (length 30-80 words, subject ≤ 8 words, no `NEGATIVE_KEYWORDS` phrases).
- [ ] `eval/llm_judge.py` — rank-based comparison using `gemini-2.5-pro`. Compares each new prompt's output against the previously-merged baseline; reports win rate.
- [ ] `eval/runner.py` — `uv run python -m eval.runner` runs all fixtures through the live LLM graph, persists output to `eval/runs/{git-sha}.jsonl` + summary `eval/runs/{git-sha}.md`.
- [ ] CI workflow (GitHub Actions) `paths-filter` triggers on changes to `app/agents/golden_snippet/prompts.py` or `app/agents/golden_snippet/nodes.py`. Assertion failures block merge. LLM-judge win rate < 60% warns but doesn't block.
- [ ] Doc: `eval/README.md` explains how to run locally, how to update baselines.

### PR 5 — Test debt closure: Tier 1 + Tier 2 + audit (≈ 4 days)

#### Tier 1 (must close — catches real bugs)
- [ ] Signal scoring formula test (base + 4 modifiers + cap at 1.0) covering each modifier independently and in combination.
- [ ] Concurrent duplicate webhook test verifying `(source, source_event_id)` partial unique constraint under threading.
- [ ] Channel/StepType validation 422 tests — 4 PATCH-validation edge cases.
- [ ] Sequence reactivation skip-terminal test — BOUNCED/REPLIED/UNSUBSCRIBED/COMPLETED never resumed.
- [ ] Bounce delivery test — `outreach_logs.error_code/error_message`, `bounced_at`, `lead.outreach_status=BOUNCED`, `enrollment.status=BOUNCED`.
- [ ] Reply-stop test — enrollment halts on reply, no further steps executed.

#### Tier 2 (should close — contract drift)
- [ ] Source-specific parser fingerprint tests (Clerk, Stripe, LinkedIn Ads, Google Ads, manual) per PRD §3.2.3 fingerprint contract.
- [ ] Inbound retry idempotency test (different from concurrent test) — retry produces same lead, no duplicates, partial-failure-resume works.
- [ ] Personalization with no SenderProfile test — Node 1.5 skip path produces null hook; Node 4 falls back to signal opening.

#### Audit existing `[x]` test claims
- [ ] Read every `[x]`-marked test claim in Sections 2–8 and verify the test exists and exercises what it claims.
- [ ] Replace `test_phase4_personalization.py` deterministic-template tests with tests against `USE_MOCK_LLM=true` deterministic stubs (still covers shape; eval harness covers real LLM path).
- [ ] Document any audit-found gaps as new unchecked items in this section.

#### Acceptance gate
- [ ] `pytest -q` full suite green; coverage report does not regress vs main.
- [ ] No flaky tests added (each new test runs 5x in CI without intermittent failure).

### PR 6 — Frontend componentization (≈ 2-3 days)

**Goal:** decompose 277-512 line page files into PRD §6's prescribed component structure.

- [ ] `components/LeadCard.tsx` — extracted from `app/leads/page.tsx`.
- [ ] `components/LeadDetailDrawer.tsx` — drawer logic from `app/leads/page.tsx`.
- [ ] `components/SignalCard.tsx`, `components/InboundEventCard.tsx` — extracted from `app/feed/page.tsx`.
- [ ] `components/CommonalityPanel.tsx` — new for `/compose`, renders the moat-moment callout.
- [ ] `components/TAMHeatmap.tsx` — extracted from `app/tam/page.tsx`.
- [ ] `components/DraftViewer.tsx` — streaming-text textarea + critique radar wrapper.
- [ ] `components/FunnelChart.tsx` — extracted from `app/analytics/page.tsx`.
- [ ] `components/QualityRadar.tsx` — Recharts `RadarChart` for Node 5 critique scores.
- [ ] `hooks/useLeads.ts`, `useSignals.ts`, `useInbound.ts`, `useTAM.ts`, `useSSE.ts` — TanStack Query hooks lifted out of pages.
- [ ] `/analytics` page: add "draft generation errors by type" tile pulling from new analytics endpoint.

#### Acceptance gate
- [ ] `npm run lint` and `npm run build` green.
- [ ] No page file exceeds 250 lines after extraction.
- [ ] Visual diff vs main: zero changes (refactor only, no UX changes).

### PR 7 — Polish + reviewer-walk readiness (≈ 2 days)

- [ ] README rewrite: 1-paragraph project pitch, Mermaid architecture diagram, local runbook (`docker compose up`, `uv run python scripts/seed_demo.py`, demo URL), "where to start reading" section pointing reviewers at `app/agents/golden_snippet/graph.py` → `prompts.py` → `eval/` → `scripts/seed_demo.py`.
- [ ] Demo script: `docs/demo-script.md` — ordered click-path with expected screen state at each step, 1-2 fallback paths if Gemini errors mid-demo.
- [ ] Playwright smoke tests for all 9 pages (Phase 6 close-out item, deferred until now because page files were churning).
- [ ] Final sweep: search for `TODO`, `FIXME`, `XXX` comments — resolve or document.

#### Acceptance gate
- [ ] `playwright test` green.
- [ ] README's runbook works on a clean clone (verify against fresh `git clone`).
- [ ] Demo script runs end-to-end without ad-hoc patches.

### Phase 7 Definition of Done

- [ ] All 11 PRs merged to `main`.
- [ ] Eval harness passing on main; LLM-judge win rate stable or improving.
- [ ] Live demo runs end-to-end with zero error-state surfaces during the curated path.
- [ ] PRD §3.5, §3.6, §4.3 reflect the as-built system; Source of Truth Index in this checklist resolves all tuning-constant pointers.
- [ ] `MEMORY.md` updated with any feedback/project memories surfaced during implementation.
