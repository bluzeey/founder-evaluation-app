# HANDOFF.md — FounderOS Complete Handoff Document

> **Audience:** Another AI agent that needs to understand the entire FounderOS codebase.
> **Orientation:** Read-only. This document explains *what exists and how it fits together*.
> **Supplements:** `README.md` (product philosophy + setup) and `architecture.md` (diagram-oriented) can be read alongside this file, but everything needed to understand the system is here.

---

## 1. What FounderOS is

FounderOS is an **evidence-first founder intelligence platform for early-stage investors**. It converts raw signals — pitch decks, LinkedIn/GitHub footprints, web search, structured simulations — into a versioned, explainable **Founder Score (0–100)** and an opportunity screen across **three independent axes** (Founder, Market, Idea-vs-Market).

It is **not** a black-box success predictor, a personality test, or a single opaque number. It separates confidence, coverage, contradictions, and unknowns so an investor can answer:

- What has this founder demonstrated?
- What evidence supports each conclusion?
- How confident are we?
- What remains unknown?
- What could change the conclusion?
- What is the next best diligence action?
- Should we advance, investigate, hold, or decline?

### What it is / is not

| It is | It is not |
|---|---|
| An evidence-weighted estimate of persistent founder capability | A prediction of startup success with certainty |
| A structured way to generate evidence for low-data founders | A personality or charisma test |
| Three independent opportunity axes | A single opaque number |
| A deterministic score engine fed by graded evidence | An LLM writing the final numeric score |
| Transparent about confidence, coverage, contradictions | A system that treats missing data as negative evidence |
| Blind to pedigree proxies | A score that rewards university, employer, or network prestige |

### Sample Founder Score output

```
Founder Score: 68
Evidence band: 56–77
Confidence: 52%
Evidence coverage: 44%
Trend: +6 since previous assessment
```

Correct interpretation: "promising signals, but more evidence required." **Not** "68% chance of succeeding."

### Three independent opportunity axes

1. **Founder axis** — persistent Founder Score, Founder-Market Fit, Team Completeness.
2. **Market axis** — bullish/neutral/bear posture, timing, buyer urgency, competition.
3. **Idea-vs-Market axis** — problem-solution coherence, distribution feasibility, defensibility, pivot potential.

No overall average is computed across axes — disagreement stays visible.

---

## 2. Repository layout

```
founder-evaluation-app/
├── README.md              # Product philosophy, setup, demo flow, evaluation posture
├── architecture.md        # Diagram-oriented system guide (Mermaid starter included)
├── HANDOFF.md              # THIS FILE
├── .gitignore
├── frontend/              # React + Vite + TypeScript + Tailwind SPA → Vercel
│   ├── src/
│   │   ├── App.tsx        # App shell, router, left nav
│   │   ├── main.tsx       # React entry (BrowserRouter + StrictMode)
│   │   ├── pages/         # 8 page components (Discovery, Cases, DealRoom, …)
│   │   ├── api/           # client.ts (fetch wrapper), cache.ts (SWR cache)
│   │   ├── store/         # appContext.tsx (React Context + localStorage)
│   │   ├── engine/        # routing.ts, trust.ts, scoring.ts, stateMachine.ts, validationSummary.ts
│   │   ├── agents/        # Deterministic specialist agent stubs
│   │   ├── domain/        # types.ts (InvestmentCase, Claim, DriverAssessment, …)
│   │   ├── types/         # backend.ts (snake_case DTOs mirroring FastAPI)
│   │   ├── components/    # Reusable UI (StatusBadge, DriverCard, MemoView, …)
│   │   ├── config/        # thesis.ts, weights.ts
│   │   ├── hooks/         # useAdaptivePolling.ts
│   │   ├── data/          # demoCases.ts, validationSet.ts
│   │   ├── tests/         # Vitest suite
│   │   └── index.css      # Tailwind + paper-folder component classes
│   ├── public/            # favicon.svg
│   ├── vercel.json        # SPA rewrites
│   ├── vite.config.ts     # Dev proxy /api → :8000
│   ├── tailwind.config.js # Manila/canvas/ink palette
│   └── package.json       # pnpm, React 18, Vite 5, lucide-react
└── backend/               # FastAPI + Pydantic + SQLAlchemy 2 + Celery → Railway
    ├── main.py            # All REST endpoints + inline request models
    ├── models.py           # Pydantic schemas + enums + weight constants
    ├── db_models.py        # SQLAlchemy ORM (11 tables)
    ├── database.py         # Engine, Base, session factory
    ├── crud.py             # All DB read/write functions
    ├── scoring.py          # Deterministic founder score engine (no LLM)
    ├── estimation.py       # Bridges LLM output → evidence items → score
    ├── document_extractor.py # Pure text extraction (PDF/DOCX/TXT/MD)
    ├── seed_data.py        # Demo theses + founders + opportunities + pool items
    ├── celery_app.py       # Celery app + beat schedule (2 periodic tasks)
    ├── logger_config.py    # LOG_LEVEL stdout handler
    ├── alembic/            # 10 migrations
    ├── alembic.ini
    ├── research/           # AI agents (OpenAIClient, SourcingAgent, SocialAgent, DocumentAgent, TavilyClient, AIFounderEstimator, extractor, prompts, api_lock, http_utils, web_search)
    ├── tasks/              # Celery tasks (social_research, founder_pool, document_extraction, estimation_task, enrichment_task, retry_utils)
    ├── tests/              # Pytest suite (13 test files)
    ├── railway.toml        # web service
    ├── railway.worker.toml # celery worker
    ├── railway.beat.toml   # celery beat
    ├── Procfile
    ├── .env.example        # Canonical env var reference (91 lines)
    └── requirements.txt
```

---

## 3. Tech stack

| Layer | Stack | Deploy target |
|-------|-------|---------------|
| Frontend | React 18.3, Vite 5.3, TypeScript 5.2, Tailwind 3.4, React Router 6.24, lucide-react 0.400, Vitest 1.6 | Vercel |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Uvicorn | Railway (web service) |
| Async jobs | Celery + Redis 7+ broker/result backend, custom retry + circuit breaker | Railway (worker + beat services) |
| AI models | OpenAI `gpt-5` (per-agent `OPENAI_*_MODEL` env vars) | External API |
| Web search | Tavily API | External API |
| Database | PostgreSQL 15+ with JSONB columns | Railway PostgreSQL |
| Cache/broker/locks | Redis 7+ | Railway Redis |

Frontend has **no** HTTP client library (raw `fetch`), **no** state library (React Context), **no** UI component library (hand-rolled Tailwind), **no** form/charting library. Very minimal dependency footprint.

---

## 4. Backend deep-dive

Stack: FastAPI + SQLAlchemy 2.0 (PostgreSQL) + Celery (Redis broker) + OpenAI + Tavily.
Entry points: `main.py` (uvicorn), `celery_app.py` (workers/beat).
Deployment: Railway (3 services: web, worker, beat) — see `railway.toml`, `railway.worker.toml`, `railway.beat.toml`, `Procfile`.

### 4.1 API surface (`main.py`, 1511 lines)

`app = FastAPI(title="FounderOS API", version="0.1.0")` at `main.py:68`. CORS allows all origins (`main.py:70`). A custom `CacheHeadersMiddleware` (`main.py:99`) adds `Cache-Control: private, max-age=N` headers to GET responses based on regex rules in `CACHE_TTL_RULES` (`main.py:83-96`).

Inline request models defined in `main.py`: `CreateFounderRequest` (116), `CreateThesisRequest` (127), `UpdateThesisRequest` (138), `UpdateOpportunityStatusRequest` (164), `AddEvidenceRequest` (168), `SimulateAssessmentRequest` (172), `ResearchFounderRequest` (178), `CreateSourcingScheduleRequest` (184), `UpdateSourcingScheduleRequest` (192). Valid case statuses enumerated in `VALID_CASE_STATUSES` (`main.py:149`).

#### Health
| Method | Path | File:line | Description | Req → Resp |
|---|---|---|---|---|
| GET | `/health` | 199 | Liveness probe | → `{status: ok}` |

#### Founders
| Method | Path | File:line | Description | Req → Resp |
|---|---|---|---|---|
| POST | `/v1/founders` | 205 | Create founder; auto-queues social background research via Celery | `CreateFounderRequest` → `Founder` |
| GET | `/v1/founders` | 755 | List all founders | → `List[Founder]` |
| GET | `/v1/founders/{founder_id}` | 449 | Get founder; reconciles completed social background into evidence + re-scores | → `Founder` |
| POST | `/v1/founders/{founder_id}/evidence` | 522 | Add evidence items and recompute score | `AddEvidenceRequest` → `ScoreSnapshot` |
| GET | `/v1/founders/{founder_id}/score` | 555 | Get latest score snapshot (creates one if missing) | → `ScoreSnapshot` |
| GET | `/v1/founders/{founder_id}/history` | 678 | List all score snapshots for a founder | → `List[ScoreSnapshot]` |
| POST | `/v1/founders/{founder_id}/research-social` | 460 | Manually re-run social background research | → `{founder_id, background_id, task_id, status}` |
| GET | `/v1/founders/{founder_id}/social-background` | 502 | Get latest social background result | → `SocialMediaBackground` |
| POST | `/v1/founders/{founder_id}/estimate` | 578 | Queue AI estimation pass (Celery) to recover cold-start founders | → `{task_id, status}` |
| POST | `/v1/founders/{founder_id}/enrich` | 601 | Queue full 3-stage enrichment pipeline (social → deep web → estimate) | → `{task_id, status}` |
| POST | `/v1/founders/research` | 408 | Synchronous Tavily + OpenAI research to create a scored founder profile | `ResearchFounderRequest` → `Founder` |

#### Founder pool / sourcing
| Method | Path | File:line | Description | Req → Resp |
|---|---|---|---|---|
| GET | `/v1/founders/pool` | 292 | List AI-sourced pool recommendations (filter by status/job_id) | → `List[FounderPoolItem]` |
| POST | `/v1/founders/pool/refresh` | 310 | Manually trigger AI sourcing agent (Celery) | → `{task_id, status}` |
| POST | `/v1/founders/pool/{item_id}/approve` | 345 | Approve a pool item → creates Founder + Opportunity | → `ApprovedPoolItemResponse` |
| POST | `/v1/founders/pool/{item_id}/dismiss` | 395 | Dismiss a pool item | → `{id, status}` |

#### Theses
| Method | Path | File:line | Description | Req → Resp |
|---|---|---|---|---|
| POST | `/v1/theses` | 693 | Create investment thesis | `CreateThesisRequest` → `Thesis` |
| GET | `/v1/theses` | 720 | List theses | → `List[Thesis]` |
| GET | `/v1/theses/{thesis_id}` | 727 | Get thesis | → `Thesis` |
| PUT | `/v1/theses/{thesis_id}` | 737 | Update thesis (partial) | `UpdateThesisRequest` → `Thesis` |

#### Opportunities
| Method | Path | File:line | Description | Req → Resp |
|---|---|---|---|---|
| POST | `/v1/opportunities/{opportunity_id}/screen` | 894 | Screen/create an opportunity; syncs founder score | → `OpportunityScreen` |
| GET | `/v1/opportunities` | 969 | List opportunities (filter by founder_id/status) | → `List[OpportunityScreen]` |
| GET | `/v1/opportunities/{opportunity_id}` | 985 | Get opportunity | → `OpportunityScreen` |
| PATCH | `/v1/opportunities/{opportunity_id}/status` | 996 | Update pipeline status (validated against `VALID_CASE_STATUSES`) | `UpdateOpportunityStatusRequest` → `OpportunityScreen` |
| GET | `/v1/opportunities/{opportunity_id}/diligence` | 1026 | Get claims; seeds demo claims if none; auto-queues estimate if cold-start | → `List[Claim]` |

#### Deck / document upload
| Method | Path | File:line | Description | Req → Resp |
|---|---|---|---|---|
| POST | `/v1/opportunities/{opportunity_id}/deck` | 1311 | Upload PDF/DOCX/TXT/MD; base64-encodes and queues extraction (Celery). **File is NOT persisted.** | multipart file → `{opportunity_id, founder_id, task_id, status}` |

#### Assessments
| Method | Path | File:line | Description | Req → Resp |
|---|---|---|---|---|
| POST | `/v1/assessments/plan` | 762 | Recommend assessment modules for low-confidence dimensions | query `founder_id` → `{founder_id, recommended_modules, reason}` |
| POST | `/v1/assessments/simulate` | 827 | Deterministic demo grader; creates `STRUCTURED_SIMULATION` evidence at rubric_level 3 | `SimulateAssessmentRequest` → `ScoreSnapshot` |

#### Enrichment
| Method | Path | File:line | Description | Req → Resp |
|---|---|---|---|---|
| GET | `/v1/enrichment/runs` | 624 | List recent enrichment runs with per-stage confidence deltas | → `List[EnrichmentRun]` |
| GET | `/v1/enrichment/status` | 640 | Queue health: count of founders below confidence threshold + last dispatch time (reads Redis) | → `{below_threshold_count, confidence_threshold, last_dispatch_at, recent_runs}` |

#### Sourcing schedules & jobs
| Method | Path | File:line | Description | Req → Resp |
|---|---|---|---|---|
| GET | `/v1/sourcing/schedules` | 1366 | List all schedules | → `List[SourcingSchedule]` |
| POST | `/v1/sourcing/schedules` | 1373 | Create schedule (one per thesis) | `CreateSourcingScheduleRequest` → `SourcingSchedule` |
| GET | `/v1/sourcing/schedules/{schedule_id}` | 1408 | Get schedule | → `SourcingSchedule` |
| PUT | `/v1/sourcing/schedules/{schedule_id}` | 1416 | Update schedule | `UpdateSourcingScheduleRequest` → `SourcingSchedule` |
| DELETE | `/v1/sourcing/schedules/{schedule_id}` | 1433 | Delete schedule | → `{id, deleted}` |
| POST | `/v1/theses/{thesis_id}/source-now` | 1442 | Manually trigger a sourcing job for a thesis | → `{thesis_id, job_id, status}` |
| GET | `/v1/sourcing/jobs` | 1454 | List sourcing jobs (filter by thesis_id/status) | → `List[SourcingJob]` |
| GET | `/v1/sourcing/status` | 1476 | Aggregate sourcing state: schedules, active jobs, recent jobs, beat health (Redis) | → `{schedules, active_jobs, recent_jobs, last_dispatch_at}` |

#### Seed
| Method | Path | File:line | Description | Req → Resp |
|---|---|---|---|---|
| POST | `/v1/seed` | 1091 | Truncate all tables; create one demo thesis + hourly sourcing schedule | → `{thesis_id, message}` |
| POST | `/v1/seed/all` | 1146 | Idempotent seed: 5 AI theses + schedules + 3 sample founders + 3 opportunities + 3 pool items | → `{theses_created, schedules_created, founders_created, opportunities_created, pool_items_created, message}` |

### 4.2 Pydantic models (`models.py`, 352 lines)

#### Enums
- **`EvidenceType`** (`models.py:7`): `VERIFIED_OUTCOME`, `WORK_SAMPLE`, `REPEATED_BEHAVIOR`, `INSPECTED_ARTIFACT`, `STRUCTURED_SIMULATION`, `STRUCTURED_INTERVIEW`, `SELF_REPORTED`, `UNVERIFIED_PROXY`, `PRESTIGE_PROXY`, `INFERRED_ESTIMATE`.
- **`EvidenceStatus`** (`models.py:20`): `POSITIVE`, `NEGATIVE`, `MIXED`, `CONTRADICTORY`, `UNKNOWN`.
- **`Dimension`** (`models.py:28`): 8 scoring dimensions — `EXECUTION_AND_SHIPPING`, `TECHNICAL_OR_DOMAIN_ABILITY`, `AGENCY_AND_INITIATIVE`, `LEARNING_VELOCITY`, `RESILIENCE_AND_PERSISTENCE`, `COMMERCIAL_RECRUITING_DISTRIBUTION_ABILITY`, `COLLABORATION_AND_INTEGRITY`, `PRIOR_VENTURE_OUTCOMES`.
- **`TrustStatus`** (`models.py:161`): `VERIFIED`, `SUPPORTED`, `FOUNDER_REPORTED`, `INFERRED`, `CONTRADICTED`, `MISSING`, `STALE`.
- **`PoolItemStatus`** (`models.py:240`): `RECOMMENDED`, `APPROVED`, `DISMISSED`.
- **`AssessmentModule`** (`models.py:264`): `PROBLEM_FRAMING`, `SALES_OBJECTION`, `PRIORITIZATION`, `BELIEF_UPDATING`, `SCALING_LEADERSHIP`, `SETBACK_OWNERSHIP`, `CLAIM_CALIBRATION`, `ROLE_WORK_SAMPLE`.
- **`Decision`** (`models.py:334`): `ADVANCE`, `DILIGENCE`, `HOLD`, `DECLINE`.

#### Constants (`models.py:39-63`)
- **`DIMENSION_WEIGHTS`** (`models.py:39`) — sum to 1.0:

  | Dimension | Weight |
  |---|---|
  | EXECUTION_AND_SHIPPING | 0.20 |
  | TECHNICAL_OR_DOMAIN_ABILITY | 0.18 |
  | AGENCY_AND_INITIATIVE | 0.15 |
  | LEARNING_VELOCITY | 0.12 |
  | RESILIENCE_AND_PERSISTENCE | 0.10 |
  | COMMERCIAL_RECRUITING_DISTRIBUTION_ABILITY | 0.10 |
  | COLLABORATION_AND_INTEGRITY | 0.10 |
  | PRIOR_VENTURE_OUTCOMES | 0.05 |

- **`EVIDENCE_TYPE_STRENGTH`** (`models.py:50`):

  | EvidenceType | Strength |
  |---|---|
  | VERIFIED_OUTCOME | 1.0 |
  | WORK_SAMPLE | 0.85 |
  | REPEATED_BEHAVIOR | 0.80 |
  | INSPECTED_ARTIFACT | 0.75 |
  | STRUCTURED_SIMULATION | 0.60 |
  | STRUCTURED_INTERVIEW | 0.45 |
  | SELF_REPORTED | 0.25 |
  | INFERRED_ESTIMATE | 0.25 |
  | UNVERIFIED_PROXY | 0.0 |
  | PRESTIGE_PROXY | 0.0 |

- **`REQUIRED_EFFECTIVE_WEIGHT`** (`models.py:63`) = `1.5` — total effective weight needed for full coverage.

#### Core models
- **`EvidenceItem`** (`models.py:66`) — atomic unit of founder evaluation. Fields: `id`, `founder_id`, `dimension`, `observation`, `source_type`, `source_id`, `source_locator`, `evidence_type`, `rubric_level` (0-4), `source_trust` (0-1), `task_relevance` (0-1), `recency_factor` (0-1), `independence_group`, `polarity`, `status`, `counter_evidence`, `unknowns`, `created_at`.
- **`DimensionBreakdown`** (`models.py:87`) — per-dimension scoring result. Fields: `dimension`, `weight`, `raw_score`, `adjusted_score`, `confidence`, `evidence_band_low/high`, `coverage`, `evidence_count`, `contradiction_count`, `unknown`, `positive_evidence`, `counter_evidence`, `unknowns`, `next_test`.
- **`ScoreSnapshot`** (`models.py:105`) — immutable score record. Fields: `id`, `founder_id`, `rubric_version`, `prompt_version`, `model_version`, `created_at`, `founder_score`, `evidence_band_low/high`, `overall_confidence`, `evidence_coverage`, `trend`, `dimension_breakdowns`, `evidence_items`, `change_explanation`.
- **`FounderMarketFit`** (`models.py:123`) — sub-scores: `domain_knowledge`, `customer_access`, `unique_insight`, `personal_motivation`, `problem_proximity`, `technical_operational_advantage`, plus aggregate `score`, `confidence`, `coverage`.
- **`TeamCompleteness`** (`models.py:135`) — `complementary_skills`, `missing_critical_roles`, `co_founder_alignment`, `decision_rights`, `commitment_availability`, plus aggregate.
- **`OpportunityScreen`** (`models.py:146`) — `opportunity_id`, `founder_id`, `founder_score`, `founder_confidence`, `founder_market_fit`, `team_completeness`, `market_posture`, `market_confidence`, `idea_vs_market_posture`, `idea_vs_market_confidence`, `next_founder_action`, `status` (default `"SCREENING"`).
- **`Claim`** (`models.py:171`) — `id`, `opportunity_id`, `founder_id`, `claim`, `source`, `trust_status`, `confidence`, `contradiction`, `owner`, `next_action`.
- **`Founder`** (`models.py:311`) — `id`, `name`, `email`, `current_company`, `role`, `location`, `location_city`, `linkedin_url`, `github_url`, `source_reason`, `source_url`, `ai_research_summary`, `ai_research_sources`, `social_background_id`, `latest_score_snapshot`.
- **`Thesis`** (`models.py:298`) — `id`, `name`, `sectors`, `stages`, `geographies`, `check_size_min/max`, `risk_appetite`, `min_evidence_requirements`, `created_at`.
- **`SourceConfig`** (`models.py:184`) — `platform` (default `"linkedin"`), `keywords`.
- **`SourcingSchedule`** (`models.py:189`) — `id`, `thesis_id`, `enabled`, `interval_seconds` (default 3600), `max_leads_per_run` (default 10), `sources: List[SourceConfig]`, `last_run_at`, `next_run_at`, timestamps.
- **`SourcingJob`** (`models.py:202`) — `id`, `thesis_id`, `schedule_id`, `status`, `progress`, `started_at`, `ended_at`, `leads_found`, `leads_added`, `leads_skipped`, `result`, `error_message`, `created_at`.
- **`SocialFootprint`** (`models.py:218`) — `platform`, `url`, `snippet`, `source_trust`.
- **`SocialMediaBackground`** (`models.py:225`) — `id`, `founder_id`, `status` (`pending|running|completed|failed`), `linkedin_url`, `github_url`, `summary`, `footprints`, `evidence_items`, `score_snapshot`, `error_message`, timestamps.
- **`FounderPoolItem`** (`models.py:246`) — `id`, `name`, `email`, `current_company`, `role`, `location`, `linkedin_url`, `github_url`, `source_url`, `source`, `reason`, `thesis_id`, `job_id`, `status`, `created_at`.
- **`GraderOutput`** (`models.py:275`) — `dimension`, `rubric_version`, `rubric_level`, `score`, `confidence`, `evidence`, `counter_evidence`, `unknowns`, `next_test`.
- **`AssessmentSession`** (`models.py:287`) — `id`, `founder_id`, `modules`, `status`, `transcript`, `grader_a_outputs`, `grader_b_outputs`, `created_at`.
- **`ApprovedPoolItemResponse`** (`models.py:329`) — `founder`, `opportunity_id`.
- **`EnrichmentRun`** (`models.py:341`) — `id`, `founder_id`, `stage`, `status`, `evidence_added`, `confidence_before`, `confidence_after`, `started_at`, `ended_at`, `error_message`, `created_at`.

### 4.3 SQLAlchemy tables (`db_models.py`, 230 lines)

SQLAlchemy 2.0 `Mapped`/`mapped_column` style. PostgreSQL with `JSONB` for list/dict columns. All inherit from `database.Base`.

| Table | Model (file:line) | Key columns | Notes |
|---|---|---|---|
| `founders` | `Founder` (15) | id, name, email (indexed), current_company, role, location, location_city, linkedin_url, github_url, source_reason (Text), source_url, ai_research_summary (Text), ai_research_sources (JSONB), social_background_id, latest_score_snapshot_id, last_enriched_at, enrichment_attempts (int default 0), created_at, updated_at | Relationships to evidence_items, score_snapshots, social_backgrounds |
| `theses` | `Thesis` (45) | id, name, sectors (JSONB), stages (JSONB), geographies (JSONB), check_size_min/max (Float), risk_appetite, min_evidence_requirements (JSONB), created_at | |
| `evidence_items` | `EvidenceItem` (60) | id, founder_id (FK→founders CASCADE, indexed), dimension (indexed), observation (Text), source_type, source_id, source_locator, evidence_type, rubric_level (Int), source_trust/task_relevance/recency_factor (Float), independence_group, polarity, status, counter_evidence (Text), unknowns (Text), created_at | |
| `score_snapshots` | `ScoreSnapshot` (85) | id, founder_id (FK indexed), rubric_version, prompt_version, model_version, created_at, founder_score, evidence_band_low/high, overall_confidence, evidence_coverage, trend (Int), dimension_breakdowns (JSONB), evidence_items (JSONB), change_explanation (Text) | Stores full snapshot as JSONB |
| `social_media_backgrounds` | `SocialMediaBackground` (107) | id, founder_id (FK indexed), status, linkedin_url, github_url, summary (Text), footprints (JSONB), evidence_items (JSONB), score_snapshot (JSONB), error_message (Text), created_at, updated_at | |
| `founder_pool_items` | `FounderPoolItem` (128) | id, name, email, current_company, role, location, linkedin_url, github_url, source_url, source (indexed), reason (Text), thesis_id (indexed), job_id (indexed), status (indexed default `"recommended"`), created_at | |
| `opportunities` | `Opportunity` (148) | id, founder_id (FK indexed), founder_score, founder_confidence, founder_market_fit (JSONB), team_completeness (JSONB), market_posture, market_confidence, idea_vs_market_posture, idea_vs_market_confidence, next_founder_action (Text), status (indexed default `"SCREENING"`) | |
| `claims` | `Claim` (167) | id, opportunity_id (FK→opportunities CASCADE indexed), founder_id (FK→founders CASCADE indexed nullable), claim (Text), source, trust_status, confidence (Float), contradiction (Text), owner, next_action (Text) | |
| `sourcing_schedules` | `SourcingSchedule` (182) | id, thesis_id (FK CASCADE indexed), enabled (Bool), interval_seconds (Int default 3600), max_leads_per_run (Int default 10), sources (JSONB), last_run_at, next_run_at, created_at, updated_at | |
| `sourcing_jobs` | `SourcingJob` (199) | id, thesis_id (FK CASCADE indexed), schedule_id (FK→sourcing_schedules SET NULL indexed), status, progress (Int), started_at, ended_at, leads_found/added/skipped (Int), result (JSONB), error_message (Text), created_at | |
| `enrichment_runs` | `EnrichmentRun` (217) | id, founder_id (FK CASCADE indexed), stage, status, evidence_added (Int), confidence_before/after (Float nullable), started_at, ended_at, error_message (Text), created_at (indexed) | |

### 4.4 Deterministic scoring engine (`scoring.py`, 226 lines)

**Fully deterministic — no LLM calls.** LLMs only produce `EvidenceItem` records; the engine computes scores from those items with fixed weights and caps.

Versions stamped on every snapshot (`scoring.py:213-215`):
- `rubric_version = "founder_score_v1"`
- `prompt_version = "gap_planner_v1"`
- `model_version = "deterministic_engine_v1"`

#### Step-by-step algorithm

**`_effective_weight(item)`** (`scoring.py:19`): `EVIDENCE_TYPE_STRENGTH[type] × source_trust × task_relevance × recency_factor`.

**`_independence_factor(items)`** (`scoring.py:28`): based on count of distinct `independence_group`s — 3+ groups → 1.0, 2 → 0.85, 1 → 0.65. *(Note: the actual confidence calc in `calculate_dimension` uses `source_diversity = min(1.0, len(groups)/3.0)` instead.)*

**`calculate_dimension(dimension, items)`** (`scoring.py:40`):

1. **Empty dimension** (`scoring.py:41`): returns `raw_score=50.0`, `adjusted_score=50.0`, `confidence=0.0`, `unknown=True`, band `[40, 60]`.
2. **Single-item cap** (`scoring.py:60-67`): if any single item's effective weight exceeds 30% of the dimension's total effective weight, it is capped down to `0.30 × total_others / 0.70`.
3. **Raw score** (`scoring.py:69-73`): `weighted_sum / total_weight` where each item contributes `(rubric_level/4.0 × 100) × effective_weight`.
4. **Coverage** (`scoring.py:76`): `min(1.0, total_weight / REQUIRED_EFFECTIVE_WEIGHT)` where `REQUIRED_EFFECTIVE_WEIGHT = 1.5`.
5. **Source diversity** (`scoring.py:79`): `min(1.0, len(distinct_groups) / 3.0)`.
6. **Contradiction factor** (`scoring.py:81-85`): `1.0 - min(0.5, contradiction_rate)` where contradiction_rate is the share of effective weight from `CONTRADICTORY` items.
7. **Confidence** (`scoring.py:87`): `coverage × (0.70 + 0.30 × source_diversity) × contradiction_factor`.
8. **Confidence caps / hard rules** (`scoring.py:89-110`):
   - **Chat-only cap** (`scoring.py:91-97`): if ALL items are `structured_simulation`/`structured_interview`/`self_reported`/`inferred_estimate`, confidence is capped at **0.60**.
   - **Non-chat artifact requirement** (`scoring.py:100-106`): confidence above **0.65** requires at least one `verified_outcome`/`work_sample`/`repeated_behavior`/`inspected_artifact`; otherwise capped at 0.65.
   - **Three-source requirement** (`scoring.py:108-110`): confidence above **0.80** requires evidence from at least 3 distinct independence groups; otherwise capped at 0.80.
9. **Shrinkage** (`scoring.py:113`): `adjusted_score = 50.0 + confidence × (raw_score - 50.0)` — shrinks toward neutral 50 when confidence is low.
10. **Evidence band** (`scoring.py:115-117`): `band_width = 20.0 × (1.0 - confidence)`; low/high = adjusted_score ∓ band_width, clamped to `[0, 100]`.

**`calculate_founder_score(founder_id, evidence_items, previous_snapshot)`** (`scoring.py:152`):

1. Groups evidence by dimension.
2. Computes `DimensionBreakdown` for each of the 8 dimensions.
3. `founder_score = Σ(adjusted_score × weight) / Σ(weight)` over non-unknown dimensions (defaults to 50.0 if all unknown).
4. `overall_confidence = mean(confidences)`, `evidence_coverage = mean(coverages)`.
5. `trend = round(founder_score - previous.founder_score)` if previous snapshot exists.
6. `change_explanation` string generated when previous snapshot exists.

### 4.5 CRUD (`crud.py`, 952 lines)

All functions take a SQLAlchemy `Session`. Organized into sections:

- **Founders** (31-95): `create_founder`, `get_founder`, `list_founders`, `update_founder`, `founder_to_pydantic` (hydrates `latest_score_snapshot`).
- **Theses** (102-152): `create_thesis`, `get_thesis`, `list_theses`, `update_thesis`, `thesis_to_pydantic`.
- **Evidence** (159-223): `evidence_to_db`, `evidence_to_pydantic`, `add_evidence_items`, `list_evidence_for_founder`.
- **Score snapshots** (230-289): `score_snapshot_to_db`, `score_snapshot_to_pydantic`, `create_score_snapshot`, `get_score_snapshot`, `list_score_snapshots_for_founder`.
- **Social media backgrounds** (296-366): `social_background_to_db/pydantic`, `create_social_background`, `get_social_background_by_founder`, `update_social_background`.
- **Founder pool** (373-463): `pool_item_to_db/pydantic`, `create_pool_items`, `list_pool_items`, `get_pool_item`, `update_pool_item_status`, `pool_item_exists` (dedup by normalized name+company+linkedin).
- **Opportunities** (470-553): `opportunity_to_db/pydantic`, `create_or_update_opportunity` (upsert, preserves status), `update_opportunity_status`, `get_opportunity`, `list_opportunities`.
- **Claims** (560-616): `claim_to_db/pydantic`, `create_claims`, `list_claims_for_opportunity`, `list_claims_for_founder`.
- **Sourcing schedules** (623-714): full CRUD + `get_sourcing_schedule_by_thesis`, `list_due_sourcing_schedules` (enabled AND `next_run_at` is null or past).
- **Sourcing jobs** (721-791): `sourcing_job_to_db/pydantic`, `create_sourcing_job`, `get_sourcing_job`, `list_sourcing_jobs`, `update_sourcing_job`.
- **Enrichment** (798-952): `list_founders_below_confidence` (cold-start founders with 0 confidence included; ordered by confidence ASC; supports `never_enriched_only` flag for enrich-once semantics), `count_founders_blocking_sourcing` (founders that block automatic sourcing), `increment_enrichment_attempts`, `mark_founder_enriched`, `enrichment_run_to_db/pydantic`, `create_enrichment_run`, `update_enrichment_run`, `list_enrichment_runs`.

### 4.6 Estimation & document extraction

#### `estimation.py` (103 lines)
AI estimation layer that bridges LLM output into the deterministic scoring engine.
- **`should_estimate_founder(db, founder_id)`** (14): returns `False` if founder already has ≥8 evidence items AND confidence ≥0.3 (skip heuristic).
- **`estimate_founder_scores(founder_id, db=None)`** (34): gathers all available context (founder `source_reason`, `ai_research_summary`, social background `summary`, all `claims`), passes them to `AIFounderEstimator.estimate()`, which returns one `EvidenceItem` per dimension (type `INFERRED_ESTIMATE`). Adds evidence, recalculates score, syncs opportunities. Returns the new snapshot as a dict or `None` if skipped/failed.

#### `document_extractor.py` (40 lines)
Pure text extraction from uploaded files. No AI.
- **`extract_text(file_bytes, filename)`** (13): dispatches by extension — `.pdf` via `pypdf.PdfReader`, `.docx` via `python-docx.Document`, `.txt`/`.md` via UTF-8 decode. All capped at `MAX_TEXT_CHARS = 200_000`. Returns `None` for unsupported types.

### 4.7 AI/research agents (`backend/research/`)

All agents call OpenAI's chat completions endpoint directly via `httpx` (not the OpenAI SDK). All use the shared `api_lock()` context manager and `raise_for_status()` which integrates with the circuit breaker. All parse JSON from the LLM response, stripping markdown fences.

| Agent | File | Main method | Inputs | Outputs | Model env var | Web search default |
|---|---|---|---|---|---|---|
| **OpenAIClient** | `openai_client.py` (137) | `research(query, channels) -> dict` | Free-text query + channel list (linkedin, twitter, github, news, company_blog) | `{profile, summary, sources, evidence}` | `OPENAI_MODEL` | true (`OPENAI_ENABLE_WEB_SEARCH_RESEARCH`) |
| **SourcingAgent** | `sourcing_agent.py` (212) | `discover(sectors, stages, geographies, risk_appetite, sources) -> dict` | Thesis params + optional source configs (platform+keywords) | `{recommendations: [{name, email, current_company, role, location, linkedin_url, github_url, source_url, reason}]}` | `OPENAI_SOURCING_MODEL` | true |
| **SocialAgent** | `social_agent.py` (152) | `research(name, linkedin_url, github_url) -> dict` | Founder name + LinkedIn/GitHub URLs | `{summary, footprints, evidence}` | `OPENAI_SOCIAL_MODEL` | **false** (URLs are usually provided) |
| **DocumentAgent** | `document_agent.py` (130) | `extract(text, filename) -> dict` | Extracted document text | `{profile, summary, claims, evidence}` | `OPENAI_DOCUMENT_MODEL` | none (timeout 120s) |
| **AIFounderEstimator** | `founder_estimator.py` (189) | `estimate(founder, source_reason, research_summary, social_summary, claims) -> List[EvidenceItem]` | All available context | One `EvidenceItem` per dimension (type `INFERRED_ESTIMATE`) | `OPENAI_ESTIMATE_MODEL` | none |
| **TavilyClient** | `tavily_client.py` (118) | `search(query, max_results, search_depth, include_answer) -> dict` + static `format_results(data) -> str` | Search query | Real-time web search results formatted for LLM prompt injection | n/a | n/a |

**SourcingAgent validation** (`_validate_recommendations` at `sourcing_agent.py:171`): enforces that each recommendation has a `name` and `source_url`; raises if none valid.

**AIFounderEstimator** uses a dedicated `_ESTIMATE_SYSTEM_PROMPT` that instructs the LLM to produce exactly one evidence item per dimension, leaning conservative. Coerces output via `evidence_from_llm` with defaults: `source_type="ai_estimate"`, `evidence_type="inferred_estimate"`, `independence_group="ai_estimate"`.

#### Supporting research modules
- **`research/web_search.py`** (46): `prepare_web_search(query, enabled) -> Optional[str]` — fetches Tavily results and formats them; degrades gracefully to a fallback message if Tavily fails.
- **`research/api_lock.py`** (199): Distributed Redis lock (`api_lock()` context manager) serializing all LLM API calls across workers + circuit breaker (`LLMAPIOverload` exception). Opens after `CIRCUIT_BREAKER_FAILURE_THRESHOLD` (3) consecutive retryable failures, stays open for `CIRCUIT_BREAKER_COOLDOWN_SECONDS` (600s). Also has `is_web_search_enabled()` for per-agent web search toggles.
- **`research/http_utils.py`** (47): `raise_for_status()` (logs body on error, updates circuit breaker counters), `is_retryable_status()` (408, 429, 500, 502, 503, 504).
- **`research/prompts.py`** (273): Four large system prompts — `FOUNDER_RESEARCH_SYSTEM_PROMPT`, `SOCIAL_RESEARCH_SYSTEM_PROMPT`, `DOCUMENT_EXTRACTION_SYSTEM_PROMPT`, `SOURCING_SYSTEM_PROMPT`. Each defines the exact JSON schema the LLM must return, dimension mappings, evidence-type guidance, rubric levels (0-4), and trust/relevance/recency guidance.
- **`research/extractor.py`** (100): coercion helpers that convert LLM JSON output into typed Pydantic models:
  - `evidence_from_llm(founder_id, item)` (15): coerces one dict into `EvidenceItem`, clamping floats to `[0,1]` and rubric_level to `[0,4]`, with safe defaults.
  - `create_founder_from_research(profile, summary, sources)` (45): builds a `Founder` from LLM profile dict.
  - `create_social_background(founder_id, result, ...)` (65): builds a `SocialMediaBackground` from LLM result with footprints and evidence.
- **`research/__init__.py`** (19): re-exports `OpenAIClient`, `SocialAgent`, `SourcingAgent`, `DocumentAgent`, `TavilyClient`, `prepare_web_search`, `evidence_from_llm`, `create_founder_from_research`, `create_social_background`.

### 4.8 Async tasks (`backend/tasks/`)

#### `celery_app.py` (62 lines)
Celery app `app = Celery("founderos")`. Broker/backend from `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` (default `redis://localhost:6379/0`). JSON serialization, UTC timezone, `task_track_started=True`. `task_always_eager` controlled by `CELERY_ALWAYS_EAGER` env (for tests).

**Celery beat schedule** (`celery_app.py:33-44`):

| Schedule name | Task | Interval | Env override |
|---|---|---|---|
| `dispatch-sourcing-jobs` | `tasks.founder_pool.dispatch_sourcing_jobs` | 60s | `SOURCING_DISPATCH_INTERVAL_SECONDS` |
| `dispatch-enrichment-jobs` | `tasks.enrichment_task.dispatch_enrichment_jobs` | 180s | `ENRICHMENT_DISPATCH_INTERVAL_SECONDS` |

Imports: `tasks.social_research`, `tasks.founder_pool`, `tasks.document_extraction`, `tasks.estimation_task`, `tasks.enrichment_task`.

#### `tasks/social_research.py` (138 lines)
- **`store_social_background(background)`** (22): persists a `SocialMediaBackground` (upsert by founder).
- **`load_social_background(founder_id)`** (35): loads latest background for a founder.
- **`@app.task research_social_background(founder_id, name, email, linkedin_url, github_url, auto_score=True)`** (47-138): rate-limited 4/min, max 3 retries. Creates a "running" background record, calls `SocialAgent.research()`, builds a `SocialMediaBackground` with evidence, optionally computes a score snapshot, updates opportunities, then calls `estimate_founder_scores()` to fill remaining unknown dimensions. On failure, marks background as "failed" and retries.

#### `tasks/founder_pool.py` (564 lines)
- **`load_founder_pool`/`save_founder_pool`** (47-75): DB persistence helpers.
- **`acquire_refresh_lock`/`release_refresh_lock`** (78-102): Redis distributed lock (`founder_pool_refresh_lock`, TTL 300s) so only one worker refreshes the pool at a time.
- **`create_founder_and_opportunity_from_pool_item(db, item)`** (143-216): promotes a pool item into a `Founder` + cold-start `OpportunityScreen` + cold-start score snapshot. Auto-queues social research if links exist. Deduplicates against existing founders.
- **`refresh_founder_pool(...)`** (219-398): core sourcing logic. Acquires lock, calls `SourcingAgent.discover()`, deduplicates against existing pool items and founders (by normalized name+company+linkedin), creates new pool items, promotes each to a founder+opportunity, runs `estimate_founder_scores`. Updates the `SourcingJob` record through stages: searching → deduplicating → persisting → completed.
- **`run_sourcing_job(thesis_id)`** (401-435): creates a `SourcingJob` record and dispatches `refresh_pool_task`.
- **`@app.task dispatch_sourcing_jobs()`** (438-525): **beat task**. **Enrichment gate**: if any founder is below `ENRICHMENT_CONFIDENCE_THRESHOLD` (0.30) AND has `enrichment_attempts == 0`, sourcing is skipped (`skipped_reason: "enrichment_pending"`). Otherwise finds due schedules, skips if a job is already running for that schedule, dispatches `run_sourcing_job`, updates `last_run_at`/`next_run_at`. Records `sourcing:last_dispatch_at` in Redis.
- **`@app.task refresh_pool_task(...)`** (528-564): rate-limited 4/min, max 3 retries. Wraps `refresh_founder_pool` with retry logic.

#### `tasks/document_extraction.py` (172 lines)
- **`@app.task extract_document(file_bytes_b64, filename, opportunity_id, founder_id)`** (30-172): rate-limited 4/min, max 3 retries. Base64-decodes the file, extracts text via `document_extractor.extract_text`, calls `DocumentAgent.extract()`, creates `Claim` records and `EvidenceItem` records, re-scores the founder, syncs opportunities, calls `estimate_founder_scores` to fill gaps, and optionally updates the founder profile from extracted data (only filling empty fields).

#### `tasks/estimation_task.py` (39 lines)
- **`@app.task run_estimate(founder_id)`** (10-39): rate-limited 4/min, max 2 retries. Thin wrapper around `estimate_founder_scores()`. Returns `{founder_id, status, snapshot}` or `{status: "skipped"}`.

#### `tasks/enrichment_task.py` (418 lines)
The 3-stage enrichment pipeline. Config: `ENRICHMENT_CONFIDENCE_THRESHOLD` (0.30), `ENRICHMENT_MAX_FOUNDERS_PER_RUN` (5), `ENRICHMENT_MIN_GAP_SECONDS` (600).
- **`enrich_social(founder_id)`** (60-145): Stage 1. Skips if no social links. Runs `research_social_background.run()` synchronously. Records an `EnrichmentRun` with `stage="social"`.
- **`enrich_deep_web(founder_id)`** (152-263): Stage 2. Skips if confidence already ≥ threshold. Calls `OpenAIClient.research()` with channels `["news", "company_blog", "twitter"]`. Adds evidence, updates `ai_research_summary`/`ai_research_sources`, re-scores. Records run with `stage="deep_web"`.
- **`enrich_estimate(founder_id)`** (270-324): Stage 3. Calls `estimate_founder_scores()`. Records run with `stage="estimate"`.
- **`@app.task enrich_founder_chain(founder_id)`** (331-367): rate-limited 3/min, max 1 retry. Runs all 3 stages sequentially; a failure in one stage does not abort the others. After completion, stamps `last_enriched_at` and increments `enrichment_attempts` (this is what unblocks the sourcing gate).
- **`@app.task dispatch_enrichment_jobs()`** (374-417): **beat task**. **Enrich-once semantics**: only founders with `enrichment_attempts == 0` AND below threshold are picked. Stamps `last_enriched_at` immediately (debounce), dispatches `enrich_founder_chain.delay()`. Records `enrichment:last_dispatch_at` in Redis.

#### `tasks/retry_utils.py` (73 lines)
Shared retry helpers. Constants: `SOURCING_MAX_RETRIES` (3), `SOCIAL_RESEARCH_MAX_RETRIES` (3), `DOCUMENT_MAX_RETRIES` (3), all base delays 60s (120s in `.env.example`), `MIN_RETRY_DELAY_SECONDS` (60/120).
- **`retry_countdown()`** (27): exponential backoff `base × 2^retries` + jitter, honoring `Retry-After` header on 429s but never below `MIN_RETRY_DELAY_SECONDS`.
- **`maybe_retry()`** (60): retries if `should_retry()` (only retryable HTTP statuses), otherwise re-raises.

### 4.9 Seed data (`seed_data.py`, 228 lines)

- **`DEFAULT_SOURCING_INTERVAL_SECONDS`** (14): 3600 (1 hour), env-overridable.
- **`AI_THESES`** (22-78): 5 AI-focused theses with `demo_` prefixed IDs:
  1. `demo_ths_ai_infra` — AI Infrastructure (US/Europe, $250k-$1.5M)
  2. `demo_ths_ai_agents` — AI Agents & Automation (Global, $100k-$1M)
  3. `demo_ths_ai_dev_tools` — AI Developer Tools (US/India, $250k-$1M)
  4. `demo_ths_vertical_ai` — Vertical AI SaaS (India/Europe, $250k-$1M)
  5. `demo_ths_india_ai` — India-first AI (India, $100k-$500k)
- **`staggered_next_run_at(now, index, total)`** (81): spreads schedule starts evenly across the interval to avoid thundering herd.
- **`default_sources_for_thesis(thesis)`** (94): generates LinkedIn + Twitter `SourceConfig` with keywords from sectors + geographies.
- **`SAMPLE_FOUNDERS`** (114-145): 3 founders — Alex Rivera (Berlin, ML Code Review), Sam Okonkwo (SF, PromptBridge), Priya Nair (Austin, TractionAI).
- **`SAMPLE_OPPORTUNITIES`** (148-182): 3 opportunities — cold_start, founder_spike, contradictory_traction.
- **`SAMPLE_POOL_ITEMS`** (185-228): 3 pool items matching the sample founders, with sources "linkedin"/"twitter" and reasons.

### 4.10 Tests (`backend/tests/`)

Test config (`conftest.py`): uses test DB `postgresql+psycopg2://postgres:founderos@localhost:5433/founderos_test`, sets `CELERY_ALWAYS_EAGER=true` and `OPENAI_API_KEY=test-key`. Recreates tables from SQLAlchemy models (not Alembic). Truncates all tables after each test.

| File | Covers |
|---|---|
| `conftest.py` (65) | Fixtures: `db`, `client` (TestClient), `clean_tables` (autouse truncate) |
| `test_scoring.py` (128) | Deterministic scoring: missing dimension → unknown, single-item cap, chat-only confidence cap (≤0.60), verified source bypasses chat cap, contradiction reduces confidence |
| `test_opportunities.py` (131) | Opportunity CRUD: list empty, 404, create+list+get, re-screen existing, default SCREENING status, status update, invalid status 400, status preservation on re-screen, status filter |
| `test_thesis.py` (79) | Thesis CRUD: create, list, get, 404, update (partial), update 404 |
| `test_enrichment.py` (184) | Enrichment pipeline: `list_founders_below_confidence` targets cold-start, social skip when no links, social runs research, deep_web adds evidence+scores, estimate records run, full chain runs all 3 stages, dispatcher queues below-threshold, enrich-once skips already-enriched, sourcing gate skips when unenriched, sourcing resumes after enriched once |
| `test_founder_pool.py` (180) | Pool: save/load, refresh adds recommendations, refresh endpoint queues task, approve creates founder, dismiss, list endpoint, duplicate skipping, `SourcingAgent._validate_recommendations` validation |
| `test_seed_all.py` (41) | `/v1/seed/all` idempotency: first call creates 5 theses/schedules, 3 founders/opportunities/pool items; second call creates nothing; verifies schedule intervals (3600s) and sources (linkedin+twitter) |
| `test_document_extraction.py` (134) | Deck upload: extracts claims+evidence, rejects unknown file type, requires existing opportunity (404) |
| `test_social_agent.py` (108) | `create_social_background` extracts footprints+evidence; `SocialAgent._parse_response` strips markdown fences |
| `test_social_tasks.py` (89) | `store/load_social_background`; `research_social_background` task runs, scores, and stores completed background |
| `test_api_social.py` (71) | POST /founders queues social research; GET social-background returns pending/completed; manual research-social endpoint |
| `test_sourcing_schedules.py` (197) | Schedule CRUD, duplicate rejection, source-now creates job, dispatch respects due time, seed creates default schedule, sourcing status endpoint |
| `test_tavily_client.py` (95) | TavilyClient: requires API key, uses env key, search hits endpoint, format_results, empty results, `prepare_web_search` disabled/enabled/degrades on failure |
| `test_api_lock.py` (110) | API lock: acquire/release, release on exception, raises when circuit open, degrades when Redis unavailable, circuit opens after 3 failures, resets on success, per-agent web search defaults (sourcing=true, social=false, research=true), per-agent overrides legacy toggle |
| `test_umans_lock.py` (5) | Deprecated placeholder (Umans lock tests moved to `test_api_lock.py`) |

### 4.11 Alembic migrations (`backend/alembic/`)

- `alembic.ini` (149): standard config, `script_location = %(here)s/alembic`, default URL `postgresql+psycopg2://postgres:founderos@localhost:5433/founderos` (overridden by `DATABASE_URL` env in `env.py`).
- `alembic/env.py` (85): imports `db_models` for autogenerate support, allows `DATABASE_URL` to override ini URL, normalizes `postgres://` → `postgresql+psycopg2://`.

**10 migration files** in `alembic/versions/`:

1. `e313542fa678_initial_schema.py` — initial schema
2. `f6cea5e9817c_seed_ai_thesis_and_sample_data.py` — seed data
3. `5501783426f8_add_sourcing_schedules_jobs_and_claim_.py` — sourcing schedules, jobs, claims
4. `45a509d755d8_add_sources_to_sourcing_schedules_and_.py` — sources field
5. `a1b2c3d4e5f6_add_status_to_opportunities.py` — opportunity status
6. `1297e6a356eb_add_source_fields_to_founders.py` — founder source fields
7. `b3c4d5e6f7a8_add_enrichment_tracking.py` — enrichment tracking
8. `c4d5e6f7a8b9_add_enrichment_attempts.py` — enrichment attempts
9. `72b73b5cbec9_add_job_observability_columns.py` — job observability
10. `96119774d656_update_demo_schedules_to_hourly_.py` — update demo schedules to hourly

### 4.12 Environment variables

There is no `env_config.py`; configuration is distributed across modules reading `os.environ` directly. The canonical reference is **`.env.example`** (91 lines).

#### Database (`database.py`)
- `DATABASE_URL` — default `postgresql+psycopg2://localhost:5432/founderos`. Legacy `postgres://` auto-normalized.

#### Celery (`celery_app.py`)
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` — default `redis://localhost:6379/0`
- `CELERY_ALWAYS_EAGER` — `false` (set `true` for tests/local)
- `SOURCING_DISPATCH_INTERVAL_SECONDS` — 60
- `ENRICHMENT_DISPATCH_INTERVAL_SECONDS` — 180

#### OpenAI (per-agent in `research/`)
- `OPENAI_API_KEY` — **required**
- `OPENAI_BASE_URL` — default `https://api.openai.com/v1/chat/completions`
- `OPENAI_MODEL` / `OPENAI_SOURCING_MODEL` / `OPENAI_SOCIAL_MODEL` / `OPENAI_DOCUMENT_MODEL` / `OPENAI_ESTIMATE_MODEL` — all default `gpt-5`
- `OPENAI_TIMEOUT` — 60 (document agent uses 120)
- `OPENAI_MAX_TOKENS` — 8000 (estimator uses 4000)
- `OPENAI_ENABLE_WEB_SEARCH` — global toggle (default true)
- `OPENAI_ENABLE_WEB_SEARCH_SOURCING` — true
- `OPENAI_ENABLE_WEB_SEARCH_SOCIAL` — false
- `OPENAI_ENABLE_WEB_SEARCH_RESEARCH` — true (per-agent overrides)

#### Tavily (`research/tavily_client.py`)
- `TAVILY_API_KEY` — **required** for web search
- `TAVILY_SEARCH_DEPTH` — `basic`
- `TAVILY_MAX_RESULTS` — 5
- `TAVILY_TIMEOUT` — 30

#### API lock & circuit breaker (`research/api_lock.py`)
- `API_LOCK_DISABLED` — false
- `API_LOCK_KEY` — `llm_api_lock`
- `API_LOCK_TTL_SECONDS` — 120
- `API_LOCK_TIMEOUT_SECONDS` — 30
- `API_CALL_DELAY_SECONDS` — 0
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD` — 3
- `CIRCUIT_BREAKER_COOLDOWN_SECONDS` — 600

#### Retry (`tasks/retry_utils.py`)
- `SOURCING_MAX_RETRIES` / `SOCIAL_RESEARCH_MAX_RETRIES` / `DOCUMENT_MAX_RETRIES` — 3
- `SOURCING_RETRY_BASE_DELAY` / `SOCIAL_RESEARCH_RETRY_BASE_DELAY` / `DOCUMENT_RETRY_BASE_DELAY` — 60 (120 in `.env.example`)
- `MIN_RETRY_DELAY_SECONDS` — 60 (120 in `.env.example`)

#### Enrichment (`tasks/enrichment_task.py`)
- `ENRICHMENT_CONFIDENCE_THRESHOLD` — 0.30
- `ENRICHMENT_MAX_FOUNDERS_PER_RUN` — 5
- `ENRICHMENT_MIN_GAP_SECONDS` — 600

#### Sourcing (`tasks/founder_pool.py`, `seed_data.py`)
- `POOL_LOCK_TTL_SECONDS` — 300
- `DEFAULT_SOURCING_INTERVAL_SECONDS` — 3600

#### Logging (`logger_config.py`)
- `LOG_LEVEL` — INFO (stdout handler, format `%(asctime)s | %(levelname)s | %(name)s | %(message)s`)

#### Server
- `PORT` — 8000

#### Deployment (Railway)
- `railway.toml`: web service — `alembic upgrade head && gunicorn main:app --workers 2 --timeout 120 -k uvicorn.workers.UvicornWorker`, healthcheck at `/health`
- `railway.worker.toml`: worker — `celery -A celery_app worker --concurrency=1 --prefetch-multiplier=1 --max-tasks-per-child=10 --max-memory-per-child=300000`
- `railway.beat.toml`: beat scheduler — `celery -A celery_app beat -l info`

---

## 5. Frontend deep-dive

App name (package.json): `founderos-web` v0.1.0. App title (index.html): "Seed Engine | Decision Workspace".
React + TypeScript + Vite SPA that serves as a VC investment decision workspace. Talks to the FastAPI/Railway backend (default `http://localhost:8000`, prod `https://api.founder-os.up.railway.app`). UI is themed as a "paper/manila file folder" workspace for screening, diligencing, and deciding on founder investment cases.

### 5.1 `package.json`

- **Package manager:** `pnpm@10.4.1`.
- **Type:** ES module.
- **Scripts:** `dev` → `vite` (port 3000), `build` → `tsc -b && vite build`, `lint` → `eslint .`, `preview` → `vite preview`, `test` → `vitest`.
- **Runtime deps:** `react` ^18.3.1, `react-dom` ^18.3.1, `react-router-dom` ^6.24.1, `lucide-react` ^0.400.0.
- **Dev deps:** `vite` ^5.3.1, `@vitejs/plugin-react` ^4.3.1, `typescript` ^5.2.2, `tailwindcss` ^3.4.4, `postcss`, `autoprefixer`, `eslint` ^8.57.0 + react-hooks/react-refresh plugins, `vitest` ^1.6.0.

### 5.2 App shell, routing, navigation (`src/App.tsx`, 93 lines)

- Wraps everything in `<AppProvider>` (global state context).
- Two-column layout:
  - **Left file rail** (`<aside>`, lines 36-64): sticky sidebar, `w-16` on mobile / `w-56` on `lg+`. Shows "Seed Engine" / "SE" logo at top, nav links in the middle, `<RoleSwitcher />` at the bottom.
  - **Main workspace** (`<div>`, lines 67-87): header bar showing current page label + "Live backend data" indicator, then `<main>` with the routed page.
- Active nav item detected via `location.pathname.startsWith(item.path)` (line 47).

#### Navigation (`NAV` array, lines 20-27)

| Path | Label | Icon |
|------|-------|------|
| `/discovery` | Discovery | Inbox |
| `/sourcing` | Sourcing | Zap |
| `/cases` | Cases | FolderOpen |
| `/decisions` | Decisions | Gavel |
| `/thesis` | Thesis | SlidersHorizontal |
| `/validation` | Validation | ShieldCheck |

#### Routes (lines 76-85)

| Route | Component | Notes |
|-------|-----------|-------|
| `/` | `<Navigate to="/discovery" replace />` | Redirect |
| `/discovery` | `<Discovery />` | Founder list |
| `/sourcing` | `<Sourcing />` | AI sourcing control |
| `/cases` | `<Cases />` | Open case files |
| `/cases/:caseId` | `<DealRoom />` | Single case detail |
| `/decisions` | `<Decisions />` | Decision queue |
| `/thesis` | `<Thesis />` | Investment mandate |
| `/validation` | `<Validation />` | System audit |

**Entry point:** `src/main.tsx` (13 lines) — renders `<App />` inside `<BrowserRouter>` and `<React.StrictMode>`, imports `./index.css`.

**Note:** `src/pages/Apply.tsx` exists but is **not wired into the router** — a standalone inbound-application page (creates a founder + opportunity + uploads deck), currently unused in the nav.

### 5.3 Pages (`src/pages/`)

#### `Discovery.tsx` (313 lines)
**Purpose:** Searchable table of all AI-sourced founders with score breakdowns.
- Fetches `api.founders.list()` + `api.opportunities.list()` in parallel, joins by `founder_id`.
- `useAdaptivePolling`: 10s when active SCREENING/DILIGENCE opps exist, else 30s.
- Search filters by name, company, role, location, source_reason.
- Table columns: Founder (avatar initials + name + meta), Idea/why surfaced, Dimension scores (7 chips: EXE, LRN, SELL, JDG, LEAD, OWN, REL with color-coded badges), Founder score (with trend + progress bar), Confidence (%), Enrichment status (Needs enrichment / In progress / Enriched).
- Clicking a row navigates to `/cases/{opportunity_id}` (or `/cases` if no opp).
- Dimension label maps at top (lines 8-36): `execution`, `learning`, `customer_selling`, `judgment`, `leadership`, `ownership`, `claim_reliability`.

#### `Cases.tsx` (123 lines)
**Purpose:** Lists all open case files (opportunities) as cards.
- Fetches `api.opportunities.list()` + `api.founders.list()`.
- Adaptive polling 10s/30s based on active opps.
- Each card: company/founder name, "Live" badge, `<CaseStatusBadge>`, three stat tiles (Founder score, Confidence, Market posture), next action (from `caseOverrides` or `next_founder_action`).
- Links to `/cases/{opportunity_id}`.

#### `DealRoom.tsx` (532 lines) — **most complex page**
**Purpose:** Single-case detail view with live enrichment pipeline orchestration.
- Route param: `caseId` (= `opportunity_id`).
- **Initial load** (lines 45-94): fetches opportunity + diligence claims in parallel, then founder + score snapshot. **Auto-triggers enrichment on cold start** (line 72-84): if `overall_confidence <= 0`, calls `api.founders.enrich(f.id)` to kick off the 3-stage pipeline (social → deep web → estimate).
- **Three polling loops** via `useAdaptivePolling`:
  1. Diligence claims refresh every 10s (lines 98-101).
  2. Score polling while estimating (every 3s, 60s timeout, stops when confidence > 0) (lines 105-129).
  3. Enrichment runs + score polling (every 3s, 90s timeout, stops when confidence >= 0.3) (lines 134-168).
- **Renders** (`LiveOpportunityView`, lines 286-531):
  - Header panel: company name, "Live" badge, LinkedIn/GitHub social links, `<CaseStatusBadge>`, 4 stat tiles (Founder score, Confidence, Market posture, Idea vs market), next action.
  - Pipeline actions: `<CaseStatusActions>` for status transitions.
  - Source signal panel: `founder.source_reason` + source URL.
  - Founder score breakdown: grid of `<DimensionCard>` (lines 242-284) showing each dimension's adjusted score, confidence, evidence count, contradictions, next test, unknowns. Badges for "Unknown" and "AI estimate" (when all evidence is `inferred_estimate`).
  - Diligence claims list with deck upload button (PDF/DOCX/TXT/MD via `api.opportunities.uploadDeck`).
  - Founder-market fit grid (domain_knowledge, customer_access, unique_insight, etc.).
  - Team completeness grid (complementary_skills, missing_critical_roles, etc.).
- Helper `stageLabel` (lines 229-240) maps enrichment stages: `social` → "stage 1/3 social", `deep_web` → "stage 2/3 web research", `estimate` → "stage 3/3 estimate".

#### `Decisions.tsx` (130 lines)
**Purpose:** Decision queue showing cases in DILIGENCE, ASSOCIATE_REVIEW, or PARTNER_REVIEW.
- `DECISION_STATUSES` filter (line 11): `["DILIGENCE", "ASSOCIATE_REVIEW", "PARTNER_REVIEW"]`.
- Fetches opps + founders, polls 10s when queue non-empty else 30s.
- Each card: company name (links to DealRoom), status badge, score/confidence, next action, `<CaseStatusActions>` for inline status updates.
- Manual refresh button.

#### `Thesis.tsx` (307 lines)
**Purpose:** Investment mandate configuration — view active thesis, parse a compound query, create new theses, switch between stored theses.
- Uses `useApp()` for `activeThesis`, `setActiveThesis`, `createThesis`.
- **Three panels:**
  1. Settings: displays active thesis config (sector, stage, geography, check size, ownership target, risk appetite, exclusions).
  2. Compound query: textarea with `THESIS_DESCRIPTION` default, parsed via `parseThesisQuery` into filter badges. Explicit note (line 154-156): "This is keyword-based parsing with transparent filters, not model reasoning presented as inference."
  3. Manual thesis form: name, sectors, stages, geographies, check_size_min/max, risk_appetite select. Calls `createThesis()`.
- Stored theses selector at bottom: click to set active.

#### `Validation.tsx` (107 lines)
**Purpose:** System audit page showing deterministic validation metrics.
- Calls `computeValidationSummary()` from `@/engine/validationSummary` on mount.
- Six metric cards: Citation coverage, Seeded contradictions detected, Unsupported numeric claims, Routing tests (passed/total), Avg processing time, Human overrides.
- Details panel: lists any failed checks.
- 24-hour processing timeline: Ingestion → Validator → Specialists → Router → Partner decision (last one pending).

#### `Sourcing.tsx` (529 lines) — **second most complex page**
**Purpose:** AI sourcing control room — schedules, jobs, and founder pool.
- Fetches `api.sourcing.status()`, `api.sourcing.schedules()`, `api.pool.list()` in parallel.
- Adaptive polling: 5s when active jobs, else 30s.
- **Actions:**
  - `handleSeed` → `api.seed()` (single seed).
  - `handleSeedAll` → `api.seedAll()` (full demo dataset) — shows summary of created counts.
  - `handleRunNow(thesisId)` → `api.sourcing.runNow(thesisId)`.
  - `handleRefreshPool(thesisId?)` → `api.pool.refresh(thesisId)`.
  - `toggleSchedule` → enable/disable a schedule.
  - `handleAddSource` / `handleRemoveSource` → manage source configs (platform + keywords) per schedule.
- **Four sections:**
  1. Status cards: Active jobs, Recommended pool count, Schedules count, Last dispatch time.
  2. Sourcing schedules: per-thesis cards with enable/disable toggle, "Source now" button, source chips (LinkedIn/Twitter/Other + keywords) with add/remove UI.
  3. Recent jobs: list with status badge, progress %, leads found/added/skipped, timestamps, errors.
  4. Founder pool: list of `BackendPoolItem` with name, status badge, company/role/location, reason, source URL.
- Helper components: `JobStatusBadge` (pending/running/searching/deduplicating/persisting/completed/failed), `PoolStatusBadge` (recommended/approved/dismissed), `formatTime`, `formatInterval`.

#### `Apply.tsx` (269 lines) — **not routed**
**Purpose:** Inbound application form ("Drop a deck on the desk").
- Form fields: company, founder, email, product URL, deck selector (3 sample fixtures), real file upload, consent checkbox.
- "Preview sample deck" button calls `extractDeck()` (local fixture) then `claimsFromDeck()` to show a `<DeckClaimTable>`.
- "Submit application" calls `api.founders.create()` → `api.opportunities.screen()` → optionally `api.opportunities.uploadDeck()`, then navigates to `/cases/{oppId}`.
- Follow-up questions section with 4 categories (founder, idea, product, business) — fields marked "Deck" if answered by deck.

### 5.4 API client (`src/api/client.ts`, 244 lines)

**Base URL:** `import.meta.env.VITE_API_URL || "/api"` (line 26). The `/api` default relies on the Vite dev proxy.

**HTTP helpers** (lines 33-99): `get<T>` (cached), `post<T>`, `put<T>`, `patch<T>`, `del<T>`, `postForm<T>`. `handleResponse` detects HTML responses (backend down) and throws `ApiError { status, message }`.

**Re-exports** (lines 30-31): `invalidateCache`, `invalidateAllCache` from `@/api/cache`.

#### Complete API surface (the `api` object, lines 101-242)

| Function | Method | Endpoint | Returns | Cache invalidation |
|----------|--------|----------|---------|-------------------|
| `api.seed()` | POST | `/v1/seed` | `BackendSeedResponse` | invalidateAll |
| `api.seedAll()` | POST | `/v1/seed/all` | `{theses_created, schedules_created, founders_created, opportunities_created, pool_items_created, message}` | invalidateAll |
| `api.theses.list()` | GET | `/v1/theses` | `BackendThesis[]` | — |
| `api.theses.get(id)` | GET | `/v1/theses/${id}` | `BackendThesis` | — |
| `api.theses.create(req)` | POST | `/v1/theses` | `BackendThesis` | `/v1/theses` |
| `api.theses.update(id, req)` | PUT | `/v1/theses/${id}` | `BackendThesis` | `/v1/theses/${id}` + `/v1/theses` |
| `api.founders.list()` | GET | `/v1/founders` | `BackendFounder[]` | — |
| `api.founders.get(id)` | GET | `/v1/founders/${id}` | `BackendFounder` | — |
| `api.founders.score(id)` | GET | `/v1/founders/${id}/score` | `BackendScoreSnapshot` | — |
| `api.founders.estimate(id)` | POST | `/v1/founders/${id}/estimate` | `QueuedResponse` | score + enrichment runs |
| `api.founders.enrich(id)` | POST | `/v1/founders/${id}/enrich` | `QueuedResponse` | score + enrichment runs |
| `api.founders.create(req)` | POST | `/v1/founders` | `BackendFounder` | `/v1/founders` |
| `api.enrichment.runs(founderId?)` | GET | `/v1/enrichment/runs?founder_id=` | `BackendEnrichmentRun[]` | — |
| `api.enrichment.status()` | GET | `/v1/enrichment/status` | `BackendEnrichmentStatus` | — |
| `api.pool.list(status?)` | GET | `/v1/founders/pool?status=` | `BackendPoolItem[]` | — |
| `api.pool.approve(id)` | POST | `/v1/founders/pool/${id}/approve` | `ApprovedPoolItemResponse` | `/v1/founders/pool` |
| `api.pool.dismiss(id)` | POST | `/v1/founders/pool/${id}/dismiss` | `BackendPoolItem` | `/v1/founders/pool` |
| `api.pool.refresh(thesisId?)` | POST | `/v1/founders/pool/refresh?thesis_id=` | `QueuedResponse` | `/v1/founders/pool` |
| `api.opportunities.list(status?)` | GET | `/v1/opportunities?status=` | `BackendOpportunity[]` | — |
| `api.opportunities.get(id)` | GET | `/v1/opportunities/${id}` | `BackendOpportunity` | — |
| `api.opportunities.screen(id, founderId?)` | POST | `/v1/opportunities/${id}/screen?founder_id=` | `BackendOpportunity` | `/v1/opportunities` |
| `api.opportunities.updateStatus(id, status)` | PATCH | `/v1/opportunities/${id}/status` | `BackendOpportunity` | opp + opp list |
| `api.opportunities.diligence(id)` | GET | `/v1/opportunities/${id}/diligence` | `BackendClaim[]` | — |
| `api.opportunities.uploadDeck(id, file, founderId?)` | POST (form) | `/v1/opportunities/${id}/deck?founder_id=` | `UploadDeckResponse` | opp |
| `api.sourcing.status()` | GET | `/v1/sourcing/status` | `BackendSourcingStatus` | — |
| `api.sourcing.schedules()` | GET | `/v1/sourcing/schedules` | `BackendSourcingSchedule[]` | — |
| `api.sourcing.createSchedule(req)` | POST | `/v1/sourcing/schedules` | `BackendSourcingSchedule` | schedules |
| `api.sourcing.updateSchedule(id, req)` | PUT | `/v1/sourcing/schedules/${id}` | `BackendSourcingSchedule` | schedules |
| `api.sourcing.deleteSchedule(id)` | DELETE | `/v1/sourcing/schedules/${id}` | `{id, deleted}` | schedules |
| `api.sourcing.jobs()` | GET | `/v1/sourcing/jobs` | `BackendSourcingJob[]` | — |
| `api.sourcing.runNow(thesisId)` | POST | `/v1/theses/${thesisId}/source-now` | `QueuedResponse` | sourcing status + jobs |

#### `src/api/cache.ts` (146 lines) — stale-while-revalidate cache
- In-memory `Map<string, CacheEntry>` with per-path TTL rules (lines 25-37).
- **TTL rules** (more-specific first): score/enrichment runs = 2s fresh/10s stale; sourcing status = 3s/15s; theses/schedules = 10s/60s; pool/diligence = 5s/30s; founders/opportunities = 5-10s/30-60s. Default 5s/30s.
- `cacheGet<T>(fetcher, key)`: fresh hit returns cached; stale hit returns cached + background refetch; miss fetches + dedupes concurrent callers via `inflight` promise.
- `invalidate(prefix)`: deletes keys starting with prefix.
- `invalidateAll()`: clears everything.
- `__cacheInternals`: test-only helpers (peek, reset, size).

### 5.5 Global state (`src/store/appContext.tsx`, 183 lines)

#### State shape (`AppState`, lines 14-22)
```ts
{
  user: User;                          // { id, name, role }
  caseOverrides: Record<string, CaseOverride>;  // per-caseId local overrides
  theses: BackendThesis[];             // cached thesis list from backend
  activeThesisId: string | null;
  thesisLoading: boolean;
  thesisError: string | null;
}
```

#### `CaseOverride` (lines 7-12)
```ts
{ status?, owner?, nextAction?, decisions?: CaseDecision[] }
```

#### What's stored & how
- **User/role:** default `{ id: "u-analyst", name: "Jordan Lee", role: "ANALYST" }`. Role switchable via `<RoleSwitcher>` (ANALYST / ASSOCIATE / PARTNER).
- **caseOverrides:** local-only overrides per case (status, owner, nextAction, decisions). Not synced to backend — purely demo/UI state.
- **theses + activeThesisId:** fetched from backend on mount via `refreshTheses()` (lines 59-77). If the active thesis is no longer in the list, falls back to `theses[0]?.id`.
- **Persistence:** entire state serialized to `localStorage` under key `"vc-brain-demo-state-v1"` (lines 23, 166-183). Loaded on init with merge over defaults.

#### Context value exposes (lines 34-45)
- `state`, `activeThesis` (derived via `useMemo`)
- `setRole(role)`, `setUserName(name)`
- `setCaseOverride(caseId, patch)` — merges into caseOverrides
- `recordDecision(caseId, decision)` — appends to `caseOverrides[caseId].decisions`
- `setActiveThesis(id)`
- `refreshTheses()` — re-fetches from `api.theses.list()`
- `createThesis(req)` — calls API, prepends to theses, sets active
- `resetDemo()` — resets to defaultState + refreshTheses

#### Hooks
- `useApp()` (line 156): returns the context, throws if used outside provider.
- `useRole()` (line 162): convenience for `state.user.role`.

### 5.6 Local decision engine (`src/engine/`)

Five files implementing a deterministic, testable decision engine over `InvestmentCase` data. **Does NOT call the backend** — operates on `InvestmentCase` objects. The `Validation` page runs it over demo fixtures as a system audit.

#### `routing.ts` (121 lines) — Case routing & spike detection

**`CaseStatus` values** (defined in `domain/types.ts:1-12`): `DISCOVERED` | `ACTIVATION_READY` | `AWAITING_APPLICATION` | `SCREENING` | `DILIGENCE` | `VALIDATION_HOLD` | `ASSOCIATE_REVIEW` | `PARTNER_REVIEW` | `INVESTED` | `DECLINED` | `MONITORING`.

**`detectSpike(drivers)`** (lines 4-39): returns `TriggeredRule[]`.
- Excludes `VALUATION_CAP` from spiking (line 8) — "Valuation/cap structure cannot create a positive spike."
- **ONE_HIGH_SPIKE:** any non-valuation driver with `score >= 85` AND `confidence >= 0.70`.
- **TWO_QUALIFYING_SPIKES:** 2+ non-valuation drivers with `score >= 75` AND `confidence >= 0.65`.

**`routeCase(investmentCase)`** (lines 41-75): priority-ordered routing:
1. Material contradiction OR `validationHoldReason` set → `VALIDATION_HOLD`
2. `thesisResult === "INELIGIBLE"` → `DECLINED`
3. `thesisResult === "EXCEPTION_REVIEW"` → `SCREENING`
4. Any decision-critical driver (FOUNDER, MARKET, VISION_PRODUCT) confidence < 0.45 → `DILIGENCE`
5. Spike detected → `ASSOCIATE_REVIEW`
6. If already `ASSOCIATE_REVIEW` → stays `ASSOCIATE_REVIEW`
7. Critical confidence < 0.55 → `DILIGENCE`
8. Else: `DISCOVERED` → `SCREENING`, else keep current status

**`hasMaterialContradiction`** (lines 77-79): any claim with `status === "CONTRADICTED"` AND `contradictionPenalty >= 0.5`.

**`decisionCriticalConfidenceLow`** (lines 81-86): checks FOUNDER, MARKET, VISION_PRODUCT drivers against a floor (default 0.45 from config).

**`nextStatusAfterDecision(decision, current)`** (lines 88-104):
- INVEST → INVESTED
- DECLINE → DECLINED
- MONITOR → MONITORING
- REQUEST_EVIDENCE → DILIGENCE

**`allowedTransitions(status)`** (lines 106-121): returns valid next statuses:
- VALIDATION_HOLD → [VALIDATION_HOLD, DILIGENCE, DECLINED]
- ASSOCIATE_REVIEW → [ASSOCIATE_REVIEW, PARTNER_REVIEW, DILIGENCE, DECLINED]
- PARTNER_REVIEW → [PARTNER_REVIEW, INVESTED, DECLINED, MONITORING, DILIGENCE]
- DILIGENCE → [DILIGENCE, ASSOCIATE_REVIEW, SCREENING, DECLINED]
- SCREENING → [SCREENING, DILIGENCE, ASSOCIATE_REVIEW, DECLINED]
- default → [SCREENING, DILIGENCE, ASSOCIATE_REVIEW, DECLINED]

#### `trust.ts` (21 lines) — Claim trust scoring
**`calculateTrustScore(claim)`** (lines 4-13): weighted sum clamped to `[0,1]`:
```
0.30*sourceReliability + 0.20*extractionConfidence + 0.20*corroboration +
0.15*recency + 0.15*evidenceSpecificity - 0.35*contradictionPenalty
```
(Weights from `CLAIM_TRUST_WEIGHTS` in `config/weights.ts`.)
- `clamp(value, min, max)` (line 15).
- `recomputeClaimTrust(claim)` (line 19): returns claim with recalculated `trustScore`.

#### `scoring.ts` (15 lines) — Queue priority
**`calculateQueuePriority(drivers)`** (lines 4-11): weighted sum of driver scores using `DRIVER_WEIGHTS` (FOUNDER 0.35, MARKET 0.15, VISION_PRODUCT 0.10, TRACTION 0.10, DIFFERENTIATION 0.20, VALUATION_CAP 0.10). Missing drivers default to 50. Rounded to 1 decimal.
- `getDriver(drivers, key)` (line 13): finds a driver by key.

#### `stateMachine.ts` (43 lines) — Time, events, status helpers
- `calculateTimeRemaining(deadline)` (lines 3-20): returns `Duration` with `totalSeconds`, `days/hours/minutes/seconds`, `isExpired`, `percentRemaining` (relative to a 24-hour SLA).
- `applyEvent(investmentCase, event)` (lines 22-28): returns new case with event appended to history (immutable — original unchanged).
- `isTerminal(status)` (line 30): true for INVESTED, DECLINED, MONITORING.
- `canDecide(status)` (line 34): true for ASSOCIATE_REVIEW, PARTNER_REVIEW, SCREENING.
- `statusLabel(status)` (lines 38-43): human-readable label (e.g. "Associate Review").

#### `validationSummary.ts` (107 lines) — System audit
**`computeValidationSummary()`** (lines 19-79): runs deterministic checks over `DEMO_CASES`:
- Citation coverage: % of claims with a source ref containing URL/slide/excerpt.
- Contradictions detected: count of CONTRADICTED claims.
- Unsupported numeric claims: claims with a digit but no source or contradicted.
- Routing tests: 3 demo cases (caseA → ACTIVATION_READY, caseB → ASSOCIATE_REVIEW, caseC → VALIDATION_HOLD) + 3 spike tests (valuation-only should NOT spike; founder spike should; two qualifying should).
- Average processing time: hardcoded 120ms (deterministic demo).
- Human override count: 0.
- Returns `ValidationSummary` with `details[]` of any failures.

### 5.7 Agent stubs (`src/agents/`)

`src/agents/index.ts` (9 lines) — barrel export re-exporting all agents.

#### `contracts.ts` (95 lines) — Agent interfaces & stubs
- `AgentContext` (line 13): `{ investmentCase, claims, role }`.
- `LeadAnalystOutput` (line 19): `{ summary, driverAssignments, nextQuestions }`.
- `DealCaptainOutput` (line 25): `{ owner, nextAction, recommendedStatus, rationale }`.
- `MemoWriterOutput` (line 32): `{ memo: CaseMemo, lockedClaimIds }`.
- `ExtractionAdapter` (line 37): interface for `extractDeck(deckName, deckText)`.
- `AGENT_NAMES` (line 41): maps DriverKey → human name (FOUNDER → "Founder Analyst", etc.).
- `specialistStub(...)` (line 50): builds a `SpecialistOutput`.
- `validationStub(...)` (line 72): builds a `ValidationOutput`.
- `skepticStub(...)` (line 88): builds a `SkepticOutput`.
- Re-exports `SpecialistOutput`, `ValidationOutput`, `SkepticOutput` from domain types.

#### `leadAnalyst.ts` (49 lines)
Reads all claims, assigns each to a driver via `categoryToDriver` mapping (TEAM → FOUNDER, MARKET → MARKET, PRODUCT → VISION_PRODUCT, TRACTION → TRACTION, DIFFERENTIATION → DIFFERENTIATION, TERMS → VALUATION_CAP). Produces a summary string, driver assignments, and up to 4 next questions (from missing evidence).

#### `founderAnalyst.ts` (28 lines)
Specialist for the FOUNDER driver. Returns the existing driver assessment or a default (score 50, confidence 0.3) with missing evidence ["Founder track record", "Reference checks", "Public artifacts"]. Recommended next question: "Can you walk us through a hard scaling decision you owned?"

#### `marketAnalyst.ts` (28 lines)
Specialist for the MARKET driver. Same pattern. Missing evidence: ["Buyer interviews", "Competitive map", "Market timing"]. Next question: "Who is the specific buyer and what budget line does this come from?"

#### `productTractionAnalyst.ts` (28 lines)
Combined specialist for VISION_PRODUCT + TRACTION. Averages the two scores, takes min confidence, unions supporting/opposing/missing claim IDs. Next question: "What is the smallest paying customer segment and how many repeat uses have you observed?"

**Note:** No separate `differentiationAnalyst.ts` or `termsAnalyst.ts` file — `AGENT_NAMES` references them, but only founder, market, and product/traction specialists are implemented as standalone functions. Differentiation and Terms would use `specialistStub`.

#### `validator.ts` (36 lines)
Validates claims. Accepts VERIFIED + DECLARED claims. Quarantines CONTRADICTED claims (with reason citing trust score). Downgrades PROJECTION/ASSUMPTION claims to 80% of trust score. Flags material contradiction if quarantined claims exist AND `validationHoldReason` is set.

#### `skeptic.ts` (24 lines)
Adversarial agent. Builds the strongest counter-case from contradicted claims (or a default about unverified founder-reported claims). Identifies the weakest driver (confidence < 0.5) as the decision-sensitive unknown. May request reanalysis of that driver.

#### `dealCaptain.ts` (16 lines)
Orchestrator. Calls `routeCase()` to get recommended status, returns owner, nextAction, recommendedStatus, and a rationale string summarizing routing result, material contradictions, and spike rules.

#### `memoWriter.ts` (24 lines)
Produces the investment memo. Returns the existing `investmentCase.memo` or a default empty memo. `lockedClaimIds` = VERIFIED + INFERRED claim IDs (these are "locked" as citable evidence).

#### `claimExtractor.ts` (47 lines)
Converts a `DeckExtractionResult` into `Claim[]`. For each slide's claims, creates a `SourceRef` (sourceType DECK, with slide number + excerpt), computes reliability by claim kind (FACT 0.75, PROJECTION 0.55, else 0.6), computes a trust score, and sets status (FACT → DECLARED, else → INFERRED).

#### `deckExtractor.ts` (45 lines)
Async adapter that returns a `DeckExtractionResult`. Looks up `DECK_EXTRACTIONS` fixtures by name match. Falls back based on keywords ("traction"/"revenue" → contradictory-traction case; "prompt"/"founder" → founder-spike case; "hackathon"/"code"/"github" → cold-start case). Ultimate fallback returns a single-slide stub with an ASSUMPTION claim and missing sections. **This is a deterministic fixture-based stub, not a real LLM call.**

### 5.8 Key TypeScript types

#### `src/domain/types.ts` (247 lines) — Core domain model

**`CaseStatus`** (lines 1-12): 11-value union (listed in §5.6).

**`ClaimStatus`** (lines 14-19): `DECLARED | INFERRED | VERIFIED | CONTRADICTED | UNRESOLVED`.

**`Trend`** (lines 21-25): `IMPROVING | DECLINING | STABLE | INSUFFICIENT_HISTORY`.

**`SourceType`** (line 27): `DECK | FORM | GITHUB | WEB | EVENT | REFERENCE`.

**`SourceRef`** (lines 29-37): `{ id, sourceType, title, url?, slide?, excerpt?, observedAt }`.

**`ClaimCategory`** (lines 39-45): `TEAM | MARKET | PRODUCT | TRACTION | DIFFERENTIATION | TERMS`.

**`Claim`** (lines 47-63):
```ts
{ id, caseId, category, text, status, sourceRefs: SourceRef[],
  sourceReliability, extractionConfidence, corroboration, recency,
  evidenceSpecificity, contradictionPenalty, trustScore,
  claimKind?: "FACT"|"PROJECTION"|"ASSUMPTION"|"OPINION",
  contradictionOf?: string }
```

**`DriverKey`** (lines 65-71): `FOUNDER | MARKET | VISION_PRODUCT | TRACTION | DIFFERENTIATION | VALUATION_CAP`.

**`DriverAssessment`** (lines 73-82):
```ts
{ key, score, confidence, trend, supportingClaimIds, opposingClaimIds,
  missingEvidence: string[], rubricReason }
```

**`AxisKey`** (line 84): `FOUNDER | MARKET | IDEA_MARKET`.

**`AxisAssessment`** (lines 86-92): `{ key, score, confidence, trend, driverKeys }`.

**`InvestmentCase`** (lines 94-118) — the central aggregate:
```ts
{ id, companyId?, founderIds: string[], sourceChannel,
  inboundOrOutbound: "INBOUND"|"OUTBOUND", status: CaseStatus,
  thesisResult: "ELIGIBLE"|"EXCEPTION_REVIEW"|"INELIGIBLE",
  owner, createdAt, decisionDeadline, nextAction,
  claims: Claim[], drivers: DriverAssessment[], axes: AxisAssessment[],
  validationHoldReason?, triggeredRules: string[],
  memo?: CaseMemo, history?: EvidenceEvent[],
  skepticCounterCase?, strongestEvidenceClaimIds?,
  termsCheckSize?, termsOwnershipTarget?, termsValuationCap? }
```

**`EvidenceEvent`** (lines 120-131): `{ id, entityId, eventType, effectiveAt, observedAt, sourceRefIds, affectedDrivers, previousValues, newValues, explanation }`.

**`CaseMemo`** (lines 133-143):
```ts
{ companySnapshot, hypotheses: string[],
  swot: { strengths, weaknesses, opportunities, threats },
  problemAndProduct, tractionKpis: string[],
  contradictions: string[], missingInformation: string[],
  recommendedNextAction, claimCitations: Record<string, string[]> }
```

**`DeckExtractionResult`** (lines 145-159): `{ slides: [{slide, title?, text, claims: [...]}], missingSections, unreadableSlides }`.

**`SpecialistOutput`** (lines 161-170): `{ driver, recommendedScore, confidence, rubricReason, supportingClaimIds, opposingClaimIds, missingEvidence, recommendedNextQuestion? }`.

**`ValidationOutput`** (lines 172-178): `{ acceptedClaimIds, downgradedClaims, quarantinedClaims, materialContradiction, holdReason? }`.

**`SkepticOutput`** (lines 180-185): `{ strongestCounterCase, evidenceClaimIds, decisionSensitiveUnknown, requestedReanalysis? }`.

**`TalentSignal`** (lines 187-201): `{ id, person, currentProject?, artifactUrl?, sourceChannel, thesisTags, strongestSignal, signalConfidence, signalDate, momentumTrend, status, whyAppeared, caseId? }`.

**`Role`** (line 203): `ANALYST | ASSOCIATE | PARTNER`.

**`DecisionOption`** (line 205): `INVEST | DECLINE | MONITOR | REQUEST_EVIDENCE`.

**`CaseDecision`** (lines 207-214): `{ caseId, role, decision, overrideReason?, requestedEvidence?, recordedAt }`.

**`User`** (lines 216-220): `{ id, name, role }`.

**`Duration`** (lines 222-230): `{ totalSeconds, days, hours, minutes, seconds, isExpired, percentRemaining }`.

**`ThesisConfig`** (lines 232-240): `{ sector, stage, geography, checkSize, ownershipTarget, riskAppetite, exclusions }`.

**`TriggeredRule`** (lines 242-247): `{ rule: "ONE_HIGH_SPIKE"|"TWO_QUALIFYING_SPIKES", driver, score, confidence }`.

#### `src/agents/contracts.ts` (95 lines)
Key interfaces: `AgentContext`, `LeadAnalystOutput`, `DealCaptainOutput`, `MemoWriterOutput`, `ExtractionAdapter`. Plus `AGENT_NAMES` map and stub builders.

#### `src/types/backend.ts` (325 lines) — Backend DTOs
Mirrors the FastAPI backend response shapes (snake_case). Key types:
- `BackendThesis`, `BackendFounder`, `BackendScoreSnapshot`, `BackendDimensionBreakdown`, `BackendEvidenceItem`, `BackendOpportunity`, `BackendClaim`, `BackendPoolItem`, `BackendSourcingSchedule`, `BackendSourcingJob`, `BackendSourcingStatus`, `BackendEnrichmentRun`, `BackendEnrichmentStatus`.
- Request types: `CreateThesisRequest`, `UpdateThesisRequest`, `CreateFounderRequest`, `CreateSourcingScheduleRequest`, `UpdateSourcingScheduleRequest`.
- Response types: `BackendSeedResponse`, `UploadDeckResponse`, `QueuedResponse`, `ApprovedPoolItemResponse`, `ApiError`.
- Type guards: `isBackendOpportunity`, `isBackendPoolItem`, `isBackendFounder` (lines 297-325).

### 5.9 Components (`src/components/`)

| File | Lines | Purpose |
|------|-------|---------|
| `StatusBadge.tsx` | 42 | `CaseStatusBadge` (color per CaseStatus) + `ClaimStatusBadge` (color per ClaimStatus). Re-exports `statusLabel`. |
| `CaseStatusActions.tsx` | 136 | Status transition UI: "Move to decision queue" button (→ PARTNER_REVIEW), 4 decision buttons (INVEST/DECLINE/MONITOR/REQUEST_EVIDENCE, shown when `canDecide`), and a `<select>` of `allowedTransitions`. Calls `api.opportunities.updateStatus`. |
| `RoleSwitcher.tsx` | 35 | Three buttons (ANALYST/ASSOCIATE/PARTNER) shown in the sidebar. Calls `setRole`. |
| `DeckClaimTable.tsx` | 135 | Sortable table of `Claim[]` with expandable rows showing category, sources, trust components. Columns: Claim, Source (slide badge), Kind (FACT/PROJECTION/ASSUMPTION/OPINION color), Status (`ClaimStatusBadge`), Trust (`TrustBadge`). |
| `MemoView.tsx` | 62 | Renders a `CaseMemo`: company snapshot, hypotheses, SWOT grid (color-coded), problem/product, traction KPIs, contradictions, missing info, recommended next action, citations. |
| `DriverCard.tsx` | 71 | Renders a `DriverAssessment`: label, trend badge, score, confidence, rubric reason, supporting/opposing/missing claim IDs (clickable). |
| `AxisCard.tsx` | 36 | Renders an `AxisAssessment` with colored left border (FOUNDER=action, MARKET=uncertain, IDEA_MARKET=contradiction). |
| `DriverMiniBars.tsx` | 25 | Compact horizontal bars for each driver (color by score threshold). |
| `HistoryTimeline.tsx` | 35 | Vertical timeline of `EvidenceEvent[]` with previous → new value transitions. |
| `TrustBadge.tsx` | 15 | Color-coded "Trust X%" badge (>=80 verified, >=60 action, >=40 uncertain, else contradiction). |
| `TrendBadge.tsx` | 25 | Trend icon (↑↓→?) with color. |
| `TimeRemaining.tsx` | 37 | Live countdown bar (updates every 1s) using `calculateTimeRemaining`. Color shifts verified → uncertain → contradiction as time runs out. |
| `DemoBadge.tsx` | 9 | Small "Synthetic data" label badge. |

### 5.10 Config, hooks & cache

#### `src/config/thesis.ts` (83 lines)
- `DEFAULT_CHECK_SIZE = 100_000`, `DEFAULT_OWNERSHIP_TARGET = 0.05` (5%), `DEFAULT_DECISION_SLA_HOURS = 24`, `ONE_DECISION_PER_DAYS = 5`.
- `DEFAULT_THESIS`: sectors [AI, AI Infra, AI Software], stage [pre-seed], geography [US, Germany], risk MODERATE, exclusions [no D2C social, no crypto, no regulated medical, no prior institutional funding].
- `THESIS_DESCRIPTION`: default compound query string.
- `isWithinThesis(sector, stage, geography, thesis)`: returns `{eligible, matches, mismatches}`.
- `parseThesisQuery(query)`: keyword-based parser (NOT LLM) — detects AI/infrastructure, pre-seed, US/Germany, shipped/artifact/hackathon keywords. Explicitly transparent, not "model reasoning presented as inference."

#### `src/config/weights.ts` (47 lines)
- `DRIVER_WEIGHTS`: FOUNDER 0.35, MARKET 0.15, VISION_PRODUCT 0.10, TRACTION 0.10, DIFFERENTIATION 0.20, VALUATION_CAP 0.10.
- `DRIVER_LABELS`, `AXIS_LABELS`, `AXIS_DRIVERS` (IDEA_MARKET = VISION_PRODUCT + TRACTION + DIFFERENTIATION + VALUATION_CAP).
- `CLAIM_TRUST_WEIGHTS`: sourceReliability 0.30, extractionConfidence 0.20, corroboration 0.20, recency 0.15, evidenceSpecificity 0.15, contradictionPenalty 0.35.
- `SPIKE_RULES`: ONE_DRIVER_HIGH {minScore 85, minConfidence 0.70}, TWO_DRIVERS_QUALIFYING {minScore 75, minConfidence 0.65}.
- `ROUTING_CONFIDENCE_FLOOR = 0.45`.

#### `src/hooks/useAdaptivePolling.ts` (48 lines)
Polling hook that:
- Calls callback every `intervalMs`.
- **Pauses while tab is hidden** (`document.hidden` check in `tick`).
- **Fires immediately on visibility return** (visibilitychange listener).
- Re-schedules only when `intervalMs` changes (callback stored in ref).
- Pass `intervalMs <= 0` to pause. Used across Discovery, Cases, DealRoom, Decisions, Sourcing.

#### `src/api/cache.ts` (146 lines) — see §5.4.

### 5.11 Build/proxy/deploy configuration

#### `vite.config.ts` (25 lines)
- Plugins: `@vitejs/plugin-react`.
- Alias: `@` → `./src` (line 12).
- Dev server port: **3000** (line 16).
- **Proxy** (lines 17-23): `/api` → `http://localhost:8000` with `changeOrigin: true` and rewrite stripping `/api` prefix. So frontend `/api/v1/theses` → backend `http://localhost:8000/v1/theses`.
- When `VITE_API_URL` is set (production), the proxy is bypassed and `API_BASE` uses the env var directly.

#### `tailwind.config.js` (51 lines)
- Content: `index.html` + `src/**/*.{js,ts,jsx,tsx}`.
- **Custom color palette** (lines 6-22): `canvas` (#FDFBF7 cream), `manila` (#E6D9C3), `ink` (#1F1F1F), `action` (#B58A3E brass), `verified` (green), `uncertain` (brass), `contradiction` (red), `missing` (gray), `inferred` (purple), `highlight` (yellow). This is a "paper file folder" theme.
- **Fonts** (lines 23-27): `display` = Sora, `sans` = Work Sans, `mono` = IBM Plex Mono (loaded via Google Fonts in `index.html`).
- Custom shadows: `paper`, `paper-lg`, `stamp`.
- Custom rotations: 1, -1, 2, -2 degrees.
- Stamp animation keyframe (lines 42-47): scale + rotate fade-in.

#### `postcss.config.js` (6 lines)
- `tailwindcss` + `autoprefixer`.

#### `vercel.json` (12 lines)
- Framework: `vite`.
- Build command: `pnpm run build`.
- Output: `dist`.
- Install: `pnpm install`.
- **SPA rewrites** (lines 6-11): `/(.*)` → `/index.html` (client-side routing fallback).

#### `tsconfig.json` (26 lines)
- Target ES2020, `jsx: react-jsx`, `strict: true`, `noUnusedLocals/Parameters: true`, `noFallthroughCasesInSwitch: true`.
- `moduleResolution: bundler`, `allowImportingTsExtensions: true`, `isolatedModules: true`, `noEmit: true` (Vite handles bundling).
- Path alias: `@/*` → `src/*`.
- References `tsconfig.node.json`.

#### `.env.example`
- `VITE_API_URL=https://api.founder-os.up.railway.app` (Railway production backend).

#### `index.html` (19 lines)
- Title: "Seed Engine | Decision Workspace".
- Loads Google Fonts: IBM Plex Mono, Sora, Work Sans.
- Body class: `bg-canvas text-ink`.
- Favicon: `/favicon.svg` (in `public/`).

#### `src/index.css` (49 lines)
- Tailwind base/components/utilities.
- Base: body bg-canvas, headings use font-display.
- Component classes: `.panel`, `.label`, `.file-tab`, `.file-tab-active`, `.index-card`, `.stamp`, `.stamp-visible`, `.stamp-mark`, `.stamp-invest`.

### 5.12 Demo fixtures & tests

#### `src/data/demoCases.ts` (1061 lines)
Three fully-fleshed demo `InvestmentCase` fixtures:
- **caseA** (`case-cold-start`): Alex Rivera, Berlin, outbound hackathon+GitHub talent. Status ACTIVATION_READY. FOUNDER 88/0.75, TRACTION 78/0.68. No spike (only one high driver but it's a cold-start case).
- **caseB** (`case-founder-spike`): Sam Okonkwo / PromptBridge, strong founder (90/0.78), weak idea. Status ASSOCIATE_REVIEW. Triggers ONE_HIGH_SPIKE on FOUNDER. Has `skepticCounterCase`.
- **caseC** (`case-contradictory-traction`): Priya Nair / TractionAI, deck claims $200k ARR but form says no revenue. Status VALIDATION_HOLD. Has `validationHoldReason` and contradicted claims (c-2, c-3 contradict c-1).
- Also exports: `DEMO_PEOPLE`, `DEMO_COMPANIES`, `TALENT_SIGNALS`, `DECK_EXTRACTIONS` (3 sample deck extraction results keyed by case ID), helper getters `getDemoCase`, `getDemoDeck`, `getDemoPerson`, `getDemoCompany`.
- Helper factory functions: `source()`, `claim()`, `driver()`, `axis()`, `memo()` with trust score computation inline.

#### `src/data/validationSet.ts` (9 lines)
Exports `VALIDATION_SET = [caseA, caseB, caseC]` and `EXPECTED_ROUTES` mapping each case to its expected routed status.

#### `src/tests/` — Vitest suite (6 files)

| File | Tests |
|------|-------|
| `routing.test.ts` (133 lines) | Trust clamping, material contradiction → VALIDATION_HOLD, one/two spike routing, valuation cannot spike, missing traction → DILIGENCE, determinism, history immutability, cold-start stability, **adversarial injection test** (line 92: "Ignore previous instructions" in a claim does not alter routing). |
| `trust.test.ts` (18 lines) | Trust clamps 0-1, contradiction penalty reduces trust. |
| `cache.test.ts` (108 lines) | Cache miss/fresh/stale/expired behavior, in-flight dedup, error non-caching, prefix invalidation. |
| `coldStart.test.ts` (44 lines) | Prestige-only signal doesn't change routing, missing critical driver → DILIGENCE. |
| `history.test.ts` (29 lines) | `applyEvent` preserves original snapshot immutably. |
| `spikes.test.ts` (34 lines) | Detects founder spike in caseB, routes to ASSOCIATE_REVIEW, valuation cannot spike. |

---

## 6. End-to-end data flows

### Flow A — Cold-start founder → structured assessment → updated score

1. Investor clicks **Seed hackathon demo** (`POST /v1/seed`).
2. Backend creates a founder with cold-start snapshot: Score 50, Confidence 0%, all dimensions Unknown.
3. Investor clicks **Invite assessment**.
4. Founder completes structured simulations: Sales and objection handling, Prioritization under constraints, Belief updating, Scaling and leadership.
5. Responses sent to `POST /v1/founders/{id}/simulate-assessment` (mapped to `/v1/assessments/simulate`).
6. Backend converts responses into `EvidenceItem`s (type `STRUCTURED_SIMULATION`).
7. `calculate_founder_score()` recomputes score, confidence, coverage, evidence band, trend.
8. New `ScoreSnapshot` is stored; `latest_score_snapshot_id` updated on founder.
9. Investor views updated Founder Score + evidence ledger + dimension breakdown.

### Flow B — AI sourcing → pool approval → social research → opportunity screen

1. Investor sets a thesis (sectors, stages, geographies).
2. Investor clicks **Refresh pool** → `POST /v1/founders/pool/refresh`.
3. Backend queues a Celery task (`refresh_pool_task`).
4. `SourcingAgent` uses OpenAI + Tavily web search to discover founders.
5. New `FounderPoolItem`s are saved as `recommended`.
6. Investor approves a recommendation → `POST /v1/founders/pool/{item_id}/approve`.
7. Backend:
   - Creates a `Founder` record.
   - Creates initial cold-start `ScoreSnapshot`.
   - Creates an `Opportunity`.
   - Queues `research_social_background` Celery task (if LinkedIn/GitHub links exist).
8. `SocialAgent` researches LinkedIn/GitHub, returns summary + evidence.
9. Backend recalculates score and updates the opportunity.
10. Investor opens the opportunity screen to see three independent axes.

### Flow C — Deck upload → claim extraction → diligence workspace

1. Investor opens a case/opportunity (DealRoom page).
2. Investor uploads a deck (PDF/DOCX/TXT/MD) → `POST /v1/opportunities/{id}/deck`.
3. Backend base64-encodes the bytes and queues `extract_document`.
4. Worker extracts plain text (`document_extractor.extract_text`), runs `DocumentAgent`.
5. Agent returns `{profile, summary, claims, evidence}`.
6. Worker saves `Claim`s and `EvidenceItem`s, then recomputes founder score.
7. Investor sees extracted claims with `TrustStatus` and any contradictions.
8. Investor reviews the diligence workspace / memo.

### Flow D — Recurring sourcing schedule (background automation)

1. Investor creates a `SourcingSchedule` attached to a thesis → `POST /v1/sourcing/schedules`.
2. Celery beat checks every minute for due schedules (`dispatch_sourcing_jobs`).
3. **Enrichment gate**: if any founder is below 0.30 confidence AND unenriched, sourcing is skipped (`skipped_reason: enrichment_pending`).
4. When due and gate passes, beat creates a `SourcingJob` and queues `run_sourcing_job`.
5. Worker runs `SourcingAgent`, deduplicates against pool/existing founders.
6. Worker updates `SourcingJob` status/progress and saves new pool items.
7. Investor views `GET /v1/sourcing/jobs` history.

---

## 7. Key product rules enforced in code

These invariants live in `scoring.py`, `crud.py`, and the README:

- Missing dimensions are marked `Unknown`, never zero. (`scoring.py:41`)
- No single evidence item contributes more than 30% of a dimension's effective weight. (`scoring.py:60-67`)
- AI chat alone cannot create confidence above 0.60. (`scoring.py:91-97`)
- Confidence above 0.65 requires at least one non-chat artifact or independently verified source. (`scoring.py:100-106`)
- Confidence above 0.80 requires evidence from at least 3 independent source groups. (`scoring.py:108-110`)
- A contradiction lowers confidence before it lowers the capability score. (`scoring.py:81-85`)
- Low-confidence scores are shrunk toward the neutral prior (50). (`scoring.py:113`)
- University, employer, geography, name, gender, age, accent, and social following do not enter the scoring formula.
- Low confidence never triggers automatic rejection.
- Every score snapshot stores rubric, prompt, model, and source versions. (`scoring.py:213-215`)
- Frontend adversarial-injection test: "Ignore previous instructions" in a claim must NOT alter routing. (`routing.test.ts:92`)
- Manual overrides (`POST /v1/founders/pool/refresh`, `POST /v1/theses/{id}/source-now`) bypass the enrichment gate.
- Each founder is enriched exactly once (`enrichment_attempts` counter gates re-enrichment).

---

## 8. Cross-cutting mechanisms

### 8.1 LLM API serialization lock + circuit breaker (`research/api_lock.py`)
- A Redis distributed lock (`api_lock()` context manager) ensures only one OpenAI request is in flight at a time across all workers.
- Circuit breaker opens after `CIRCUIT_BREAKER_FAILURE_THRESHOLD` (3) consecutive retryable failures (429/5xx) for `CIRCUIT_BREAKER_COOLDOWN_SECONDS` (600s).
- Degrades gracefully when Redis unavailable (calls proceed without the lock).

### 8.2 Enrichment gating of sourcing
- Sourcing and enrichment are sequenced, not parallel.
- Automatic sourcing is paused while any founder is still awaiting its enrichment pass, and resumes only once every founder has been enriched once.
- The beat dispatcher `dispatch_sourcing_jobs` checks `count_founders_blocking_sourcing` on every tick. If any founder is below 0.30 confidence AND has `enrichment_attempts == 0`, sourcing is skipped.
- In-flight enrichments keep blocking until the chain completes and increments `enrichment_attempts`.
- Manual sourcing endpoints are NOT gated.

### 8.3 Enrich-once rule & 3-stage chain
- Each founder is enriched exactly once. The dispatcher only picks founders with `enrichment_attempts == 0` and below `ENRICHMENT_CONFIDENCE_THRESHOLD` (0.30). After one pass, the founder never re-enters the queue.
- Dispatcher runs every `ENRICHMENT_DISPATCH_INTERVAL_SECONDS` (180s), selects up to `ENRICHMENT_MAX_FOUNDERS_PER_RUN` (5), debounced by `ENRICHMENT_MIN_GAP_SECONDS` (600s).
- For each candidate, `POST /v1/founders/{id}/enrich` queues `enrich_founder_chain`:
  1. **Social** — re-runs LinkedIn/GitHub background research (skipped if no links).
  2. **Deep web** — OpenAI + Tavily research across `news`, `company_blog`, `twitter`; persists `ai_research_summary` + sources, adds evidence.
  3. **Estimate** — derives one evidence item per dimension from all available context and re-scores.
- Each stage records an `EnrichmentRun` row with `confidence_before`/`confidence_after`; `enrichment_attempts` is incremented when the chain finishes.

### 8.4 Cold-start recovery flow
Founder created → social research queued → social evidence + score → `estimate_founder_scores` fills remaining dimensions → if still cold, `POST /v1/founders/{id}/enrich` runs the full 3-stage chain (social → deep web → estimate). The frontend DealRoom auto-triggers enrichment on cold start (confidence ≤ 0) and polls through the 3 stages until confidence ≥ 0.30.

### 8.5 Ephemeral file uploads
Uploaded decks are base64-encoded, passed through Celery, text-extracted, sent to OpenAI for structured extraction, then discarded. Only extracted claims/evidence are persisted. `document_extractor.extract_text` caps text at `MAX_TEXT_CHARS = 200_000`.

### 8.6 Frontend SWR cache & adaptive polling
- All GETs go through a stale-while-revalidate cache (`api/cache.ts`) with per-endpoint TTLs and in-flight dedup. Mutations invalidate by URL prefix.
- `useAdaptivePolling` pauses on hidden tabs and fires immediately on return. Polling cadence adapts: 10s when active work, 30s when idle; 3s during enrichment/estimate; 5s when sourcing jobs active.

### 8.7 Dual data model on the frontend
The frontend has a rich local domain model (`src/domain/types.ts` — `InvestmentCase`, `Claim`, `DriverAssessment`, etc.) used by the engine and agents, AND a separate backend DTO model (`src/types/backend.ts` — snake_case `BackendOpportunity`, `BackendFounder`, etc.). Pages primarily render backend DTOs; the engine/agents/tests operate on the local domain model with demo fixtures. The two are not formally bridged by mappers — the demo cases are static fixtures.

### 8.8 No backend writes for decisions
`caseOverrides` and `decisions` in `appContext` are local-only (localStorage). Status updates go to the backend via `api.opportunities.updateStatus`, but decision records (INVEST/DECLINE/etc.) are only stored locally.

---

## 9. Deployment topology

- **Frontend → Vercel:** Deploy the `frontend/` directory. Set `VITE_API_URL` to the Railway backend URL. SPA rewrites in `vercel.json`.
- **Backend → Railway (3 services):**
  - **Web** (`railway.toml`): `alembic upgrade head && gunicorn main:app --workers 2 --timeout 120 -k uvicorn.workers.UvicornWorker`. Healthcheck at `/health`.
  - **Worker** (`railway.worker.toml`): `celery -A celery_app worker --concurrency=1 --prefetch-multiplier=1 --max-tasks-per-child=10 --max-memory-per-child=300000`.
  - **Beat** (`railway.beat.toml`): `celery -A celery_app beat -l info`.
- **PostgreSQL + Redis → Railway services.** Set `DATABASE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.
- The web start command runs `alembic upgrade head` before starting the server.

Local development prerequisites: PostgreSQL and Redis running locally. See README.md for the full `uvicorn` + `vite` setup sequence.

---

## 10. Glossary

- **EvidenceItem** — one observed signal about a founder (a work sample, simulation result, verified outcome, etc.). Has a dimension, rubric_level (0-4), source_trust, task_relevance, recency_factor, independence_group, and status. The atomic unit fed into the scoring engine.
- **ScoreSnapshot** — an immutable point-in-time record of a founder's score, evidence band, confidence, coverage, trend, and dimension breakdowns. Stored as JSONB.
- **OpportunityScreen** — a three-axis investment view (Founder, Market, Idea-vs-Market) attached to a founder, with `next_founder_action` and a pipeline status.
- **Claim** — a diligence statement extracted from a deck or surfaced in research, with `trust_status`, `confidence`, and optional `contradiction`.
- **FounderPoolItem** — an AI-sourced candidate from `SourcingAgent`, with `status` (recommended/approved/dismissed).
- **SourcingSchedule** — recurring config attached to a thesis (`interval_seconds`, `max_leads_per_run`, `sources`).
- **SourcingJob** — one sourcing run with `status`, `progress`, `leads_found/added/skipped`.
- **EnrichmentRun** — one stage of the enrichment chain (`social`/`deep_web`/`estimate`) with `confidence_before`/`confidence_after`.
- **Dimension** — one of 8 scoring axes (Execution, Technical, Agency, Learning, Resilience, Commercial, Collaboration, Prior Ventures). Each has a weight (`DIMENSION_WEIGHTS`) and a `DimensionBreakdown` per snapshot.
- **Rubric level** — 0-4 ordinal scale grading the strength of an `EvidenceItem` for its dimension. 0 = no signal, 4 = strongest.
- **Evidence band** — `[adjusted_score − 20×(1−confidence), adjusted_score + 20×(1−confidence)]` — the plausible range around the score, wider when confidence is low.
- **Coverage** — `min(1.0, total_effective_weight / 1.5)` — how much evidence weight is present relative to the `REQUIRED_EFFECTIVE_WEIGHT = 1.5`.
- **Independence group** — a label on an `EvidenceItem` indicating the source cluster; 3+ distinct groups are required for confidence > 0.80.
- **TrustStatus** — VERIFIED, SUPPORTED, FOUNDER_REPORTED, INFERRED, CONTRADICTED, MISSING, STALE.
- **CaseStatus** (frontend) — 11-value pipeline state (DISCOVERED, ACTIVATION_READY, AWAITING_APPLICATION, SCREENING, DILIGENCE, VALIDATION_HOLD, ASSOCIATE_REVIEW, PARTNER_REVIEW, INVESTED, DECLINED, MONITORING).
- **Spike** — a routing signal in the frontend engine: ONE_HIGH_SPIKE (driver score ≥85 + confidence ≥0.70) or TWO_QUALIFYING_SPIKES (2+ drivers score ≥75 + confidence ≥0.65). Valuation/cap can never spike.

---

## 11. Pointers for further detail

If more precision is needed, read these files in order:

1. `README.md` — product philosophy, hackathon demo flow, evaluation posture, AI config, key product rules.
2. `architecture.md` — diagram-oriented system guide (includes a Mermaid starter).
3. `backend/main.py` — full REST API surface (1511 lines).
4. `backend/models.py` — Pydantic schemas, enums, weight constants (352 lines).
5. `backend/db_models.py` — SQLAlchemy ORM tables (230 lines).
6. `backend/scoring.py` — deterministic scoring rules (226 lines).
7. `backend/crud.py` — all DB read/write functions (952 lines).
8. `backend/estimation.py` — AI estimation bridge.
9. `backend/research/*.py` — AI agent internals (`openai_client.py`, `sourcing_agent.py`, `social_agent.py`, `document_agent.py`, `founder_estimator.py`, `tavily_client.py`, `extractor.py`, `prompts.py`, `api_lock.py`, `http_utils.py`, `web_search.py`).
10. `backend/tasks/*.py` — async worker internals (`celery_app.py`, `social_research.py`, `founder_pool.py`, `document_extraction.py`, `estimation_task.py`, `enrichment_task.py`, `retry_utils.py`).
11. `backend/seed_data.py` — demo data.
12. `backend/.env.example` — canonical env var reference (91 lines).
13. `backend/tests/` — pytest suite (13 test files).
14. `frontend/src/App.tsx` — navigation and routes.
15. `frontend/src/api/client.ts` — frontend API calls.
16. `frontend/src/api/cache.ts` — SWR cache internals.
17. `frontend/src/store/appContext.tsx` — global state.
18. `frontend/src/engine/*.ts` — local decision engine (routing, trust, scoring, stateMachine, validationSummary).
19. `frontend/src/agents/*.ts` — specialist agent stubs.
20. `frontend/src/domain/types.ts` — frontend domain model.
21. `frontend/src/types/backend.ts` — backend DTOs (snake_case).
22. `frontend/src/data/demoCases.ts` — three demo `InvestmentCase` fixtures.
23. `frontend/src/config/weights.ts` — driver weights, trust weights, spike rules.
24. `frontend/src/tests/` — vitest suite (6 test files).
25. `frontend/vite.config.ts`, `frontend/tailwind.config.js`, `frontend/vercel.json`, `frontend/tsconfig.json` — build/proxy/deploy config.

---

*End of HANDOFF.md. This document is self-contained; for product philosophy and setup commands see `README.md`, and for visual architecture diagrams see `architecture.md`.*
