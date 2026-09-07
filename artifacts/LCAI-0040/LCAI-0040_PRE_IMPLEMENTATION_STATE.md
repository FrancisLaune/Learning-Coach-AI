# LCAI-0040 — Pre-implementation state

- generated_at: 2026-09-07T17:38:07+00:00
- db_sha256: `6c249d8398b4b7f0bc6ba0edc288a5ae530ff07fba7a542c07c0a8c8609c7bf3`
- counts: `{"domains": 34, "chapters": 171, "skills": 291, "subskills": 562, "content_items": 10320, "official_archive": 1098, "archive_derived": 6, "canonical_skills": 213}`
- coverage_before: `{"PARTIAL": 18, "COMPLETE": 195}`

## Anomalie official_count LCAI-0039

Cause exacte: le refresh 0039 filtrait `validation_status IN (AUTO_VALIDATED, APPROVED, VALIDATED)`
alors que les 1098 `OFFICIAL_ARCHIVE` sont en statut `REVIEW`. Elles étaient bien remappées
vers des skills canoniques, mais `official_count` restait à 0.

Correction 0040: `official_count` compte les OFFICIAL_ARCHIVE liées sans exiger AUTO_VALIDATED.
