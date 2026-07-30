-- LCAI-0019: additive pedagogical intelligence diagnostic runs (V1).

CREATE TABLE pedagogical_intelligence_diagnostic_runs (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    path_code VARCHAR NOT NULL CHECK (path_code IN ('CM1_TO_CM2', 'FR_4E_TO_3E')),
    status VARCHAR NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'ABANDONED')),
    questions_asked INTEGER NOT NULL DEFAULT 0 CHECK (questions_asked >= 0),
    confidence_threshold DOUBLE NOT NULL DEFAULT 0.85 CHECK (confidence_threshold BETWEEN 0 AND 1),
    target_skill_ids JSON NOT NULL DEFAULT '[]',
    assessed_skill_ids JSON NOT NULL DEFAULT '[]',
    confidence_by_skill JSON NOT NULL DEFAULT '{}',
    current_skill_id BIGINT REFERENCES skills(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pi_diagnostic_runs_learner_status
    ON pedagogical_intelligence_diagnostic_runs(learner_id, status, updated_at DESC);
