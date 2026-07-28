# LCAI-0013B — Codex Integration Handoff V1

## Goal

Integrate the prepared DNB library as an adaptive revision source for the virtual teacher.

## Do not build a year-first student experience

Year, zone and official reference are provenance fields.

The primary query path should be:

`grade → subject → Skill → mastery/error → usage → difficulty → compatible DNB question`

## Required target entities

A normalized imported item should support, at minimum:

- source exam metadata;
- source component / exercise / question identifier;
- subject;
- chapter;
- primary Skill;
- secondary Skills;
- difficulty;
- estimated time;
- response type;
- curriculum compatibility;
- usage flags: practice / assessment / revision / remediation / mock exam;
- required asset references;
- provenance URL/reference.

## Virtual-teacher behavior

### Guided practice
Hints are progressive and should not reveal the answer immediately.

### Revision
Mix compatible questions from different years around the same weak Skill.

### Assessment
No assistance until submission.

### Mock exam
Timer and exam-mode behavior; feedback only after completion.

### Remediation
Select a focused, usually easier or equivalent question addressing the diagnosed error.

## Student display

Default:
`Entraînement Brevet — <Subject> — <Skill>`

Do not display the year unless requested or pedagogically useful.

## Safety / quality gates

- never expose Draft content;
- never drop required documents/figures;
- never infer exact Skill IDs from loose keyword matching without review;
- never treat historical scoring rules as current exam rules;
- preserve official-source provenance.

## Recommended next implementation ticket

`LCAI-0013C — DNB Skill Mapping, Asset Ingestion & Virtual Teacher Revision Integration`
