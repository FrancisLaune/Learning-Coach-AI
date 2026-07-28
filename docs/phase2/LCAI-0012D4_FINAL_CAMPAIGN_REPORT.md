# LCAI-0012D4 — Final Campaign Report

**Campaign:** `LCAI-0012D4-WAVE2`  
**Status:** CLOSED — AI-controlled publication complete  
**Date:** 2026-07-28  
**Database:** `data/learning_coach_v2.duckdb`

---

## 1. Initial context

LCAI-0012D4 extends the Phase 2 content approval programme for **4e / 3e** enriched skills (`372` active skills). The objective was to increase production Tier 1 coverage through:

1. **Wave 1** — minimal human review for high-confidence completion candidates.
2. **Wave 2** — OpenAI pedagogical review, calibrated AI decisions, and controlled AI publication for `AI_PREVALIDATED_HIGH` candidates only.

Human approval remains mandatory for Teacher, Fact Check, and rejected cases.

---

## 2. Initial Tier coverage

Before LCAI-0012D4 Wave 2 publication:

| Tier | Skills | Meaning |
| ---: | ---: | --- |
| 1 | **100** | Practice + assessment approved |
| 2 | **0** | Partial approval (one slot only) |
| 3 | **272** | No approved slot |
| **Total** | **372** | Active 4e/3e skills |

---

## 3. Wave 1 result

Wave 1 targeted up to **100 Tier 1 skills** via minimal human review. Implementation artifacts:

- `resources/content/quality/lcai_0012d4_wave1_review_queue.json`
- `resources/content/quality/lcai_0012d4_wave1_summary.json`
- UI: `ui/content_approval_d4_wave1_app.py`

Wave 1 established the **100-skill Tier 1 baseline** retained as the pre–Wave 2 reference point.

---

## 4. Wave 2 candidate population

Wave 2 reviewed **184 candidates** across **92 skills** (2 lots × 50 skills, combined review):

| Source | Candidates |
| --- | ---: |
| Existing drafts | 92 |
| Generated Lot 1 | 46 |
| Generated Lot 2 | 46 |
| **Total reviewed** | **184** |

Authoritative OpenAI review evidence: `resources/content/quality/lcai_0012d4_ai_pedagogical_review_authoritative.jsonl`  
Combined bundle: `resources/content/quality/lcai_0012d4_wave2_combined_review.json`

---

## 5. OpenAI pedagogical review architecture

- **Assessor:** OpenAI (`gpt-5-mini`) via `infrastructure/assessors/openai_pedagogical_review.py`
- **Pipeline:** `lcai-0012d4-ai-review-v2`
- **Campaign ID:** `LCAI-0012D4-WAVE2`
- **Evidence model:** one authoritative JSONL record per candidate version, keyed by idempotency

Each review captures pedagogical dimensions (answer agreement, explanation quality, grade appropriateness, fact-check flags, escalation rationale).

---

## 6. Calibration root cause and correction

### Symptom

After the first OpenAI pass, **184 / 184** candidates were routed to `TEACHER_REVIEW_REQUIRED`, largely due to `grade_appropriateness=false`.

### Root cause

Not a curriculum mismatch (`skill_alignment` was true for all). Two implementation bugs:

1. **Existing candidates:** `grade_appropriateness` was only set when manual `difficulty_alignment` existed (LCAI-0012C small-sample path).
2. **Generated candidates:** `d4_wave2.evaluate_generated_candidate()` hardcoded `grade_appropriateness=False`.

### Correction

- New module: `services/content/grade_appropriateness.py`
- Calibrated engine: `services/content/ai_review_calibration.py`
- Recalibration script: `scripts/run_ai_pedagogical_review_recalibrate.py`
- Output: `resources/content/quality/lcai_0012d4_ai_pedagogical_review_calibrated.jsonl`

Recalibration was performed **without rerunning OpenAI**.

---

## 7. Final AI decisions

Post-calibration decisions (184 candidates):

| Decision | Count |
| --- | ---: |
| `AI_PREVALIDATED_HIGH` | **168** |
| `TEACHER_REVIEW_REQUIRED` | **15** |
| `FACT_CHECK_REQUIRED` | **15** |
| `AI_REJECTED` | **1** |

Notes:

- `FACT_CHECK_REQUIRED` is tracked via the `fact_check_required` flag (15 cases); these overlap with Teacher routing on the same candidates where applicable.
- **Rejected skill:** `SK-ENR-GEOGRAPHY-4E-URBANIZATION-INEQUALITY` (assessment, `alternate_count=0`, replacement required).

Human specialist workload reduction after calibration: **~91.8%**.

---

## 8. Controlled publication architecture

Publication service: `services/content/ai_controlled_publication.py`  
Repository path: `infrastructure/repositories/content_quality.py` → `approve_for_ai_controlled_publication`  
CLI: `scripts/run_ai_controlled_publication.py`

Each publication:

- Creates a new **Approved** exercise projection from the Draft source
- Preserves the Draft source version
- Persists provenance under `AI_CONTROLLED_APPROVAL`
- Enables the production gate atomically

Execution manifest: `resources/content/quality/lcai_0012d4_ai_controlled_publication_manifest.json` (168 entries)

---

## 9. Safety gates

Real execution requires **all three**:

```powershell
python scripts/run_ai_controlled_publication.py --execute --campaign LCAI-0012D4-WAVE2 --confirm-ai-controlled-publication
```

Per-candidate guards:

- Decision must remain `AI_PREVALIDATED_HIGH`
- Campaign must match `LCAI-0012D4-WAVE2`
- Teacher / Fact Check / AI rejected candidates excluded
- Draft source must exist
- Manifest must match fresh eligibility at execution time
- Atomic transaction per candidate; idempotent re-approval returns existing exercise

Campaign metadata repair applied to **1** candidate (version `114842`) via `services/content/wave2_campaign_repair.py`.

---

## 10. Idempotence verification

A second full `--execute` run was performed after the initial publication:

| Check | Result |
| --- | --- |
| Exit code | **0** |
| New duplicate publications | **0** |
| Duplicate approved versions | **0** |
| Duplicate production gates | **0** |

**Idempotence: PASS**

---

## 11. Rollback mechanism

Dry-run rollback:

```powershell
python scripts/run_ai_controlled_publication.py --rollback --campaign LCAI-0012D4-WAVE2
```

Execute rollback (emergency only):

```powershell
python scripts/run_ai_controlled_publication.py --rollback --execute --campaign LCAI-0012D4-WAVE2 --confirm-ai-controlled-rollback
```

All **168** publications retain rollback metadata (`ai_controlled_publication` provenance + revocable production gates).

**Rollback availability: PASS**

---

## 12. Final publication statistics

| Metric | Value |
| --- | ---: |
| Eligible candidates | 168 |
| Attempted | 168 |
| Published | **168** |
| Skipped | 0 |
| Failed | 0 |
| Practice published | 84 |
| Assessment published | 84 |
| Complete skill pairs added | **76** |
| AI-controlled approvals persisted | 168 |
| Production gates enabled | 168 |
| Duplicate publications | 0 |

Publication breakdown by subject (published manifest):

| Subject | Count |
| --- | ---: |
| HISTORY | 64 |
| GEOGRAPHY | 43 |
| SVT | 35 |

---

## 13. Tier coverage before and after

| Tier | Before Wave 2 | After Wave 2 | Delta |
| ---: | ---: | ---: | ---: |
| 1 | 100 | **176** | **+76** |
| 2 | 0 | **16** | +16 |
| 3 | 272 | **180** | −92 |
| **Total** | **372** | **372** | 0 |

### Tier 2 / Tier 3 note

The campaign added **76 complete Tier 1 skill pairs** (100 → 176). The remaining **16** Wave 2 publications are **single-slot approvals** on skills whose sibling slot remains excluded (Teacher / Fact Check / Rejected). Those skills moved from Tier 3 to **Tier 2** (partial coverage), which explains:

- Tier 2: 0 → **16**
- Tier 3: 272 → **180** (not 196)

Tier arithmetic: `176 + 16 + 180 = 372` ✓

---

## 14. Remaining workload

| Category | Count | Published |
| --- | ---: | --- |
| Teacher review required | **15** | 0 |
| Fact check required | **15** | 0 |
| AI rejected / replacement required | **1** | 0 |

These cases were intentionally excluded from AI-controlled publication.

---

## 15. Production DB impact

Database: `data/learning_coach_v2.duckdb` (Git LFS tracked)

Changes:

- **168** new Approved exercise projections with `approval_type=AI_CONTROLLED_APPROVAL`
- **168** production gates enabled
- **168** Draft source versions preserved
- **0** duplicate approved projections
- Campaign provenance on all 168 publications: `LCAI-0012D4-WAVE2`

No Teacher, Fact Check, or rejected content was auto-approved.

---

## 16. Known remaining work

1. Process **15** Teacher review cases manually.
2. Resolve **15** fact-check flags (same candidate set, flag-based tracking).
3. Generate replacement for `SK-ENR-GEOGRAPHY-4E-URBANIZATION-INEQUALITY` assessment.
4. Complete **16** Tier 2 partial skills (sibling slot still missing).
5. Do **not** start Wave 3 without explicit authorization.

---

## 17. Exact execution and rollback commands

### Dry-run

```powershell
python scripts/run_ai_controlled_publication.py --campaign LCAI-0012D4-WAVE2
```

### Execute (completed)

```powershell
python scripts/run_ai_controlled_publication.py --execute --campaign LCAI-0012D4-WAVE2 --confirm-ai-controlled-publication
```

### Recalibrate (offline, no OpenAI rerun)

```powershell
python scripts/run_ai_pedagogical_review_recalibrate.py
```

### Rollback dry-run

```powershell
python scripts/run_ai_controlled_publication.py --rollback --campaign LCAI-0012D4-WAVE2
```

### UI

```powershell
python -m streamlit run ui/content_approval_d4_app.py
```

---

## 18. Final verdict

**LCAI-0012D4-WAVE2 AI-controlled publication: SUCCESS**

- 168 / 168 eligible candidates published
- Tier 1 increased from 100 to **176** (+76 complete pairs)
- Idempotence verified
- Rollback available
- Exclusions preserved
- No duplicate publications

**Campaign status: CLOSED**
