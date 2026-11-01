# FounderOS

**Evidence-first founder intelligence for early-stage investors.**

## Google sign-in and manual AI

The workspace accepts any verified Google account. Each identity is keyed by
Google's stable subject, never by an email allowlist or a shared access key.
The backend verifies both the Google identity and a server-side session before
serving records or accepting changes. The browser never stores an API key or
Google token. Sign-out revokes the session and clears cached workspace data.

AI runs only after an explicit manual request. Opening pages, importing or
saving founders, approving pool records, and uploading deck text do not start
research or estimation. The Run AI controls show progress and errors. Periodic
AI dispatch is disabled; legacy dispatch messages are inert. A worker processes
only explicitly authorized manual workflows. Do not run a beat scheduler.

### Vercel and Coolify

Vercel forwards same-origin `/api/*` requests to the protected Coolify backend.
The client uses `/api` directly, including for Google login, so the existing
Vercel address supports secure HTTP-only session cookies. `VITE_API_URL` no
longer selects the production backend. API and authentication responses must
remain private and uncached.

Configure these values only in the backend's private runtime settings:

- `FOUNDEROS_GOOGLE_CLIENT_ID` and `FOUNDEROS_GOOGLE_CLIENT_SECRET`
- `FOUNDEROS_FRONTEND_ORIGIN`: the canonical HTTPS frontend origin
- `FOUNDEROS_REDIRECT_URI`: that origin followed by `/api/auth/google/callback`
- `FOUNDEROS_WORKSPACE_MODE=private`: every verified Google identity receives
  a separate private workspace. Missing or invalid mode blocks access.

Register that exact redirect URI in the Google web client. Apply `alembic
upgrade head` after taking a database backup. Authentication migrations preserve
business records and never assign existing records to a new signup. Missing
configuration, schema or sign-in fails closed;
`/health` remains a minimal public health response. Existing business records
are preserved. Google sign-in uses only basic identity scopes.

Private workspaces use separate PostgreSQL schemas and restricted roles. Each
business transaction selects the verified user's role and schema; the held
legacy tables and other users' schemas remain inaccessible. Role and search-path
selection reset at transaction end. Worker grants and task status also belong
to one verified user. No client field selects a workspace or grants ownership.

New accounts always start empty. After the final source freeze and backup, an
operator can use `copy_legacy_to_verified_owner` with the independently verified
Google subject to copy existing records to their owner's empty workspace. This
is not an HTTP endpoint and never runs on ordinary signup. It preserves and
verifies all original rows, keeps the held copy, and refuses a second adoption
or overwriting a non-empty workspace.

Back up the complete database, including all private schemas and the auth
registry. A restore without cluster roles can reconstruct each exact restricted
role from its validated registry entry. Future business-schema changes must
migrate every workspace and advance `SCHEMA_REVISION`; mismatches fail closed.

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
├── backend/           # FastAPI + Pydantic + deterministic engine → Coolify
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
- **AI layer:** Explicit manual workflows use **OpenRouter** (`openai/gpt-5` by default) with **Tavily** for web search. The deterministic score calculation itself lives in Python code, not in an LLM.
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

- **Frontend on Vercel:** Deploy the `frontend/` directory with its `/api` rewrite. API requests use the frontend's own origin.
- **Backend on Coolify:** Deploy the `backend/` directory. The retained Railway configuration files document the original process commands.
  - Add a PostgreSQL database service and set `DATABASE_URL`.
  - Add a Redis service and set `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`.
  - The web start command runs `alembic upgrade head` before starting the server.
  - Run a worker service (`celery -A celery_app worker -l info`) for explicitly requested AI jobs. Keep Celery beat stopped.

## Deck uploads and manual sourcing

- **Deck upload:** `POST /v1/opportunities/{id}/deck` saves parsed text without a provider call. Optional **Run AI deck extraction** uses the separate `/deck/extract` endpoint to queue the requested extraction workflow.
- **Saved sourcing settings:** source configurations remain attached to theses. Legacy interval and enabled fields are retained for compatibility but cannot schedule AI work.
- **Manual sourcing:** `POST /v1/theses/{id}/source-now` triggers a one-time sourcing job immediately.
- **Job history:** `GET /v1/sourcing/jobs` returns the list of sourcing runs with counts of leads found, added, and skipped.

## Founder enrichment

Enrichment is optional and manual. Low confidence, a new founder, a page load,
an import, or a saved source configuration never starts it. The former sourcing
and enrichment dispatch tasks return without scheduling work. Old provider
messages without a fresh grant for their exact workflow, target and task ID are
also skipped. Status polling never starts or retries a workflow.

- **Manual sourcing:** `POST /v1/founders/pool/refresh` and `POST /v1/theses/{id}/source-now` require a signed-in Google session. Sourcing does not automatically start social research or estimation for each result.
- **3-stage chain:** for each candidate, `POST /v1/founders/{id}/enrich` queues `enrich_founder_chain`, which runs sequentially:
  1. **Social** — re-runs LinkedIn/GitHub background research (skipped if no links).
  2. **Deep web** — OpenRouter + Tavily research across `news`, `company_blog`, `twitter`; persists `ai_research_summary` + sources and adds evidence.
  3. **Estimate** — derives one evidence item per dimension from all available context and re-scores.
  Each stage records an `EnrichmentRun` row with `confidence_before`/`confidence_after`; `enrichment_attempts` is incremented when the chain finishes.
- **Observability:** `GET /v1/enrichment/runs?founder_id=…` lists recent runs; `GET /v1/enrichment/status` returns the count of founders below threshold and the last dispatch time.

## AI configuration

AI remains inactive until `OPENROUTER_API_KEY` is added to the backend and worker
runtime settings. Buttons show **AI setup pending** while setup is missing;
manual POST requests also fail before queueing or web search. Existing OpenAI
or UMANS credentials are never used as a fallback. `/v1/ai/config` reports local
readiness behind sign-in, without contacting a provider or revealing secrets.

Set provider values only in the backend and worker runtime settings:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/founderos
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=openai/gpt-5
OPENROUTER_TIMEOUT=60
OPENROUTER_MAX_TOKENS=8000

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

POOL_LOCK_TTL_SECONDS=300

# Used by the explicitly requested enrichment workflow, not a schedule.
ENRICHMENT_CONFIDENCE_THRESHOLD=0.30
```

The deterministic score engine does not call an LLM; only the evidence extraction, grading, and memo agents do.

### Avoiding API rate limits in production

1. **Use Tavily for web search**: Real-time search is handled by `TAVILY_API_KEY`, so model requests through OpenRouter handle reasoning.
2. **Serialize calls**: `API_LOCK_*` settings ensure only one model request is in flight at a time across sourcing, social research, and document extraction.
3. **Disable web search where it is not needed**: `OPENAI_ENABLE_WEB_SEARCH_SOCIAL=false` avoids redundant searches when LinkedIn/GitHub URLs are already provided.
4. **Use the circuit breaker**: After `CIRCUIT_BREAKER_FAILURE_THRESHOLD` consecutive retryable failures, new model calls are rejected for `CIRCUIT_BREAKER_COOLDOWN_SECONDS` to stop retry storms.
5. **Slow down retries**: Increase `MIN_RETRY_DELAY_SECONDS` and `*_RETRY_BASE_DELAY` if the provider keeps returning 429s.

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
