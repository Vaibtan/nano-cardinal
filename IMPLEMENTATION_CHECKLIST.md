# Orion v3.2 Strict Implementation Checklist

Source of truth: `PRD.md` (Version 3.2).
Execution policy: do not start the next phase until the current phase gate is fully green.

## 0. Global Rules (Apply to Every Phase)

- [ ] Use one branch per phase: `phase-1-core`, `phase-2-leads`, etc.
- [ ] Keep API contracts in sync across router, schema, DB model, and tests.
- [ ] Keep enum values aligned across Python enums, SQL defaults, and frontend constants.
  - All `LeadSource` values are UPPERCASE (`MANUAL`, `CSV_IMPORT`, `INBOUND`, etc.).
  - All `EnrichmentStatus`, `OutreachStatus`, `EnrollmentStatus` values are UPPERCASE.
  - SQL `DEFAULT` values must match Python enum `.value` exactly.
- [ ] Any new DB field requires: migration + ORM model + schema + test coverage.
- [ ] Any new endpoint requires: request schema, response schema, success test, failure test.
- [ ] Any async worker change requires idempotency checks and retry-safe behavior.
- [ ] SSE event names and payload shapes must match frontend type definitions.
- [ ] No unresolved `TODO`, `TBD`, or placeholder parser logic in completed phase scope.
- [ ] `pytest -q` must pass before phase close.
- [ ] Frontend `npm run lint` and `npm run build` must pass before phase close.
- [ ] Circular FK between `leads ↔ inbound_events` handled via SQLAlchemy `relationship(post_update=True)`.

## 1. Definition of Done (Per Phase)

- [ ] All checklist items in the phase are complete.
- [ ] Phase-specific tests pass.
- [ ] API surface for that phase is documented in OpenAPI and matches PRD.
- [ ] Developer runbook for that phase is updated (commands + env vars).
- [ ] Demo path for that phase works locally via Docker Compose.

## 2. Phase 1 - Core Data Layer + Sender Profile (Week 1)

### Build Checklist

- [ ] Docker Compose services run: `postgres`, `redis`, `qdrant`, `backend`, `worker`, `frontend`.
- [ ] Docker Compose has no deprecated `version` key.
- [ ] Health checks exist and fail fast on bad dependencies.
- [ ] SQLAlchemy async setup complete.
- [ ] Alembic baseline migration created and applies cleanly.
- [ ] Core schema implemented with v3.2 corrected fields:
  - [ ] `leads.company_name` nullable.
  - [ ] `leads.icp_score_breakdown` JSONB.
  - [ ] `leads.updated_at` TIMESTAMPTZ DEFAULT NOW().
  - [ ] `leads.source` DEFAULT `'MANUAL'` (uppercase, matching `LeadSource.MANUAL` enum value).
  - [ ] `sequence_steps.requires_approval` boolean.
  - [ ] `lead_sequence_enrollments.next_step_at` not null default `NOW()`.
  - [ ] `personalization_drafts.sequence_id`, `sequence_step_id`, `enrollment_id` + FK constraints.
  - [ ] Circular FK `leads.inbound_event_id → inbound_events(id)` created via ALTER TABLE.
  - [ ] Circular FK note in ORM: use `relationship(post_update=True)`.
- [ ] All indexes from PRD schema applied, including `idx_leads_updated_at` and `idx_drafts_enrollment_id`.
- [ ] FastAPI app scaffold with router registration and CORS.
- [ ] `config.py` includes: `EMBEDDING_PROVIDER`, `CRITIQUE_REWRITE_THRESHOLD`, `BUILTWITH_API_KEY`, and all threshold env vars.
- [ ] ICP CRUD endpoints complete.
- [ ] Sender profile create/update/get endpoints complete.
- [ ] Frontend Next.js App Router scaffold complete.
- [ ] `/icp` page implemented (wizard shell + form validation).
- [ ] `/sender` page implemented (dynamic arrays + save flow).

### Phase 1 Test Gate

- [ ] `docker compose up -d` succeeds with all services healthy.
- [ ] `alembic upgrade head` succeeds on clean DB.
- [ ] `pytest -q` includes passing API tests for ICP and sender routes.
- [ ] Verify: `leads.source` SQL default matches `LeadSource.MANUAL` Python enum value (both UPPERCASE).
- [ ] `npm run lint` passes.
- [ ] `npm run build` passes.

## 3. Phase 2 - Lead Pipeline + TAM Mapping (Week 2)

### Build Checklist

- [ ] Lead CRUD endpoints implemented (create, list, get, delete).
- [ ] `GET /api/v1/leads/{id}/outreach` endpoint returns outreach history from `outreach_logs`.
- [ ] CSV import endpoint implemented with validation and row-level error reporting.
- [ ] YC import endpoint implemented (mock fixture mode supported).
- [ ] `GET /api/v1/leads/search?q=` semantic search endpoint implemented.
- [ ] ARQ worker configuration implemented (`WorkerSettings`, queue wiring).
- [ ] Enrichment pipeline implemented (6 steps from PRD).
- [ ] Enrichment status lifecycle enforced: `PENDING -> RUNNING -> COMPLETE/FAILED`.
- [ ] `leads.updated_at` set on every enrichment/scoring update.
- [ ] Qdrant `leads` collection initialization implemented (vector dim from `EMBEDDING_MODEL`, distance: Cosine).
- [ ] Embedding generation uses `EMBEDDING_PROVIDER` + `EMBEDDING_MODEL` config (supports gemini/openai/ollama).
- [ ] ICP scoring computes against all active ICPs.
- [ ] Best ICP persisted to `leads.icp_id` + `leads.icp_score`.
- [ ] Optional full score map persisted to `leads.icp_score_breakdown`.
- [ ] TAM heatmap endpoint implemented.
- [ ] TAM whitespace endpoint implemented.
- [ ] `/leads` page implemented with filtering and status badges.
- [ ] `/tam` page implemented with heatmap and whitespace action UI.

### Phase 2 Test Gate

- [ ] Unit tests for enrichment step functions (mock mode).
- [ ] Integration tests for lead import + enrichment job enqueue.
- [ ] TAM aggregation tests with deterministic fixtures.
- [ ] Semantic similarity endpoint test (`/api/v1/leads/{id}/similar`).
- [ ] Semantic search endpoint test (`/api/v1/leads/search?q=`).
- [ ] `pytest -q`, `npm run lint`, and `npm run build` all pass.

## 4. Phase 3 - Inbound Capture + Signal Monitor (Week 3)

### Build Checklist

- [ ] Webhook endpoint: `POST /api/v1/inbound/webhook/{source}` implemented.
- [ ] Source parsers implemented and tested for: `clerk`, `stripe`, `linkedin_ads`, `google_ads`, `manual`.
- [ ] Inbound events audit endpoints implemented (`GET /events`, `GET /events/{id}`, `POST /events/{id}/retry`, `GET /stats`).
- [ ] Inbound worker pipeline implemented (Steps 1-5):
  - [ ] store event → extract identity → dedup → lead create/link → enrichment trigger.
- [ ] Lead creation from inbound sets `source='INBOUND'` and `inbound_event_id`.
- [ ] Inbound auto-routing (Step 6) implemented as graceful no-op when no matching sequences exist.
  - [ ] Queries sequences with `auto_enroll=true AND icp_id matching`.
  - [ ] Full end-to-end auto-routing tested in Phase 5 when Sequence CRUD is built.
- [ ] Signal workers implemented: Funding, Hiring, LinkedIn, News.
- [ ] Signal strength scoring formula implemented (base score + modifiers):
  - [ ] Base scores per signal type (PRODUCT_SIGNUP: 0.98, WEBSITE_VISIT: 0.95, etc.).
  - [ ] Recency boost (×1.2 if within 48h).
  - [ ] ICP score boost (×1.1 if icp_score > 80).
  - [ ] Cool-off penalty (×0.8 if contacted in last 30 days, via outreach_logs query).
  - [ ] Final score capped at 1.0.
- [ ] Inbound-to-signal bridge mappings implemented:
  - [ ] `PRODUCT_SIGNUP` → `PRODUCT_SIGNUP`.
  - [ ] `AD_CLICK` / `WEBSITE_OPT_IN` → `WEBSITE_VISIT`.
  - [ ] `CONFERENCE_REGISTRATION` → `CONFERENCE_ATTENDANCE`.
- [ ] Redis dedup implemented with SHA256 hash + 7-day TTL.
- [ ] Unified SSE endpoint implemented: `GET /api/v1/events/stream` with Redis Pub/Sub bridge.
- [ ] Signals filtered view supported: `GET /api/v1/events/stream?topic=signals`.
- [ ] Signal dismiss endpoint (`DELETE /api/v1/signals/{id}`) is soft-delete (sets `is_read=true`, excluded from feed).
- [ ] `/feed` page implemented with inbound + signal cards and live updates.

### Phase 3 Test Gate

- [ ] Parser coverage tests for all 5 supported inbound sources.
- [ ] Idempotency tests for inbound retry and signal dedup.
- [ ] Signal strength scoring formula tests (base + all 3 modifiers + cap at 1.0).
- [ ] SSE contract tests for event types and payload schema.
- [ ] End-to-end test: inbound webhook → lead enriched (auto-routing is no-op without sequences).
- [ ] `pytest -q`, `npm run lint`, and `npm run build` all pass.

## 5. Phase 4 - Commonalities Engine + LangGraph Agent (Week 4)

### Build Checklist

- [ ] LangGraph `StateGraph` implemented with nodes 1, 1.5, 2, 3, 4, 5, 6.
- [ ] Node 1.5 commonality matcher returns strict JSON structure.
- [ ] Node 1.5 gracefully skips when no SenderProfile exists (returns `strongest_hook=null`, `hook_strength=0`).
- [ ] Node 3 RAG retrieval implemented against `winning_snippets` collection.
- [ ] Qdrant `winning_snippets` collection initialized (same vector dim/distance as `leads` collection).
- [ ] Seed job for `winning_snippets` fixture implemented and tested.
- [ ] Node 4 draft output contract matches v3.2:
  - [ ] `subject_line`, `email_body`, `linkedin_message`.
- [ ] Node 5 rewrite loop uses `CRITIQUE_REWRITE_THRESHOLD` env var.
- [ ] Rewrite loop bounded to max 3 iterations.
- [ ] Personalization endpoints implemented:
  - [ ] single generate, batch generate, list drafts, patch draft, approve draft.
- [ ] Draft persistence includes: `status` field (DRAFT | APPROVED | SENT) + optional sequence linkage fields.
- [ ] Draft approve endpoint sets `status=APPROVED`, `approved_at=NOW()`; if linked to enrollment, sets enrollment `ACTIVE` + `next_step_at=NOW()`.
- [ ] Token streaming: worker publishes tokens to Redis channel `sse:{draft_id}`, SSE endpoint subscribes and relays.
- [ ] `/compose` page implemented with streaming draft tokens, commonality panel, and quality radar.

### Phase 4 Test Gate

- [ ] Unit tests for node-level output parsing and validation.
- [ ] Test: personalization works with no SenderProfile (skips Node 1.5, falls back to signal/company opening).
- [ ] Failure-path tests for invalid LLM JSON with safe recovery.
- [ ] Token usage and critique score persistence tests.
- [ ] SSE `draft.token` and `draft.generated` event tests (including Redis Pub/Sub bridge).
- [ ] `pytest -q`, `npm run lint`, and `npm run build` all pass.

## 6. Phase 5 - Sequence Manager + Engagement Steps (Week 5)

### Build Checklist

- [ ] Sequence CRUD implemented (create, list, get detail, update).
- [ ] Sequence step CRUD supports `OUTREACH` and `ENGAGEMENT`.
- [ ] Channel/StepType validation enforced:
  - [ ] ENGAGEMENT steps → only `LINKEDIN_ENGAGE` channel.
  - [ ] OUTREACH steps → only `EMAIL`, `LINKEDIN_MESSAGE`, or `LINKEDIN_CONNECTION`.
  - [ ] Mismatched combinations return HTTP 422.
- [ ] `LINKEDIN_ENGAGE` channel behavior implemented (log engagement action, no message sent).
- [ ] Execution worker cron runs every 15 minutes.
- [ ] Enrollment scheduler query uses `status='ACTIVE' AND next_step_at <= NOW()`.
- [ ] Approval flow implemented end-to-end:
  - [ ] AI draft generated with `enrollment_id + sequence_id + sequence_step_id`.
  - [ ] if `requires_approval=true`, enrollment moves to `PENDING_APPROVAL`.
  - [ ] approve endpoint sets draft approved and resumes enrollment (`ACTIVE`, `next_step_at=NOW()`).
  - [ ] worker prefers approved draft for same enrollment+step (no regeneration).
- [ ] Mock SMTP send logging implemented.
- [ ] Mock LinkedIn action logging implemented.
- [ ] `lead.outreach_status` transitions implemented:
  - [ ] UNTOUCHED → IN_SEQUENCE on enrollment creation.
  - [ ] IN_SEQUENCE → REPLIED on reply.
  - [ ] IN_SEQUENCE → BOUNCED on send failure.
- [ ] Auto-enroll logic uses sequence threshold + global fallback.
- [ ] Inbound auto-routing (Phase 3 Step 6) activated and tested end-to-end:
  - [ ] Create sequence with `auto_enroll=true` + ICP.
  - [ ] Inbound webhook → lead enriched → ICP score computed → auto-enrolled into sequence.
  - [ ] SSE `inbound.lead.enrolled` event emitted.
- [ ] `/sequences` page implemented with `dnd-kit` reordering and step config UI.

### Phase 5 Test Gate

- [ ] Worker tests for step transitions and completion behavior.
- [ ] Channel/StepType validation tests (422 on mismatch).
- [ ] Approval-state tests for `PENDING_APPROVAL` pause/resume path.
- [ ] Reply-stop tests (enrollment halts on reply).
- [ ] Engagement step tests (no message send, logs only).
- [ ] Outreach status transition tests (UNTOUCHED → IN_SEQUENCE → REPLIED).
- [ ] Auto-routing end-to-end test: inbound webhook → lead enriched → auto-enrolled → SSE event.
- [ ] `pytest -q`, `npm run lint`, and `npm run build` all pass.

## 7. Phase 6 - Analytics + Polish (Week 6)

### Build Checklist

- [ ] Full `AnalyticsMetrics` aggregation service implemented.
- [ ] Analytics endpoints complete:
  - [ ] overview, funnel, tam, signals, inbound, sequence detail, personalization.
- [ ] Clarify overlapping endpoint scopes:
  - [ ] `/api/v1/inbound/stats` → operational view (last 30d counts by source/type).
  - [ ] `/api/v1/analytics/inbound` → strategic view (includes reply rates, conversion rates).
  - [ ] `/api/v1/tam/heatmap` → full cell-level breakdown.
  - [ ] `/api/v1/analytics/tam` → summary metrics only.
- [ ] `/analytics` page implemented with required charts/tables.
- [ ] Seed script creates demo dataset (leads, signals, inbound events, sender profile, drafts, sequences, enrollments).
- [ ] End-to-end demo path scripted and reproducible.
- [ ] README updated with architecture diagram and local runbook.
- [ ] Pytest coverage added for services + workers.
- [ ] Playwright smoke tests for all 9 pages.

### Phase 6 Test Gate

- [ ] `pytest -q` full suite green.
- [ ] `playwright test` smoke suite green.
- [ ] `npm run lint` and `npm run build` green.
- [ ] `docker compose up` demo flow runs without manual patching.
- [ ] Demo checklist validated:
  - [ ] YC import → enrichment → signal → personalization → sequence progression.
  - [ ] Inbound webhook → auto-routing → sequence progression.

## 8. Release Readiness Gate (Must Be Green)

- [ ] All phase gates complete.
- [ ] No schema drift between Alembic head and actual models.
- [ ] No endpoint drift between OpenAPI and frontend clients.
- [ ] No enum value drift between Python enums, SQL defaults, and frontend constants.
- [ ] No blocker-severity bugs in backlog.
- [ ] Worker env vars match backend env vars (all thresholds, API keys, feature flags present).
- [ ] Local setup from clean machine succeeds using README only.
- [ ] Final demo run recorded and repeatable.

## 9. Suggested Daily Execution Cadence

- [ ] Start day: choose one checklist section and define exact acceptance tests first.
- [ ] Mid day: merge only when tests for touched scope are green.
- [ ] End day: update checklist status and note blockers with owner + next action.
