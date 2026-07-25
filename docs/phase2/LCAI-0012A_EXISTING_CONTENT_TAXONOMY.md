# LCAI-0012A — Existing Approved Content Taxonomy Audit

Audit source: the read-only `approved_learning_catalog` and its normalized
content tables. No Approved record was changed.

## Results

- 68/68 Approved contents remain resolvable.
- 34 curriculum Skills are represented.
- Every represented Skill has a two-item pedagogical family: one worked example
  (guided/model role, difficulty 2) and one retrieval/evaluative activity
  (difficulty 3).
- Therefore there are 34 intentional variant groups and 34 pedagogically
  distinct targets, not 34 accidental text duplicates.
- Normalized prompt comparison finds 0 exact/normalized duplicate groups among
  the 68 questions.
- Sub-skill linkage is absent from this historical seed and is not fabricated.

| Current type | Count | Canonical type | Intent | Difficulty |
|---|---:|---|---|---:|
| `worked_example` | 34 | `WORKED_EXAMPLE` | `MODEL` | 2 |
| `exercise` | 16 | `PRACTICE` | `PRACTICE` | 3 |
| `exam_practice` | 18 | `ASSESSMENT` | `CHECK` | 3 |

The 34 families are identified by the stable code prefix before the terminal
`-1`/`-2`. This explicit family rule preserves the known 68 → 34 relationship
without falsely classifying differently worded guided and evaluative prompts
as duplicates.

| Grade | Approved |
|---|---:|
| 4e (`FR-4E`) | 28 |
| 3e (`FR-3E`) | 40 |

| Subject | Approved |
|---|---:|
| Mathematics | 32 |
| French | 24 |
| English | 2 |
| Spanish | 2 |
| History | 2 |
| Geography | 2 |
| Physics-Chemistry | 2 |
| SVT | 2 |

