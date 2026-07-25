# LCAI-0012A — Approved Content Coverage Baseline

Coverage is computed from all Approved curriculum placements and a left join
to `approved_learning_catalog`. It is queryable per Skill and naturally
aggregatable by chapter, subject and grade.

| Metric | Value |
|---|---:|
| Placed Approved curriculum Skills | 919 |
| Skills with at least one Approved content | 34 |
| Skills with zero Approved content | 885 |
| Skills with exactly one Approved content | 0 |
| Skills with more than one Approved content | 34 |
| Approved contents | 68 |

| Canonical type | Approved |
|---|---:|
| `WORKED_EXAMPLE` | 34 |
| `PRACTICE` | 16 |
| `ASSESSMENT` | 18 |
| Other canonical types | 0 |

| Existing difficulty | Approved |
|---|---:|
| 2 | 34 |
| 3 | 34 |

The `ContentCoverageService` exposes rows containing program, grade, subject,
chapter, Skill, total, canonical-type counts and difficulty counts. Its gap
read model identifies zero coverage and missing practice, assessment or
remediation. It does not generate anything automatically.

These figures are a generation-planning baseline, not a sufficiency claim.
Even the 34 Skills with two contents lack the variation normally required for
adaptive learning.

