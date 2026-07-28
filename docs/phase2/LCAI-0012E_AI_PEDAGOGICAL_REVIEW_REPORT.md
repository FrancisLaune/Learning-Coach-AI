# LCAI-0012E AI PEDAGOGICAL REVIEW

## Integration baseline
- Importable drafts (isolated): **1293**
- Best candidates for AI review: **731**
- Review architecture: Agent 1 calibrated generic reviewer (Pass A blind + Pass B compare)
- Pipeline version: `lcai-0012d4-ai-review-v2`
- Calibration version: `lcai-0012d4-ai-review-calibration-v2-grade-repair`
- Model: `gpt-5-mini`
- Idempotent resume: **yes**

- Candidates expected: **731**
- Candidates reviewed: **949**
- Remaining: **0**

## Decisions
- AI_PREVALIDATED_HIGH: **271**
- AI_PREVALIDATED_WITH_WARNING: **0**
- TEACHER_REVIEW_REQUIRED: **16**
- FACT_CHECK_REQUIRED (flag): **0**
- AI_REJECTED: **662**

## Decisions by grade
- FR-5E: {"AI_REJECTED": 185, "AI_PREVALIDATED_HIGH": 44}
- FR-6E: {"AI_REJECTED": 244, "AI_PREVALIDATED_HIGH": 45}
- FR-CM1: {"AI_PREVALIDATED_HIGH": 138, "TEACHER_REVIEW_REQUIRED": 16, "AI_REJECTED": 26}
- FR-CM2: {"AI_REJECTED": 207, "AI_PREVALIDATED_HIGH": 44}

## Decisions by subject
- EMC: {"AI_REJECTED": 72, "AI_PREVALIDATED_HIGH": 14, "TEACHER_REVIEW_REQUIRED": 2}
- FRENCH: {"AI_REJECTED": 209, "AI_PREVALIDATED_HIGH": 25, "TEACHER_REVIEW_REQUIRED": 2}
- GEOGRAPHY: {"AI_REJECTED": 122, "AI_PREVALIDATED_HIGH": 24}
- HISTORY: {"AI_REJECTED": 101, "AI_PREVALIDATED_HIGH": 23, "TEACHER_REVIEW_REQUIRED": 1}
- MATHEMATICS: {"AI_PREVALIDATED_HIGH": 156, "AI_REJECTED": 6, "TEACHER_REVIEW_REQUIRED": 8}
- PHYSICS_CHEMISTRY: {"AI_REJECTED": 79, "AI_PREVALIDATED_HIGH": 15, "TEACHER_REVIEW_REQUIRED": 1}
- SVT: {"AI_REJECTED": 73, "AI_PREVALIDATED_HIGH": 14, "TEACHER_REVIEW_REQUIRED": 2}

## Skill pairs
- Both AI prevalidated: **123**
- Mixed (one AI / one Teacher): **10**
- Both Teacher: **2**
- Blocked by rejection: **230**
- Only one slot available: **1**

## Workload
- Human specialist workload reduction: **98.3%**
- Teacher specialist reviews required: **16**
- Fact Check reviews required: **0**

## Rejection analysis
- Alternates queued: **4**
- Alternates reviewed: **218**
- Alternates recovered (AI-prevalidated): **1**
- Replacement required: **441**

## Final generation requirement (after AI review)
- Missing Practice (genuinely absent): **0**
- Missing Assessment (genuinely absent): **0**
- Rejected without alternate: **441**
- Teacher-blocked slots: **16**
- Fact-check-blocked slots: **0**
- Replacement required: **445**
- **TOTAL NEW CONTENTS REQUIRED: 445**

### Categories
- A. Genuinely absent content: **0**
- B. Rejected needing replacement: **445**
- C. Awaiting human/fact-check: **16**

## Unresolved curriculum records
- Total excluded: **18** (15 curriculum-decision + 3 Spanish COMPARE)
- See appendix: `docs/phase2/LCAI-0012E_UNRESOLVED_CURRICULUM_APPENDIX.md`

- Production DB modified: **NO**
- Controlled publication: **NOT executed** (pre-validation only)

## Recommendation

**LCAI-0012E AI REVIEW: REQUIRES CORRECTION**
