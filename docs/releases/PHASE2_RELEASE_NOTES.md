# Learning Coach AI — Phase 2 Release Notes

**Version:** 2.0.0  
**Date:** 2026-07-28  
**Branch:** `develop`  
**Tag:** `v2.0.0`  
**Release type:** FINAL PHASE 2

---

## Summary

Phase 2 delivers the educational content platform for Learning Coach AI: DuckDB V2, curriculum reference data, content factory, AI pedagogical review, human approval workflows, and controlled AI publication. This release freezes Phase 2 deliverables and prepares the repository for Phase 3.

---

## Major features

### Architecture (LCAI-0004, LCAI-0010B)

- DuckDB V2 with 116 tables, 8 views, migration level 17
- Unified learning experience shell
- Platform runtime version 2.0.0
- Session integrity, operational health, and parent dashboard foundations

### Content management (LCAI-0005, LCAI-0012A)

- Content factory with Draft lifecycle
- Exercise / question / version persistence
- Approval coverage tiers (Tier 1 / 2 / 3)
- Human approval queue and production gates

### Curriculum (LCAI-0011A/B/C)

- Target curriculum model CM1–3e
- Reference data and skill enrichment
- 919 curriculum skill details, 1227 skills, 166 chapters

### Content generation (LCAI-0012B/C)

- Generation pilot for 4e/3e
- Full 4e/3e educational content expansion
- Deterministic answer audit and quality gates

### AI review & controlled publication (LCAI-0012D/D4, LCAI-0012E)

- OpenAI pedagogical review pipeline (`lcai-0012d4-ai-review-v2`)
- Wave 2 controlled publication: 168 candidates published for 4e/3e
- CM1–5e primary integration: 1293 Draft sources imported
- CM1–5e publication dry-run: 270 eligible `AI_PREVALIDATED_HIGH` candidates

---

## Database evolution

| Metric | Value |
|---|---|
| Migration level | 17 |
| Draft versions | 2491 |
| Approved versions | 423 |
| Approved catalog items | 423 |
| Primary import mappings | 1293 |
| Publication mapping resolved | 1293 / 1293 |

Production database: `data/learning_coach_v2.duckdb` (Git LFS)

---

## LCAI-0012E publication status

| Check | Status |
|---|---|
| Primary Draft import | PASS |
| 271/271 AI_HIGH resolved | PASS |
| Tier coverage unchanged | PASS |
| Production DB integrity | PASS |
| Post-import publication dry-run | PASS |
| Eligible candidates | 270 |
| Complete skill pairs (projected) | 123 |

Real publication execution awaits final human authorization.

---

## Known limitations

1. **18 unresolved curriculum records** excluded from CM1–5e import
2. **445 skill slots** require replacement content after AI rejection
3. **16 Teacher review cases** excluded from automatic publication
4. **V2 UI** and session execution remain disabled by default (feature flags)
5. **Brevet library** (LCAI-0013A/B) prepared as Phase 2 inventory; not part of this runtime release

---

## Migration notes

- V1 database (`objectif_brevet_2027.duckdb`) remains separate and unchanged
- V2 is the authoritative production database for content approval
- Git LFS required for `*.duckdb` files
- Run migrations via application startup or `migrations/runner.py`

---

## Phase 3 roadmap

- Execute authorized LCAI-0012E controlled publication (270 candidates)
- Teacher review workflow for 16 remaining cases
- Replacement content generation for 445 rejected skill slots
- Brevet revision library integration (LCAI-0013B)
- V2 UI and session execution enablement
- Parent dashboard production rollout

---

## Verification commands

```powershell
# Database integrity
python scripts/audit_phase2_database.py

# Publication dry-run
python scripts/run_ai_controlled_publication_0012e.py

# Full test suite
python -m pytest --cov -q

# Static analysis
python -m ruff check .
python -m mypy
```

---

## Work packages included

LCAI-0004, LCAI-0005, LCAI-0010B, LCAI-0011A, LCAI-0011B, LCAI-0011C, LCAI-0012A, LCAI-0012B, LCAI-0012C, LCAI-0012D, LCAI-0012D4, LCAI-0012E
