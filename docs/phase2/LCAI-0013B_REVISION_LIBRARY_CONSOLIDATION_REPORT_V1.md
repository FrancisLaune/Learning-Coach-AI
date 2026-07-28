# LCAI-0013B — DNB Revision Library Consolidation V1

## Product orientation

The DNB archive is consolidated as a **Skill-driven revision library**, not as a chronology-driven archive.

The learner does not need to know whether a useful exercise comes from 2018, 2023 or 2026. The source year is retained for provenance, audit and exam-format compatibility, while learner selection is driven by:

- Skill / sub-skill;
- mastery level;
- error category;
- difficulty;
- pedagogical usage;
- estimated time;
- compatibility with the current curriculum.

## Consolidated inventory

- Unique exam/source records found in prepared LCAI-0013B artifacts: **28**
- JSON artifacts consolidated: **30**
- Markdown reports consolidated: **7**
- JSON parse errors: **0**

## Learner-facing usages

Each normalized DNB question/exercise may support one or more of:

- PRACTICE
- ASSESSMENT
- REVISION
- REMEDIATION
- MOCK_EXAM

The same authentic question may therefore be reused outside its original full paper when its Skill mapping and required source materials are preserved.

## Virtual teacher

The virtual teacher is expected to orchestrate:

1. guided practice with progressive hints;
2. adaptive revision by weak Skill;
3. assessment without live help;
4. mock exam conditions with delayed feedback;
5. remediation targeted to the diagnosed error.

The year of the source must not be used as a proxy for difficulty.

## Curriculum compatibility

Historical DNB questions should be classified as:

- CURRENT_CURRICULUM_COMPATIBLE
- PARTIALLY_COMPATIBLE
- NOT_RECOMMENDED

This compatibility status is more important for selection than the original exam year.

## Critical integration requirements

Before student use, Codex must resolve:

- exact LCAI-0011C 3e `chapter_code`;
- exact `primary_skill_code` and secondary Skills;
- curriculum compatibility;
- difficulty;
- expected time;
- response type;
- required documents/images/graphs/tables/Scratch assets.

## Known gaps

- Exact LCAI-0011C Skill IDs are not yet resolved for most historical records.
- Some multi-subject records are source-level inventories rather than full question decompositions.
- French 2021 decomposition is incomplete.
- HG-EMC 2021 general-series source was intentionally left unresolved in the prepared V1 block.
- Some science second-discipline details remain at component level.
- Document/image/graph/annex assets are referenced but not yet ingested as a managed asset library.
- 2016-2017 remain outside the official Eduscol core and require a separately sourced archive if still desired.

## Database

This consolidation does not modify DuckDB and does not create Approved educational content.
