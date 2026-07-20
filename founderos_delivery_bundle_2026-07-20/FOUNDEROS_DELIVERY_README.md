# FounderOS delivery — 2026-07-20

## Files

- `founderos_founder_import_150.csv` — app-import dataset, one row per named person.
- `founderos_founder_import_schema.json` — column order, recommendation rule, enumerations, and list-field encodings.
- `founderos_founder_dataset_methodology.md` — research, funding-screen, scoring, and import caveats.
- `founderos_founder_import_150_QA.txt` — independent structural and rule-validation report.
- `FOUNDEROS_AI_AGENT_CODE_UPDATE_INSTRUCTIONS.md` — paste-ready implementation brief for the coding agent.

## Important interpretation

- “No public institutional funding found” is a dated public-web screen, not proof of an empty cap table.
- Program/school affiliation is a sourcing field and was not used to increase scores.
- The new workflow has four independent scores and no final weighted score.
- Associate Call recommendation is deterministic: any one score >75 or at least two scores >50.
- Most multi-person rows repeat project/team-level evidence; see `evaluation_scope` and `individual_attribution_confidence`.
- Imported rows should default to manual enrichment so the app does not enqueue 150 research jobs at once.
