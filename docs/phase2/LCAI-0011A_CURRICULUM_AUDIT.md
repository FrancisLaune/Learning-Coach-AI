# LCAI-0011A — Current Curriculum Audit

## Scope and method

This audit reflects the implementation on `develop` at commit `8bb793a`
(`LCAI-0010B - Unified Learning Experience`). The working tree was clean and
the local branch was one commit ahead of `origin/develop` before this audit.

Evidence was collected from:

- `data/learning_coach_v2.duckdb`, opened read-only;
- migrations `001` through `016`;
- `resources/catalog/lcai_0009_catalog.json`;
- the curriculum, content, recommendation, decision, learning, onboarding and
  unified-experience domain/services/repositories;
- Streamlit presentation code and selector-state helpers.

No database, migration, curriculum record or educational content was changed.

## Executive finding

The existing V2 schema is structurally capable of separating curriculum nodes
from content instances. `curriculum_chapters`, `curriculum_skill_details`,
`skills` and `subskills` can exist without rows in `approved_learning_catalog`.
The Approved view is a strict content publication projection, not the
curriculum itself.

The principal Phase 2 issue is data and integration completeness, not a need
for a parallel curriculum architecture:

- all six target school levels exist;
- all nine target subjects exist;
- reusable subject domains exist;
- detailed chapters and grade-bound skills exist only for 4e and 3e;
- Approved content exists only for those same curriculum nodes;
- curriculum import currently bundles structure and content in one document;
- the Learning Engine still reads `program_skills` and
  `skill_prerequisites`, whereas the richer imported model uses
  `curriculum_skill_details` and `curriculum_skill_relations`.

## Current conceptual hierarchy

```text
programs
  ├─ program_subjects ─ school_levels
  │                     └─ subjects
  │                         └─ domains
  │                             └─ skills
  │                                 └─ subskills
  └─ curriculum_chapters
       └─ curriculum_skill_details ─ skills
            └─ curriculum_skill_relations

curriculum skill/sub-skill
  └─ learning_content_metadata / question mappings
       └─ exercises + content_versions + editorial approval
            └─ approved_learning_catalog
```

`approved_learning_catalog` requires active, current, approved content and an
active editorial approval. It correctly excludes unapproved content.

## Relevant database inventory

Volumes below are the observed V2 values during the audit.

| Structure | Purpose and identifiers | Relationships | Repository/service and usage | Rows | Phase 2 assessment |
|---|---|---|---|---:|---|
| `school_levels` | Grade reference; numeric `id`, stable unique `code`, French `label`, `rank` | Referenced by programmes, chapters and journeys | Onboarding and unified-experience repositories; active | 9 | Reuse. Six target levels plus three lycée levels are present. |
| `subjects` | Subject reference; numeric `id`, stable unique `code`, French `default_label` | Parent of domains; linked to programmes and chapters | Multiple repositories; active | 10 | Reuse. Nine target subjects plus Technology. |
| `domains` | Subject-scoped pedagogical domain; `id`, `(subject_id, code)` | Parent of skills; referenced by chapters | Content/curriculum repositories; active | 21 | Reuse and populate only where authoritative curriculum data supports it. |
| `programs` | Versioned programme header; stable `code`, `version`, dates, optional exam type | Linked through `program_subjects`, `program_skills`, chapters | Content and curriculum repositories; active | 3 | Reuse. New grade programmes can be additive data. |
| `program_subjects` | Programme × subject × grade association | FK to programme, subject and school level | Onboarding/Learning Engine reference data; active | 20 | Reuse. Missing for CM1–5e except imported 4e. |
| `program_skills` | Skills expected by a programme with priority/mastery | FK to programme and skill | Read by `DuckDBLearningRepository.load_curriculum` | 25 | Active but populated only for the original BREVET programme. Integration gap with imported curricula. |
| `curriculum_chapters` | Versioned grade/programme/subject/domain chapter; stable `stable_code` | FK to programme, subject, domain, school level | `DuckDBCurriculumRepository`; selector repositories | 34 | Reuse. Correct Phase 2 chapter entity. |
| `skills` | Stable reusable skill identity; numeric `id`, unique `code`, label | FK to domain; parent of sub-skills | Content, curriculum, learning repositories | 59 | Reuse. 25 seed skills are not grade/chapter mapped; 34 imported skills are mapped. |
| `curriculum_skill_details` | Grade/chapter/version-specific skill metadata | FK to skill, chapter and grade | Curriculum import and selectors | 34 | Reuse as the curriculum placement of a stable skill. |
| `subskills` | Stable child of a skill | FK to skill | Content import, question mappings | 40 | Reuse. 34 imported sub-skills plus 6 seed sub-skills. |
| `skill_prerequisites` | Simple skill prerequisite with weight | Skill-to-skill FK, no self-edge | Read by the Learning Engine | 5 | Legacy-active compatibility model; insufficient as the sole Phase 2 graph. |
| `curriculum_skill_relations` | Versioned typed prerequisite relation with role, threshold and rationale | Skill-to-skill FK, active/version fields | Written by curriculum importer; validated for cycles before import | 38 | Preferred rich Phase 2 relation, but runtime bridge is incomplete. |
| `learning_objectives` | Observable chapter objective | FK to chapter | Curriculum import | 34 | Reuse. |
| `skill_learning_objectives` | Skill-to-objective mapping | FK to skill/objective | Curriculum and content import | 34 | Reuse. |
| `exam_references` / `exam_skill_references` | Versioned examination mappings | Grade and skill references | Curriculum import, exam preparation | 1 / 18 | Reuse for DNB; not a general programme substitute. |
| `exercises` | Executable content identity and current content version | FK to subject | Content repositories and execution | 68 | Active content entity. |
| `questions` / `exercise_questions` | Legacy-compatible executable question representation | Exercise/question link | Session execution compatibility | 68 / 68 | Active compatibility projection. |
| `content_questions` | Detailed question payload | FK to exercise | Assessment and session execution | 68 | Active detailed model. |
| `question_skills` / `question_subskills` | Content-to-curriculum mappings | FK to question, skill and sub-skill | Import and assessment | 68 / 68 | Reuse. |
| `learning_content_metadata` | Chapter, sub-skill, type, compatibility and source metadata | FK to exercise/chapter/sub-skill | Curriculum import and Approved view | 68 | Reuse. |
| `content_versions` | Immutable version payload and editorial state | Logical entity reference | Content lifecycle services | 68 | Reuse. All observed versions are version 1. |
| `content_status_events` | Editorial transition history | FK to content version | Import/workflow | 204 | Reuse. Three events per content. |
| `editorial_reviews` / `editorial_approvals` | Human review and active approval | FK to content version and validation | Approved view gate | 68 / 68 | Reuse. |
| `content_quality_assessments` | Quality scoring and blocking issues | FK to content version | Publication evidence | 68 | Reuse. |
| `tags` / `content_tags` | Stable tag vocabulary and assignments | Tag/entity logical mapping | Candidate selection and search | 8 / 326 | Reuse. |
| `approved_learning_catalog` | Strict read view of learner-eligible content | Joins current active content, curriculum mappings, version and approval | Recommendation, unified experience, execution and health checks | 68 | Reuse as the sole learner-eligible catalog projection. |

## Existing reference data

### School levels

The database contains `FR-CM1`, `FR-CM2`, `FR-6E`, `FR-5E`, `FR-4E`,
`FR-3E`, `FR-2NDE`, `FR-1ERE` and `FR-TERM`.

The target levels therefore require no new grade table or duplicate grade
entity. The observed ranks are not globally unique (6e/2nde, CM2/1ère and
CM1/Terminale share ranks), so ordering should use an explicit supported-level
sequence rather than assuming `rank` is a unique ordinal.

### Subjects and domains

All target subject codes already exist:

| Subject code | UI label | Existing domains |
|---|---|---|
| `MATHEMATICS` | Mathématiques | Numbers, Algebra, Geometry, Data |
| `FRENCH` | Français | Reading, Language Study, Writing |
| `ENGLISH` | Anglais | Communication, Language |
| `SPANISH` | Espagnol | Communication, Language |
| `HISTORY` | Histoire | Modern History, Contemporary History |
| `GEOGRAPHY` | Géographie | Territories, Globalization |
| `EMC` | EMC | Citizenship |
| `SVT` | SVT | Living World, Earth |
| `PHYSICS_CHEMISTRY` | Physique-Chimie | Matter, Energy |

These are reusable domain categories. Their existence does not prove that each
domain is applicable to every grade.

### Grade-bound curriculum

Only these grade/subject combinations have detailed chapters:

| Grade | Subject | Chapters | Skills | Sub-skills | Approved |
|---|---|---:|---:|---:|---:|
| 4e | Mathematics | 8 | 8 | 8 | 16 |
| 4e | French | 6 | 6 | 6 | 12 |
| 3e | Mathematics | 8 | 8 | 8 | 16 |
| 3e | French | 6 | 6 | 6 | 12 |
| 3e | English | 1 | 1 | 1 | 2 |
| 3e | Spanish | 1 | 1 | 1 | 2 |
| 3e | History | 1 | 1 | 1 | 2 |
| 3e | Geography | 1 | 1 | 1 | 2 |
| 3e | SVT | 1 | 1 | 1 | 2 |
| 3e | Physics-Chemistry | 1 | 1 | 1 | 2 |

CM1, CM2, 6e and 5e have school-level reference rows but no programme-subject
curriculum, chapter, grade-bound skill or Approved content.

EMC has a subject/domain reference and appears in the original BREVET
programme, but has no detailed chapter or Approved content. Technology is
present as existing reference data but is outside this ticket's target list.

## Approved content audit

Observed publication state:

- 68 rows in `approved_learning_catalog`;
- 68 active exercises and 68 active questions;
- 68 approved content versions, all at version 1;
- 34 worked examples at difficulty 2;
- 18 exam-practice records at difficulty 3;
- 16 exercise records at difficulty 3.

After removing the exact guided prefix
`Étudier cet exemple guidé puis répondre : ` and comparing normalized
statement + expected answer + pedagogical explanation, there are exactly
34 unique triples. Every unique task has:

1. one guided worked example;
2. one evaluated exercise or exam-practice record.

The pair differs in type, difficulty, evaluative flag, activity metadata and
the guided prefix. The expected answer and explanation are identical. This is
deliberate format variation, not 68 pedagogically distinct tasks.

## Curriculum/content separation

The database supports the required cardinality:

```text
curriculum skill/sub-skill → zero, one or many content records
```

No FK requires a curriculum node to have content. The current empty-state
problem is at the repository query boundary: `subjects_for_grade`, `chapters`
and `skills` in the unified experience deliberately query through
`approved_learning_catalog`. This is correct for a content-selection screen,
but it is not a general curriculum-browser API.

Phase 2 should add curriculum-only read methods to the existing curriculum
repository/service. Learner execution must continue using the Approved view.

## Prerequisite audit

Two representations coexist:

1. `skill_prerequisites`: five simple seed edges, consumed by
   `LearningEngineService`;
2. `curriculum_skill_relations`: 38 versioned, typed and thresholded edges
   imported from the demonstration catalog.

The rich graph supports cross-chapter and cross-grade edges because both ends
reference stable skills; 14 active relation joins currently cross grade
placements. `CatalogValidator.assert_acyclic` rejects self-edges and cycles in
an import document and rejects unknown relation skills.

Limitations:

- database constraints prevent self-edges but do not independently detect
  multi-node cycles;
- runtime prerequisite evaluation does not consume the rich relation table;
- content payloads carry denormalized prerequisite skill IDs;
- imported programme skills are not projected into `program_skills`.

The minimal robust direction is one authoritative rich relation graph, checked
for unknown nodes and cycles at import, with an explicit compatibility
projection for existing Learning Engine consumers until they migrate.

## Identifier strategy

The current convention is suitable:

- numeric database PK: internal persistence identity;
- stable uppercase code: integration/import identity
  (`FR-4E`, `MATHEMATICS`, `CH-*`, `SK-*`, `SUB-*`);
- French label/title: mutable presentation;
- content code + integer version: content identity/version;
- learner `external_ref`: cross-boundary learner identity, unrelated to
  curriculum identity.

Phase 2 should preserve this convention. French labels must never replace
stable codes in relationships.

## UI and hard-coded curriculum search

No chapter, skill, grade or subject curriculum lists were found hard-coded in
`ui/`. The unified Streamlit form obtains its options through repository
queries. `ui/curriculum_state.py` contains only generic dependent-selector
state reconciliation.

Classification:

- French navigation and mode labels: legitimate presentation constants;
- subject/chapter/skill option values: repository-driven;
- no observed reference-data leakage in Streamlit;
- legacy subject question banks under `subjects/` are separate V1 behavior and
  must not be treated as the Phase 2 V2 curriculum.

## Runtime and integration safety

No change is proposed to runtime migration behavior. Migrations remain applied
at process initialization, not during each Streamlit rerun. Repository-owned
DuckDB connections use explicit close/finally handling. Deferred Streamlit
navigation and dependent-selector state remain unchanged.

## Conclusion

The existing architecture should be reused. LCAI-0011B should populate
authoritative reference data and close the projection gaps; it should not
introduce a second curriculum system or generate Approved educational content.
