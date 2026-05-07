**Nano Cardinal PRD**

\# PRD: Orion — AI Precision Outbound Engine  
\#\#\# Inspired by Cardinal (YC W26)  
\*\*Version:\*\* 3.6 (Clarifies pause reasons, irreducible inbound events, LinkedIn mock outcomes, signal time semantics, and ICP signal thresholds)  
\*\*Status:\*\* Ready for Implementation  
\*\*Stack:\*\* FastAPI · NextJS · PostgreSQL (with pgvector) · Redis · LangGraph

\---

\#\# 1\. Project Overview

Orion is a locally-runnable, full-stack AI outbound engine that automates the complete B2B  
prospecting workflow — from ICP definition and TAM mapping to lead enrichment, signal  
monitoring, commonality-based personalization, and multi-channel sequence execution.  
It replaces a 10-tool GTM stack with a single agentic platform.

\#\#\# 1.1 Goals  
\- Demonstrate deep GTM engineering competency (signal infra, enrichment pipelines, inbound webhooks, agent orchestration)  
\- Showcase full-stack ML engineering (RAG, vector search, LangGraph agents, background workers)  
\- Run entirely on localhost with Docker Compose (cloud APIs optional; local LLM/embedding fallback supported)  
\- Be impressive to senior technical leaders: clean architecture, observable pipelines, typed APIs

\#\#\# 1.2 Non-Goals  
\- Production email sending (mock SMTP only for local demo)  
\- Real LinkedIn scraping (use mock/fixture data or Proxycurl API if key is provided)  
\- Multi-tenant SaaS (single-user local tool)
\---

\#\# 2\. System Architecture

\`\`\`text  
┌───────────────────────────────────────────────────────────────────┐  
│                          NextJS UI (Port 3000\)                     │  
│  Dashboard | TAM Explorer | Sender Profile | ICP Builder           │  
│  Lead Board | Signal+Inbound Feed | Sequence Builder               │  
│  Email Composer | Analytics                                        │  
└────────────────────────────┬──────────────────────────────────────┘  
                             │ REST \+ SSE (Server-Sent Events)  
┌────────────────────────────▼──────────────────────────────────────┐  
│                      FastAPI Backend (Port 8000\)                    │  
│                                                                    │  
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐    │  
│  │ICP & TAM │  │ Inbound  │  │  Lead    │  │   Signal       │    │  
│  │ Module   │  │ Capture  │  │ Pipeline │  │   Monitor      │    │  
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘    │  
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐    │  
│  │Commonal- │  │Sequence  │  │Analytics │  │  Email Infra   │    │  
│  │ity+Pers. │  │ Manager  │  │ Engine   │  │  (Mock SMTP)   │    │  
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘    │  
└──────────┬───────────────┬───────────────────────────────────────┘  
           │               │  
      ┌────▼────┐     ┌────▼────┐  
      │Postgres │     │  Redis  │  
      │(Primary │     │(Queue \+ │  
      │ Store \+ │     │ Cache \+ │  
      │pgvector)│     │ Pub/Sub)│  
      └─────────┘     └────┬────┘  
                           │  
                      ┌────▼────┐  
                      │  ARQ    │  
                      │(Async   │  
                      │Workers) │  
                      └─────────┘

## **2.1 Component Responsibilities**

| Component | Responsibility |
| ----- | ----- |
| **FastAPI** | REST API, SSE streams, webhook receivers, agent orchestration entrypoints |
| **NextJS** | App Router frontend (SSR/CSR hybrid), dashboard pages, form workflows, SSE client |
| **PostgreSQL (with pgvector)** | Primary store for Leads, ICPs, Sequences, Signals, Inbound Events, Sender Profile, Outreach Logs. Also hosts vector embeddings via the `pgvector` extension: `leads.embedding` (semantic search of enriched lead profiles) and `winning_snippets.embedding` (RAG for agent Node 3). Distance: cosine; index: HNSW. The DB column dimension is fixed at schema-creation time (default `768`); the `EMBEDDING_MODEL` config must produce vectors of that dimension. A startup validator (`validate_embedding_dimension`) refuses to boot the API/worker on mismatch. To switch to a model of a different dimension (e.g., `text-embedding-3-small` at 1536), run an Alembic migration that ALTERs the vector columns to the new dimension and re-embeds existing rows. Multi-provider: any provider whose configured model matches the column dimension (e.g., gemini `text-embedding-004` 768, ollama `nomic-embed-text` 768; for 1536-dim columns: openai `text-embedding-3-small`). |
| **Redis** | ARQ job queue, enrichment result cache, signal dedup hashes |
| **ARQ Workers** | Background enrichment, signal polling, inbound event processing, sequence execution |
| **LangGraph** | Multi-step agent: Commonality Matching → Signal Selection → RAG → Draft → Critique → Tone |

---

## **3\. Module Specifications**

---

## **Module 1: ICP Builder & TAM Mapping**

**Purpose:** Define the Ideal Customer Profile that drives all downstream lead discovery and  
 scoring, and visually map the Total Addressable Market (TAM) coverage versus whitespace.

## **3.1.1 Data Model**

python  
*`# models/icp.py`*  
`class ICP(BaseModel):`  
    `id: UUID`  
    `name: str`  
    `description: str`

    `# Firmographic filters`  
    `industries: list[str]          # e.g. ["SaaS", "Fintech"]`  
    `company_size_min: int          # employee count`  
    `company_size_max: int`  
    `funding_stages: list[str]      # ["Seed", "Series A", "Series B"]`  
    `geographies: list[str]         # ["USA", "UK", "India"]`  
    `tech_stack: list[str]          # ["Salesforce", "HubSpot", "Stripe"]`

    `# Persona filters`  
    `target_titles: list[str]       # ["VP Sales", "Head of Growth", "CRO"]`  
    `seniority_levels: list[str]    # ["Director", "VP", "C-Suite"]`  
    `departments: list[str]         # ["Sales", "Marketing", "Revenue"]`

    `# Signal preferences used by Phase 3 signal scoring/filtering`
    `selected_signal_types: list[SignalType]  # Signal types this ICP cares about`
    `signal_recency_days: int = 30            # ICP-scoped signal queries ignore signals older than this window`
    `min_signal_strength: float = 0.0         # ICP-scoped feeds/triggers hide signals below this final score`
    `signal_keywords: list[str] = []          # Optional phrases to boost signal relevance`

    `# Scoring weights (0.0 - 1.0, must sum to 1.0)`  
    `weights: dict[str, float]      # {"funding_stage": 0.3, "tech_stack": 0.4, ...}`

    `created_at: datetime`  
    `updated_at: datetime`

## **3.1.2 ICP Scoring Algorithm**

Each lead is scored 0–100 against a selected ICP using a weighted criteria match:

`ICP Score = Σ (weight_i × match_i) / Σ weight_i × 100`

`Where match_i ∈ {0, 0.5, 1.0}:`  
  `- 1.0 = exact match`  
  `- 0.5 = partial match (e.g. industry adjacent)`  
  `- 0.0 = no match`

## **`3.1.3 TAM Mapping Aggregation`**

`The TAM endpoint groups all leads in the DB by ICP dimensions and computes coverage buckets.`  
 `This exposes whitespace (combinations of firmographic attributes not yet targeted).`

`python`  
`class TAMCell(BaseModel):`  
    `dimension_x: str               # e.g. industry = "Fintech"`  
    `dimension_y: str               # e.g. company_size = "51-200"`  
    `total_estimated: int           # Estimated total companies in cell (from enrichment data)`  
    `captured: int                  # Leads in DB matching this cell`  
    `in_sequence: int               # Of captured, how many are in an active sequence`  
    `replied: int                   # Of in_sequence, how many have replied`  
    `coverage_pct: float            # captured / total_estimated × 100`

`class TAMHeatmapResponse(BaseModel):`  
    `icp_id: UUID`  
    `x_dimension: str               # Axis label`  
    `y_dimension: str               # Axis label`  
    `cells: list[TAMCell]`  
    `total_tam_size: int`  
    `total_captured: int`  
    `overall_coverage_pct: float`

**`API Endpoints:`**

`text`  
`POST   /api/v1/icp                        — Create ICP`  
`GET    /api/v1/icp                        — List all ICPs`  
`GET    /api/v1/icp/{id}                   — Get ICP detail`  
`PUT    /api/v1/icp/{id}                   — Update ICP`  
`DELETE /api/v1/icp/{id}                   — Delete ICP`  
`POST   /api/v1/icp/{id}/score             — Score a batch of lead IDs against this ICP`  
`GET    /api/v1/tam/heatmap?icp_id={id}    — TAM coverage heatmap data`  
`GET    /api/v1/tam/whitespace?icp_id={id} — Return cells with lowest coverage_pct`

**Implementation note:** the current API stores ICP filters inside `icps.config` JSONB. The frontend wizard must expose the same logical sections in this order: Firmographics -> Persona -> Signals -> Weighting. `name` and `description` are metadata fields, not a wizard step. Weight controls auto-normalize in the UI so the displayed total is 1.0; the backend scorer still divides by total weight defensively.

## **Module 2: Inbound Capture Engine \[NEW\]**

**Purpose:** Ingest push events from external systems (product signups, ad impressions,  
 social media engagement) via webhooks. Unifies inbound intent with the outbound pipeline  
 by auto-creating enriched leads and routing them into sequences.

## **3.2.1 Inbound Event Types**

python  
`class InboundEventType(str, Enum):`  
    `PRODUCT_SIGNUP        = "product_signup"        # User signed up in your app`  
    `AD_IMPRESSION         = "ad_impression"         # Saw LinkedIn/Google ad`  
    `AD_CLICK              = "ad_click"              # Clicked on your ad`  
    `LINKEDIN_LIKE         = "linkedin_like"         # Liked one of your posts`  
    `LINKEDIN_COMMENT      = "linkedin_comment"      # Commented on your post`  
    `LINKEDIN_CONNECTION   = "linkedin_connection"   # Accepted your connection`  
    `WEBSITE_OPT_IN        = "website_opt_in"        # Submitted a form on your site`  
    `CONFERENCE_REGISTRATION = "conference_registration"  # Registered for your event`

## **3.2.2 Inbound Event Data Model**

python  
`class InboundEvent(BaseModel):`  
    `id: UUID`  
    `source: str                    # "clerk", "stripe", "linkedin_ads", "google_ads", "manual"`  
    `event_type: InboundEventType`  
    `raw_payload: dict              # Full original webhook body, stored as JSONB`

    `# Extracted identity fields (parsed from raw_payload)`  
    `email: Optional[str]`  
    `first_name: Optional[str]`  
    `last_name: Optional[str]`  
    `linkedin_url: Optional[str]`  
    `company_domain: Optional[str]`

    `# Processing state`  
    `processed: bool                # Has this been turned into a Lead?`  
    `processing_error: Optional[str]`  
    `created_lead_id: Optional[UUID]  # FK to leads table after processing`
    `source_event_id: Optional[str]   # Stable upstream ID when source provides one`
    `event_fingerprint: Optional[str] # SHA256(source + event_type + source-specific fingerprint keys), NULL if no stable keys exist`

    `received_at: datetime`  
    `processed_at: Optional[datetime]`

## **3.2.3 Inbound Processing Pipeline (ARQ Worker)**

text  
`Webhook POST hits /api/v1/inbound/webhook/{source}`  
    `│`  
    `▼`  
`[Step 1] Store Raw Event`  
    `INSERT into inbound_events with processed=false`  
    `Set source_event_id and/or event_fingerprint only when stable source keys are available`  
    `Return HTTP 200 immediately (async processing)`  
    `│`  
    `▼`  
`[Step 2] Identity Extraction Worker (ARQ)`  
    `Parse email/linkedin_url from raw_payload based on source schema`  
    `If no identifiable fields and no stable idempotency key exist → processed=true, processing_error='no_stable_identity', skip lead creation`  
    `│`  
    `▼`  
`[Step 3] Deduplication Check`  
    `Check if lead with same email or linkedin_url already exists`  
    `If exists → link existing lead (update created_lead_id), skip creation`  
    `│`  
    `▼`  
`[Step 4] Lead Auto-Creation`  
    `Create Lead record with:`  
      `source = "INBOUND"`  
      `inbound_event_id = {event.id}`  
      `enrichment_status = PENDING`  
    `│`  
    `▼`  
`[Step 5] Trigger Enrichment Pipeline`  
    `Enqueue full enrichment pipeline (same as outbound, Module 3)`  
    `│`  
    `▼`  
`[Step 6] Post-Enrichment Auto-Routing`  
    `Once enrichment completes and ICP score is computed:`  
    `If lead has best-matched icp_id + icp_score:`  
        `Find sequences with auto_enroll=true AND icp_id matching`  
        `Use threshold = sequence.auto_enroll_threshold (fallback: AUTO_ENROLL_ICP_THRESHOLD)`  
        `If icp_score >= threshold: create LeadSequenceEnrollment`  
    `If enrollment created: emit SSE event "inbound.lead.enrolled"`  
    `│`  
    `▼`  
`Mark InboundEvent processed=true, processed_at=now()`

**Retry/idempotency contract for `POST /api/v1/inbound/events/{id}/retry`:**

* `Retry first loads the existing InboundEvent row and never creates a second InboundEvent.`
* `If created_lead_id is already set, retry reuses that lead and continues from enrichment/auto-routing.`
* `If created_lead_id is null, retry deduplicates by email, linkedin_url, company_domain + name, then event_fingerprint when non-null.`
* `For payloads without stable source_event_id or event_fingerprint, keep the raw audit row with event_fingerprint=NULL, set processed=true, set processing_error='no_stable_identity', and do not create a lead.`
* `Retry is safe after partial failure: lead creation, lead linking, enrichment enqueue, and processed=true updates are each written so reruns can resume without double-creating leads.`
* `Webhook inserts must be race-safe: source_event_id is protected by a partial unique index on (source, source_event_id) WHERE source_event_id IS NOT NULL; event_fingerprint is globally unique when non-null as the fallback idempotency key.`

**Inbound event fingerprint contract:**

| Source | `source_event_id` | `event_fingerprint` key material |
| ----- | ----- | ----- |
| `clerk` | `data.id` when present | `source + event_type + data.id` |
| `stripe` | top-level `id` when present | `source + event_type + data.object.id` |
| `linkedin_ads` | `leadGenFormResponse.id` when present | `source + event_type + leadGenFormResponse.formId + normalized_email` |
| `google_ads` | `lead.id` or `gclid` when present | `source + event_type + conversion_action + gclid_or_normalized_email` |
| `manual` | Optional caller-provided `source_event_id` | `source + event_type + normalized_email_or_linkedin_url_or_company_domain` |

**Fingerprint rules:** use only stable identity keys, never volatile timestamps such as `received_at`, `submitted_at`, `created`, or local ingestion time. Normalize emails/domains to lowercase and trim whitespace before hashing. Never compute weak fallback hashes such as `SHA256(source + event_type)`; irreducible events must use `event_fingerprint=NULL` plus `processing_error='no_stable_identity'`.

## **3.2.4 Source Payload Schemas (Fixtures for local dev)**

python  
*`# Source-specific payload parsers`*  
`PAYLOAD_PARSERS = {`  
    `"clerk": lambda p: {"email": p["data"]["email_addresses"][0]["email_address"],`  
                        `"first_name": p["data"]["first_name"],`  
                        `"last_name": p["data"]["last_name"]},`  
    `"stripe": lambda p: {"email": p["data"]["object"]["customer_email"],`  
                         `"company_domain": p["data"]["object"]["metadata"].get("domain")},`  
    `"linkedin_ads": lambda p: {"email": p["leadGenFormResponse"]["email"],`  
                               `"first_name": p["leadGenFormResponse"].get("firstName"),`  
                               `"last_name": p["leadGenFormResponse"].get("lastName"),`  
                               `"linkedin_url": p.get("profileUrl"),`  
                               `"company_domain": p.get("company", {}).get("domain")},`  
    `"google_ads": lambda p: {"email": p.get("lead", {}).get("email"),`  
                             `"first_name": p.get("lead", {}).get("first_name"),`  
                             `"last_name": p.get("lead", {}).get("last_name"),`  
                             `"company_domain": p.get("lead", {}).get("company_domain")},`  
    `"manual": lambda p: p,  # Pass-through for manually posted payloads`  
`}`

**API Endpoints:**

text  
`POST   /api/v1/inbound/webhook/{source}   — Generic webhook receiver (supports clerk, stripe,`  
                                             `linkedin_ads, google_ads, manual)`  
`GET    /api/v1/inbound/events             — Paginated audit log of all received inbound events`  
`GET    /api/v1/inbound/events/{id}        — Detail of a single inbound event + processing status`  
`POST   /api/v1/inbound/events/{id}/retry  — Re-process a failed inbound event`  
`GET    /api/v1/inbound/stats              — Inbound event counts by type and source (last 30d)`

## **Module 3: Lead Discovery & Enrichment Pipeline**

**Purpose:** Ingest leads from multiple sources (CSV, YC scraper, manual, inbound webhook)  
 and enrich them with firmographic, technographic, and social data.

## **3.3.1 Lead Data Model**

python  
`class LeadSource(str, Enum):`
    `CSV_IMPORT = "CSV_IMPORT"`
    `YC_SCRAPER = "YC_SCRAPER"`
    `MANUAL     = "MANUAL"`
    `API        = "API"`
    `INBOUND    = "INBOUND"            # Set when created by Inbound Capture Engine`

`class EnrichmentStatus(str, Enum):`  
    `PENDING  = "PENDING"`  
    `RUNNING  = "RUNNING"`  
    `COMPLETE = "COMPLETE"`  
    `FAILED   = "FAILED"`

`class OutreachStatus(str, Enum):`  
    `UNTOUCHED   = "UNTOUCHED"`  
    `IN_SEQUENCE = "IN_SEQUENCE"`  
    `REPLIED     = "REPLIED"`  
    `BOUNCED     = "BOUNCED"`

`class Lead(BaseModel):`  
    `id: UUID`

    `# Identity`  
    `first_name: Optional[str]`  
    `last_name: Optional[str]`  
    `email: Optional[str]`  
    `linkedin_url: Optional[str]`  
    `github_url: Optional[str]`  
    `twitter_url: Optional[str]`

    `# Company`  
    `company_name: Optional[str]`  
    `company_domain: Optional[str]`  
    `company_linkedin_url: Optional[str]`  
    `company_size: Optional[int]`  
    `industry: Optional[str]`  
    `funding_stage: Optional[str]`  
    `total_funding_usd: Optional[int]`  
    `tech_stack: list[str]`

    `# Persona`  
    `title: Optional[str]`  
    `seniority: Optional[str]`  
    `department: Optional[str]`

    `# Enrichment metadata`  
    `enrichment_status: EnrichmentStatus`  
    `enrichment_sources: list[str]        # ["proxycurl", "clearbit", "builtwith"]`  
    `enrichment_at: Optional[datetime]`

    `# Scoring`  
    `icp_score: Optional[float]`  
    `icp_id: Optional[UUID]`  
    `icp_score_breakdown: Optional[dict[str, float]]`

    `# Embedding (pgvector column on leads.embedding; ORM exposes it as a list[float])`  
    `embedding: Optional[list[float]]     # VECTOR(VECTOR_DIMENSION); NULL until Step 5 runs`

    `# Signals`  
    `recent_signals: list[UUID]         # Derived field (not persisted column)`

    `# Outreach`
    `outreach_status: OutreachStatus`
    `last_contacted_at: Optional[datetime] # Updated after successful outbound send/engagement`

    `# Source tracking`
    `source: LeadSource`
    `inbound_event_id: Optional[UUID]     # FK if created by Inbound Capture Engine`

    `created_at: datetime`
    `updated_at: datetime`

**`3.3.1a Outreach Status Transition Rules`**

`The lead.outreach_status field transitions as follows:`
  `UNTOUCHED → IN_SEQUENCE:  When a LeadSequenceEnrollment is created for the lead`
  `IN_SEQUENCE → REPLIED:    When enrollment.reply_received is set to true`
  `IN_SEQUENCE → BOUNCED:    When a send attempt returns a bounce (logged in outreach_logs.delivery_status='BOUNCED', bounced_at set, error fields populated)`
  `Any status → UNTOUCHED:   Only if all enrollments are deleted/unsubscribed (manual reset)`
`These transitions are enforced by the sequence enrollment service and the sequence execution worker.`

## **`3.3.2 Enrichment Pipeline (ARQ Worker)`**

`text`  
`Lead Created (any source)`  
    `│`  
    `▼`  
`[Step 1] Email Finder`  
    `Uses Hunter.io API (or mock) to find work email from name + domain`  
    `│`  
    `▼`  
`[Step 2] LinkedIn Enrichment`  
    `Uses Proxycurl API (or fixture JSON if no key):`  
    `- Current role, tenure, past companies`  
    `- Education (university, degree, graduation year)`  
    `- Skills, certifications`  
    `- Activity feed (last 5 posts, engagement patterns)`  
    `│`  
    `▼`  
`[Step 3] Company Enrichment`  
    `Uses Clearbit/Apollo mock or Crunchbase scraper:`  
    `- Headcount, 3-month growth rate`  
    `- Funding rounds with dates and investors`  
    `- Tech stack via BuiltWith API`  
    `- News mentions (last 30 days)`  
    `│`  
    `▼`  
`[Step 4] GitHub Enrichment (only if github_url present)`  
    `Fetches: repos, primary languages, recent commits, README summaries`  
    `Extracts "building story" text for personalization`  
    `│`  
    `▼`  
`[Step 5] Embedding Generation`  
    `Concatenates enriched data into structured text blob:`  
    `"{name} is {title} at {company}. Company uses {tech_stack}.`  
     `They recently {linkedin_activity}. Company raised {funding}`  
     `in {industry}. Education: {education}. GitHub: {repo_summary}"`

    `Generates embedding via the configured EMBEDDING_PROVIDER /`  
    `EMBEDDING_MODEL (gemini text-embedding-004, openai`  
    `text-embedding-3-small, or ollama nomic-embed-text).`  
    `Writes the vector to leads.embedding (pgvector column).`  
    `Dimension must match VECTOR_DIMENSION; mismatch is rejected`  
    `at startup by validate_embedding_dimension().`  
    `│`  
    `▼`  
`[Step 6] ICP Scoring`  
    `Scores against all active ICPs`  
    `Stores best match on lead record: icp_id + icp_score`  
    `Optionally stores all per-ICP scores in icp_score_breakdown JSON`
    `│`  
    `▼`  
`Lead marked COMPLETE — SSE event emitted: "lead.enrichment.complete"`

## **`3.3.3 YC Company Scraper (Built-in Data Source)`**

`python`  
`class YCScraper:`  
    `async def scrape_recent_launches(`  
        `self,`  
        `batch: str = "W25",`  
        `limit: int = 100`  
    `) -> list[RawLead]:`  
        `# Fetches YC directory, parses company cards`  
        `# Returns structured RawLead objects`  
        `# Rate limited: 1 req/2s, respects robots.txt`

**`API Endpoints:`**

`text`  
`POST   /api/v1/leads                        — Create single lead`  
`POST   /api/v1/leads/import/csv             — Bulk import via CSV upload`  
`POST   /api/v1/leads/import/yc              — Trigger YC scraper (batch param optional)`  
`GET    /api/v1/leads                        — List leads (paginated, filterable by ICP score,`  
                                             `enrichment_status, outreach_status, source)`  
`GET    /api/v1/leads/{id}                   — Get lead detail with full enrichment data`  
`POST   /api/v1/leads/{id}/enrich            — Re-trigger enrichment for a single lead`  
`GET    /api/v1/leads/{id}/similar           — Semantic similarity search via pgvector cosine distance on leads.embedding (top-5)`  
`DELETE /api/v1/leads/{id}                   — Delete lead`  
`GET    /api/v1/leads/search?q=              — Semantic search across all leads`
`GET    /api/v1/leads/{id}/outreach         — Outreach history for a lead (from outreach_logs)`

## **`Module 4: Signal Monitor`**

**`Purpose:`** `Continuously poll for real-world "buying signal" events that indicate a lead`  
 `or their company is in an active moment worth targeting.`

## **`3.4.1 Signal Types`**

`python`  
`class SignalType(str, Enum):`  
    `# Polled by FundingWorker`  
    `FUNDING_ROUND          = "funding_round"`  
    `PRODUCT_LAUNCH         = "product_launch"`  

    `# Polled by HiringWorker`  
    `HIRING_SURGE           = "hiring_surge"`  
    `JOB_POSTING_ICP_ROLE   = "job_posting_icp_role"`  
    `LEADERSHIP_HIRE        = "leadership_hire"`  

    `# Polled by LinkedInWorker`  
    `JOB_CHANGE             = "job_change"`  
    `LINKEDIN_POST          = "linkedin_post"`  

    `# Polled by NewsWorker`  
    `NEWS_MENTION           = "news_mention"`  
    `TECH_STACK_CHANGE      = "tech_stack_change"`  

    `# Emitted from inbound bridge logic (Module 2)`
    `PRODUCT_SIGNUP         = "product_signup"`
    `WEBSITE_VISIT          = "website_visit"`
    `CONFERENCE_ATTENDANCE  = "conference_attendance"`

## **`3.4.2 Signal Data Model`**

`python`  
`class Signal(BaseModel):`  
    `id: UUID`  
    `lead_id: UUID`  
    `company_domain: str`  
    `signal_type: SignalType`  
    `signal_title: str               # "Acme Corp raised Series A"`  
    `signal_body: str                # "$10M led by Sequoia Capital"`  
    `signal_url: Optional[str]`  
    `signal_strength: float          # 0.0 - 1.0`  
    `signal_hash: str                # SHA256 of (lead_id + signal_type + key_fields) for dedup`  
    `detected_at: datetime`  
    `expires_at: datetime             # Feed retention cutoff; default detected_at + 90 days`
    `is_read: bool`  
    `triggered_outreach: bool`

**Signal retention policy:** unread signals remain eligible for the feed until `expires_at` (default 90 days after `detected_at`). `is_read=true` hides the signal immediately from the default feed. Hard deletion is out of scope for MVP; old rows can be archived later if analytics volume requires it.

## **3.4.3 Signal Workers Architecture**

text  
`┌─────────────────────────────────────────────────────────┐`  
`│                    Signal Scheduler                      │`  
`│   (runs via ARQ cron — configurable per signal type)     │`  
`└──┬──────────┬──────────┬────────────┬───────────────────┘`  
   `│          │          │            │`  
   `▼          ▼          ▼            ▼`  
`FundingWorker  HiringWorker  LinkedInWorker  NewsWorker`  
`(every 6h)    (every 12h)   (every 2h)      (every 4h)`  
   `│`  
   `▼`  
`For each monitored lead/company:`  
  `1. Fetch data from source API (or mock fixture)`  
  `2. Compute signal_hash = SHA256(lead_id + signal_type + key_data)`  
  `3. Check Redis SET: if hash exists → skip (TTL 7 days)`  
  `4. If new: INSERT into signals table`  
  `5. Store hash in Redis with TTL`  
  `6. Update signal_strength score`  
  `7. Emit SSE event: "signal.detected"`  
  `8. If signal_strength > AUTO_PERSONALIZE_THRESHOLD AND lead ICP score > 70:`  
       `→ Enqueue personalization draft generation job`

`Inbound Bridge (inside inbound_worker):`
  `Map inbound events to high-intent signal types where applicable:`
  `- PRODUCT_SIGNUP -> PRODUCT_SIGNUP (highest intent — user signed up for your product)`
  `- AD_CLICK / WEBSITE_OPT_IN -> WEBSITE_VISIT`
  `- CONFERENCE_REGISTRATION -> CONFERENCE_ATTENDANCE`

## **3.4.4 Signal Strength Scoring**

text  
`Base score by type:`
  `PRODUCT_SIGNUP:        0.98   (highest — signed up for your product)`
  `WEBSITE_VISIT:         0.95   (active intent)`
  `FUNDING_ROUND:         0.90`  
  `JOB_CHANGE:            0.85`  
  `LEADERSHIP_HIRE:       0.80`  
  `PRODUCT_LAUNCH:        0.75`  
  `HIRING_SURGE:          0.70`  
  `JOB_POSTING_ICP_ROLE:  0.65`  
  `NEWS_MENTION:          0.60`  
  `TECH_STACK_CHANGE:     0.55`  
  `LINKEDIN_POST:         0.50`  
  `CONFERENCE_ATTENDANCE: 0.50`

`Modifiers (multiplicative):`  
  `× 1.2  if signal detected within last 48h (recency boost)`  
  `× 1.1  if lead icp_score > 80`  
  `× 0.8  if lead.last_contacted_at is within last 30 days (cool-off penalty)`  
  `× 1.05 if signal_title or signal_body matches any icp.signal_keywords entry`  
    
`Final score capped at 1.0`

**Signal timing and threshold semantics:** `icp.signal_recency_days` filters which signals enter ICP-scoped scoring/feed queries; the 48h recency boost rewards freshness inside the scoring formula; `signals.expires_at` controls default feed visibility and retention. These are independent and should not be collapsed into one field.

**ICP threshold semantics:** after final `signal_strength` is computed and capped, ICP-scoped feeds and auto-personalization triggers exclude signals below `icp.min_signal_strength`. The default `0.0` means no minimum.

**Performance note:** signal scoring must not query `outreach_logs` once per signal to compute the cool-off modifier. Phase 2.5 creates `leads.last_contacted_at` with default `NULL`; Phase 3 signal scoring reads that denormalized field in the lead batch query and treats `NULL` as "never contacted." Phase 5 sequence execution updates it after successful sends and engagement touches.

**API Endpoints:**

text  
`GET    /api/v1/signals                    — List visible signals (is_read=false and expires_at>now by default, paginated, sorted by detected_at)`  
`GET    /api/v1/signals/lead/{lead_id}     — All signals for a specific lead`  
`POST   /api/v1/signals/poll               — Manually trigger a full signal poll cycle`  
`PATCH  /api/v1/signals/{id}/read          — Mark signal as read`  
`GET    /api/v1/events/stream?topic=signals — SSE stream for real-time new signals (filtered view)`  
`DELETE /api/v1/signals/{id}              — Dismiss signal (soft-delete: sets is_read=true and excluded from feed; does NOT hard-delete)`

## **Module 5: Commonalities & Personalization Engine**

**Purpose:** The core moat. Generate hyper-personalized outreach by first discovering genuine  
 overlapping experiences between the Sender and the Prospect (Commonalities), then combining  
 that hook with buying signals in a multi-step LangGraph agent with a self-critique loop.

## **3.5.1 Sender Profile Model**

python  
`class SenderProfile(BaseModel):`  
    `id: UUID`  
    `user_id: str                      # Single-user system, use "default"`  
    `name: str`  
    `current_title: str`  
    `current_company: str`

    `# Background data used for Commonality matching`  
    `education: list[dict]             # [{"school": "University of Michigan",`  
                                      `#   "degree": "BS Computer Science",`  
                                      `#   "grad_year": 2018}]`  
    `past_employers: list[dict]        # [{"company": "Stripe", "role": "SWE",`  
                                      `#   "from_year": 2018, "to_year": 2021}]`  
    `cities_lived: list[str]           # ["San Francisco", "Ann Arbor", "London"]`  
    `hobbies_and_interests: list[str]  # ["Marathon running", "Chess", "Rust programming"]`  
    `investors: list[str]              # ["Y Combinator", "Sequoia"] (if applicable)`  
    `languages_spoken: list[str]       # ["English", "Hindi"]`  
    `conferences_attended: list[str]   # ["SaaStr", "YC Demo Day", "NeurIPS"]`

    `updated_at: datetime`

## **`3.5.2 LangGraph Agent Architecture`**

`text`  
`┌─────────────────────────────────────────────────────────────────┐`  
`│                Golden Snippet Agent (LangGraph)                  │`  
`│                                                                 │`  
`│  AgentState: {                                                  │`  
`│    lead, sender, enriched_data, signals,                        │`  
`│    commonalities, selected_signal,                              │`  
`│    rag_snippets, draft, critique, tone_adjusted_draft           │`  
`│  }                                                              │`  
`│                                                                 │`  
`│  ┌──────────┐    ┌──────────┐    ┌──────────┐                 │`  
`│  │  NODE 1  │───▶│ NODE 1.5 │───▶│  NODE 2  │                 │`  
`│  │ Context  │    │Commonal- │    │ Signal   │                 │`  
`│  │ Retrieval│    │ity Match │    │ Selector │                 │`  
`│  └──────────┘    └──────────┘    └──────────┘                 │`  
`│                                        │                        │`  
`│                                        ▼                        │`  
`│                               ┌──────────────┐                 │`  
`│                               │    NODE 3    │                 │`  
`│                               │  RAG Fetch   │                 │`  
`│                               └──────┬───────┘                 │`  
`│                                      │                          │`  
`│                               ┌──────▼───────┐                 │`  
`│                               │    NODE 4    │                 │`  
`│                               │ Draft Writer │                 │`  
`│                               │ (Signal +    │                 │`  
`│                               │ Commonality) │                 │`  
`│                               └──────┬───────┘                 │`  
`│                                      │                          │`  
`│                               ┌──────▼───────┐                 │`  
`│                               │    NODE 5    │                 │`  
`│                               │   Critique   │◀── Rewrite loop │`  
`│                               │   & Score    │    (max 3 iters)│`  
`│                               └──────┬───────┘                 │`  
`│                         score >= 7   │  score < 7              │`  
`│                               ┌──────▼───────┐                 │`  
`│                               │    NODE 6    │                 │`  
`│                               │  Tone Adapt  │                 │`  
`│                               └──────┬───────┘                 │`  
`│                                      ▼                          │`  
`│                                Final Output                     │`  
`└─────────────────────────────────────────────────────────────────┘`

## **`3.5.3 Node Descriptions`**

**`Node 1 — Context Retrieval:`**

* `Load lead's full enriched profile (all fields) from PostgreSQL`

* `Load active SenderProfile`

* `Pull last 5 signals from signals table for this lead, sorted by signal_strength DESC`

**`Node 1.5 — Commonality Matcher (NEW):`**
 `LLM cross-references SenderProfile and Lead enriched data to extract genuine, non-trivial overlaps.`
 `If no SenderProfile exists, this node is SKIPPED: commonalities=[], strongest_hook=null, hook_strength=0.`
 `Node 4 then falls back to signal-based or company-observation opening (see draft writer rules).`

`System: You are analyzing two professional profiles to find genuine shared experiences.`  
        `Non-trivial means: NOT "both work in tech" or "both use LinkedIn."`  
        `Look for: same employer (overlapping tenure), same university, same city at same time,`  
        `shared investors, shared conferences attended, same niche interest or hobby,`  
        `notable mutual connections, same specific subfield or programming language community.`

`User:`  
  `Sender Profile: {sender_profile_json}`  
  `Prospect Profile: {enriched_lead_json}`

`Task: Return a JSON with:`  
  `{`  
    `"commonalities": [`  
      `{"type": "past_employer", "detail": "Both worked at Stripe — overlapping 2019-2021",`  
       `"strength": 9},`  
      `{"type": "education", "detail": "Both studied at University of Michigan, CS dept",`  
       `"strength": 7}`  
    `],`  
    `"strongest_hook": "Both worked at Stripe during the same period (2019-2021)",`  
    `"hook_strength": 9`  
  `}`  
    
  `If no genuine commonality exists, set strongest_hook to null and hook_strength to 0.`

**`Node 2 — Signal Selector:`**  
 `LLM picks the single most timely, relevant signal to reference:`

`text`  
`Prompt: "Given these signals about {lead_name}, select the ONE signal that creates the most`   
`natural, non-creepy opening for a cold email. Avoid signals older than 14 days if fresher`   
`ones exist. Return: {signal_id, signal_title, reason}"`

**`Node 3 — RAG Fetch:`**

* `Embed: {strongest_hook} + {selected_signal_title} + {lead_title} at {lead_industry} as query vector`

* `Search winning_snippets table via pgvector cosine distance on winning_snippets.embedding (pre-seeded with mock high-performing emails)`

* `Retrieve top-3 snippets by cosine similarity`

* `These serve as style/structure examples, NOT as templates to copy`

**`Node 4 — Draft Writer:`**  
**`Receives: sender, lead, commonality hook, selected signal, RAG examples`**

**`text`**

**`System: You are an expert B2B cold email writer. Write like a thoughtful human peer.`**

        

        **`NEVER use these phrases:`**

        **`"I came across your profile", "hope this finds you well",`**

        **`"I wanted to reach out", "synergy", "quick call", "touch base",`**

        **`"circle back", "leverage", "at the end of the day", "game changer"`**

        

        **`Rules:`**

        **`- Max 75 words total (body only)`**

        **`- Exactly 3 sentences`**

        **`- Subject line max 8 words, no emoji`**

        **`- If a commonality hook exists (strength >= 6), open with it`**

        **`- If no commonality, open with the signal observation`**
        
        **`- If NEITHER exist, open with a highly relevant observation about their company/industry`**

        **`- Sentence 2: connect to a concrete, specific problem your product solves`**

        **`- Sentence 3: CTA must be a yes/no question or a single specific ask`**

          **`(NOT "hop on a call", NOT "let me know your thoughts")`**

**`User:`**

  **`Sender: {name}, {title} at {company}`**

  **`Prospect: {lead_name}, {lead_title} at {lead_company}`**

  **`Commonality: {strongest_hook} (strength: {hook_strength}/10)`**

  **`Signal: {selected_signal_title} — {selected_signal_body}`**

  **`Company tech stack: {tech_stack}`**

  **`RAG style examples: {winning_snippets}`**

**`Output JSON:`**

  **`{`**

    **`"subject_line": "...",`**

    **`"email_body": "...",`**

    **`"linkedin_message": "..."   (max 40 words, even more casual)`**

  **`}`**

**`Node 5 — Critique & Score:`**  
 **`LLM self-critiques draft on 5 dimensions (score 1–10 each):`**

**`text`**

**`Dimensions:`**

  **`1. Specificity   — Is this unmistakably about THIS person? (not generic)`**

  **`2. Relevance     — Does the pain point logically connect to their role/company?`**

  **`3. Tone          — Does it read like a human wrote it, not an AI?`**

  **`4. CTA Clarity   — Is the ask unambiguous and low-friction?`**

  **`5. Subject Line  — Would you open this email?`**

**`Return: {scores: {}, average: float, rewrite_note: str}`**

**`If average < CRITIQUE_REWRITE_THRESHOLD → loop back to Node 4 with rewrite_note as additional instruction`**

**`Max 3 rewrite iterations before accepting best-scoring draft`**

**`Node 6 — Tone Adapter:`**  
 **`Applies final adjustments based on lead context:`**

* **`C-Suite / VP → formal, no contractions, third-party social proof`**

* **`IC / Manager → casual, contractions allowed, peer-to-peer framing`**

* **`Fintech / Legal / Gov → formal register throughout`**

* **`Consumer / Dev Tools / Creative → casual register throughout`**

* **`LinkedIn variant → always casual, shorter, more direct`**

## **`3.5.4 Personalization Output Schema`**

**`python`**

**`class PersonalizationOutput(BaseModel):`**

    **`lead_id: UUID`**

    **`sender_id: UUID`**

    **`subject_line: str`**

    **`email_body: str`**

    **`linkedin_message: str`**

    **`personalization_hook: str            # The commonality or signal hook used`**

    **`hook_type: str                       # "commonality" | "signal" | "none"`**

    **`hook_strength: float                 # 0-10`**

    **`signal_used: Optional[SignalType]`**

    **`critique_score: float                # Final average across 5 dimensions`**

    **`critique_breakdown: dict[str, float] # Per-dimension scores`**

    **`generation_iterations: int`**

    **`token_usage: dict                    # {"prompt_tokens": int, "completion_tokens": int}`**

    **`status: str                        # "DRAFT" | "APPROVED" | "SENT"`**

    **`approved_at: Optional[datetime]`**

    **`generated_at: datetime`**

**`API Endpoints:`**

**`text`**

**`POST   /api/v1/sender                              — Create/update sender profile`**

**`GET    /api/v1/sender                              — Get current sender profile`**

**`POST   /api/v1/personalize/{lead_id}               — Generate snippet (queues agent job)`**

**`POST   /api/v1/personalize/batch                   — Batch generation for list of lead_ids`**

**`GET    /api/v1/personalize/{lead_id}/drafts        — All drafts for a lead`**

**`PATCH  /api/v1/personalize/{draft_id}              — Edit draft body/subject manually`**

**`POST   /api/v1/personalize/{draft_id}/approve      — Approve draft; if linked to sequence enrollment, set enrollment ACTIVE and next_step_at=NOW()`**

**Draft status transition rules:**

* **`DRAFT -> APPROVED`** when a user approves a generated draft.
* **`APPROVED -> SENT`** after the sequence execution worker successfully writes the outbound `outreach_logs` row for the same `draft_id`.
* **`DRAFT -> SENT`** is allowed only for no-approval sequence steps where the worker generates and immediately sends the draft.
* Failed, bounced, or skipped send attempts do not mark a draft `SENT`.

---

## **`Module 6: Sequence Manager`**

**`Purpose: Define multi-step, multi-channel outreach sequences and manage each lead's`**  
 **`position within them. Includes a warm-up channel (LINKEDIN_ENGAGE) for pre-outreach`**  
 **`social engagement before cold messages.`**

## **`3.6.1 Data Models`**

**`python`**

**`class Channel(str, Enum):`**

    **`EMAIL                = "EMAIL"`**

    **`LINKEDIN_MESSAGE     = "LINKEDIN_MESSAGE"`**

    **`LINKEDIN_CONNECTION  = "LINKEDIN_CONNECTION"`**

    **`LINKEDIN_ENGAGE      = "LINKEDIN_ENGAGE"   # Like/comment on a post (warm-up)`**

**`Channel/StepType Validation Rules (enforced at API and worker level):`**
  **`ENGAGEMENT steps → only LINKEDIN_ENGAGE channel`**
  **`OUTREACH steps → only EMAIL, LINKEDIN_MESSAGE, or LINKEDIN_CONNECTION`**
  **`Creating a step with mismatched channel/type returns HTTP 422`**

**`class StepType(str, Enum):`**

    **`OUTREACH   = "OUTREACH"    # Sends a message`**

    **`ENGAGEMENT = "ENGAGEMENT"  # Warm-up action (like/comment) — no message sent`**

**`class Sequence(BaseModel):`**

    **`id: UUID`**

    **`name: str`**

    **`icp_id: UUID`**

    **`steps: list[SequenceStep]`**

    **`is_active: bool`**

    **`auto_enroll: bool              # Auto-enroll leads matching ICP when threshold met`**

    **`auto_enroll_threshold: Optional[float]   # Per-sequence override; fallback is AUTO_ENROLL_ICP_THRESHOLD`**

    **`created_at: datetime`**

**`Sequence is_active behavior:`**
  **`Setting is_active=false pauses execution for the sequence. The update service moves ACTIVE enrollments for that sequence to PAUSED, sets paused_reason='SEQUENCE_DEACTIVATED', and sets paused_at=NOW().`**
  **`Setting is_active=true resumes only enrollments with status='PAUSED' AND paused_reason='SEQUENCE_DEACTIVATED', restoring them to ACTIVE without changing next_step_at and clearing paused_reason/paused_at.`**
  **`User-paused enrollments use paused_reason='USER' and remain PAUSED when a sequence is reactivated.`**
  **`Terminal enrollments (BOUNCED, REPLIED, UNSUBSCRIBED, COMPLETED) are never resumed by sequence reactivation.`**
  **`Invariant: paused_reason and paused_at are NULL unless status='PAUSED'; every PAUSED row must have a non-null paused_reason.`**

**`class SequenceStep(BaseModel):`**

    **`id: UUID`**

    **`sequence_id: UUID`**

    **`step_number: int`**

    **`step_type: StepType            # OUTREACH or ENGAGEMENT`**

    **`channel: Channel`**

    **`delay_days: int                # Days after previous step`**

    **`template: Optional[str]        # Static template (merge fields: {{name}}, {{company}})`**

    **`use_ai_personalization: bool   # Use LangGraph agent for this step`**
    **`requires_approval: bool        # Wait for manual AI draft review`**

    **`engagement_action: Optional[str]  # For ENGAGEMENT steps: "like_latest_post" |`**

                                      **`#   "comment_latest_post" | "react_company_post"`**

**`class LeadSequenceEnrollment(BaseModel):`**

    **`id: UUID`**

    **`lead_id: UUID`**

    **`sequence_id: UUID`**

    **`current_step: int`**

    **`status: EnrollmentStatus       # ACTIVE | PAUSED | PENDING_APPROVAL | REPLIED | BOUNCED | UNSUBSCRIBED | COMPLETED`**

    **`paused_reason: Optional[PauseReason]  # USER | SEQUENCE_DEACTIVATED; NULL unless status=PAUSED`**

    **`paused_at: Optional[datetime]`**

    **`enrolled_at: datetime`**

    **`next_step_at: datetime          # Initialized at enrollment creation (default NOW)`**

    **`reply_received: bool`**

    **`reply_body: Optional[str]`**

**`class EnrollmentStatus(str, Enum):`**

    **`ACTIVE           = "ACTIVE"`**

    **`PAUSED           = "PAUSED"`**
    
    **`PENDING_APPROVAL = "PENDING_APPROVAL"  # Waiting for manual AI draft review`**

    **`REPLIED          = "REPLIED"`**

    **`BOUNCED          = "BOUNCED"  # Terminal: invalid/unreachable address, never auto-resumed`**

    **`UNSUBSCRIBED = "UNSUBSCRIBED"`**

    **`COMPLETED    = "COMPLETED"`**

**`class PauseReason(str, Enum):`**

    **`USER                 = "USER"`**

    **`SEQUENCE_DEACTIVATED = "SEQUENCE_DEACTIVATED"`**

## **`3.6.2 Sequence Execution Worker`**

**`text`**

**`ARQ Cron: every 15 minutes`**

**`Query: SELECT * FROM lead_sequence_enrollments`**

       **`WHERE status = 'ACTIVE' AND next_step_at <= NOW()`**

**`For each enrollment:`**

  **`1. Load current SequenceStep by (sequence_id, current_step)`**


  **`2a. If step_type = ENGAGEMENT (warm-up):`**

        **`Log engagement action to outreach_logs with step_type='ENGAGEMENT', channel='LINKEDIN_ENGAGE', engagement_action=<value>, delivery_status='ENGAGED'`**

        **`No message sent; lead.last_contacted_at=NOW() because this is still an intentional outbound touch`**

        

  **`2b. If step_type = OUTREACH:`**

        **`If approved draft exists for (enrollment_id, sequence_step_id):`**
          **`→ Use approved draft content directly (no regeneration)`**

        **`Else if use_ai_personalization = true:`**

          **`→ Invoke LangGraph Golden Snippet agent to generate draft`**
          **`→ Save draft with enrollment_id + sequence_id + sequence_step_id`**
          **`→ If step.requires_approval = true: Set status=PENDING_APPROVAL and stop (do not send)`**

        **`Else:`**

          **`→ Render template with lead merge fields`**

        

        **`Send via channel:`**

          **`EMAIL           → Mock SMTP (log to outreach_logs)`**

          **`LINKEDIN_*      → Mock API call (log to outreach_logs)`**

        **`Mock outcomes are deterministic by default:`**
          **`MOCK_SMTP_MODE=deterministic`**
          **`MOCK_SMTP_BOUNCE_DOMAINS=bounce.test,invalid.test`**
          **`MOCK_SMTP_REPLY_DOMAINS=reply.test`**
          **`EMAIL uses MOCK_SMTP_* rules: bounce domains return BOUNCED, reply domains return REPLIED, all other recipients return SENT.`**
          **`LINKEDIN_MESSAGE and LINKEDIN_CONNECTION always return SENT in mock mode; only EMAIL can produce deterministic BOUNCED/REPLIED outcomes.`**
          **`LINKEDIN_ENGAGE always returns ENGAGED in mock mode and follows the engagement logging rule above.`**
          **`Optional MOCK_SMTP_MODE=seeded_random may use MOCK_SMTP_BOUNCE_RATE, MOCK_SMTP_REPLY_RATE, and MOCK_SMTP_RANDOM_SEED, but tests and demos must use deterministic or seeded outcomes only.`**


  **`3. Record OutreachLog entry with all metadata`**
      **`delivery_status starts as PENDING only inside the worker transaction; worker must set final status before commit`**

      **`SENT outcome:`**
        **`outreach_logs.delivery_status='SENT'`**
        **`outreach_logs.sent_at=NOW()`**
        **`draft.status='SENT' if draft_id exists`**
        **`lead.last_contacted_at=NOW()`**

      **`BOUNCED outcome:`**
        **`outreach_logs.delivery_status='BOUNCED', bounced_at=NOW(), error_code/error_message populated`**
        **`lead.outreach_status='BOUNCED'`**
        **`enrollment.status='BOUNCED'`**
        **`do not advance to the next step`**

      **`ENGAGED outcome:`**
        **`outreach_logs.delivery_status='ENGAGED', engagement_action populated`**
        **`outreach_logs.sent_at=NOW()`**
        **`lead.last_contacted_at=NOW()`**

      **`REPLIED outcome:`**
        **`outreach_logs.delivery_status='REPLIED', replied_at=NOW()`**
        **`outreach_logs.sent_at=NOW()`**
        **`lead.outreach_status='REPLIED'`**
        **`enrollment.status='REPLIED', reply_received=true`**
        **`do not advance to the next step`**


  **`4. Advance enrollment:`**

        **`If more steps remain:`**

          **`current_step += 1`**

          **`next_step_at = NOW() + next_step.delay_days`**

        **`Else:`**

          **`status = COMPLETED`**


  **`5. If reply_received flag set (manually or via mock):`**

        **`status = REPLIED`**

        **`Stop further steps`**

**`API Endpoints:`**

**`text`**

**`POST   /api/v1/sequences                              — Create sequence`**

**`GET    /api/v1/sequences                              — List sequences`**

**`GET    /api/v1/sequences/{id}                         — Sequence detail + all steps`**

**`PUT    /api/v1/sequences/{id}                         — Update sequence`**

**`POST   /api/v1/sequences/{id}/enroll/{lead_id}        — Enroll single lead`**

**`POST   /api/v1/sequences/{id}/enroll/batch            — Bulk enroll by min ICP score`**

**`GET    /api/v1/sequences/{id}/enrollments             — List all enrollments with status`**

**`PATCH  /api/v1/sequences/{id}/enrollments/{eid}       — Update enrollment status`**
**`POST   /api/v1/sequences/{id}/enrollments/{eid}/resume — Resume PENDING_APPROVAL enrollment (sets ACTIVE + next_step_at=NOW())`**

---

## **`Module 7: Analytics Engine`**

**`Purpose: Track and visualize performance across the full outbound + inbound funnel,`**  
 **`including TAM coverage, personalization quality, and sequence effectiveness.`**

## **`3.7.1 Metrics Tracked`**

**`python`**

**`class TimeSeriesPoint(BaseModel):`**

    **`date: date`**

    **`value: int`**

**`class AnalyticsMetrics(BaseModel):`**

    **`# TAM Coverage (NEW)`**

    **`tam_total_estimated: int`**

    **`tam_captured: int`**

    **`tam_in_sequence: int`**

    **`tam_coverage_pct: float`**

    **`# Funnel metrics`**

    **`total_leads: int`**

    **`leads_enriched: int`**

    **`leads_icp_qualified: int           # ICP score > 70`**

    **`leads_in_sequence: int`**

    **`emails_sent: int`**

    **`emails_opened: int                 # Mock pixel tracking`**

    **`replies_received: int`**

    **`meetings_booked: int               # Manually marked`**

    **`# Inbound vs Outbound Split (NEW)`**

    **`inbound_leads_total: int`**

    **`outbound_leads_total: int`**

    **`inbound_reply_rate: float`**

    **`outbound_reply_rate: float`**

    **`inbound_events_by_type: dict[str, int]`**

    **`# Signal metrics`**

    **`signals_detected_7d: int`**

    **`signals_by_type: dict[str, int]`**

    **`avg_signal_strength: float`**

    **`signals_auto_triggered_drafts: int`**

    **`# Personalization metrics`**

    **`avg_critique_score: float`**

    **`avg_hook_strength: float           # NEW — average commonality hook quality`**

    **`pct_commonality_hooks: float       # NEW — % of drafts that used a commonality vs signal`**

    **`avg_generation_iterations: float`**

    **`total_tokens_used: int`**

    **`estimated_cost_usd: float          # Calculated from token usage + model pricing`**

    **`# Sequence metrics`**

    **`sequence_completion_rate: float`**

    **`avg_reply_step: float              # Which step number gets most replies`**

    **`top_performing_sequence_id: UUID`**

    **`top_performing_sequence_name: str`**

    **`# Time series for charts`**

    **`daily_leads_added: list[TimeSeriesPoint]`**

    **`daily_emails_sent: list[TimeSeriesPoint]`**

    **`daily_signals: list[TimeSeriesPoint]`**

    **`daily_inbound_events: list[TimeSeriesPoint]  # NEW`**

**`API Endpoints:`**

**`text`**

**`GET    /api/v1/analytics/overview          — Full dashboard metrics object`**

**`GET    /api/v1/analytics/funnel            — Funnel conversion chart data`**

**`GET    /api/v1/analytics/tam               — TAM coverage breakdown`**

**`GET    /api/v1/analytics/signals           — Signal distribution + trend`**

**`GET    /api/v1/analytics/inbound           — Inbound event stats by source/type`**

**`GET    /api/v1/analytics/sequences/{id}    — Per-sequence performance breakdown`**

**`GET    /api/v1/analytics/personalization   — Quality scores + token cost tracker`**

---

## **`4. NextJS Frontend Specification`**

## **`4.1 Tech Stack`**

* **`Framework: NextJS App Router (TypeScript) + React 18`**

* **`UI Library: shadcn/ui + Tailwind CSS`**

* **`State Management: Zustand`**

* **`Data Fetching: TanStack Query v5 (React Query)`**

* **`Charts: Recharts`**

* **`Real-time: EventSource (SSE client)`**

* **`Forms: React Hook Form + Zod`**

**Phase 2.5 frontend alignment requirement:** before starting Phase 3, install and adopt the frontend libraries above for the pages that will carry real-time and form-heavy workflows. Use TanStack Query for server state, React Hook Form + Zod for `/icp` and `/sender`, Recharts for TAM/analytics/quality charts, and a typed EventSource helper for SSE. Zustand is reserved for cross-page UI/session state that is not already handled by URL params or TanStack Query cache.

## **`4.2 Pages & Views`**

## **`Page 1: Dashboard (/)`**

**`text`**

**`┌─────────────────────────────────────────────────────┐`**

**`│  ORION                              [+ Add Leads]   │`**

**`├──────────┬──────────┬──────────┬───────────────────┤`**

**`│  Leads   │  ICP     │ Signals  │ Inbound Events    │`**

**`│   247    │  142     │  38 🔔   │   12 today 🔔     │`**

**`├──────────┴──────────┴──────────┴───────────────────┤`**

**`│  Funnel Chart                                       │`**

**`│  [Leads → Enriched → ICP Qual → Sequenced → Sent]  │`**

**`├────────────────────────┬────────────────────────────┤`**

**`│  Live Feed (SSE)        │  Active Sequences          │`**

**`│  ● [IN] Signup: j@x.co  │  YC Founders Outbound      │`**

**`│  ● [SIG] Acme raised $12M│   34 enrolled, 12 replied │`**

**`│  ● [SIG] John joined Stripe│                         │`**

**`└────────────────────────┴────────────────────────────┘`**

## **`Page 2: TAM Explorer (/tam) [NEW]`**

* **`ICP selector at top`**

* **`Heatmap/Treemap (Recharts Treemap component):`**

  * **`X-axis: Industry buckets from ICP`**

  * **`Y-axis: Company size buckets from ICP`**

  * **`Cell color: Grey (0% coverage) → Blue (partially contacted) → Green (>50% penetrated)`**

  * **`Cell label: {coverage_pct}% covered, {in_sequence} in sequence`**

* **`Click a grey cell → triggers "Discover Leads" action: YC scraper or mock import filtered to that cell's criteria`**

* **`If the backing data source is not implemented yet, clicking a grey cell opens a Discover Leads action panel with the selected industry/company-size criteria prefilled and a disabled/explained real-source action plus an enabled mock import action.`**

* **`Summary bar at top: Total TAM: 4,200 | Captured: 247 (5.9%) | In Sequence: 142 (3.4%)`**

## **`Page 3: Sender Profile (/sender) [NEW]`**

* **`Single-page form with sections: Basic Info, Education, Work History, Interests & Hobbies, Conferences`**

* **`Each section allows adding multiple items via dynamic field arrays (React Hook Form useFieldArray)`**

* **`On save, shows: "Your profile is used to find commonalities with prospects. Complete profiles produce stronger personalization."`**

* **`Preview panel: shows a sample commonality analysis against a mock lead`**

## **`Page 4: ICP Builder (/icp)`**

* **`Multi-step wizard: Firmographic → Persona → Signals → Weighting`**

* **`Signals step captures selected signal types, signal recency window, minimum signal strength, and optional relevance keywords. These values are stored in icps.config and used by Phase 3 signal scoring/filtering.`**

* **`Live preview of matching lead count as criteria are configured`**

* **`Slider-based weight configuration per criterion (weights auto-normalize to sum to 1.0)`**

## **`Page 5: Lead Board (/leads)`**

* **`Table view columns: Name, Company, Source badge (Inbound/Outbound), ICP Score (progress bar), Enrichment Status badge, Last Signal, Outreach Status`**

* **`Filter panel: ICP Score range slider, Signal type, Outreach status, Industry, Source type`**

* **`Click row → Lead Detail Drawer (full-width right panel):`**

  * **`Full enriched profile (all 20+ fields)`**

  * **`Signal timeline (chronological)`**

  * **`Commonality analysis panel (shows strongest hooks if sender profile is set)`**

  * **`All generated drafts with critique scores`**

  * **`Current sequence enrollment + step position`**

  * **`For P3/P4/P5-only sections with no data yet, render stable empty states instead of omitting the section. This keeps the drawer layout ready for signals, commonalities, drafts, and sequence position as those modules land.`**

* **`Bulk actions: Enrich selected, Enroll in sequence, Export CSV, Delete`**

## **`Page 6: Signal & Inbound Feed (/feed)`**

* **`Unified real-time SSE-powered feed merging outbound signals AND inbound webhook events`**

* **`Toggle tabs: "All" | "Outbound Signals" | "Inbound Events"`**

* **`Each Signal card shows:`**

  * **`Lead avatar + name + company`**

  * **`Signal type badge (color-coded by type)`**

  * **`Signal title + body`**

  * **`Signal strength score (progress bar)`**

  * **`Time ago`**

  * **`[Generate Draft] → triggers personalization agent inline`**

  * **`[Dismiss] button`**

* **`Each Inbound card shows:`**

  * **`Event type badge (e.g. "Product Signup", "Ad Click")`**

  * **`Source badge (e.g. "Clerk", "LinkedIn Ads")`**

  * **`Email/name extracted`**

  * **`Enrichment status`**

  * **`[View Lead] button`**

## **`Page 7: Sequence Builder (/sequences)`**

* **`Left panel: list of all sequences with enrollment counts`**

* **`Right panel: visual step builder for selected sequence`**

  * **`Drag-and-drop step reordering (dnd-kit)`**

  * **`Per-step config:`**

    * **`Step type: OUTREACH or ENGAGEMENT (warm-up)`**

    * **`Channel: EMAIL / LINKEDIN_MESSAGE / LINKEDIN_ENGAGE`**

    * **`Delay (days)`**

    * **`For OUTREACH: Template text vs AI Personalization toggle`**

    * **`For ENGAGEMENT: Select engagement action (like / comment)`**

  * **`Enrollment metrics per step: sent / opened / replied counts`**

* **`Auto-enroll toggle with ICP threshold slider`**

## **`Page 8: Email Composer (/compose)`**

* **`Lead search/autocomplete`**

* **`Signal selector (shows all signals for selected lead, sorted by strength)`**

* **`Panel layout (3 columns):`**

  1. **`Lead profile summary + commonality hooks (extracted from sender profile vs lead)`**

  2. **`AI Draft (streaming SSE — characters appear as agent generates)`**

  3. **`Edit mode (editable text area, pre-filled from generated draft)`**

* **`Quality score display: 5-axis radar chart (Recharts RadarChart) showing per-dimension critique scores`**

* **`Approve → sends to sequence queue → toast notification`**

## **`Page 9: Analytics (/analytics)`**

* **`TAM coverage summary card (links to TAM Explorer)`**

* **`Funnel conversion waterfall chart (Recharts BarChart with reference lines)`**

* **`Inbound vs Outbound performance split (side-by-side grouped bars)`**

* **`Signal volume by type (stacked bar, last 30 days)`**

* **`ICP score distribution (histogram)`**

* **`Personalization quality over time (line chart: avg critique score by week)`**

* **`Sequence performance table (cols: name, enrolled, sent, opened, replied, reply rate)`**

* **`Token usage + estimated cost tracker (daily bar chart + running total)`**

## **`4.3 Real-Time SSE Events`**

**`Client subscribes to GET /api/v1/events/stream (text/event-stream):`**

**SSE contract source of truth:** backend Pydantic schemas own the event union in `backend/app/schemas/events.py`. The frontend imports generated or mirrored types from `frontend/src/lib/events/types.ts`; Phase 3 contract tests must assert every emitted event name and payload shape matches that union. Do not add ad-hoc event names in workers or UI code.

**`typescript`**

**`type SSEEvent =`**

  **`| { type: "lead.enrichment.complete";     payload: { lead_id: string; icp_score: number; company_name: string } }`**

  **`| { type: "lead.enrichment.failed";       payload: { lead_id: string; error: string } }`**

  **`| { type: "signal.detected";              payload: Signal }`**

  **`| { type: "inbound.event.received";       payload: { event_id: string; event_type: string; source: string; email: string } }`**

  **`| { type: "inbound.lead.enrolled";        payload: { lead_id: string; sequence_id: string; icp_score: number } }`**

  **`| { type: "draft.generated";              payload: { lead_id: string; draft_id: string; critique_score: number } }`**

  **`| { type: "draft.token";                  payload: { draft_id: string; token: string } }   // streaming`**

  **`| { type: "sequence.step.sent";           payload: { lead_id: string; sequence_id: string; step_number: number; channel: string } }`**

  **`| { type: "lead.created";                  payload: { lead_id: string; source: string; company_name: string | null } }`**

  **`| { type: "worker.status";                payload: { worker: string; status: "running" | "idle" | "error"; queue_depth: number } }`**

**`4.3.1 Token Streaming Architecture (Worker → Browser)`**

**`LLM token streaming from background ARQ workers to the browser uses Redis Pub/Sub as the bridge:`**

  **`1. ARQ worker generates tokens via LangGraph agent (streaming LLM call)`**
  **`2. Each token is published to Redis channel: "sse:{draft_id}"`**
  **`3. SSE endpoint (/api/v1/events/stream) subscribes to relevant Redis channels`**
  **`4. SSE endpoint relays tokens as draft.token events to connected browsers`**
  **`5. On completion, worker publishes final draft.generated event`**

**`This decouples the worker (producer) from the API server (consumer) via Redis Pub/Sub.`**

---

## **`5. Database Schema`**

**`sql`**

***`-- ============================================================`***

***`-- FULL SCHEMA: All tables including V1 + new additions`***

***`-- ============================================================`***

**`CREATE EXTENSION IF NOT EXISTS "pgcrypto";`**

**`CREATE EXTENSION IF NOT EXISTS "vector";   -- pgvector for semantic search & RAG`**

***`-- ICPs`***

**`CREATE TABLE icps (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`name VARCHAR NOT NULL,`**

    **`description TEXT,`**

    **`config JSONB NOT NULL,           -- All ICP criteria as JSON`**

    **`weights JSONB NOT NULL,`**

    **`is_active BOOLEAN DEFAULT true,`**

    **`created_at TIMESTAMPTZ DEFAULT NOW(),`**

    **`updated_at TIMESTAMPTZ DEFAULT NOW()`**

**`);`**

***`-- Sender Profile (NEW)`***

**`CREATE TABLE sender_profiles (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`user_id VARCHAR NOT NULL UNIQUE DEFAULT 'default',`**

    **`name VARCHAR NOT NULL,`**

    **`current_title VARCHAR,`**

    **`current_company VARCHAR,`**

    **`education JSONB DEFAULT '[]',`**

    **`past_employers JSONB DEFAULT '[]',`**

    **`cities_lived JSONB DEFAULT '[]',`**

    **`hobbies_and_interests JSONB DEFAULT '[]',`**

    **`investors JSONB DEFAULT '[]',`**

    **`languages_spoken JSONB DEFAULT '[]',`**

    **`conferences_attended JSONB DEFAULT '[]',`**

    **`updated_at TIMESTAMPTZ DEFAULT NOW()`**

**`);`**

***`-- Leads`***

**`CREATE TABLE leads (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`first_name VARCHAR,`**

    **`last_name VARCHAR,`**

    **`email VARCHAR,`**

    **`linkedin_url VARCHAR,`**

    **`github_url VARCHAR,`**

    **`twitter_url VARCHAR,`**

    **`company_name VARCHAR,             -- Nullable for early inbound records before enrichment`**

    **`company_domain VARCHAR,`**

    **`company_linkedin_url VARCHAR,`**

    **`company_size INTEGER,`**

    **`industry VARCHAR,`**

    **`funding_stage VARCHAR,`**

    **`total_funding_usd BIGINT,`**

    **`tech_stack JSONB DEFAULT '[]',`**

    **`title VARCHAR,`**

    **`seniority VARCHAR,`**

    **`department VARCHAR,`**

    **`enriched_data JSONB,`**

    **`enrichment_status VARCHAR DEFAULT 'PENDING',`**

    **`enrichment_sources JSONB DEFAULT '[]',`**

    **`enrichment_at TIMESTAMPTZ,`**

    **`icp_score FLOAT,`**

    **`icp_id UUID REFERENCES icps(id),`**

    **`icp_score_breakdown JSONB,        -- Optional map: {"icp_id": score} for analytics/debugging`**

    **`outreach_status VARCHAR DEFAULT 'UNTOUCHED',`**

    **`last_contacted_at TIMESTAMPTZ,  -- Denormalized for signal cool-off scoring`**

    **`embedding VECTOR(768),           -- pgvector; dimension fixed at schema-create time, must match EMBEDDING_MODEL`**

    **`source VARCHAR DEFAULT 'MANUAL',`**

    **`inbound_event_id UUID,           -- FK set after inbound_events table created`**

    **`created_at TIMESTAMPTZ DEFAULT NOW(),`**

    **`updated_at TIMESTAMPTZ DEFAULT NOW()`**

**`);`**

***`-- Inbound Events (NEW)`***

**`CREATE TABLE inbound_events (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`source VARCHAR NOT NULL,`**

    **`event_type VARCHAR NOT NULL,`**

    **`email VARCHAR,`**

    **`first_name VARCHAR,`**

    **`last_name VARCHAR,`**

    **`linkedin_url VARCHAR,`**

    **`company_domain VARCHAR,`**

    **`source_event_id VARCHAR,          -- Stable upstream event ID when available; unique per source when non-null`**

    **`event_fingerprint VARCHAR UNIQUE, -- Nullable; SHA256(source + event_type + source-specific fingerprint keys) when stable keys exist`**

    **`raw_payload JSONB NOT NULL,`**

    **`processed BOOLEAN DEFAULT false,`**

    **`processing_error TEXT,`**

    **`created_lead_id UUID REFERENCES leads(id),`**

    **`received_at TIMESTAMPTZ DEFAULT NOW(),`**

    **`processed_at TIMESTAMPTZ`**

**`);`**

***`-- Add FK from leads to inbound_events (circular FK — in SQLAlchemy, use relationship() with post_update=True)`***

**`ALTER TABLE leads ADD CONSTRAINT fk_leads_inbound_event`**

    **`FOREIGN KEY (inbound_event_id) REFERENCES inbound_events(id);`**

***`-- Signals`***

**`CREATE TABLE signals (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,`**

    **`company_domain VARCHAR,`**

    **`signal_type VARCHAR NOT NULL,`**

    **`signal_title VARCHAR NOT NULL,`**

    **`signal_body TEXT,`**

    **`signal_url VARCHAR,`**

    **`signal_strength FLOAT,`**

    **`signal_hash VARCHAR UNIQUE,`**

    **`is_read BOOLEAN DEFAULT false,`**

    **`triggered_outreach BOOLEAN DEFAULT false,`**

    **`detected_at TIMESTAMPTZ DEFAULT NOW(),`**

    **`expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '90 days')`**

**`);`**

***`-- Personalization Drafts`***

**`CREATE TABLE personalization_drafts (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,`**

    **`sender_id UUID REFERENCES sender_profiles(id),`**

    **`sequence_id UUID,`**

    **`sequence_step_id UUID,`**

    **`enrollment_id UUID,`**

    **`subject_line VARCHAR,`**

    **`email_body TEXT,`**

    **`linkedin_message TEXT,`**

    **`personalization_hook TEXT,`**

    **`hook_type VARCHAR,               -- 'commonality' | 'signal' | 'none'`**

    **`hook_strength FLOAT,`**

    **`signal_used VARCHAR,`**

    **`critique_score FLOAT,`**

    **`critique_breakdown JSONB,`**

    **`generation_iterations INT DEFAULT 1,`**

    **`token_usage JSONB,`**

    **`status VARCHAR DEFAULT 'DRAFT',  -- DRAFT | APPROVED | SENT`**

    **`approved_at TIMESTAMPTZ,`**

    **`created_at TIMESTAMPTZ DEFAULT NOW()`**

**`);`**

***`-- Sequences`***

**`CREATE TABLE sequences (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`name VARCHAR NOT NULL,`**

    **`icp_id UUID REFERENCES icps(id),`**

    **`is_active BOOLEAN DEFAULT true,`**

    **`auto_enroll BOOLEAN DEFAULT false,`**

    **`auto_enroll_threshold FLOAT,   -- NULL => use AUTO_ENROLL_ICP_THRESHOLD`**

    **`created_at TIMESTAMPTZ DEFAULT NOW()`**

**`);`**

***`-- Sequence Steps`***

**`CREATE TABLE sequence_steps (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`sequence_id UUID REFERENCES sequences(id) ON DELETE CASCADE,`**

    **`step_number INT NOT NULL,`**

    **`step_type VARCHAR DEFAULT 'OUTREACH',       -- 'OUTREACH' | 'ENGAGEMENT'`**

    **`channel VARCHAR NOT NULL,`**

    **`delay_days INT DEFAULT 0,`**

    **`template TEXT,`**

    **`use_ai_personalization BOOLEAN DEFAULT true,`**

    **`requires_approval BOOLEAN DEFAULT false,`**

    **`engagement_action VARCHAR,                  -- 'like_latest_post' | 'comment_latest_post'`**

    **`UNIQUE(sequence_id, step_number)`**

**`);`**

***`-- Lead Sequence Enrollments`***

**`CREATE TABLE lead_sequence_enrollments (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`lead_id UUID REFERENCES leads(id),`**

    **`sequence_id UUID REFERENCES sequences(id),`**

    **`current_step INT DEFAULT 1,`**

    **`status VARCHAR DEFAULT 'ACTIVE', -- ACTIVE | PAUSED | PENDING_APPROVAL | REPLIED | BOUNCED | UNSUBSCRIBED | COMPLETED`**

    **`paused_reason VARCHAR, -- USER | SEQUENCE_DEACTIVATED; NULL unless status='PAUSED'`**

    **`paused_at TIMESTAMPTZ,`**

    **`next_step_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),`**

    **`enrolled_at TIMESTAMPTZ DEFAULT NOW(),`**

    **`reply_received BOOLEAN DEFAULT false,`**

    **`reply_body TEXT,`**

    **`UNIQUE(lead_id, sequence_id)`**

**`);`**

***`-- Add draft linkage FKs after dependent tables exist`***

**`ALTER TABLE personalization_drafts`**

    **`ADD CONSTRAINT fk_drafts_sequence`**
    **`FOREIGN KEY (sequence_id) REFERENCES sequences(id);`**

**`ALTER TABLE personalization_drafts`**

    **`ADD CONSTRAINT fk_drafts_sequence_step`**
    **`FOREIGN KEY (sequence_step_id) REFERENCES sequence_steps(id);`**

**`ALTER TABLE personalization_drafts`**

    **`ADD CONSTRAINT fk_drafts_enrollment`**
    **`FOREIGN KEY (enrollment_id) REFERENCES lead_sequence_enrollments(id);`**

***`-- Outreach Logs`***

**`CREATE TABLE outreach_logs (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`lead_id UUID REFERENCES leads(id),`**

    **`sequence_id UUID REFERENCES sequences(id),`**

    **`step_number INT,`**

    **`step_type VARCHAR,`**

    **`channel VARCHAR,`**

    **`subject VARCHAR,`**

    **`body TEXT,`**

    **`engagement_action VARCHAR,`**

    **`delivery_status VARCHAR DEFAULT 'PENDING', -- PENDING | SENT | BOUNCED | REPLIED | FAILED | ENGAGED`**

    **`error_code VARCHAR,`**

    **`error_message TEXT,`**

    **`sent_at TIMESTAMPTZ, -- Set only after final SENT/ENGAGED/REPLIED outcome is known`**

    **`opened_at TIMESTAMPTZ,`**

    **`replied_at TIMESTAMPTZ,`**

    **`bounced_at TIMESTAMPTZ,`**

    **`draft_id UUID REFERENCES personalization_drafts(id)`**

**`);`**

***`-- Winning Snippets (RAG corpus for agent Node 3 — populated by Phase 4 seed script)`***

**`CREATE TABLE winning_snippets (`**

    **`id UUID PRIMARY KEY DEFAULT gen_random_uuid(),`**

    **`subject_line VARCHAR,`**

    **`body TEXT NOT NULL,`**

    **`hook_type VARCHAR,                -- 'commonality' | 'signal' | 'observation'`**

    **`industry VARCHAR,                 -- denormalised filter for retrieval`**

    **`role_seniority VARCHAR,           -- e.g. 'C-Suite', 'IC'`**

    **`reply_rate FLOAT,                 -- mock metric used for RAG ranking`**

    **`embedding VECTOR(768) NOT NULL,   -- same dimension as leads.embedding`**

    **`created_at TIMESTAMPTZ DEFAULT NOW()`**

**`);`**

***`-- ============================================================`***

***`-- INDEXES`***

***`-- ============================================================`***

**`CREATE INDEX idx_leads_icp_score ON leads(icp_score DESC);`**

**`CREATE INDEX idx_leads_enrichment_status ON leads(enrichment_status);`**

**`CREATE INDEX idx_leads_source ON leads(source);`**

**`CREATE INDEX idx_leads_outreach_status ON leads(outreach_status);`**

**`CREATE INDEX idx_leads_last_contacted_at ON leads(last_contacted_at DESC);`**

**`CREATE INDEX idx_signals_lead_id ON signals(lead_id);`**

**`CREATE INDEX idx_signals_detected_at ON signals(detected_at DESC);`**

**`CREATE INDEX idx_signals_expires_at ON signals(expires_at);`**

**`CREATE INDEX idx_signals_type ON signals(signal_type);`**

**`CREATE INDEX idx_signals_strength ON signals(signal_strength DESC);`**

**`CREATE INDEX idx_inbound_events_processed ON inbound_events(processed);`**

**`CREATE INDEX idx_inbound_events_received ON inbound_events(received_at DESC);`**

**`CREATE INDEX idx_inbound_events_email ON inbound_events(email);`**

**`CREATE UNIQUE INDEX uq_inbound_source_event_id ON inbound_events(source, source_event_id) WHERE source_event_id IS NOT NULL;`**

**`CREATE INDEX idx_enrollments_next_step ON lead_sequence_enrollments(next_step_at)`**

    **`WHERE status = 'ACTIVE';`**

**`CREATE INDEX idx_enrollments_paused_reason ON lead_sequence_enrollments(sequence_id, paused_reason)`**

    **`WHERE status = 'PAUSED';`**

**`CREATE INDEX idx_drafts_lead_id ON personalization_drafts(lead_id);`**

**`CREATE INDEX idx_drafts_enrollment_id ON personalization_drafts(enrollment_id);`**

**`CREATE INDEX idx_outreach_logs_lead ON outreach_logs(lead_id);`**

**`CREATE INDEX idx_leads_updated_at ON leads(updated_at DESC);`**

***`-- pgvector HNSW indexes for cosine-distance similarity (added in migration 002)`***

**`CREATE INDEX idx_leads_embedding_hnsw ON leads`**
**`    USING hnsw (embedding vector_cosine_ops);`**

**`CREATE INDEX idx_winning_snippets_embedding_hnsw ON winning_snippets`**
**`    USING hnsw (embedding vector_cosine_ops);`**

---

## **`6. Project File Structure`**

**`text`**

**`orion/`**

**`├── docker-compose.yml`**

**`├── .env.example`**

**`├── README.md`**

**`│`**

**`├── backend/                               # FastAPI`**

**`│   ├── pyproject.toml`**

**`│   ├── alembic/`**

**`│   │   └── versions/`**

**`│   ├── app/`**

**`│   │   ├── main.py`**

**`│   │   ├── config.py                      # Settings via pydantic-settings`**

**`│   │   ├── database.py                    # SQLAlchemy async engine + session`**

**`│   │   ├── redis.py                       # Redis client (arq + cache)`**

**`│   │   ├── embeddings.py                  # Vector dim constants + dimension validator + provider clients`**

**`│   │   │`**

**`│   │   ├── models/                        # SQLAlchemy ORM models`**

**`│   │   │   ├── icp.py`**

**`│   │   │   ├── lead.py`**

**`│   │   │   ├── signal.py`**

**`│   │   │   ├── draft.py`**

**`│   │   │   ├── sequence.py`**

**`│   │   │   ├── outreach.py`**

**`│   │   │   ├── sender.py                  # NEW`**

**`│   │   │   └── inbound.py                 # NEW`**

**`│   │   │`**

**`│   │   ├── schemas/                       # Pydantic request/response schemas`**

**`│   │   │   ├── icp.py`**

**`│   │   │   ├── lead.py`**

**`│   │   │   ├── signal.py`**

**`│   │   │   ├── draft.py`**

**`│   │   │   ├── sequence.py`**

**`│   │   │   ├── analytics.py`**

**`│   │   │   ├── sender.py                  # NEW`**

**`│   │   │   ├── inbound.py                 # NEW`**

**`│   │   │   └── tam.py                     # NEW`**

**`│   │   │`**

**`│   │   ├── api/v1/`**

**`│   │   │   ├── icp.py`**

**`│   │   │   ├── leads.py`**

**`│   │   │   ├── signals.py`**

**`│   │   │   ├── personalize.py`**

**`│   │   │   ├── sequences.py`**

**`│   │   │   ├── analytics.py`**

**`│   │   │   ├── events.py                  # SSE stream endpoint`**

**`│   │   │   ├── sender.py                  # NEW`**

**`│   │   │   ├── inbound.py                 # NEW: Webhook receivers`**

**`│   │   │   └── tam.py                     # NEW: TAM heatmap aggregation`**

**`│   │   │`**

**`│   │   ├── services/`**

**`│   │   │   ├── icp_scorer.py`**

**`│   │   │   ├── enrichment.py`**

**`│   │   │   ├── analytics.py`**

**`│   │   │   ├── tam_aggregator.py          # NEW`**

**`│   │   │   └── inbound_processor.py       # NEW`**

**`│   │   │`**

**`│   │   ├── workers/`**

**`│   │   │   ├── worker.py                  # ARQ WorkerSettings + cron definitions`**

**`│   │   │   ├── enrichment_worker.py`**

**`│   │   │   ├── inbound_worker.py          # NEW`**

**`│   │   │   └── signal_workers/`**

**`│   │   │       ├── funding.py`**

**`│   │   │       ├── hiring.py`**

**`│   │   │       ├── linkedin.py`**

**`│   │   │       └── news.py`**

**`│   │   │`**

**`│   │   ├── agents/`**

**`│   │   │   └── golden_snippet/`**

**`│   │   │       ├── graph.py               # LangGraph StateGraph definition`**

**`│   │   │       ├── nodes.py               # Nodes 1, 1.5, 2, 3, 4, 5, 6`**

**`│   │   │       ├── commonalities.py       # NEW: Node 1.5 logic + prompt`**

**`│   │   │       ├── state.py               # TypedDict AgentState`**

**`│   │   │       └── prompts.py             # All prompt templates as constants`**

**`│   │   │`**

**`│   │   └── scrapers/`**

**`│   │       ├── yc_scraper.py`**

**`│   │       └── fixtures/`**

**`│   │           ├── proxycurl_sample.json`**

**`│   │           ├── crunchbase_sample.json`**

**`│   │           ├── winning_snippets.json   # Pre-seed data for RAG (loaded into winning_snippets pgvector table)`**

**`│   │           └── inbound_payloads/`**

**`│   │               ├── clerk_signup.json`**

**`│   │               ├── linkedin_ads.json`**

**`│   │               └── google_ads.json`**

**`│`**

**`└── frontend/                              # NextJS App Router`**

    **`├── package.json`**

    **`├── next.config.js`**

    **`├── tsconfig.json`**

    **`├── public/`**

    **`└── src/`**

    **`    ├── app/`**

    **`    │   ├── layout.tsx`**

    **`    │   ├── page.tsx                   # Dashboard (/)`**

    **`    │   ├── tam/page.tsx               # TAM Explorer`**

    **`    │   ├── sender/page.tsx            # Sender Profile`**

    **`    │   ├── icp/page.tsx               # ICP Builder`**

    **`    │   ├── leads/page.tsx             # Lead Board`**

    **`    │   ├── feed/page.tsx              # Signal + Inbound Feed`**

    **`    │   ├── sequences/page.tsx         # Sequence Builder`**

    **`    │   ├── compose/page.tsx           # Email Composer`**

    **`    │   └── analytics/page.tsx         # Analytics`**

    **`    ├── components/`**

    **`    │   ├── LeadCard.tsx`**

    **`    │   ├── LeadDetailDrawer.tsx`**

    **`    │   ├── SignalCard.tsx`**

    **`    │   ├── InboundEventCard.tsx`**

    **`    │   ├── CommonalityPanel.tsx`**

    **`    │   ├── TAMHeatmap.tsx`**

    **`    │   ├── DraftViewer.tsx`**

    **`    │   ├── FunnelChart.tsx`**

    **`    │   └── QualityRadar.tsx`**

    **`    ├── hooks/`**

    **`    │   ├── useLeads.ts`**

    **`    │   ├── useSignals.ts`**

    **`    │   ├── useInbound.ts`**

    **`    │   ├── useTAM.ts`**

    **`    │   └── useSSE.ts`**

    **`    ├── store/`**

    **`    │   ├── leads.store.ts`**

    **`    │   ├── signals.store.ts`**

    **`    │   ├── inbound.store.ts`**

    **`    │   └── ui.store.ts`**

    **`    └── lib/`**

    **`        ├── api-client.ts`**

    **`        └── sse-client.ts`**

---

## **`7. Docker Compose`**

**`text`**

**`services:`**

  **`postgres:`**

    **`image: pgvector/pgvector:pg16        # bundles the pgvector extension`**

    **`environment:`**

      **`POSTGRES_DB: orion`**

      **`POSTGRES_USER: orion`**

      **`POSTGRES_PASSWORD: orion_secret`**

    **`volumes:`**

      **`- postgres_data:/var/lib/postgresql/data`**

      **`- ./infra/init-scripts:/docker-entrypoint-initdb.d`**

    **`ports:`**

      **`- "5432:5432"`**

    **`healthcheck:`**

      **`test: ["CMD-SHELL", "pg_isready -U orion -d orion"]`**

      **`interval: 5s`**

      **`retries: 10`**

  **`redis:`**

    **`image: redis:7-alpine`**

    **`ports:`**

      **`- "6379:6379"`**

    **`healthcheck:`**

      **`test: ["CMD", "redis-cli", "ping"]`**

      **`interval: 5s`**

      **`retries: 10`**

  **`backend:`**

    **`build: ./backend`**

    **`command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`**

    **`ports:`**

      **`- "8000:8000"`**

    **`environment:`**

      **`DATABASE_URL: postgresql+asyncpg://orion:orion_secret@postgres/orion`**

      **`REDIS_URL: redis://redis:6379`**

      **`OPENAI_API_KEY: ${OPENAI_API_KEY}`**

      **`GEMINI_API_KEY: ${GEMINI_API_KEY}`**

      **`OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://host.docker.internal:11434}`**

      **`PROXYCURL_API_KEY: ${PROXYCURL_API_KEY:-mock}`**

      **`HUNTER_API_KEY: ${HUNTER_API_KEY:-mock}`**

      **`CLEARBIT_API_KEY: ${CLEARBIT_API_KEY:-mock}`**

      **`BUILTWITH_API_KEY: ${BUILTWITH_API_KEY:-mock}`**

      **`USE_MOCK_ENRICHMENT: ${USE_MOCK_ENRICHMENT:-true}`**

      **`USE_MOCK_SIGNALS: ${USE_MOCK_SIGNALS:-true}`**

      **`ENABLE_INBOUND_WEBHOOKS: ${ENABLE_INBOUND_WEBHOOKS:-true}`**

      **`LLM_PROVIDER: ${LLM_PROVIDER:-gemini}`**

      **`LLM_MODEL: ${LLM_MODEL:-gemini-2.5-flash}`**

      **`EMBEDDING_PROVIDER: ${EMBEDDING_PROVIDER:-gemini}`**

      **`EMBEDDING_MODEL: ${EMBEDDING_MODEL:-text-embedding-004}`**

      **`AUTO_PERSONALIZE_THRESHOLD: ${AUTO_PERSONALIZE_THRESHOLD:-0.75}`**

      **`AUTO_ENROLL_ICP_THRESHOLD: ${AUTO_ENROLL_ICP_THRESHOLD:-70.0}`**

      **`CRITIQUE_REWRITE_THRESHOLD: ${CRITIQUE_REWRITE_THRESHOLD:-7.0}`**

    **`depends_on:`**

      **`postgres:`**

        **`condition: service_healthy`**

      **`redis:`**

        **`condition: service_healthy`**

    **`volumes:`**

      **`- ./backend:/app`**

  **`worker:`**

    **`build: ./backend`**

    **`command: python -m arq app.workers.worker.WorkerSettings`**

    **`environment:`**

      **`DATABASE_URL: postgresql+asyncpg://orion:orion_secret@postgres/orion`**

      **`REDIS_URL: redis://redis:6379`**

      **`OPENAI_API_KEY: ${OPENAI_API_KEY}`**

      **`GEMINI_API_KEY: ${GEMINI_API_KEY}`**

      **`OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://host.docker.internal:11434}`**

      **`PROXYCURL_API_KEY: ${PROXYCURL_API_KEY:-mock}`**

      **`HUNTER_API_KEY: ${HUNTER_API_KEY:-mock}`**

      **`CLEARBIT_API_KEY: ${CLEARBIT_API_KEY:-mock}`**

      **`BUILTWITH_API_KEY: ${BUILTWITH_API_KEY:-mock}`**

      **`LLM_PROVIDER: ${LLM_PROVIDER:-gemini}`**

      **`LLM_MODEL: ${LLM_MODEL:-gemini-2.5-flash}`**

      **`EMBEDDING_PROVIDER: ${EMBEDDING_PROVIDER:-gemini}`**

      **`EMBEDDING_MODEL: ${EMBEDDING_MODEL:-text-embedding-004}`**

      **`USE_MOCK_ENRICHMENT: ${USE_MOCK_ENRICHMENT:-true}`**

      **`USE_MOCK_SIGNALS: ${USE_MOCK_SIGNALS:-true}`**

      **`ENABLE_INBOUND_WEBHOOKS: ${ENABLE_INBOUND_WEBHOOKS:-true}`**

      **`AUTO_PERSONALIZE_THRESHOLD: ${AUTO_PERSONALIZE_THRESHOLD:-0.75}`**

      **`AUTO_ENROLL_ICP_THRESHOLD: ${AUTO_ENROLL_ICP_THRESHOLD:-70.0}`**

      **`CRITIQUE_REWRITE_THRESHOLD: ${CRITIQUE_REWRITE_THRESHOLD:-7.0}`**

    **`depends_on:`**

      **`postgres:`**

        **`condition: service_healthy`**

      **`redis:`**

        **`condition: service_healthy`**

    **`volumes:`**

      **`- ./backend:/app`**

  **`frontend:`**

    **`build: ./frontend`**

    **`command: npm run dev`**

    **`ports:`**

      **`- "3000:3000"`**

    **`environment:`**

      **`NEXT_PUBLIC_API_URL: http://localhost:8000`**

    **`depends_on:`**

      **`- backend`**

**`volumes:`**

  **`postgres_data:`**

---

## **`8. Environment Variables`**

**`bash`**

***`# .env.example`***

***`# ── LLM ──────────────────────────────────────────────────────`***

**`OPENAI_API_KEY=sk-...`**

**`GEMINI_API_KEY=AIza...`**

**`OLLAMA_BASE_URL=http://localhost:11434`**

**`LLM_PROVIDER=gemini            # gemini | openai | ollama`**

**`LLM_MODEL=gemini-2.5-flash     # e.g. gemini-2.5-flash | gpt-4.1-mini | llama3.1:8b`**

**`EMBEDDING_PROVIDER=gemini          # gemini | openai | ollama (can differ from LLM_PROVIDER)`**

**`EMBEDDING_MODEL=text-embedding-004  # MUST match the dimension of the leads.embedding / winning_snippets.embedding pgvector columns.`**
**`                                    # Known mappings (see app/embeddings.py:EMBEDDING_DIMS):`**
**`                                    #   text-embedding-004      → 768   (gemini)   ✓ default`**
**`                                    #   nomic-embed-text        → 768   (ollama)   ✓ swap-in compatible`**
**`                                    #   text-embedding-3-small  → 1536  (openai)   ✗ requires column ALTER + reindex`**
**`                                    #   text-embedding-3-large  → 3072  (openai)   ✗ requires column ALTER + reindex`**
**`                                    # The FastAPI app and ARQ worker call validate_embedding_dimension()`**
**`                                    # at startup and refuse to boot on mismatch (no silent corruption).`**

**Embedding-dimension migration runbook:** stop API and workers; create an Alembic migration that drops dependent HNSW indexes, alters `leads.embedding` and `winning_snippets.embedding` to the new `VECTOR(N)` dimension, and recreates the indexes with the same cosine operator class; update `EMBEDDING_MODEL` and `VECTOR_DIMENSION`; re-embed existing lead profiles and winning snippets; run the startup validator and semantic-search tests; restart API and workers only after validation passes.

***`# ── Enrichment APIs (all optional — mocked if not set) ───────`***

**`PROXYCURL_API_KEY=             # LinkedIn enrichment (proxycurl.com)`**

**`HUNTER_API_KEY=                # Email finder (hunter.io)`**

**`CLEARBIT_API_KEY=              # Company data (clearbit.com)`**

**`BUILTWITH_API_KEY=             # Tech stack (builtwith.com)`**

***`# ── Feature Flags ────────────────────────────────────────────`***

**`USE_MOCK_ENRICHMENT=true       # Use fixture JSON instead of real APIs`**

**`USE_MOCK_SIGNALS=true          # Generate synthetic signals for demo`**

**`ENABLE_INBOUND_WEBHOOKS=true   # Toggle inbound capture module`**

***`# ── Mock SMTP / Demo Outcomes ───────────────────────────────`***

**`MOCK_SMTP_MODE=deterministic        # deterministic | seeded_random`**

**`MOCK_SMTP_BOUNCE_DOMAINS=bounce.test,invalid.test`**

**`MOCK_SMTP_REPLY_DOMAINS=reply.test`**

**`MOCK_SMTP_BOUNCE_RATE=0.0           # Used only in seeded_random mode`**

**`MOCK_SMTP_REPLY_RATE=0.0            # Used only in seeded_random mode`**

**`MOCK_SMTP_RANDOM_SEED=42            # Stable seed for repeatable demos/tests`**

***`# ── Thresholds ───────────────────────────────────────────────`***

**`AUTO_PERSONALIZE_THRESHOLD=0.75   # signal_strength ≥ this → auto-generate draft`**

**`AUTO_ENROLL_ICP_THRESHOLD=70.0    # Global fallback if sequence.auto_enroll_threshold is not set`**

**`CRITIQUE_REWRITE_THRESHOLD=7.0    # avg critique score < this → rewrite loop`**

---

## **`9. Implementation Phases`**

## **`Phase 1 — Core Data Layer + Sender Profile (Week 1)`**

* **`Docker Compose setup (Postgres + pgvector, Redis) + health checks`**

* **`SQLAlchemy async models for all 10 tables`**

* **`Alembic migrations with full schema`**

* **`FastAPI app scaffold with router registration and CORS`**

* **`NextJS App Router scaffold + React 18 setup with shadcn/ui and Tailwind`**

* **`ICP CRUD endpoints + ICP Builder multi-step wizard UI`**

* **`Sender Profile CRUD endpoints + Sender Profile UI page`**

## **`Phase 2 — Lead Pipeline + TAM Mapping (Week 2)`**

* **`Lead CRUD endpoints + CSV import`**

* **`YC scraper (mock fixtures mode)`**

* **`ARQ worker setup (WorkerSettings, cron definitions)`**

* **`Full enrichment pipeline worker (all 6 steps, mock mode)`**

* **`pgvector extension enabled + leads.embedding column + HNSW index; embedding upsert in Step 5; startup dimension validator wired into FastAPI lifespan and ARQ worker`**

* **`ICP scoring algorithm service`**

* **`TAM aggregation service + heatmap endpoint`**

* **`Lead Board UI with enrichment status badges`**

* **`TAM Explorer UI with Recharts Treemap + Whitespace discovery`**

## **`Phase 2.5 — Frontend + Contract Alignment (Before Phase 3)`**

* **`Install and adopt TanStack Query v5, React Hook Form, Zod, Recharts, and the typed SSE/EventSource helper before building Phase 3 UI.`**

* **`Refactor ICP Builder to PRD order: Firmographics -> Persona -> Signals -> Weighting; name/description stay as metadata, not a wizard step.`**

* **`Add ICP signal preferences to icps.config: selected_signal_types, signal_recency_days, min_signal_strength, signal_keywords.`**

* **`Add leads.last_contacted_at TIMESTAMPTZ + idx_leads_last_contacted_at via migration, ORM model, and schemas before Phase 3; default NULL means "never contacted."`**

* **`Add live matching-lead-count preview for ICP criteria and slider-based weight controls that auto-normalize to 1.0 in the UI.`**

* **`Upgrade Lead Board filters with ICP score range and signal type. Scaffold drawer sections for enriched profile, signal timeline, commonality hooks, drafts, and sequence position with empty states until later modules provide data.`**

* **`Make zero/low-coverage TAM cells clickable and open a Discover Leads action using the selected industry/company-size criteria.`**

* **`Update planning docs/checklist so Phase 3 implementation consumes the clarified contracts for signals, SSE, inbound retry, and frontend state management.`**

## **`Phase 3 — Inbound Capture + Signal Monitor (Week 3)`**

* **`Inbound webhook receiver endpoints (all source parsers)`**

* **`Inbound ARQ worker (identity extraction → idempotent lead link/create → enrichment trigger)`**

* **`Inbound retry contract: reuse created_lead_id if present, dedup by extracted identity, require source_event_id/event_fingerprint for no-email events, and resume safely after partial failure.`**

* **`Irreducible inbound event handling: if no stable source_event_id or event_fingerprint can be produced, store the audit row with event_fingerprint=NULL, mark processed=true with processing_error='no_stable_identity', and do not create a lead.`**

* **`Inbound-to-signal bridge mappings (PRODUCT_SIGNUP -> PRODUCT_SIGNUP, AD_CLICK/OPT_IN -> WEBSITE_VISIT, CONFERENCE_REGISTRATION -> CONFERENCE_ATTENDANCE)`**

* **`4 Signal ARQ workers (Funding, Hiring, LinkedIn, News) in mock mode`**

* **`Redis signal deduplication (SHA256 hash + TTL)`**

* **`Signal scoring reads leads.last_contacted_at for the cool-off modifier instead of doing per-signal outreach_logs lookups.`**

* **`Signal scoring applies the icp.signal_keywords relevance modifier and filters out expired/read signals from the default feed.`**

* **`SSE event stream endpoint (/api/v1/events/stream) with Redis Pub/Sub bridge for worker → browser streaming`**

* **`Unified Signal + Inbound Feed UI with real-time SSE updates`**

* **`NOTE: Inbound auto-routing to sequences (Step 6 of inbound pipeline) is implemented as a no-op`**
  **`when no matching sequences exist. Full auto-routing tested in Phase 5 when Sequence CRUD is built.`**
  **`All sequence/enrollment tables already exist from Phase 1 migrations.`**

## **`Phase 4 — Commonalities Engine + LangGraph Agent (Week 4)`**

* **`LangGraph StateGraph definition with AgentState TypedDict`**

* **`Node 1: Context Retrieval`**

* **`Node 1.5: Commonality Matcher (cross-reference prompt + output parser)`**

* **`Node 2: Signal Selector`**

* **`Node 3: RAG Fetch (pgvector cosine-distance query on winning_snippets table)`**

* **`Seed winning_snippets pgvector table from fixtures JSON (embeddings generated with the same EMBEDDING_MODEL the agent will query with — same dimension as leads.embedding)`**

* **`Node 4: Draft Writer (full prompt with negative keywords list)`**

* **`Node 5: Critique & Score with conditional rewrite edge (max 3 loops)`**

* **`Node 6: Tone Adapter`**

* **`Personalization endpoints (single + batch)`**

* **`Email Composer UI: streaming draft via SSE + commonality panel + quality radar chart`**

## **`Phase 5 — Sequences + Engagement Steps (Week 5)`**

* **`Sequence, SequenceStep, LeadSequenceEnrollment CRUD endpoints`**

* **`Channel/StepType validation (ENGAGEMENT → LINKEDIN_ENGAGE only; OUTREACH → EMAIL/LINKEDIN_MESSAGE/LINKEDIN_CONNECTION)`**

* **`LINKEDIN_ENGAGE step type support in execution worker`**

* **`LINKEDIN_ENGAGE writes outreach_logs with delivery_status='ENGAGED', engagement_action populated, no message body, and updates lead.last_contacted_at.`**

* **`Sequence execution ARQ cron (every 15 min)`**

* **`Mock SMTP + LinkedIn mock logging`**

* **`Deterministic mock outcomes: EMAIL bounce domains -> BOUNCED, EMAIL reply domains -> REPLIED, other EMAIL recipients -> SENT; LINKEDIN_MESSAGE/LINKEDIN_CONNECTION -> SENT; LINKEDIN_ENGAGE -> ENGAGED.`**

* **`Bounced sends set enrollment.status='BOUNCED' as a terminal state; sequence reactivation never resumes bounced enrollments.`**

* **`Auto-enrollment logic (sequence threshold with global fallback)`**

* **`Activate and test inbound auto-routing (Phase 3 Step 6) end-to-end with real sequences`**

* **`Outreach status transition logic (UNTOUCHED → IN_SEQUENCE on enrollment, → REPLIED on reply, → BOUNCED on deterministic/mock bounce)`**

* **`Draft SENT transition after successful outreach log write; failed/bounced/skipped sends do not mark drafts SENT.`**

* **`Sequence is_active=false pauses active enrollments with paused_reason='SEQUENCE_DEACTIVATED'; reactivation resumes only those rows and never user-paused or terminal rows.`**

* **`Sequence Builder UI with drag-and-drop step ordering + engagement step config`**

## **`Phase 6 — Analytics + Polish (Week 6)`**

* **`Full AnalyticsMetrics aggregation service`**

* **`All analytics endpoints including TAM and Inbound splits`**

* **`Analytics dashboard: funnel waterfall, signal trends, Inbound vs Outbound, quality over time, token cost tracker`**

* **`Seed script: 50 mock leads + signals + inbound events + sender profile for instant demo`**

* **`End-to-end demo flow: YC Import → Enrich → Signal → Commonality → Generate → Sequence`**

* **`README with architecture diagram (Mermaid)`**

* **`pytest: services + workers coverage`**

* **`Playwright: smoke tests for all 9 UI pages`**

---

## **`10. Technical Depth Highlights`**

| `Component` | `Why It's Impressive` |
| ----- | ----- |
| **`LangGraph agent with Node 1.5 Commonality Matcher`** | **`Cross-profile semantic reasoning before drafting; structured JSON output with strength scoring`** |
| **`Commonalities cross-reference algorithm`** | **`Sender ↔ Prospect overlap detection; non-trivial match filtering via LLM; direct analog to Cardinal's core moat`** |
| **`Inbound Capture webhook pipeline`** | **`Generic receiver + source-specific payload parsers + async ARQ processing + dedup + auto-routing`** |
| **`TAM Heatmap aggregation`** | **`Multi-dimensional GROUP BY analytics over lead data; whitespace discovery algorithm`** |
| **`ARQ async workers with Redis dedup`** | **`Production-grade job queue patterns; idempotent signal processing with SHA256 + TTL`** |
| **`pgvector dual-purpose usage`** | **`leads.embedding for semantic search; winning_snippets.embedding for RAG in agent Node 3 — both indexed with HNSW (cosine), dimension enforced at startup`** |
| **`SSE real-time event bus (unified feed)`** | **`Low-latency push architecture merging outbound signals + inbound webhook events without WebSocket overhead`** |
| **`LangGraph self-critique loop`** | **`Conditional graph edges; multi-dimensional scoring rubric; bounded rewrite iterations`** |
| **`Full async FastAPI + SQLAlchemy 2.0`** | **`Modern Python async patterns throughout; no sync bottlenecks`** |
| **`Streaming LLM tokens to UI`** | **`Token-by-token SSE from agent to browser via draft.token events`** |
| **`Ollama fallback (local mode)`** | **`Allows fully local demos when cloud keys are unavailable`** |
