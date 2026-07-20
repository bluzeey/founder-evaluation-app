# FounderOS — AI coding-agent implementation brief

**Task type:** Repository update specification  
**Audience:** Coding agent with access to the complete FounderOS repository  
**Primary inputs:** `67b8043a-87d4-474e-9f50-29600b47273b.pdf`, `HANDOFF(1).md`, and `founderos_founder_import_150.csv`  
**Target product viewpoint:** Associate-only  
**Screening version to stamp:** `associate_screen_v1`

---

## 0. Operating instruction for the coding agent

Implement the changes in this document in the existing FounderOS repository. First inspect the current files named below, then make the smallest coherent end-to-end change spanning database, API, frontend, migrations, and tests. Do not replace the existing deterministic evidence engine or delete historical data. Introduce the new four-parameter associate screen as a distinct, versioned model and make it the primary sourcing/discovery experience.

Before editing, run the existing backend and frontend test suites to establish a baseline. After editing, run migrations, type checking, frontend tests, backend tests, and a production build. Report every changed file, migration, test result, and any unresolved issue.

Do not invent product rules beyond this brief. Do not use university prestige as a scoring feature. Do not calculate or display a weighted or averaged final score.

---

## 1. Source-of-truth product rules

The PDF describes the original pipeline and its source channels, scoring categories, and associate-call threshold. The later product direction overrides the original weighted scoring model.

### 1.1 Final screening parameters

Use exactly these four independent 0–100 parameters:

1. `founder_score`
2. `vision_product_score`
3. `differentiation_score`
4. `traction_score`

The four values must remain visibly independent. **Never average, sum, normalize, or weight them into a final score.** Do not create a `final_score`, `overall_score`, or weighted queue score for this workflow.

`founder_score` is the renamed product-facing equivalent of Founder Fit. It is not the same object as the legacy eight-dimension evidence-weighted `ScoreSnapshot.founder_score`; both may coexist, but their provenance must be explicit.

### 1.2 Deterministic recommendation rule

A founder appears in the Recommended list and is eligible for an Associate Call when:

```text
ANY one of the four scores is strictly greater than 75
OR
AT LEAST two of the four scores are strictly greater than 50
```

Exact boundary behavior is required:

```python
scores = [
    founder_score,
    vision_product_score,
    differentiation_score,
    traction_score,
]

one_high = any(score > 75 for score in scores)
two_above_50 = sum(score > 50 for score in scores) >= 2
recommended = one_high or two_above_50
```

Use strict `>` comparisons. A score of exactly `75` does not satisfy the first rule. A score of exactly `50` does not count toward the second rule. Confidence may be shown and used only as a secondary sort/tie-break signal; it must not alter recommendation eligibility.

Persist the trigger as one of:

- `ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50`
- `ONE_SCORE_GT_75`
- `TWO_SCORES_GT_50`
- `NOT_RECOMMENDED`
- `INCOMPLETE_EVALUATION`

The backend is the source of truth. Recompute the flag and trigger on every create/update/import. Never trust an imported Boolean without recomputing it.

### 1.3 Associate-only product viewpoint

Remove the UI mode switch among Analyst, Associate, and Partner. The signed-in workspace should always render from an Associate viewpoint.

This does **not** mean deleting pipeline stages. Keep workflow states such as Associate DD, Partner Review, Invested, Declined, and Monitoring where the current state machine needs them. From the associate UI, “Move to Partner Review” remains a valid handoff action. Remove role-switching controls and role-conditioned presentation, not necessarily all historic role types in one risky migration.

### 1.4 List structure

The left sidebar must contain both:

- **Discovery** — all imported/discovered founders with completed or incomplete associate screens.
- **Recommended** — only founders for whom the backend-computed rule returns `recommended=true`.

Both pages should share one table/list implementation so filters, score display, pagination, and row behavior cannot drift.

### 1.5 Required filtering

At minimum, support:

- City
- Recommended status
- Institution/program
- School/lab
- Source type
- Sector
- Funding status
- Cohort year
- Free-text search across founder, project, role, summary, and tags

City must be a normalized server-side filter. Because imported city values may represent an event or program rather than residence, surface `city_basis` and `city_confidence` in the UI, preferably as a tooltip or secondary label.

---

## 2. Architectural decision: preserve legacy scoring, add a new screen

The current backend has an eight-dimension deterministic evidence engine and immutable `ScoreSnapshot` records. Preserve that system for evidence history, enrichment, and backward compatibility. Do not mutate its dimension enum into the new four fields and do not silently reinterpret its `founder_score`.

Add a separate, versioned **Founder Screening Profile** for the new associate workflow.

### Why this separation is required

- The legacy score is calculated from eight weighted evidence dimensions and confidence shrinkage.
- The new workflow contains four direct screening parameters and explicitly forbids a weighted final score.
- Mixing them would make existing snapshots historically incorrect and make imported rows impossible to interpret.
- A separate model allows later human review or automated re-evaluation without destroying source evidence.

The Discovery and Recommended pages should read the new screening profile first. Existing founders without one must remain accessible and display `Not evaluated` rather than receiving fabricated values.

---

## 3. Backend implementation

Relevant current files include:

- `backend/models.py`
- `backend/db_models.py`
- `backend/crud.py`
- `backend/main.py`
- `backend/scoring.py`
- `backend/tasks/founder_pool.py`
- `backend/tasks/enrichment_task.py`
- `backend/seed_data.py`
- `backend/alembic/versions/`
- `backend/tests/`

Names may be adapted to repository conventions, but preserve the behavior specified below.

### 3.1 Add the domain model

In `backend/models.py`, add typed models/enums similar to the following.

```python
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl
from typing import Any


class ScreeningFundingStatus(str, Enum):
    NO_PUBLIC_INSTITUTIONAL_FUNDING_FOUND = "no_public_institutional_funding_found"
    NON_DILUTIVE_GRANT_OR_PRIZE_ONLY = "non_dilutive_grant_or_prize_only"
    PUBLIC_EQUITY_FUNDING_FOUND = "public_equity_funding_found"
    UNKNOWN = "unknown"


class RecommendationTrigger(str, Enum):
    ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50 = "ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50"
    ONE_SCORE_GT_75 = "ONE_SCORE_GT_75"
    TWO_SCORES_GT_50 = "TWO_SCORES_GT_50"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"
    INCOMPLETE_EVALUATION = "INCOMPLETE_EVALUATION"


class FounderScreeningProfile(BaseModel):
    id: str
    founder_id: str
    external_record_id: str | None = None

    project_name: str | None = None
    project_summary: str | None = None
    founder_role: str | None = None
    sector: str | None = None
    stage: str | None = None

    source_type: str | None = None
    institution_or_program: str | None = None
    school_or_lab: str | None = None
    cohort_year: str | None = None
    institution_affiliation_basis: str | None = None

    city: str | None = None
    country: str | None = None
    city_basis: str | None = None
    city_confidence: float | None = Field(default=None, ge=0, le=1)
    target_market_geography: str | None = None

    website_url: str | None = None
    primary_source_url: str | None = None
    source_locator: str | None = None
    source_date: str | None = None

    funding_status: ScreeningFundingStatus = ScreeningFundingStatus.UNKNOWN
    funding_check_as_of: str | None = None
    funding_check_confidence: float | None = Field(default=None, ge=0, le=1)
    funding_notes: str | None = None

    founder_score: int | None = Field(default=None, ge=0, le=100)
    founder_score_rationale: str | None = None
    vision_product_score: int | None = Field(default=None, ge=0, le=100)
    vision_product_rationale: str | None = None
    differentiation_score: int | None = Field(default=None, ge=0, le=100)
    differentiation_rationale: str | None = None
    traction_score: int | None = Field(default=None, ge=0, le=100)
    traction_rationale: str | None = None

    evidence_confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_coverage: float | None = Field(default=None, ge=0, le=1)
    individual_attribution_confidence: float | None = Field(default=None, ge=0, le=1)
    evaluation_scope: str | None = None

    key_evidence: list[str] = []
    counter_evidence: list[str] = []
    unknowns: list[str] = []
    next_diligence_action: str | None = None

    recommended: bool = False
    recommendation_trigger: RecommendationTrigger = RecommendationTrigger.INCOMPLETE_EVALUATION
    recommended_reason: str | None = None

    evaluation_version: str = "associate_screen_v1"
    pedigree_used_in_scoring: bool = False
    import_status: str | None = None
    research_priority: str | None = None
    tags: list[str] = []

    created_at: str
    updated_at: str
```

Use safe Pydantic defaults (`Field(default_factory=list)`) in the actual implementation. The abbreviated example above communicates shape, not a reason to use mutable defaults.

Also define:

- `CreateFounderScreeningProfileRequest`
- `UpdateFounderScreeningProfileRequest`
- `FounderDiscoveryItem` combining a `Founder` and optional profile
- `FounderDiscoveryPage` containing `items`, `total`, `limit`, `offset`, and available filter facets
- `CsvImportRowError`
- `CsvImportResult`

### 3.2 Add the SQLAlchemy table

In `backend/db_models.py`, add `FounderScreeningProfile` with a one-to-one or one-to-many versioned relationship to `Founder`. Prefer one current profile per `(founder_id, evaluation_version)` and preserve timestamps.

Minimum columns:

- `id` primary key
- `founder_id` indexed FK to `founders.id`, `ON DELETE CASCADE`
- `external_record_id`, unique where non-null
- all discovery metadata needed by the CSV
- four nullable integer score columns with database checks from 0 to 100
- four rationale text columns
- confidence/coverage columns with checks from 0 to 1
- JSONB arrays for `key_evidence`, `counter_evidence`, `unknowns`, and `tags`
- `recommended` indexed Boolean
- `recommendation_trigger` indexed string
- `evaluation_version` indexed string
- `pedigree_used_in_scoring` Boolean default false
- `created_at`, `updated_at`

Recommended indexes:

```text
(founder_id, evaluation_version) UNIQUE
external_record_id UNIQUE WHERE external_record_id IS NOT NULL
(recommended, city)
(recommended, institution_or_program)
(source_type)
(sector)
(funding_status)
(cohort_year)
```

Normalize/filter using separate normalized columns only where required for stable lookup, for example `city_normalized`, `linkedin_url_normalized`, and `project_name_normalized`. Do not overwrite the human-readable source values.

### 3.3 Add an Alembic migration

Create a migration after the current head that:

1. Creates `founder_screening_profiles` and constraints/indexes.
2. Adds `external_record_id` or equivalent stable import identity only in the new table, not necessarily to `founders`.
3. Adds an enrichment/import control described in §3.9 if implemented as a founder column.
4. Does not rewrite or delete legacy `score_snapshots`.
5. Has a valid downgrade that drops only newly introduced schema objects.

Do not backfill guessed scores. Existing founders may have a null profile.

### 3.4 Add a dedicated deterministic screening module

Create `backend/screening.py` rather than overloading `backend/scoring.py`.

Required functions:

```python
def evaluate_recommendation(
    founder_score: int | None,
    vision_product_score: int | None,
    differentiation_score: int | None,
    traction_score: int | None,
) -> tuple[bool, RecommendationTrigger, str]:
    ...


def validate_screening_scores(...) -> None:
    ...


def screening_sort_key(profile: FounderScreeningProfile) -> tuple:
    ...
```

Behavior:

- Any missing score produces `recommended=False`, trigger `INCOMPLETE_EVALUATION`.
- Reject Booleans masquerading as integers.
- Reject non-finite numbers, out-of-range values, and decimals unless the product explicitly chooses to round; preferred behavior is integer-only validation.
- Recompute recommendation on every write.
- Keep the function pure and free of database or LLM calls.

### 3.5 Add CRUD operations

In `backend/crud.py`, add:

- `create_or_update_screening_profile`
- `get_screening_profile(founder_id, evaluation_version="associate_screen_v1")`
- `get_screening_profile_by_external_record_id`
- `list_founder_discovery_items(...)`
- `count_founder_discovery_items(...)`
- `screening_profile_to_pydantic`
- `bulk_upsert_founders_and_profiles(...)`

The list query must perform filtering and pagination in SQL rather than loading all founders and filtering in Python.

Deduplication/upsert priority for the provided CSV:

1. Exact `external_record_id` (`record_id`).
2. Normalized LinkedIn URL when present.
3. Normalized tuple `(founder_name, project_name, cohort_year)`.

Do not merge two different people solely because they share a venture or school. Return a row-level conflict when candidate matches disagree.

### 3.6 Add API endpoints

In `backend/main.py`, add or adapt the following:

#### Discovery list

```http
GET /v1/founders/discovery
```

Query parameters:

```text
q
recommended
city
country
institution_or_program
school_or_lab
source_type
sector
funding_status
cohort_year
limit (default 50, max 200)
offset (default 0)
sort
```

Response: `FounderDiscoveryPage`.

The endpoint should include profile fields and basic founder fields in one response to avoid the current client-side join of every founder with every opportunity.

#### Recommended list

Either implement:

```http
GET /v1/founders/recommended
```

as a thin call to the discovery query with `recommended=true`, or use only:

```http
GET /v1/founders/discovery?recommended=true
```

Prefer the second internally, even if a convenience route is exposed.

#### Profile detail/update

```http
GET /v1/founders/{founder_id}/screening-profile
PUT /v1/founders/{founder_id}/screening-profile
```

The PUT endpoint must recompute `recommended`, `recommendation_trigger`, and `recommended_reason` server-side.

#### CSV import

```http
POST /v1/founders/import-csv?dry_run=true
Content-Type: multipart/form-data
```

Support `dry_run=true` by default. A non-dry run must be explicit.

Response shape:

```json
{
  "dry_run": true,
  "file_name": "founderos_founder_import_150.csv",
  "rows_received": 150,
  "rows_valid": 150,
  "rows_invalid": 0,
  "founders_to_create": 150,
  "founders_to_update": 0,
  "profiles_to_create": 150,
  "profiles_to_update": 0,
  "rows_skipped": 0,
  "errors": [],
  "warnings": [],
  "import_id": null
}
```

For a committed import, return created/updated IDs and an `import_id` for auditability.

### 3.7 CSV import contract

The supplied CSV contains 51 columns. The importer may ignore unknown future columns but must require and validate the fields needed for a usable row.

Required columns:

```text
record_id
founder_name
project_name
primary_source_url
funding_status
founder_score
founder_score_rationale
vision_product_score
vision_product_rationale
differentiation_score
differentiation_rationale
traction_score
traction_rationale
evaluation_version
```

Recommended optional columns are all remaining columns in `founderos_founder_import_150.csv`.

Parsing rules:

- Decode UTF-8 with or without BOM.
- Trim whitespace without changing internal punctuation.
- Parse `key_evidence`, `counter_evidence`, and `unknowns` as semicolon-delimited lists; parse `tags` as a pipe-delimited (`|`) list. Trim items and discard empty entries. Also accept JSON arrays for forward compatibility. Do not split rationale or notes fields.
- Parse Boolean text case-insensitively, but ignore the imported recommendation Boolean for eligibility and recompute it.
- Validate URLs syntactically but do not reject a row merely because LinkedIn/GitHub is absent.
- Keep `funding_notes`, caveats, and attribution scope; do not collapse them into one summary.
- Reject rows with an empty founder name, project name, source URL, required rationale, or invalid score.
- Reject duplicate `record_id` values within the same upload.
- Limit file size and row count, for example 10 MB and 5,000 rows.
- Execute committed imports in a transaction with chunked inserts. On row-level validation failures, do not partially commit unless the endpoint explicitly supports a reviewed partial-import mode.
- Prevent spreadsheet formula injection on any future CSV export by prefixing cells beginning with `=`, `+`, `-`, or `@` where necessary.
- Store a checksum of the uploaded file and reject accidental duplicate committed imports unless `force=true` is supplied.

### 3.8 Funding semantics

Treat `funding_status` as a research classification, not a fact that can never change.

- `no_public_institutional_funding_found` means the public screen did not locate disclosed institutional funding as of `funding_check_as_of`.
- `non_dilutive_grant_or_prize_only` allows grants, prizes, cloud credits, and similar support while still indicating no disclosed institutional equity round was located.
- Never render either status as “definitely unfunded.”
- Show the as-of date, confidence, and notes on detail screens.
- Profiles with `public_equity_funding_found` may remain in Discovery but should be excluded from Recommended by a configurable sourcing-policy filter if that is part of the active thesis. Do not silently alter the score-based recommendation rule; funding eligibility and score recommendation are separate fields.

### 3.9 Prevent import-triggered enrichment storms

The current founder creation path queues social research and the current automatic sourcing flow can be blocked by low-confidence, never-enriched founders. Importing 150 rows through the ordinary `POST /v1/founders` path would therefore create an avoidable job burst and may block recurring sourcing.

Implement one of the following, with option A preferred:

**A. Add `enrichment_policy`** to founders or profiles:

```text
AUTO    — current behavior
MANUAL  — do not enqueue automatically; a user may run enrichment later
NONE    — never enrich automatically
```

Rows imported from this CSV should default to `MANUAL`.

Update:

- founder creation service
- social research queueing
- `count_founders_blocking_sourcing`
- `list_founders_below_confidence`
- enrichment dispatcher

so `MANUAL` and `NONE` imports do not block automatic sourcing.

**B. Alternative:** treat a complete imported associate profile as satisfying the sourcing gate while keeping legacy confidence separate. If choosing this approach, document it and test it carefully.

Do not queue 150 Celery jobs during import.

### 3.10 Recommended ordering without a final score

The Recommended page needs deterministic ordering, but it must not invent an aggregate score. Use lexicographic sorting:

1. Trigger class:
   - both one-score and two-score rules satisfied
   - one-score rule only
   - two-score rule only
2. Highest of the four scores, descending
3. Number of scores strictly above 50, descending
4. Evidence confidence, descending, null last
5. Evidence coverage, descending, null last
6. Founder name, ascending

This is a rank/order function, not a displayed score. Expose each sort component or document it; do not label it “final score.”

### 3.11 Audit/version behavior

Every profile must retain:

- `evaluation_version`
- created/updated timestamps
- who or what produced the evaluation when available
- original imported recommendation value for audit only, if retained
- computed recommendation and trigger
- source URL and source locator
- funding check date

For later edits, preferably create a `founder_screening_profile_history` table or append an immutable version rather than overwriting silently. If that is too large for this implementation, at minimum preserve `updated_at`, editor identity, and an audit event.

---

## 4. Frontend implementation

Relevant current files include:

- `frontend/src/App.tsx`
- `frontend/src/pages/Discovery.tsx`
- `frontend/src/pages/DealRoom.tsx`
- `frontend/src/pages/Decisions.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/cache.ts`
- `frontend/src/store/appContext.tsx`
- `frontend/src/components/RoleSwitcher.tsx`
- `frontend/src/components/CaseStatusActions.tsx`
- `frontend/src/engine/routing.ts`
- `frontend/src/engine/scoring.ts`
- `frontend/src/domain/types.ts`
- `frontend/src/types/backend.ts`
- `frontend/src/tests/`

### 4.1 Sidebar and routes

Update `frontend/src/App.tsx`:

```text
/discovery    Discovery
/recommended  Recommended
```

Recommended should appear immediately after Discovery. Use an appropriate existing `lucide-react` icon such as `Sparkles`, `Star`, or `BadgeCheck` without adding a new UI library.

Keep other navigation items unless product requirements explicitly remove them. The essential change is to make the two founder lists first-class sidebar destinations.

Add:

```tsx
<Route path="/recommended" element={<Recommended />} />
```

### 4.2 Remove role switching

- Remove `<RoleSwitcher />` from `App.tsx`.
- Remove role buttons from the rendered product.
- In `appContext.tsx`, make the current user Associate by default and remove `setRole` from the public context API.
- Migrate the localStorage key, for example from `vc-brain-demo-state-v1` to `vc-brain-demo-state-v2`, or sanitize loaded state so an old Analyst/Partner role cannot change the UI.
- Keep the `Role` TypeScript union temporarily only if legacy agent contracts or tests require it; hard-code `ASSOCIATE` at those boundaries and remove role-conditioned UI logic.
- Search the full frontend for `useRole`, `setRole`, `RoleSwitcher`, `ANALYST`, and `PARTNER`. Remove dead branches or explicitly mark compatibility-only types.
- Do not break pipeline status `PARTNER_REVIEW`; it is a stage, not a selectable UI persona.

Delete `RoleSwitcher.tsx` only after all imports are removed. Otherwise leave a clearly deprecated file out of the render path until a cleanup commit.

### 4.3 Shared discovery-list implementation

Refactor `Discovery.tsx` into shared components/hooks rather than copying it.

Suggested structure:

```text
frontend/src/features/founders/
  FounderListPage.tsx
  FounderTable.tsx
  FounderFilters.tsx
  FourScoreStrip.tsx
  RecommendationBadge.tsx
  useFounderDiscovery.ts
frontend/src/pages/Discovery.tsx
frontend/src/pages/Recommended.tsx
```

Behavior:

- `Discovery.tsx` renders `FounderListPage` with no fixed recommendation filter.
- `Recommended.tsx` renders it with `recommended=true`, a page explanation of the exact rule, and recommendation trigger labels.
- Filters and pagination update URL query parameters so pages are shareable and browser navigation works.
- Debounce free-text search.
- Fetch server-side filtered/paginated data.
- Preserve loading, empty, stale, and error states.
- Do not join all founders and opportunities on the client for these pages.

### 4.4 Table columns

Recommended default columns:

1. Founder and project
2. Institution/program and cohort
3. City, with city-basis indicator
4. Founder Score
5. Vision & Product
6. Differentiation
7. Traction
8. Recommendation trigger
9. Evidence confidence / coverage
10. Funding screen
11. Next diligence action

On narrower screens, collapse score cells into a four-chip stack and move lower-priority fields into an expandable row.

Use labels consistently:

```text
Founder
Vision & Product
Differentiation
Traction
```

Do not show the old seven dimension chips as the primary score breakdown on Discovery/Recommended. Legacy evidence dimensions may appear in a clearly labeled secondary section on the founder detail page.

### 4.5 Score visual behavior

- Show all four independent values.
- Do not render a total bar or overall percentage.
- Use threshold indicators that visually respect strict boundaries:
  - `>75`: high trigger
  - `>50`: qualifying
  - `<=50`: does not qualify
- A score of exactly 75 should not receive the `>75` trigger style.
- A score of exactly 50 should not receive the `>50` qualifying style.
- Missing scores render `—` and make the profile incomplete.
- Provide accessible text, not color alone.

### 4.6 Founder detail / DealRoom

In `DealRoom.tsx` or a dedicated founder detail view:

1. Add a primary **Associate Screen** section with the four parameters.
2. For each parameter show:
   - score
   - rationale
   - key evidence relevant to it, where available
   - counter-evidence
   - unknowns
3. Show the deterministic recommendation result and exact trigger.
4. Show source provenance, funding screen status/as-of/confidence, evaluation scope, and individual attribution confidence.
5. Show `next_diligence_action` prominently.
6. Keep the legacy eight-dimension Founder Score/evidence ledger in a collapsible **Evidence Engine (legacy)** section if it remains useful.
7. Do not label the legacy score as the same thing as the new four-field Founder Score without an explanatory label.

### 4.7 API client and types

In `frontend/src/types/backend.ts`, add DTOs for:

- `BackendFounderScreeningProfile`
- `BackendFounderDiscoveryItem`
- `BackendFounderDiscoveryPage`
- `BackendCsvImportResult`
- filter facet types

In `frontend/src/api/client.ts`, add:

```ts
api.founders.discovery(params)
api.founders.recommended(params)
api.founders.screeningProfile(founderId)
api.founders.updateScreeningProfile(founderId, request)
api.founders.importCsv(file, { dryRun })
```

Use `URLSearchParams`; do not hand-concatenate unescaped query values.

In `frontend/src/api/cache.ts`, add specific TTLs/invalidation for:

- discovery list
- recommended list
- screening profile
- import mutation

A profile update or committed import must invalidate both list variants and founder detail.

### 4.8 Optional import UI

An import endpoint is mandatory; an import UI is desirable.

If implemented, add a compact action on Discovery or Sourcing:

1. Choose CSV.
2. Run dry validation.
3. Display row counts, creates, updates, warnings, and row errors.
4. Require an explicit second click to commit.
5. Display that imported rows use manual enrichment and do not automatically launch 150 research jobs.

Never commit immediately on file selection.

### 4.9 Associate actions

Update `CaseStatusActions.tsx` and any role-conditioned controls so the visible actions are appropriate for an Associate:

- Start/continue DD
- Schedule Associate Call
- Move to Partner Review
- Request evidence
- Decline / monitor when allowed by the state machine

Do not expose an Analyst/Partner mode selector. Do not remove status validation from the backend.

---

## 5. Local decision engine changes

The current frontend engine has weighted queue scoring and older spike thresholds. Update only what maps to the new associate-screen workflow.

### 5.1 Routing rule

In `frontend/src/engine/routing.ts`, introduce a pure helper matching the backend exactly:

```ts
export type AssociateScreenScores = {
  founderScore: number | null;
  visionProductScore: number | null;
  differentiationScore: number | null;
  tractionScore: number | null;
};

export function evaluateAssociateRecommendation(
  scores: AssociateScreenScores,
): {
  recommended: boolean;
  trigger:
    | "ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50"
    | "ONE_SCORE_GT_75"
    | "TWO_SCORES_GT_50"
    | "NOT_RECOMMENDED"
    | "INCOMPLETE_EVALUATION";
} {
  const values = Object.values(scores);
  if (values.some((value) => value === null)) {
    return { recommended: false, trigger: "INCOMPLETE_EVALUATION" };
  }

  const numeric = values as number[];
  const oneHigh = numeric.some((value) => value > 75);
  const twoAbove50 = numeric.filter((value) => value > 50).length >= 2;

  if (oneHigh && twoAbove50) {
    return { recommended: true, trigger: "ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50" };
  }
  if (oneHigh) {
    return { recommended: true, trigger: "ONE_SCORE_GT_75" };
  }
  if (twoAbove50) {
    return { recommended: true, trigger: "TWO_SCORES_GT_50" };
  }
  return { recommended: false, trigger: "NOT_RECOMMENDED" };
}
```

The frontend helper is for instant rendering/tests only. The API response remains authoritative.

Do not retrofit this rule onto valuation/cap. Valuation/cap is not one of the four parameters.

### 5.2 Retire weighted final/queue score from this surface

`frontend/src/engine/scoring.ts` currently calculates queue priority using driver weights. Do not use that value for Discovery/Recommended ordering, display, or eligibility. Either:

- mark it legacy and keep it only for old validation fixtures, or
- replace its consumers with the lexicographic ordering described above and remove it once tests confirm no remaining dependency.

Do not rename weighted priority to “Founder Score.”

---

## 6. Data import mapping

Map the supplied CSV as follows.

| CSV column | Destination |
|---|---|
| `record_id` | `FounderScreeningProfile.external_record_id` |
| `founder_name` | `Founder.name` |
| `founder_role` | profile `founder_role`, optionally fill `Founder.role` when blank |
| `project_name` | profile `project_name`; optionally fill `Founder.current_company` when blank |
| `project_summary` | profile `project_summary`; do not overwrite a richer manually edited founder summary |
| `city` | profile `city`; optionally fill `Founder.location_city` only with provenance retained |
| `country` | profile `country` |
| `linkedin_url` | `Founder.linkedin_url` when valid and blank; use for deduplication |
| `github_url` | `Founder.github_url` when valid and blank |
| `primary_source_url` | profile provenance; optionally `Founder.source_url` when blank |
| `key_evidence` | profile JSONB list |
| `counter_evidence` | profile JSONB list |
| `unknowns` | profile JSONB list |
| four scores/rationales | four direct profile fields |
| imported recommendation fields | retain only for audit; recompute canonical fields |
| `pedigree_used_in_scoring` | must parse to false; reject/warn if true |
| `evaluation_version` | profile version |

Never overwrite non-empty, user-edited founder identity fields during an upsert without returning a conflict or explicit merge decision.

---

## 7. Tests

### 7.1 Backend unit tests

Create `backend/tests/test_screening.py` with at least:

```python
# one strict high score
assert evaluate_recommendation(76, 0, 0, 0).recommended is True

# exactly 75 is not high; only one score > 50
assert evaluate_recommendation(75, 51, 49, 49).recommended is False

# two strict scores above 50
assert evaluate_recommendation(51, 51, 0, 0).recommended is True

# exact 50 values do not count
assert evaluate_recommendation(50, 50, 100, 0).recommended is True  # one-high rule only
assert evaluate_recommendation(50, 50, 75, 0).recommended is False

# both rules
assert trigger(90, 80, 40, 40) == "ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50"

# incomplete
assert evaluate_recommendation(None, 90, 90, 90).trigger == "INCOMPLETE_EVALUATION"

# validation
reject(-1)
reject(101)
reject(float("nan"))
reject(True)
```

Also test every permutation of score order so no parameter is privileged accidentally.

### 7.2 Backend API/integration tests

Add tests for:

- creating/updating a screening profile recomputes recommendation
- discovery includes all profiles
- recommended excludes non-qualifying/incomplete profiles
- every filter, especially normalized city
- pagination and total counts
- stable ordering without a final score
- import dry run makes no writes and queues no tasks
- committed import creates founders/profiles once
- second identical import is idempotent or rejected as duplicate by checksum
- upsert by external id
- LinkedIn deduplication
- conflicting identity returns a row error
- invalid score/rationale/source produces a row error
- imported `associate_call_recommended=false` cannot override computed true
- imported `associate_call_recommended=true` cannot override computed false
- formula-like text survives safely and is escaped on export
- manual-enrichment imports do not block sourcing dispatcher
- legacy score snapshots remain readable

Use a small 4–8 row fixture in tests; do not load the full 150-row production file into every unit test.

### 7.3 Frontend tests

Add Vitest/React tests for:

- exact 50 and 75 boundaries
- all trigger combinations
- Discovery calls unfiltered endpoint
- Recommended always requests `recommended=true`
- city filter persists in URL and API request
- four score chips render independently
- no final score is rendered
- incomplete score renders `—`
- role switcher is absent
- old localStorage role cannot re-enable role switching
- “Move to Partner Review” remains available where state permits
- import dry-run review does not commit
- cache invalidation after profile update/import

Update existing routing/spike fixtures only where they represent the new associate-screen rule. Keep separate legacy tests for the old evidence engine if that code remains.

### 7.4 Regression/build commands

Run the repository’s actual commands. Based on the handoff, expected commands are similar to:

```bash
# backend
cd backend
pytest
alembic upgrade head

# frontend
cd frontend
pnpm test
pnpm run build
pnpm run lint
```

Do not report success unless each command actually ran. If local PostgreSQL/Redis is unavailable, run all test subsets that do not require them and clearly identify the blocked integration tests.

---

## 8. Acceptance criteria

The task is complete only when all of the following are true:

1. Sidebar shows Discovery and Recommended.
2. No Analyst/Associate/Partner mode switch is visible.
3. Associate is the only rendered product viewpoint.
4. Discovery shows all founders returned by the new list API.
5. Recommended is derived from the backend’s strict four-score rule.
6. Exactly 75 and exactly 50 behave as non-qualifying boundaries.
7. Only Founder, Vision & Product, Differentiation, and Traction are shown as the primary screen parameters.
8. No weighted or averaged final score is calculated or displayed for the new workflow.
9. City filtering occurs server-side and exposes city provenance/confidence.
10. The supplied 150-row CSV passes a dry run and can be committed idempotently.
11. Imported recommendation flags are recomputed, not trusted.
12. A committed 150-row import does not automatically launch 150 enrichment jobs.
13. Imported manual-enrichment founders do not block recurring sourcing.
14. Existing founder evidence, score snapshots, opportunities, and statuses remain readable.
15. Founder detail shows score rationales, evidence, counter-evidence, unknowns, funding caveats, and next diligence action.
16. API, frontend, migrations, tests, lint, and build pass.
17. No pedigree field contributes to recommendation or any score.
18. Every new profile is versioned and auditable.

---

## 9. Suggested implementation sequence

Use small, reviewable commits in this order:

1. **Domain + deterministic rule** — models, `screening.py`, unit tests.
2. **Persistence** — SQLAlchemy model, Alembic migration, CRUD, persistence tests.
3. **Discovery API** — filters, pagination, ordering, profile endpoints, API tests.
4. **CSV import** — dry run, validation, idempotent upsert, audit, task suppression tests.
5. **Enrichment policy** — update dispatch/gate logic and tests.
6. **Frontend data layer** — DTOs, API client, cache.
7. **Discovery/Recommended UI** — shared components, city filters, score rendering.
8. **Associate-only shell** — remove RoleSwitcher and sanitize persisted state.
9. **Founder detail** — primary four-parameter screen and provenance.
10. **Regression cleanup** — remove dead weighted-score consumers, update docs, run full test/build suite.

Each commit should leave the repository buildable where practical.

---

## 10. Rollout and rollback

### Rollout

1. Deploy the database migration.
2. Deploy backend endpoints while old frontend still works.
3. Run the CSV endpoint with `dry_run=true` and archive the response.
4. Review all errors/warnings and identity conflicts.
5. Commit the import with manual enrichment policy.
6. Verify counts and spot-check at least one MIT, Harvard, TreeHacks, HackUMass, and LA Hacks record.
7. Deploy frontend.
8. Verify Discovery, Recommended, filters, detail view, and pipeline handoff.
9. Monitor API latency, import logs, Celery queue depth, and recurring sourcing dispatch.

### Rollback

- Frontend can roll back independently because legacy endpoints remain.
- Backend rollback should stop use of new routes before downgrading the migration.
- Preserve the uploaded CSV and import audit outside the database before dropping the new table.
- Never roll back by rewriting legacy `ScoreSnapshot` data.

---

## 11. Non-goals for this change

Do not expand scope into:

- replacing the existing LLM/research agents
- retraining or changing the legacy eight-dimension score engine
- proving that any company is definitively unfunded
- scraping private LinkedIn data
- automatically contacting founders on WhatsApp
- creating a new Partner-only application
- deleting Partner Review as a workflow stage
- converting pedigree into a score
- adding a hidden weighted final score under another name

---

## 12. Final coding-agent report format

At completion, return:

1. Summary of behavior implemented.
2. File-by-file change list.
3. Database migration name and schema changes.
4. API routes and request/response examples.
5. CSV dry-run and committed-import results.
6. Proof that no automatic enrichment burst occurred.
7. Test, lint, type-check, migration, and build command outputs.
8. Screenshots or concise descriptions of Discovery, Recommended, city filter, and founder detail.
9. Remaining risks or follow-ups, with no claim of completion where a check did not run.

