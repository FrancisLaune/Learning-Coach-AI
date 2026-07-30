-- LCAI-0019 Phase 2: additive diagnostic answers, skill states and refresh runs.

ALTER TABLE pedagogical_intelligence_diagnostic_runs ADD COLUMN IF NOT EXISTS current_exercise_id BIGINT;
ALTER TABLE pedagogical_intelligence_diagnostic_runs ADD COLUMN IF NOT EXISTS current_sequence INTEGER;
ALTER TABLE pedagogical_intelligence_diagnostic_runs ADD COLUMN IF NOT EXISTS stop_reason VARCHAR;
ALTER TABLE pedagogical_intelligence_diagnostic_runs ADD COLUMN IF NOT EXISTS computed_confidence DOUBLE;
ALTER TABLE pedagogical_intelligence_diagnostic_runs ADD COLUMN IF NOT EXISTS readiness_score DOUBLE;

UPDATE pedagogical_intelligence_diagnostic_runs
SET current_sequence = 0
WHERE current_sequence IS NULL;

CREATE TABLE pedagogical_intelligence_diagnostic_answers (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    run_id BIGINT NOT NULL REFERENCES pedagogical_intelligence_diagnostic_runs(id),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    exercise_id BIGINT NOT NULL,
    sequence_number INTEGER NOT NULL CHECK (sequence_number > 0),
    normalized_score DOUBLE NOT NULL CHECK (normalized_score BETWEEN 0 AND 100),
    correct BOOLEAN NOT NULL,
    elapsed_ms INTEGER NOT NULL DEFAULT 0 CHECK (elapsed_ms >= 0),
    answer_payload JSON NOT NULL DEFAULT '{}',
    idempotency_key VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pedagogical_intelligence_diagnostic_skill_states (
    run_id BIGINT NOT NULL REFERENCES pedagogical_intelligence_diagnostic_runs(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    confidence DOUBLE NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    mastery_score DOUBLE NOT NULL CHECK (mastery_score BETWEEN 0 AND 1),
    assessed BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, skill_id)
);

CREATE TABLE pedagogical_intelligence_refresh_runs (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    session_id BIGINT NOT NULL,
    pathway_code VARCHAR NOT NULL,
    refresh_version VARCHAR NOT NULL DEFAULT 'pi-v1',
    status VARCHAR NOT NULL CHECK (status IN ('COMPLETED', 'PARTIAL', 'FAILED')),
    correlation_id VARCHAR NOT NULL,
    result_snapshot JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (learner_id, session_id, pathway_code, refresh_version)
);

CREATE INDEX idx_pi_diag_answers_run_seq ON pedagogical_intelligence_diagnostic_answers(run_id, sequence_number);
CREATE INDEX idx_pi_diag_answers_learner ON pedagogical_intelligence_diagnostic_answers(learner_id, created_at DESC);
CREATE INDEX idx_pi_refresh_runs_learner_session ON pedagogical_intelligence_refresh_runs(learner_id, session_id);
CREATE INDEX idx_pi_refresh_runs_pathway_status ON pedagogical_intelligence_refresh_runs(pathway_code, status, created_at DESC);
