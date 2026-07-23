# Learning Session orchestration

## Scope

LCAI-0010 Parts 03-A to 03-D add an optional V2 application layer. It is
independent from Streamlit and does not change the V1 execution path.

The implementation is split into deterministic, testable services:

- `LearningSessionService` creates and controls a persisted session;
- `SessionScheduler` accepts only current Approved content, validates duration,
  difficulty, questions, assessment availability and duplicates;
- `ActivityPipelineBuilder`, `ActivityRunner` and `SessionStateManager` execute
  one selected activity through the documented lifecycle;
- `AutoSaveService`, `OfflineBuffer` and `ResumeService` provide atomic
  answer/checkpoint/event saves and ownership-checked recovery;
- `DeterministicAssessmentEngine` normalizes and evaluates supported answer
  types without an LLM;
- `SubmissionService` enforces the order assessment, Learning Engine update,
  attempt persistence, then Decision Engine notification.

## Determinism and auditability

All decisions depend exclusively on persisted inputs and explicit request
parameters. Assessment results expose their strategy, raw score, penalties,
bonus and mastery delta. Attempts use caller-provided idempotency keys. Session
events, checkpoints, content versions and engine versions preserve the
execution context required for audit and replay.

The generic `QuestionView` DTO deliberately contains no framework object. The
future UI adapter may render it without placing Streamlit concerns in the
domain or application services.

## Recovery contract

The default heartbeat interval is 15 seconds. Autosave writes the draft answer,
checkpoint and audit event in one DuckDB transaction. A failed write enters a
bounded, idempotent in-memory buffer. Resume is allowed only for the owning
learner and a `PAUSED` session with a valid checkpoint.

## Compatibility

The implementation reuses the additive Part 02 V2 schema and repositories.
No V1 database, pedagogical content or existing UI route is modified. V1
remains the default product behavior.
