# Learning Intelligence Layer

## Purpose and boundaries

LCAI-0010 Part 06 derives deterministic, explainable indicators from committed
session evidence. It does not modify answers, assessments, mastery, curriculum
or Approved content. No LLM, psychological inference, official mark prediction
or cross-learner comparison is used.

The dependency flow is:

```text
Analytics controllers
  → LearningIntelligenceService
  → pure learning_intelligence policies
  → evidence/snapshot ports
  → DuckDB V2 adapters
```

## Evidence and canonical scales

`LearningEvidence` references the persisted session, activity, attempt,
assessment, skill, content and version. Draft answers are excluded at query
time. Scores use 0–100; mastery and confidence retain the existing 0–1
Learning Engine scale. Invalid scores, durations or difficulties are excluded
from decisions and counted by rebuild reports.

Supported windows include custom, 7-day, 14-day and current-month windows.
Every result includes the window, calculation version, evidence count,
explanation code, parameters and source attempt references.

## Versioned policy

Calculation version: `learning-intelligence-v1`.
Configuration version: `learning-intelligence-thresholds-v1`.

- strength: at least 5 assessed attempts;
- weakness: at least 4 assessed attempts;
- recurring error: 3 occurrences of the same structured code;
- trend: at least 3 assessment dates;
- emerging strength: mastery and accuracy at least 70%;
- established strength: mastery and accuracy at least 80%;
- stable strength: mastery and accuracy at least 85%, cross-session evidence
  and acceptable hint use;
- fragile: mastery or accuracy below 55% after minimum evidence.

A single failure produces `WATCH`, not a weakness classification. Difficulty
guidance is `INCREASE`, `MAINTAIN`, `DECREASE`, `MIX`, `REASSESS` or
`INSUFFICIENT_DATA`; content selection remains owned by Decision and
Recommendation services.

## Reused Learning Engine semantics

Mastery, mastery confidence, trend, forgetting adjustment, prerequisite
evaluation, difficulty recommendation and readiness remain defined by
`domain.learning`. The intelligence layer explains their persisted results and
does not introduce a second mastery or forgetting formula.

## Persistence and rebuild

Migration `013_learning_intelligence_layer.sql` adds only rebuildable derived
records:

- calculation runs;
- versioned snapshots;
- structured explanations;
- recurring-error observations;
- parent insights.

Raw evidence is not copied into snapshots. Stable SHA-256 keys make identical
rebuild inputs idempotent. Failed and superseded runs remain auditable.

Dry run:

```powershell
python -m scripts.rebuild_learning_intelligence --learner-id 100000 --dry-run
```

Dry-run performs zero writes. A normal rebuild changes only derived Part 06
tables.

## Security and wording

Parent analytics requires an active guardian relationship. Query results never
contain raw answers, answer keys or hidden correction rules. Student wording
must remain factual and encouraging; parent wording must remain supportive and
actionable. Localization belongs to presentation.

## Known integration boundary

Part 03 remains unchanged by product direction. Consequently, Part 06 creates
typed `DecisionEvidenceBundle` values but does not claim that the previously
deferred Journey mutation and Decision refresh execution are complete.
Analytics failure must not roll back a completed session; retry orchestration
remains an integration-review item.
