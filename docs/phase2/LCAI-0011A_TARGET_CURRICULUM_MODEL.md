# LCAI-0011A — Target Curriculum Model

## Design decision

Extend the existing V2 curriculum. Do not create a parallel hierarchy.

```text
Programme
  → Grade (programme_subjects.school_level_id)
    → Subject (programme_subjects.subject_id)
      → Domain (domains.subject_id)
        → Chapter (curriculum_chapters)
          → Skill placement (curriculum_skill_details → skills)
            → Sub-skill (subskills)
              → Prerequisite relation (curriculum_skill_relations)
```

Content remains downstream and optional:

```text
Skill/Sub-skill
  → 0..n learning_content_metadata / question mappings
    → content version
      → editorial approval
        → approved_learning_catalog
```

## Concept mapping

| Target concept | Existing structure | Action | Reason |
|---|---|---|---|
| Programme | `programs` | Reuse/extend data | Already versioned, dated and jurisdiction-aware. |
| Grade | `school_levels` plus `program_subjects.school_level_id` | Reuse | All six target grades exist. |
| Subject | `subjects` plus `program_subjects` | Reuse/extend associations | All nine target subject identities exist. |
| Domain | `domains` | Reuse/extend data cautiously | Stable subject-scoped domains already exist. Applicability must come from validated curriculum data. |
| Chapter | `curriculum_chapters` | Reuse/extend data | Already programme-, subject-, domain-, grade-, version- and status-aware. |
| Skill | `skills` stable identity + `curriculum_skill_details` placement | Reuse/extend data | Separates stable skill identity from grade/chapter curriculum metadata. |
| Sub-skill | `subskills` | Reuse/extend data | Existing stable child identity is adequate. |
| Observable objective | `learning_objectives` + `skill_learning_objectives` | Reuse | Already linked to chapters and skills. |
| Prerequisite | `curriculum_skill_relations` | Reuse as authoritative Phase 2 graph | Supports types, progression roles, thresholds, rationale, versions and cross-grade edges. |
| Learning Engine compatibility | `skill_prerequisites`, `program_skills` | Retain temporarily; add explicit projection/adapter | Existing Learning Engine reads these tables. Removing or bypassing them would regress validated behavior. |
| Educational content | Existing exercise/question/content metadata/version tables | Reuse | Complete lifecycle and mappings already exist. |
| Learner-eligible content | `approved_learning_catalog` | Reuse without weakening | Correctly enforces active current version and approval. |

No new table is required by LCAI-0011A.

## Stable identifier rules

1. Numeric `id` remains the database PK and must never appear in authored
   curriculum files.
2. Stable codes are the import/integration identity:
   - grade: `FR-CM1`, `FR-6E`, `FR-3E`;
   - subject: `MATHEMATICS`, `FRENCH`;
   - chapter: existing `CH-{SUBJECT}-{GRADE}-{TOKEN}` convention;
   - skill: existing `SK-{SUBJECT}-{GRADE}-{TOKEN}` convention;
   - sub-skill: existing `SUB-{SUBJECT}-{GRADE}-{TOKEN}` convention.
3. French titles and labels are presentation values and may evolve without
   changing relationships.
4. Versions are explicit; a changed meaning must produce a new version or a
   new stable code, not silently reuse an incompatible identity.
5. Codes must be globally unique where the database already enforces global
   uniqueness. The importer should validate this before persistence.

## Programme and grade strategy

LCAI-0011B should define explicit, source-backed programme records for the
supported curriculum scope and link applicable subjects per grade. It must not
create every grade × subject Cartesian product.

The import format should allow:

```text
programmes and programme-subject-grade mappings
chapters
skills and placements
sub-skills
objectives
relations
```

without requiring a `contents` array. An empty `contents` array is a valid
curriculum import.

## Prerequisite strategy

`curriculum_skill_relations` should be the authoritative authored relation:

- edge direction: prerequisite skill → target skill;
- allowed cross-chapter and cross-grade edges;
- typed relation and progression role;
- `mandatory` and mastery threshold;
- human rationale and source;
- active/version lifecycle.

Import validation must:

- reject unknown endpoints;
- reject self-edges;
- detect cycles across the complete resulting graph, not only the incoming
  file;
- allow cross-grade edges only when both skill placements exist;
- ensure prerequisite grade progression is pedagogically coherent or carries
  an explicit reviewed rationale.

For compatibility, LCAI-0011B should define one deterministic adapter or
projection from required active rich relations into the simple prerequisite
shape consumed by `LearningEngineService`. Do not maintain two independently
authored graphs.

## Curriculum integrity rules

### Hierarchy

- A programme-subject mapping references an existing programme, grade and
  subject.
- A chapter belongs to exactly one programme, grade, subject and compatible
  subject domain.
- A skill placement belongs to a chapter and the same grade.
- A sub-skill references an existing skill.
- A learning objective references the same chapter/skill branch.

### Referential and semantic integrity

- No orphan chapter, skill placement, sub-skill, objective or relation.
- A chapter's `domain_id` must belong to its `subject_id`.
- A skill's domain must match its chapter's domain unless a reviewed explicit
  cross-domain model is introduced later.
- Stable codes are unique and non-empty.
- Sequence values are deterministic within their parent.
- Difficulty ranges are valid and placement difficulty is within the chapter
  range.
- Effective dates and versions cannot overlap ambiguously for the same stable
  code.
- Only supported Phase 2 grades are accepted by the Phase 2 importer.

### Content integrity

- Content may reference only existing programme/grade/subject/chapter/skill
  and optional sub-skill nodes.
- Content subject, chapter domain, skill domain and grade must agree.
- Approved publication continues to require a current approved version,
  validation, review and active approval.
- Curriculum nodes with zero content remain valid.
- Learner execution never substitutes content from another subject or grade.

### Selector integrity

- UI option values come from repository APIs, never presentation lists.
- Changing subject clears chapter and skill state.
- Changing chapters removes invalid skills.
- Curriculum browsing and Approved content selection use separate repository
  methods so an empty content catalog cannot erase a valid curriculum.

## Repository and service boundaries

Extend `DuckDBCurriculumRepository` and `CurriculumService` rather than adding
a second repository family:

- curriculum inventory by grade/subject;
- hierarchy read model independent of Approved content;
- deterministic import of curriculum-only documents;
- integrity report and graph validation;
- compatibility projection status for Learning Engine programme skills and
  prerequisites.

Keep:

- SQL in infrastructure repositories;
- validation and mapping policy in domain/services;
- Streamlit limited to rendering and orchestration;
- recommendation/execution restricted to `approved_learning_catalog`.

## Future import sequence

Recommended LCAI-0011B workflow:

1. load source document and calculate checksum;
2. validate stable codes and supported grades;
3. resolve all existing references;
4. build the complete post-import prerequisite graph and reject cycles;
5. dry-run and emit counts/diffs;
6. transactionally upsert programme mappings and curriculum nodes;
7. build deterministic compatibility projections for existing consumers;
8. commit and record import/domain events;
9. report zero-content nodes honestly;
10. do not create Approved content.

If additive schema support is demonstrated to be necessary during LCAI-0011B,
use migration `017` or the next number actually available at that time.
Historical migrations `001`–`016` must remain untouched.

## Runtime connections

- Onboarding selects stable grade/subject references.
- Curriculum services expose the structural hierarchy.
- Candidate selection and PersonalizedSessionService continue loading only
  Approved content.
- Decision Engine receives candidates and prerequisite projections; it is not
  bypassed.
- Learning Engine retains longitudinal mastery by stable skill IDs.
- Session orchestration and assessment continue executing versioned Approved
  content only.
- Student and parent UI behavior remains unchanged until a later explicitly
  scoped integration ticket.
