# Changelog

All notable changes to Learning Coach AI are documented in this file.

## [2.0.0] - 2026-07-28

Phase 2 release — curriculum foundation, content factory, AI review, and controlled publication.

### Added

- DuckDB V2 schema with unified learning experience (LCAI-0004, LCAI-0010B)
- Content management foundation and approval workflow (LCAI-0005)
- Curriculum reference data CM1–3e and skill enrichment (LCAI-0011A/B/C)
- Content factory, taxonomy, generation pilot, and 4e/3e expansion (LCAI-0012A/B/C)
- Content quality audit, human approval acceleration, and production tiers (LCAI-0012D/D2/D3)
- AI pedagogical review and controlled publication for 4e/3e Wave 2 (LCAI-0012D4)
- CM1–5e primary integration, AI review, primary draft import, and publication dry-run (LCAI-0012E)
- Phase 2 database integrity audit script (`scripts/audit_phase2_database.py`)
- Application version module (`core/version.py`)

### Changed

- Production database `learning_coach_v2.duckdb` includes 1293 CM1–5e primary Draft sources
- Platform runtime version aligned to 2.0.0
- Streamlit page title reflects application version 2.0.0

### Security / Governance

- AI-controlled publication restricted to `AI_PREVALIDATED_HIGH` decisions only
- Human review remains mandatory for Teacher, Fact Check, Warning, and rejected cases
- Publication campaigns are idempotent and support rollback

### Known limitations

- LCAI-0012E controlled publication dry-run validated; real execution awaits final authorization
- 18 unresolved curriculum records excluded from import
- 445 primary skill slots require replacement content after AI rejection
- V2 UI and session execution remain feature-flagged off by default

[2.0.0]: https://github.com/your-org/Learning-Coach-AI/releases/tag/v2.0.0
