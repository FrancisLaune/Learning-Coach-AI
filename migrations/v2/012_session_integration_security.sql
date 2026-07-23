-- LCAI-0010 Part 05: additive integration, authorization and reliability state.

CREATE TABLE learner_guardian_links (
    guardian_external_ref VARCHAR NOT NULL,
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ,
    PRIMARY KEY (guardian_external_ref, learner_id)
);

CREATE TABLE session_command_results (
    idempotency_key VARCHAR PRIMARY KEY,
    session_id BIGINT REFERENCES learning_sessions(id),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    command_type VARCHAR NOT NULL,
    correlation_id VARCHAR NOT NULL,
    result_payload JSON NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE session_pause_intervals (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    session_id BIGINT NOT NULL REFERENCES learning_sessions(id),
    paused_at TIMESTAMPTZ NOT NULL,
    resumed_at TIMESTAMPTZ,
    pause_reason VARCHAR,
    actor_ref VARCHAR NOT NULL,
    automatic BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (resumed_at IS NULL OR resumed_at >= paused_at)
);

CREATE TABLE session_activity_snapshots (
    activity_id BIGINT PRIMARY KEY REFERENCES session_activities(id),
    content_version_number INTEGER NOT NULL,
    question_version_ids JSON NOT NULL,
    correction_version_ids JSON NOT NULL,
    curriculum_version VARCHAR NOT NULL,
    assessment_contract_version VARCHAR NOT NULL,
    frozen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE session_state_revisions (
    session_id BIGINT PRIMARY KEY REFERENCES learning_sessions(id),
    revision_number BIGINT NOT NULL DEFAULT 1,
    state_token VARCHAR NOT NULL UNIQUE,
    active_client_ref VARCHAR,
    heartbeat_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE decision_refresh_queue (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    session_id BIGINT NOT NULL UNIQUE REFERENCES learning_sessions(id),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    status VARCHAR NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    correlation_id VARCHAR NOT NULL,
    last_error_code VARCHAR,
    next_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_guardian_links_active
    ON learner_guardian_links(guardian_external_ref, active);
CREATE INDEX idx_command_results_session
    ON session_command_results(session_id, command_type);
CREATE INDEX idx_pause_intervals_session_time
    ON session_pause_intervals(session_id, paused_at);
CREATE INDEX idx_refresh_queue_status
    ON decision_refresh_queue(status, next_attempt_at);

CREATE VIEW v_active_learning_sessions AS
SELECT s.learner_id, d.*
FROM learning_session_details d
JOIN learning_sessions s ON s.id = d.session_id
WHERE d.status IN ('READY','RUNNING','PAUSED') AND d.archived_at IS NULL;

CREATE VIEW v_session_progress AS
SELECT d.session_id, s.learner_id, d.status, d.planned_duration_seconds,
       count(a.id) AS activity_count,
       count(a.id) FILTER (WHERE a.status='COMPLETED') AS completed_activity_count,
       coalesce(avg(a.score) FILTER (WHERE a.status='COMPLETED'), 0) AS current_score
FROM learning_session_details d
JOIN learning_sessions s ON s.id=d.session_id
LEFT JOIN session_activities a ON a.session_id=d.session_id AND a.archived_at IS NULL
GROUP BY d.session_id,s.learner_id,d.status,d.planned_duration_seconds;

CREATE VIEW v_learner_session_history AS
SELECT s.learner_id,d.session_id,d.creation_time,d.end_time,d.actual_duration_seconds,
       d.session_score,d.estimated_mastery_gain,d.completion_rate
FROM learning_session_details d
JOIN learning_sessions s ON s.id=d.session_id
WHERE d.status='COMPLETED' AND d.archived_at IS NULL;
