# FounderOS

**Evidence-first founder intelligence for early-stage investors.**

FounderOS is a versioned, evidence-backed estimate of demonstrated founder capabilities—not an AI personality score. It separates confidence, coverage, contradictions, and unknowns so investors can answer:

- What has this founder demonstrated?
- What evidence supports each conclusion?
- How confident are we?
- What remains unknown?
- What could change the conclusion?
- What is the next best diligence action?
- Should we advance, investigate, hold, or decline?

## What FounderOS is and is not

| It is | It is not |
|---|---|
| An evidence-weighted estimate of persistent founder capability | A prediction of startup success with certainty |
| A structured way to generate evidence for low-data founders | A personality or charisma test |
| Three independent opportunity axes (Founder, Market, Idea-vs-Market) | A single opaque number |
| A deterministic score engine fed by graded evidence | An LLM writing the final numeric score |
| Transparent about confidence, coverage, and contradictions | A system that treats missing data as negative evidence |
| Blind to pedigree proxies | A score that rewards university, employer, or network prestige |

## Core product principle

The system should never say:

> “AI believes this person is a strong founder.”

It should say:

> “The founder demonstrated strong belief updating in two structured scenarios, supported by these responses. They showed moderate commercial ability in one sales simulation, but no real customer reference is currently available. Leadership remains unknown. The current Founder Score is 68, with 52% confidence. The next highest-value action is a customer reference and a team-scaling review.”

## Repository structure

```
founder-evaluation-app/
├── frontend/          # React + Vite + TypeScript + Tailwind → Vercel
│   ├── src/
│   ├── vercel.json
│   └── package.json
├── backend/           # FastAPI + Pydantic + deterministic engine → Railway
│   ├── main.py
│   ├── scoring.py
│   ├── models.py
│   ├── database.py
│   ├── db_models.py
│   ├── crud.py
│   ├── alembic/
│   ├── tests/
│   ├── railway.toml
│   └── Procfile
├── .gitignore
└── README.md
```

## Architecture overview

- **Frontend:** Desktop-first investor interface and mobile-friendly founder assessment workspace.
- **Backend:** FastAPI application that owns data models, evidence normalization, deterministic scoring, and workflow endpoints.
- **AI layer:** Agents for ingestion, gap planning, assessment conduction, independent grading, diligence validation, and memo generation. Model calls are routed through environment variables and use **OpenAI** (`gpt-5`) with **Tavily** for real-time web search. The deterministic score calculation itself lives in Python code, not in an LLM.
- **Memory layer:** Founder Score persists across ventures; opportunity axes (Founder-Market Fit, Team Completeness, Market, Idea-vs-Market) are contextual.

## Founder Score outputs

Every score is presented together, never alone:

```
Founder Score: 68
Evidence band: 56–77
Confidence: 52%
Evidence coverage: 44%
Trend: +6 since previous assessment
```

Correct interpretation: “There are promising signals, but additional evidence is required.” It is **not** “this founder has a 68% chance of succeeding.”

## The three opportunity axes

The opportunity screen keeps these independent so a strong founder in a weak market is still visible:

1. **Founder axis:** Persistent Founder Score, Founder-Market Fit, Team Completeness
2. **Market axis:** Bullish / neutral / bear posture, timing, buyer urgency, competition
3. **Idea-vs-Market axis:** Problem-solution coherence, distribution feasibility, defensibility, pivot potential

No overall average is computed to hide disagreement.

## Local development

Prerequisites: **PostgreSQL** and **Redis** running locally.

```bash
# 1. Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set DATABASE_URL and Redis URLs, then run migrations
export DATABASE_URL="postgresql://user:password@localhost:5432/founderos"
export CELERY_BROKER_URL="redis://localhost:6379/0"
export CELERY_RESULT_BACKEND="redis://localhost:6379/0"
alembic upgrade head

uvicorn main:app --reload --port 8000

# 2. Frontend
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`.

Run backend tests (uses a dedicated `founderos_test` PostgreSQL database):

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

## Deployment

- **Frontend on Vercel:** Deploy the `frontend/` directory. Set `VITE_API_URL` to your Railway backend URL.
- **Backend on Railway:** Deploy the `backend/` directory. Configuration is in `backend/railway.toml` and `backend/Procfile`.
  - Add a PostgreSQL database service and set `DATABASE_URL`.
  - Add a Redis service and set `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`.
  - The web start command runs `alembic upgrade head` before starting the server.
  - Run a Celery beat service (`celery -A celery_app beat -l info`) and a worker service (`celery -A celery_app worker -l info`) for background tasks.

## Deck upload and sourcing automation

- **Deck upload:** `POST /v1/opportunities/{id}/deck` accepts a PDF, DOCX, TXT, or MD file. The file is **not stored**; its text is extracted and sent to the AI model. Extracted claims are saved to the opportunity, and extracted evidence is saved to the founder's score ledger.
- **Sourcing schedules:** `POST /v1/sourcing/schedules` attaches a repeating interval to a thesis. The Celery beat dispatcher checks every minute and queues a sourcing job for any due schedule.
- **Manual sourcing:** `POST /v1/theses/{id}/source-now` triggers a one-time sourcing job immediately.
- **Job history:** `GET /v1/sourcing/jobs` returns the list of sourcing runs with counts of leads found, added, and skipped.

## Founder enrichment

The sourcing loop finds new leads, but a separate recurring pipeline deepens data on each existing founder so confidence does not stay at 0. **Sourcing and enrichment are sequenced, not parallel:** automatic sourcing is paused while any founder is still awaiting its enrichment pass, and resumes only once every founder has been enriched once.

- **Enrich-once rule:** each founder is enriched exactly once. The dispatcher only picks founders that have never completed an enrichment pass (`enrichment_attempts == 0`) and are below `ENRICHMENT_CONFIDENCE_THRESHOLD` (default 0.30). After one pass, the founder never re-enters the queue.
- **Sourcing gate:** the automatic beat dispatcher (`dispatch_sourcing_jobs`) checks `count_founders_blocking_sourcing` on every tick. If any founder is below 0.30 confidence AND has not yet been enriched once, sourcing is skipped for that tick (`skipped_reason: enrichment_pending`). Sourcing resumes once the queue is drained. In-flight enrichments keep blocking until the chain completes and increments `enrichment_attempts`.
- **Manual overrides:** `POST /v1/founders/pool/refresh` and `POST /v1/theses/{id}/source-now` are explicit user actions and are NOT gated — you can always force a sourcing pass manually.
- **Dispatcher:** Celery beat runs `dispatch_enrichment_jobs` every `ENRICHMENT_DISPATCH_INTERVAL_SECONDS` (default 180s). It selects up to `ENRICHMENT_MAX_FOUNDERS_PER_RUN` (default 5) founders per tick, debounced by `ENRICHMENT_MIN_GAP_SECONDS` (default 600s) so an in-flight founder isn't re-queued.
- **3-stage chain:** for each candidate, `POST /v1/founders/{id}/enrich` queues `enrich_founder_chain`, which runs sequentially:
  1. **Social** — re-runs LinkedIn/GitHub background research (skipped if no links).
  2. **Deep web** — OpenAI + Tavily research across `news`, `company_blog`, `twitter`; persists `ai_research_summary` + sources and adds evidence.
  3. **Estimate** — derives one evidence item per dimension from all available context and re-scores.
  Each stage records an `EnrichmentRun` row with `confidence_before`/`confidence_after`; `enrichment_attempts` is incremented when the chain finishes.
- **Observability:** `GET /v1/enrichment/runs?founder_id=…` lists recent runs; `GET /v1/enrichment/status` returns the count of founders below threshold and the last dispatch time.

## AI configuration

Set environment variables on Railway:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/founderos
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Use a Wallet key for deployed/production backends. Personal Plan keys are
# throttled and deprioritized for unattended automation.
UMANS_API_KEY=sk-your-umans-api-key

OPENAI_API_KEY=sk-your-openai-api-key
# gpt-4o is deprecated; use gpt-5.
OPENAI_MODEL=gpt-5
OPENAI_SOURCING_MODEL=gpt-5
OPENAI_SOCIAL_MODEL=gpt-5
OPENAI_DOCUMENT_MODEL=gpt-5

# Tavily configuration
TAVILY_API_KEY=tvly-your-tavily-api-key
TAVILY_SEARCH_DEPTH=basic
TAVILY_MAX_RESULTS=5

# Per-agent web search toggles. Sourcing keeps web search for real-time
# discovery; social research defaults to false because it already receives URLs.
OPENAI_ENABLE_WEB_SEARCH_SOURCING=true
OPENAI_ENABLE_WEB_SEARCH_SOCIAL=false
OPENAI_ENABLE_WEB_SEARCH_RESEARCH=true

# Global serialization lock: only one LLM request in flight at a time.
API_LOCK_DISABLED=false
API_LOCK_TTL_SECONDS=120

# Circuit breaker pauses all LLM calls after repeated 429/5xx errors.
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
CIRCUIT_BREAKER_COOLDOWN_SECONDS=600

SOURCING_DISPATCH_INTERVAL_SECONDS=60
POOL_LOCK_TTL_SECONDS=300

# Enrichment pipeline: a recurring Celery beat task gathers more data around
# each founder (social research → deep web research → AI estimate) so founders
# do not sit at 0% confidence. Only founders below the threshold are enriched,
# debounced per founder.
ENRICHMENT_DISPATCH_INTERVAL_SECONDS=180
ENRICHMENT_CONFIDENCE_THRESHOLD=0.30
ENRICHMENT_MIN_GAP_SECONDS=600
ENRICHMENT_MAX_FOUNDERS_PER_RUN=5
```

The deterministic score engine does not call an LLM; only the evidence extraction, grading, and memo agents do.

### Avoiding API rate limits in production

1. **Use Tavily for web search**: Real-time search is handled by `TAVILY_API_KEY`, so OpenAI only does reasoning. This removes provider-specific web-search overload errors.
2. **Serialize calls**: `API_LOCK_*` settings ensure only one OpenAI request is in flight at a time across sourcing, social research, and document extraction.
3. **Disable web search where it is not needed**: `OPENAI_ENABLE_WEB_SEARCH_SOCIAL=false` avoids redundant searches when LinkedIn/GitHub URLs are already provided.
4. **Use the circuit breaker**: After `CIRCUIT_BREAKER_FAILURE_THRESHOLD` consecutive retryable failures, all new OpenAI calls are rejected for `CIRCUIT_BREAKER_COOLDOWN_SECONDS` to stop retry storms.
5. **Slow down retries**: Increase `MIN_RETRY_DELAY_SECONDS` and `*_RETRY_BASE_DELAY` if OpenAI keeps returning 429s.

## Hackathon demonstrator flow

1. Open the investor dashboard.
2. Click **Seed hackathon demo**.
3. See a cold-start founder profile: **Founder Score 50**, **0% confidence**, all dimensions **Unknown**.
4. Click **Invite assessment** and complete the structured simulations:
   - Sales and objection handling
   - Prioritization under constraints
   - Belief updating
   - Scaling and leadership
5. Review the updated Founder Score and explore the evidence ledger.
6. Open the opportunity screen to see the three independent axes.
7. View diligence claims with trust status and contradictions.

## Key product rules enforced in code

- Missing dimensions are marked `Unknown`, never zero.
- No single evidence item contributes more than 30% of a dimension’s effective weight.
- AI chat alone cannot create confidence above 0.60.
- Confidence above 0.65 requires at least one non-chat artifact or independently verified source.
- Confidence above 0.80 requires evidence from at least three independent source groups.
- A contradiction lowers confidence before it lowers the capability score.
- Low-confidence scores are shrunk toward the neutral prior (50).
- University, employer, geography, name, gender, age, accent, and social following do not enter the scoring formula.
- Low confidence never triggers automatic rejection.
- Every score snapshot stores rubric, prompt, model, and source versions.

## Evaluation posture

FounderOS is built to be evaluated as a measurement system:

- Synthetic profiles with seeded contradictions and cold-start cases
- Human rubric agreement studies
- Counterfactual identity tests (name, gender-coded name, geography, university)
- Test-retest reliability with equivalent scenario variants
- Adversarial tests for prompt injection, memorized jargon, and unsupported claims

## Delivery roadmap

1. **Measurement foundation** — rubrics, evidence taxonomy, confidence rules, scoring engine, synthetic test sets
2. **Memory and ingestion** — founder records, document upload, claims, evidence items, deduplication, score snapshots
3. **Cold-start assessment** — Gap Planner, conductor, two graders, validator, human review, score update
4. **Investor experience** — dashboard, profile, score explorer, three-axis screen, decision queue
5. **Diligence and memo** — contradiction workspace, per-claim Trust Score, evidence-backed memo
6. **Evaluation and hardening** — Evaluation Lab, model comparison, bias tests, observability, tenant isolation

## License

MIT
