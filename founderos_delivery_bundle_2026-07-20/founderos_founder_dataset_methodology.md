# FounderOS founder import dataset — methodology and data dictionary

**File:** `founderos_founder_import_150.csv`  
**Rows:** 150  
**Research/funding screen date:** 2026-07-20  
**Evaluation version:** `associate_screen_v1_2026-07-20`

## What this file is

This is a curated **sourcing and first-screen dataset**, not completed investment due diligence. It contains one row per named person and repeats venture-level evidence for co-founders because most public accelerator and hackathon sources describe the team/project, not each person’s contribution.

Source distribution:

- MIT delta v 2025: 52 people
- Harvard Innovation Labs / 2026 President’s Innovation Challenge: 24 people
- TreeHacks 2026 (Stanford-hosted): 66 people
- HackUMass XIII: 4 people
- LA Hacks 2026: 4 people

## Recommendation rule

There is **no weighted final score** and no overall average. The only four parameters are:

1. `founder_score`
2. `vision_product_score`
3. `differentiation_score`
4. `traction_score`

`associate_call_recommended = true` when either:

```text
ANY one score > 75
OR
AT LEAST two scores > 50
```

The inequalities are strict: 75 and 50 themselves do not qualify. Confidence is retained for context and sorting but does not change eligibility.

Recommended rows in this curated set: 150  
Not recommended rows: 0

## Funding interpretation

`funding_status` is deliberately conservative:

- `no_public_institutional_funding_found`: no disclosed institutional equity round was located in the public-web screen for the exact entity.
- `non_dilutive_grant_or_prize_only`: public grants, fellowships, competition prizes, cloud credits, or similar support were located, but no disclosed institutional equity round was found.

These labels **do not prove** that a founder has never raised. They are leads for cap-table verification. Entity-name collisions, undisclosed angel/SAFE financing, family capital, or recent filings may not be visible.

Funding-status counts:

- no public institutional funding found: 122
- non-dilutive grant or prize only: 28

Several publicly funded ventures were excluded during research, including teams with disclosed pre-seed/seed rounds that appeared in university program materials. One unresolved Devpost creator handle was also omitted rather than guessed.

## Scoring principles

- Institution, university, accelerator prestige, geography, name, and network were **not** used as positive scoring inputs.
- Scores reflect publicly visible execution, product clarity, differentiation, and customer/technical traction.
- Accelerator admission and hackathon awards are evidence of selection, not customer traction.
- Grants/prizes are classified as non-dilutive funding, not revenue.
- Hackathon prototypes receive low evidence confidence unless there is real-user or field evidence.
- Claims such as accuracy, savings, or performance are preserved as reported claims and called out for verification.

## Important columns

| Column | Meaning |
|---|---|
| `record_id` | Stable import identifier. |
| `founder_name` | Person named by the official source. |
| `founder_role` | Founder/team role; hackathon founder status is explicitly unverified. |
| `project_name` | Venture or project name. |
| `institution_or_program` | Sourcing channel only; not a score input. |
| `city` | Usually event/program city for filtering. Use `city_basis` and `city_confidence` before treating it as residence. |
| `primary_source_url` / `source_locator` | Main public evidence and location within it. |
| `funding_status` | Public-web funding screen classification. |
| `funding_check_confidence` | Confidence in exact-entity matching and public coverage. |
| four score columns | Independent 0–100 parameter scores; never average them. |
| four rationale columns | Human-readable reason for each score. |
| `evidence_confidence` | Overall confidence in available public evidence, 0–1. |
| `evidence_coverage` | Breadth of evidence across execution/product/differentiation/traction, 0–1. |
| `evaluation_scope` | Warns when evaluation is team-level. |
| `counter_evidence` / `unknowns` | What prevents overconfidence. |
| `next_diligence_action` | Highest-value follow-up before advancing. |
| `recommendation_trigger` | Exact deterministic rule path. |
| `pedigree_used_in_scoring` | Always `false`. |
| `import_status` | `ready_with_caveats`; importer should retain caveats. |

## Delimited multi-value fields

The CSV remains a flat import file. Parse these fields as follows:

- `key_evidence`, `counter_evidence`, and `unknowns`: semicolon-delimited text items. Trim each item and discard empty items. Preserve the original cell for audit if the importer also stores parsed JSON arrays.
- `tags`: pipe-delimited values (`|`). Trim each tag and discard empty values.

Do not split narrative rationale or notes fields on punctuation.

## Suggested import behavior

Use `record_id` as an external id. Upsert by normalized LinkedIn URL when present; otherwise by normalized `(founder_name, project_name, cohort_year)`. Do not auto-trigger 150 individual enrichment jobs during the import. Import should support a dry run, row-level errors, and a later batch-enrichment action.
