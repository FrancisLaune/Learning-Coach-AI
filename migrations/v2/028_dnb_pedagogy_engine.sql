-- LCAI-0031 Phase 3 — pedagogical decision / remediation / readiness snapshots (additive).

CREATE TABLE IF NOT EXISTS brevet_readiness_snapshots (
    id BIGINT PRIMARY KEY,
    learner_id BIGINT NOT NULL,
    score DOUBLE NOT NULL,
    band VARCHAR NOT NULL,
    mastery DOUBLE NOT NULL,
    coverage DOUBLE NOT NULL,
    stability DOUBLE NOT NULL,
    exam_performance DOUBLE NOT NULL,
    critical_gap_penalty DOUBLE NOT NULL,
    explanation VARCHAR NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prerequisite_remediation_runs (
    id BIGINT PRIMARY KEY,
    learner_id BIGINT NOT NULL,
    target_skill_id BIGINT NOT NULL,
    prerequisite_skill_id BIGINT NOT NULL,
    status VARCHAR NOT NULL,
    estimated_minutes INTEGER NOT NULL,
    reason VARCHAR NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS pedagogical_decision_log (
    decision_id VARCHAR PRIMARY KEY,
    learner_id BIGINT NOT NULL,
    decision_type VARCHAR NOT NULL,
    inputs JSON NOT NULL,
    output JSON NOT NULL,
    reason VARCHAR NOT NULL,
    confidence DOUBLE,
    rules_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
