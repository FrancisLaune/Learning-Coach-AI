-- LCAI-0022D — Professor AI decision journal (additive)
CREATE TABLE IF NOT EXISTS ai_decision_log (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    correlation_id VARCHAR NOT NULL,
    operating_mode VARCHAR NOT NULL
        CHECK (operating_mode IN ('PROFESSOR', 'COMPANION', 'MANUAL')),
    cycle_step VARCHAR NOT NULL,
    objective VARCHAR,
    justification VARCHAR NOT NULL,
    engine_version VARCHAR NOT NULL,
    candidates_json JSON NOT NULL DEFAULT '[]',
    exclusions_json JSON NOT NULL DEFAULT '[]',
    deficit_json JSON NOT NULL DEFAULT '{}',
    context_json JSON NOT NULL DEFAULT '{}',
    homework_id BIGINT,
    session_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_decision_log_learner_time
    ON ai_decision_log(learner_id, created_at);

CREATE INDEX IF NOT EXISTS idx_ai_decision_log_correlation
    ON ai_decision_log(correlation_id, created_at);
