# Session integration, security and operations

## Integration façade

`SessionApplicationService` coordinates the validated Part 03 services and
adds actor, ownership, recommendation, active-session and idempotency
validation. It does not duplicate recommendation, assessment or mastery rules.
Commands carry an actor, learner, idempotency key, correlation ID and
timestamp. Structured errors expose a safe message and recovery action while
retaining technical diagnostics outside the UI.

## Security

Student mutations require the authenticated learner identity. Parent access is
read-only and requires an active `learner_guardian_links` relationship.
Session, activity and question membership use parameterized SQL. Expected
answers and corrections remain server-side.

## Reliability and versions

Migration 012 adds command idempotency, parent grants, pause intervals, frozen
activity/question/correction references, state tokens, a decision-refresh
queue and bounded read views.

By explicit product direction, the Part 03 answer/mastery pipeline is retained
unchanged. Its repository transaction protects answer, assessment, attempt and
session mastery audit persistence. Cross-repository atomicity with the
longitudinal Learning Engine is not expanded here and remains a review risk.

## Configuration

V1 remains enabled by default:

- `LCAI_ENABLE_V2_UI=false`
- `LCAI_V2_SESSION_EXECUTION_ENABLED=false`
- `LCAI_V2_PARENT_DASHBOARD_ENABLED=false`
- `LCAI_SESSION_AUTOSAVE_INTERVAL_SECONDS=15`
- `LCAI_SESSION_HEARTBEAT_INTERVAL_SECONDS=15`
- `LCAI_SESSION_INACTIVITY_PAUSE_SECONDS=900`
- `LCAI_SESSION_RECOVERY_ENABLED=true`

## Operations

`OperationalHealthService` checks database accessibility, migration level,
required objects, Approved catalogue and flags without writing learner data.
`SessionIntegrityService` detects orphaned execution records and incomplete
terminal states.

```powershell
python -m scripts.measure_session_performance
python scripts/check_quality.py
```

The benchmark reconstructs a temporary V2 database, inserts 100 completed
sessions and 1,000 adaptive attempt inputs, then reports average and p95
dashboard latency. It never touches product databases.

Troubleshooting codes include `ACTIVE_SESSION_EXISTS`, `STATE_CONFLICT`,
`SESSION_ACCESS_DENIED`, `PARENT_ACCESS_DENIED` and `DATABASE_UNAVAILABLE`.
Logs must not include passwords, expected answers or raw learner responses.
