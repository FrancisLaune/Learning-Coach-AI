# LCAI-0012E — CM1/CM2/6e/5e Pre-integration Inventory V1

## Scope

Pre-validation only. DuckDB was not modified. No content was Approved.

## Global summary

- Candidates inspected: **1311**
- Unique candidate codes: **1311**
- Duplicate candidate codes: **0**
- READY_TO_IMPORT_DRAFT: **465**
- IMPORT_WITH_REVIEW: **845**
- BLOCKED: **1**

## By grade

| Grade | Subjects | Skills declared | Candidates | Ready | Review | Blocked |
|---|---:|---:|---:|---:|---:|---:|
| 5E | 9 | 125 | 375 | 75 | 300 | 0 |
| 6E | 8 | 117 | 351 | 69 | 282 | 0 |
| CM1 | 8 | 94 | 282 | 249 | 32 | 1 |
| CM2 | 8 | 101 | 303 | 72 | 231 | 0 |

## Integration rules

- `READY_TO_IMPORT_DRAFT`: structurally usable candidate with a text/exact response model and no hard failure detected.
- `IMPORT_WITH_REVIEW`: open-response or non-text/oral modality that must pass the LCAI-0012D pedagogical/executability pipeline before student exposure.
- `BLOCKED`: missing mandatory structure or invalid QCM choice structure.

## Important production rule

This report does **not** certify pedagogical correctness. The final import must use the quality, QCM, deterministic-answer and promotion controls delivered by LCAI-0012D. All imported content remains Draft until that pipeline approves it.

## Next step

After Codex completes LCAI-0012D, adapt one generic external-pack importer to consume these artifacts and run the same hard gates used for 4e/3e. Do not create grade-specific importers.