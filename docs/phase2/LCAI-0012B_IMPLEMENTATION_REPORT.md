# LCAI-0012B — Implementation Report

## Executive summary

The pilot used two strictly separated generators:

1. a deterministic reviewed generator used only by automated tests and
   technical orchestration checks, with zero production persistence;
2. a real OpenAI structured-output adapter implementing the existing
   provider-independent `ContentGenerator` contract.

The real pilot generated 93 requested candidates for 24 approved 4e/3e Skills.
After first-pass validation, bounded retry and manual pedagogical review, 88
candidates were persisted as Draft. Approved content remains exactly 68.

## Git pre-flight

Branch `develop`; initial working tree clean and synchronized; LCAI-0012A
present at `a9eb382`; Git LFS clean.

## Scope

Exactly 12 Skills in 4e and 12 in 3e: 8 Mathematics, 8 French and 8 across
English, Spanish, History, Geography, EMC, SVT and Physics-Chemistry. Eighteen
were uncovered and six had existing Approved content. See
`LCAI-0012B_PILOT_SCOPE.md`.

## Architecture

The adapter lives in infrastructure and uses structured output. The prompt is
versioned under `resources/content/pilot/prompts/`. Domain and service code
contain no provider dependency. Generation resolves curriculum, performs the
external call without a transaction, validates in memory, then persists in a
short Draft-only transaction.

Automated tests never call OpenAI. The user-supplied key was read only into the
generation process memory. No key is stored in generated provenance or data.

## Results

- Requested: 93.
- First-pass valid: 70 (75.27%).
- First-pass rejected: 23 (24.73%).
- Controlled request retries: 19.
- Technically valid after retry: 90.
- Manual pedagogical rejects: 2.
- Final Drafts: 88 (94.62%).
- Approved before/after: 68/68.
- No source generation failure.
- No exact, normalized or near duplicate.
- 30/30 directly deterministic accepted answers correct.
- 42/42 accepted Mathematics answers manually checked correct.
- Audited accepted alignment: 22/22 after two manual rejects.

The real first-pass rate is useful but not yet high enough for unattended
industrial generation. Retry dependence and the QCM answer-label defect require
another controlled iteration.

## Lifecycle and regressions

All 88 candidates have exercise and content-version status `draft`. None has
learning-content approval metadata or editorial approval. Student, Homework,
Revision and Recommendation continue reading the Approved catalog only.
Approved coverage remains production coverage; Draft pilot coverage is
reported separately.

## Files

Created:

- `infrastructure/generators/__init__.py`
- `infrastructure/generators/openai_content.py`
- `services/content/pilot.py`
- `scripts/run_content_pilot.py`
- `scripts/run_real_content_pilot.py`
- `scripts/consolidate_content_pilot.py`
- `tests/test_content_generation_pilot.py`
- `resources/content/pilot/prompts/lcai_0012b_v1.txt`
- `resources/content/pilot/lcai_0012b_real_candidates.json`
- six LCAI-0012B Phase 2 reports

Modified:

- `infrastructure/repositories/content_factory.py`
- `data/learning_coach_v2.duckdb` (88 real Drafts; 68 Approved unchanged)
- `.streamlit/config.toml` (the uncommitted OpenAI section was removed; the
  pre-existing user email configuration remains)
- `.streamlit/secrets.toml` (ignored local secret store; never tracked)

Deleted after consolidation: three temporary shard exports. No migration,
renaming or curriculum change.

## Final validation

- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed, 184 files formatted.
- `python -m mypy .`: passed, 184 source files checked.
- `python -m pytest -q`: passed, 218 tests.
- `python scripts/check_quality.py`: passed; Ruff, format, MyPy and all 218
  tests passed.
- `python -m compileall app.py application domain infrastructure services ui
  core analytics subjects tests scripts`: passed.
- `git diff --check`: passed; Git emitted only its informational future
  LF-to-CRLF conversion notice for `content_factory.py`.
- `streamlit run app.py`: health endpoint returned HTTP 200 with body `ok`;
  the temporary process was then stopped.
- The three V1 databases are absent from Git status. No V1 schema or data was
  modified.
- Final V2 verification: 24 pilot Skills, 88 pilot Drafts and 68 Approved
  entries.

## Required review answers

1. Genuinely different same-Skill activities? **YES.**
2. Pedagogically distinguishable difficulties 1/2/3? **YES.**
3. Accepted deterministic answers correct? **YES — 100% of the 30 directly
   deterministic audited answers; 42/42 Mathematics candidates checked.**
4. Coherent Diagnostic/Remediation pairs? **YES.**
5. Useful cross-disciplinary generation? **YES, with two manual rejects
   demonstrating the review boundary.**
6. Accidental duplicates controlled? **YES.**
7. Complete Draft isolation until Approval? **YES.**
8. First-pass quality sufficient for larger-scale generation? **NO.** The
   measured 75.27% first-pass acceptance and 19 retried requests require a
   correction iteration before controlled expansion.

## Known limitations and decision

The deterministic validator cannot fully establish factual, linguistic,
age-level or pedagogical quality. Open responses require rubric-aware execution
and human editorial review. The API key is user configuration and must never be
committed. The current pilot supports a correction iteration, not mass
generation.

NOT READY FOR CONTENT EXPANSION — PILOT REQUIRES CORRECTION
