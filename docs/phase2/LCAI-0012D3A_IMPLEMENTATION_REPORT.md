# LCAI-0012D3A — Approval Queue Priority UX

## Baseline

- Branch: `develop`
- Baseline: `54e16c3 LCAI-0012D3 - Production Approval Sprint`
- Existing human approvals and modified DuckDB files were preserved.

## Implementation

- Dynamic coverage and minimal-plan recalculation on every Streamlit rerun.
- Separate `approval_priority_status` and `review_status`; neither replaces the
  editorial lifecycle.
- P1 to P5 priority display, counts and direct filters.
- Default P1 + P2 minimal-plan view.
- Grade, subject, Tier-1-only, 4e-first and balanced-subject filters.
- Fully French visible approval interface.
- Treated content is removed and the next priority is displayed after each
  explicit decision.
- Reviewer/approver separation and individual approval workflow preserved.

## Safety

- No automated approval performed.
- No existing data modified by the implementation or tests.
- No pipeline, lifecycle, schema or feature-gating change.
- Out-of-scope curriculum and Brevet resources left untouched.

## Validation

- Dynamic UI test: PASS; default plan contains 47 decisions.
- P1 filter: PASS; 1 current result.
- P3 filter: PASS; 54 results outside the minimal plan.
- 4e P1/P2 filter: PASS; 46 results.
- Ruff: PASS; 201 files formatted.
- MyPy: PASS; 201 source files.
- Pytest: PASS; 259 tests.
- Consolidated quality gate: PASS; 259 tests.
- Compileall: PASS.
- Git diff check: PASS.
- Streamlit HTTP smoke test: PASS (`200`, `ok`).
