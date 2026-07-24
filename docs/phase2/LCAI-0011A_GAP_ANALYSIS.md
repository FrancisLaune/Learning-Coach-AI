# LCAI-0011A — Gap Analysis

## Missing curriculum structure

### Blocking for curriculum expansion

| Gap | Evidence | Recommended LCAI-0011B action |
|---|---|---|
| CM1 curriculum absent | Grade exists; zero programme-subject mappings, chapters and placements | Import validated programme/reference data. |
| CM2 curriculum absent | Same | Import validated programme/reference data. |
| 6e curriculum absent | Same | Import validated programme/reference data. |
| 5e curriculum absent | Same | Import validated programme/reference data. |
| 4e limited to Mathematics and French | 14 chapters total | Expand only from reviewed curriculum sources. |
| 3e highly uneven | Mathematics/French have several nodes; six subjects have one; EMC has none | Complete the hierarchy before content generation. |
| Grade applicability of generic domains is implicit | 21 subject domains exist without grade mapping | Express applicability through validated chapters; do not duplicate domains per grade without need. |
| Programme skills not populated for imported programmes | `program_skills` has 25 rows for original BREVET only | Deterministically project imported curriculum placements for Learning Engine consumption. |

## Missing educational content

- CM1, CM2, 6e and 5e: zero Approved records.
- 4e: Approved records only for 14 targeted Mathematics/French nodes.
- 3e: Approved records only for 20 targeted nodes.
- EMC: zero Approved content.
- The 68 records contain only 34 normalized pedagogical tasks.
- No current content version is greater than 1.
- Existing content is a demonstration lot and must not be represented as a
  complete official programme.

These are content/data gaps, not schema defects.

## Architecture gaps

### Dual prerequisite representations

`skill_prerequisites` is consumed by the Learning Engine; the richer
`curriculum_skill_relations` is authored by the current catalog importer.
Maintaining both independently risks divergent decisions.

Recommendation: make the rich relation authoritative and retain a deterministic
compatibility adapter/projection until all consumers migrate.

### Dual programme-skill paths

The Learning Engine loads `program_skills`; imported curriculum places skills
through `curriculum_skill_details` but does not populate `program_skills`.
Consequently, a valid imported programme may have chapters and Approved
content while returning no Learning Engine curriculum context.

Recommendation: define and test the projection during LCAI-0011B.

### Curriculum reads are content-backed in unified experience

The homework/revision repository correctly queries
`approved_learning_catalog`, but those methods cannot serve a curriculum
browser because zero-content nodes disappear.

Recommendation: add curriculum-only reads to the existing curriculum
repository/service. Keep execution selection Approved-backed.

### Import document couples structure and content

The current JSON contains programmes, chapters, skills, sub-skills, relations,
exam references and contents in one file. The service technically accepts
empty arrays, but there is no explicit Phase 2 curriculum-only contract or
coverage report.

Recommendation: define a validated curriculum-reference manifest and dry-run
report without building another importer framework.

### Graph validation scope

Cycle validation checks relations in the incoming document. It does not prove
that merging a partial import with existing active relations remains acyclic.

Recommendation: validate the complete post-import graph transactionally.

## Data-quality gaps

- Grade `rank` values are not unique across primary/collège/lycée.
- Twenty-five seed skills are not mapped by `curriculum_skill_details`.
- Six seed sub-skills belong to those unmapped skills.
- Thirty-eight rich relations and five simple prerequisites coexist.
- Fourteen rich relation joins cross grades; these require source/rationale
  review, not automatic rejection.
- All 34 imported skills use one generic “Mobiliser” skill and one
  “Application guidée” sub-skill per chapter. This is structurally valid but
  too coarse for a complete curriculum.
- Each existing curriculum node has exactly two Approved records and one
  normalized pedagogical task, which is inadequate for repeated adaptive
  practice.

## Legacy concerns

- The V1 `subjects/` question banks are user-visible legacy behavior but are
  not the V2 curriculum source of truth.
- `domain.content`/`services.content` provide the earlier general content
  management vocabulary; `domain.curriculum` and
  `DuckDBCurriculumRepository` provide the stricter LCAI-0009 publication
  path. They share database entities and should be converged incrementally,
  not deleted or duplicated.
- Compatibility question/exercise tables remain actively used by execution
  and cannot be removed during curriculum expansion.

## Deferred technical debt

Out of scope for LCAI-0011A and not required before reference-data modelling:

- UI redesign;
- content factory or mass content generation;
- V1 retirement;
- lycée curriculum;
- password/security work;
- Decision Engine or Learning Engine redesign;
- replacing the current editorial lifecycle.

## LCAI-0011B readiness

**READY FOR LCAI-0011B**, subject to these implementation constraints:

1. use the existing hierarchy and stable codes;
2. import curriculum structure before educational content;
3. populate only source-validated grade/subject combinations;
4. close the `program_skills` and prerequisite compatibility projections;
5. add curriculum-only read APIs while preserving Approved-only execution;
6. validate the complete prerequisite graph;
7. use additive migration `017+` only if a demonstrated schema blocker remains;
8. preserve all existing Parent, Student, Learning Engine and Decision Engine
   behavior.
