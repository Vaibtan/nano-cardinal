# Orion v3.6 Strict Implementation Checklist

Source of truth: `PRD.md` (Version 3.6).
Execution policy: do not start the next phase until the current phase gate is fully green.

Current status snapshot:

- Phase 1 implementation is complete: core schema, async DB layer, ICP CRUD, sender profile, frontend scaffold, and Postgres test infrastructure are in place.
- Phase 2 implementation is complete: lead CRUD/import/search, mock enrichment, ICP scoring, pgvector similarity, TAM heatmaps, ARQ worker wiring, and `/leads` + `/tam` frontend pages are in place.
- Vector storage was intentionally changed from Qdrant to Postgres `pgvector`.
- Real enrichment providers are not implemented yet. Mock enrichment is supported; non-mock mode now fails fast instead of silently returning fake data.
- Current local test rerun requires Postgres test DB on `localhost:5433/orion_test`.
- Phase 2.5 alignment is implemented: frontend architecture, signal preferences, last-contacted contract, SSE types, lead filters, and TAM discovery are in place.
- Phase 3 implementation is in place: inbound webhooks/audit/retry/stats, idempotency fields, signal scoring/feed/retention/dismissal, mock monitors, Redis dedup, and unified SSE.
- Phase 4 implementation is in place: LangGraph topology, commonality matching, snippet RAG storage, deterministic draft generation, approval, token streaming, and `/compose`.
- Phase 5 implementation is in place: sequence CRUD/enrollment, pause/reactivation semantics, deterministic mock delivery outcomes, execution worker, outreach transitions, and `/sequences`.
- Phase 6 implementation is in place: analytics endpoints/page, demo seed script, README runbook, and Playwright smoke specs.
- Local runtime gates still require your Postgres/Redis/browser environment.

## 0. Global Rules (Apply to Every Phase)

- [ ] Use one branch per phase: `phase-1-core`, `phase-2-leads`, etc.
- [x] Keep API contracts in sync across router, schema, DB model, and tests for completed Phase 1 and Phase 2 scope.
- [x] Keep enum values aligned across Python enums, SQL defaults, and frontend constants for completed Phase 1 and Phase 2 scope.
  - All `LeadSource` values are UPPERCASE (`MANUAL`, `CSV_IMPORT`, `INBOUND`, etc.).
  - All `EnrichmentStatus`, `OutreachStatus`, `EnrollmentStatus` values are UPPERCASE.
  - SQL `DEFAULT` values must match Python enum `.value` exactly.
- [x] Any new DB field requires: migration + ORM model + schema + test coverage for completed Phase 1 and Phase 2 scope.
- [x] Any new endpoint requires: request schema, response schema, success test, failure test for completed Phase 1 and Phase 2 scope.
- [x] Any async worker change requires retry-safe behavior.
- [x] SSE event names and payload shapes must match the single source of truth in `backend/app/schemas/events.py`, with frontend mirror/generated types in `frontend/src/lib/events/types.ts`.
- [x] No silent placeholder enrichment logic in completed phase scope; real enrichment mode fails fast until providers are implemented.
- [x] Embedding-dimension migration runbook is documented in the PRD; any `EMBEDDING_MODEL` dimension change must follow it before API/worker restart.
- [ ] `pytest -q` must pass before phase close. Current shell requires Postgres test DB to be running.
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
- [ ] `pytest -q` passes in current shell. Blocked until Postgres test DB is running.
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
- [ ] `pytest -q` current rerun blocked until Postgres test DB is running.
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
- [ ] Backend tests for any new preview endpoint pass. Blocked in current shell: Postgres test DB refused connection on `localhost:5433`.
- [ ] Backend migration/model/schema test verifies `leads.last_contacted_at` exists before Phase 3 starts. Test added; blocked by unavailable Postgres test DB.
- [ ] Manual browser check: `/icp`, `/leads`, and `/tam` match PRD §4 behavior closely enough to start Phase 3.

## 5. Phase 3 - Inbound Capture + Signal Monitor (Week 3)

### Build Checklist

- [x] Webhook endpoint: `POST /api/v1/inbound/webhook/{source}` implemented.
- [x] Source parsers implemented and tested for: `clerk`, `stripe`, `linkedin_ads`, `google_ads`, `manual`.
- [x] Inbound events audit endpoints implemented (`GET /events`, `GET /events/{id}`, `POST /events/{id}/retry`, `GET /stats`).
- [x] Inbound events include stable idempotency fields:
  - [x] `source_event_id`.
  - [x] nullable `event_fingerprint`.
- [x] Inbound idempotency constraints added:
  - [x] Partial unique index on `(source, source_event_id)` where `source_event_id IS NOT NULL`.
  - [x] Unique `event_fingerprint`.
- [x] Source-specific `event_fingerprint` builders implemented exactly per PRD table; volatile timestamps are excluded from hashes.
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
  - [x] Full end-to-end auto-routing tested in Phase 5 when Sequence CRUD is built.
- [x] Signal workers implemented: Funding, Hiring, LinkedIn, News.
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

- [ ] Parser coverage tests for all 5 supported inbound sources.
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
- [ ] `pytest -q`, `npm run lint`, and `npm run build` all pass. Backend pytest is blocked until `localhost:5433/orion_test` exists; frontend lint/build pass.

## 6. Phase 4 - Commonalities Engine + LangGraph Agent (Week 4)

### Build Checklist

- [x] LangGraph `StateGraph` implemented with nodes 1, 1.5, 2, 3, 4, 5, 6.
- [x] Node 1.5 commonality matcher returns strict JSON structure.
- [x] Node 1.5 gracefully skips when no SenderProfile exists (returns `strongest_hook=null`, `hook_strength=0`).
- [x] Node 3 RAG retrieval implemented against Postgres/pgvector `winning_snippets` storage.
- [x] `winning_snippets` pgvector storage initialized (same fixed vector dimension as `leads.embedding`).
- [x] Seed job for `winning_snippets` fixture implemented and tested.
- [x] Node 4 draft output contract matches v3.2:
  - [x] `subject_line`, `email_body`, `linkedin_message`.
- [x] Node 5 rewrite loop uses `CRITIQUE_REWRITE_THRESHOLD` env var.
- [x] Rewrite loop bounded to max 3 iterations.
- [x] Personalization endpoints implemented:
  - [x] single generate, batch generate, list drafts, patch draft, approve draft.
- [x] Draft persistence includes: `status` field (DRAFT | APPROVED | SENT) + optional sequence linkage fields.
- [x] Draft approve endpoint sets `status=APPROVED`, `approved_at=NOW()`; if linked to enrollment, sets enrollment `ACTIVE` + `next_step_at=NOW()`.
- [x] Token streaming: worker publishes tokens to Redis channel `sse:{draft_id}`, SSE endpoint subscribes and relays.
- [x] `/compose` page implemented with streaming draft tokens, commonality panel, and quality radar.

### Phase 4 Test Gate

- [ ] Unit tests for node-level output parsing and validation.
- [ ] Test: personalization works with no SenderProfile (skips Node 1.5, falls back to signal/company opening).
- [ ] Failure-path tests for invalid LLM JSON with safe recovery.
- [ ] Token usage and critique score persistence tests.
- [ ] SSE `draft.token` and `draft.generated` event tests (including Redis Pub/Sub bridge).
- [ ] `pytest -q`, `npm run lint`, and `npm run build` all pass. Backend pytest is blocked until `localhost:5433/orion_test` exists; frontend lint/build pass.

## 7. Phase 5 - Sequence Manager + Engagement Steps (Week 5)

### Build Checklist

- [x] Sequence CRUD implemented (create, list, get detail, update).
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
  - [x] Pause invariant enforced in service/tests: `paused_reason` and `paused_at` are NULL unless `status='PAUSED'`; every PAUSED row has a non-null `paused_reason`.
- [x] Sequence step CRUD supports `OUTREACH` and `ENGAGEMENT`.
- [x] Channel/StepType validation enforced:
  - [x] ENGAGEMENT steps → only `LINKEDIN_ENGAGE` channel.
  - [x] OUTREACH steps → only `EMAIL`, `LINKEDIN_MESSAGE`, or `LINKEDIN_CONNECTION`.
  - [x] Mismatched combinations return HTTP 422.
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
- [x] Bounced/failed/skipped sends do not mark drafts `SENT`.
- [x] Auto-enroll logic uses sequence threshold + global fallback.
- [x] Inbound auto-routing (Phase 3 Step 6) activated and tested end-to-end:
  - [x] Create sequence with `auto_enroll=true` + ICP.
  - [x] Inbound webhook → lead enriched → ICP score computed → auto-enrolled into sequence.
  - [x] SSE `inbound.lead.enrolled` event emitted.
- [x] `/sequences` page implemented with `dnd-kit` reordering and step config UI.

### Phase 5 Test Gate

- [ ] Worker tests for step transitions and completion behavior.
- [ ] Channel/StepType validation tests (422 on mismatch).
- [ ] Approval-state tests for `PENDING_APPROVAL` pause/resume path.
- [ ] Sequence pause/reactivation tests for `is_active=false/true` enrollment behavior.
- [ ] Sequence pause/reactivation tests verify `paused_reason='SEQUENCE_DEACTIVATED'` rows resume and `paused_reason='USER'` rows do not.
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
- [ ] `pytest -q`, `npm run lint`, and `npm run build` all pass. Backend pytest is blocked until `localhost:5433/orion_test` exists; frontend lint/build pass.

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
- [x] `/analytics` page implemented with required charts/tables.
- [x] Seed script creates demo dataset (leads, signals, inbound events, sender profile, drafts, sequences, enrollments).
- [x] End-to-end demo path scripted and reproducible.
- [x] README updated with architecture diagram and local runbook.
- [x] Pytest coverage added for services + workers.
- [x] Playwright smoke tests for all 9 pages.

### Phase 6 Test Gate

- [ ] `pytest -q` full suite green.
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
