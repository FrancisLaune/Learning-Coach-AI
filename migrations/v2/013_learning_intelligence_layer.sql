-- LCAI-0010 Part 06: rebuildable, versioned derived analytics only.

CREATE TABLE analytics_calculation_runs (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    stable_key VARCHAR NOT NULL UNIQUE,
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    calculation_type VARCHAR NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    calculation_version VARCHAR NOT NULL,
    configuration_version VARCHAR NOT NULL,
    source_cutoff_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    status VARCHAR NOT NULL CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED','SUPERSEDED')),
    result_count INTEGER NOT NULL DEFAULT 0,
    error_code VARCHAR,
    CHECK (window_end >= window_start)
);

CREATE TABLE learning_analytics_snapshots (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    stable_key VARCHAR NOT NULL UNIQUE,
    run_id BIGINT NOT NULL REFERENCES analytics_calculation_runs(id),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    scope_type VARCHAR NOT NULL,
    scope_id BIGINT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    calculation_version VARCHAR NOT NULL,
    source_cutoff_at TIMESTAMPTZ NOT NULL,
    facts JSON NOT NULL,
    indicators JSON NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUPERSEDED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE learning_explanations (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    snapshot_id BIGINT NOT NULL REFERENCES learning_analytics_snapshots(id),
    subject_type VARCHAR NOT NULL,
    subject_id BIGINT NOT NULL,
    decision_code VARCHAR NOT NULL,
    result_code VARCHAR NOT NULL,
    primary_reason_code VARCHAR NOT NULL,
    secondary_reason_codes JSON NOT NULL DEFAULT '[]',
    parameters JSON NOT NULL,
    evidence_references JSON NOT NULL,
    policy_version VARCHAR NOT NULL,
    calculation_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_id,subject_type,subject_id,decision_code)
);

CREATE TABLE recurring_error_observations (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    snapshot_id BIGINT NOT NULL REFERENCES learning_analytics_snapshots(id),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    error_code VARCHAR NOT NULL,
    occurrence_count INTEGER NOT NULL CHECK (occurrence_count > 0),
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    severity VARCHAR NOT NULL,
    evidence_references JSON NOT NULL,
    UNIQUE(snapshot_id,skill_id,error_code)
);

CREATE TABLE parent_learning_insights (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    snapshot_id BIGINT NOT NULL REFERENCES learning_analytics_snapshots(id),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    category VARCHAR NOT NULL,
    priority INTEGER NOT NULL,
    title_code VARCHAR NOT NULL,
    message_code VARCHAR NOT NULL,
    message_parameters JSON NOT NULL,
    recommended_parent_action_code VARCHAR,
    calculation_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analytics_runs_learner_window
    ON analytics_calculation_runs(learner_id,window_start,window_end);
CREATE INDEX idx_analytics_snapshots_learner_scope
    ON learning_analytics_snapshots(learner_id,scope_type,scope_id,created_at);
CREATE INDEX idx_recurring_errors_learner_skill
    ON recurring_error_observations(learner_id,skill_id,last_seen_at);
CREATE INDEX idx_parent_insights_learner_time
    ON parent_learning_insights(learner_id,created_at);
