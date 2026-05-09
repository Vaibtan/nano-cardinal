# Orion

Orion is an AI-native precision outbound platform. It combines ICP definition,
lead enrichment, inbound capture, buying-signal monitoring, personalized draft
generation, sequence execution, and analytics into one local demo stack.

Current implementation status:

- Phase 1 and Phase 2 are implemented.
- Phase 2.5 through Phase 6 have broad vertical-slice implementations, and
  the Claude-reported blockers have been patched.
- The active work currently lives on the `lead-pipeline` branch and has not
  been merged into `main`.
- Frontend `npm run lint` and `npm run build` pass.
- Backend tests pass against Docker Postgres/pgvector + Redis.

## Architecture

```text
Next.js App Router
  -> FastAPI REST + SSE API
      -> SQLAlchemy async ORM
      -> Postgres 16 + pgvector
      -> Redis Pub/Sub + ARQ workers
          -> mock enrichment
          -> mock signal monitors
          -> deterministic mock SMTP/LinkedIn delivery
```

Core backend modules:

- `backend/app/api/v1`: API routers.
- `backend/app/services`: business logic and state machines.
- `backend/app/models`: SQLAlchemy ORM models.
- `backend/alembic/versions`: forward-only schema migrations.
- `backend/scripts/seed_demo.py`: reproducible demo dataset.

Core frontend pages:

- `/icp`: ICP wizard and live match preview.
- `/sender`: sender profile and commonality inputs.
- `/leads`: lead table, filters, detail drawer.
- `/tam`: TAM heatmap and discovery panel.
- `/feed`: inbound and signal feed with SSE refresh.
- `/compose`: personalized draft generation and streaming.
- `/sequences`: sequence builder, enrollment, execution.
- `/analytics`: GTM metrics dashboard.

## Local Runbook

Docker-first path:

```powershell
docker compose up -d postgres redis
docker compose run --rm backend alembic upgrade head
docker compose up -d backend worker frontend
docker compose exec -T backend python scripts/seed_demo.py
```

Local development path:

```powershell
docker compose up -d postgres redis
cd backend
uv run alembic upgrade head
uv run python scripts/seed_demo.py
uv run uvicorn app.main:app --reload
```

In a second shell:

```powershell
cd frontend
npm install
npm run dev
```

Optional worker:

```powershell
cd backend
uv run python -m arq app.workers.worker.WorkerSettings
```

## Test And Verification Commands

Backend:

```powershell
cd backend
uv run --extra dev pytest -q
uv run python -m compileall app
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
npx playwright test
```

The backend test suite expects a Postgres test database at
`localhost:5433/orion_test`.

## Demo Path

1. Run `uv run python scripts/seed_demo.py`.
2. Open `/leads` and confirm enriched leads have ICP scores.
3. Open `/feed` and run a mock signal scan.
4. Open `/compose`, pick a lead, generate a draft, approve it, and stream it.
5. Open `/sequences`, enroll a lead, then run `Execute Due`.
6. Open `/analytics` to verify funnel, signal, inbound, sequence, and draft
   metrics update.

Current demo caveats:

- Signal monitoring is deterministic mock scanning, not real Funding/Hiring/
  LinkedIn/News source polling.
- Draft token streaming is worker-published over Redis `sse:{draft_id}` from
  the stored draft body. It is not real provider-token streaming yet.
- LangGraph is now the executed deterministic personalization path. The
  remaining production gap is replacing deterministic nodes with real LLM/tool
  nodes when provider integrations are wired.

## Important Mock Semantics

- Non-mock enrichment fails fast until real providers are wired.
- Deterministic email outcomes:
  - domains in `MOCK_SMTP_BOUNCE_DOMAINS` become `BOUNCED`.
  - domains in `MOCK_SMTP_REPLY_DOMAINS` become `REPLIED`.
  - all other email sends become `SENT`.
- LinkedIn message/connection steps become `SENT`.
- LinkedIn engagement steps become `ENGAGED`.

## Known Gaps Before Demo/PR

- Real source-specific signal polling workers are still mocked by the
  deterministic scanner.
- Real enrichment providers are intentionally fail-fast until API integrations
  are implemented.
- Real LLM/provider-token streaming is not implemented; streaming currently
  replays persisted draft tokens from an ARQ worker.
- Sequence UI still needs the per-step metrics overlay.
- Broader Phase 3-6 edge-case coverage remains useful beyond the targeted
  regression tests now added.
- Open and review a PR from `lead-pipeline` into `main`.
