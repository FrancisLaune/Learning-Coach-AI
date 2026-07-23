-- LCAI-0010 Part 02 preserves the existing learning_sessions, session_exercises
-- and attempts tables. New execution details are additive and linked to them.

CREATE TABLE learning_session_details (
    session_id BIGINT PRIMARY KEY REFERENCES learning_sessions(id),
    journey_version_id BIGINT NOT NULL REFERENCES learner_journey_versions(id),
    proposal_id BIGINT NOT NULL REFERENCES personalized_session_proposals(id),
    status VARCHAR NOT NULL CHECK (status IN ('CREATED','READY','RUNNING','PAUSED','COMPLETED','ABANDONED','FAILED','ARCHIVED')),
    creation_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    planned_duration_seconds INTEGER NOT NULL CHECK (planned_duration_seconds >= 0),
    actual_duration_seconds INTEGER NOT NULL DEFAULT 0 CHECK (actual_duration_seconds >= 0),
    estimated_mastery_gain DOUBLE NOT NULL DEFAULT 0 CHECK (estimated_mastery_gain BETWEEN -100 AND 100),
    completion_rate DOUBLE NOT NULL DEFAULT 0 CHECK (completion_rate BETWEEN 0 AND 100),
    session_score DOUBLE NOT NULL DEFAULT 0 CHECK (session_score BETWEEN 0 AND 100),
    session_version INTEGER NOT NULL DEFAULT 1 CHECK (session_version > 0),
    application_version VARCHAR NOT NULL,
    curriculum_version VARCHAR NOT NULL,
    content_version VARCHAR NOT NULL,
    decision_engine_version VARCHAR NOT NULL,
    assessment_engine_version VARCHAR NOT NULL,
    archived_at TIMESTAMPTZ,
    CHECK (end_time IS NULL OR start_time IS NULL OR end_time >= start_time)
);

CREATE TABLE session_activities (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    session_id BIGINT NOT NULL REFERENCES learning_sessions(id),
    proposal_item_id BIGINT REFERENCES personalized_session_items(id),
    content_id BIGINT NOT NULL REFERENCES exercises(id),
    content_version_id BIGINT NOT NULL REFERENCES content_versions(id),
    activity_order INTEGER NOT NULL CHECK (activity_order > 0),
    activity_type VARCHAR NOT NULL,
    difficulty SMALLINT NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
    estimated_duration_seconds INTEGER NOT NULL CHECK (estimated_duration_seconds >= 0),
    status VARCHAR NOT NULL DEFAULT 'NOT_STARTED' CHECK (status IN ('NOT_STARTED','RUNNING','PAUSED','COMPLETED','SKIPPED','FAILED')),
    score DOUBLE NOT NULL DEFAULT 0 CHECK (score BETWEEN 0 AND 100),
    mastery_delta DOUBLE NOT NULL DEFAULT 0 CHECK (mastery_delta BETWEEN -100 AND 100),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    UNIQUE (session_id, activity_order),
    UNIQUE (session_id, proposal_item_id),
    CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)
);

CREATE TABLE student_answers (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    activity_id BIGINT NOT NULL REFERENCES session_activities(id),
    question_id BIGINT NOT NULL REFERENCES content_questions(id),
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    answer_type VARCHAR NOT NULL CHECK (answer_type IN ('INTEGER','DECIMAL','TEXT','SHORT_TEXT','LONG_TEXT','BOOLEAN','FRACTION','MCQ_SINGLE','MCQ_MULTI','MATCHING','ORDERING','FORMULA')),
    raw_answer JSON NOT NULL,
    normalized_answer JSON NOT NULL,
    submission_time TIMESTAMPTZ NOT NULL,
    time_spent_ms BIGINT NOT NULL CHECK (time_spent_ms >= 0),
    draft BOOLEAN NOT NULL DEFAULT TRUE,
    validated BOOLEAN NOT NULL DEFAULT FALSE,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    archived_at TIMESTAMPTZ,
    UNIQUE (activity_id, question_id, attempt_number)
);

CREATE TABLE answer_assessments (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    answer_id BIGINT NOT NULL UNIQUE REFERENCES student_answers(id),
    correct BOOLEAN NOT NULL,
    score DOUBLE NOT NULL CHECK (score BETWEEN 0 AND 100),
    penalty DOUBLE NOT NULL DEFAULT 0 CHECK (penalty >= 0),
    hint_penalty DOUBLE NOT NULL DEFAULT 0 CHECK (hint_penalty >= 0),
    time_penalty DOUBLE NOT NULL DEFAULT 0 CHECK (time_penalty >= 0),
    assessment_method VARCHAR NOT NULL CHECK (assessment_method IN ('EXACT_MATCH','NUMERIC_EQUALITY','NUMERIC_TOLERANCE','FRACTION_SIMPLIFICATION','BOOLEAN','MCQ','MATCHING','ORDERING','FORMULA')),
    feedback_generated JSON NOT NULL,
    assessment_engine_version VARCHAR NOT NULL,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- The historical attempts table remains the canonical immutable question
-- attempt. This record adds the new bounded-context relationships without
-- changing its existing insert contract.
CREATE TABLE session_attempt_records (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    legacy_attempt_id BIGINT NOT NULL UNIQUE REFERENCES attempts(id),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    activity_id BIGINT NOT NULL REFERENCES session_activities(id),
    answer_id BIGINT NOT NULL UNIQUE REFERENCES student_answers(id),
    assessment_id BIGINT NOT NULL UNIQUE REFERENCES answer_assessments(id),
    success BOOLEAN NOT NULL,
    mastery_before DOUBLE NOT NULL CHECK (mastery_before BETWEEN 0 AND 1),
    mastery_after DOUBLE NOT NULL CHECK (mastery_after BETWEEN 0 AND 1),
    duration_ms BIGINT NOT NULL CHECK (duration_ms >= 0),
    hint_count INTEGER NOT NULL CHECK (hint_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ
);

CREATE TABLE hint_usage (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    activity_id BIGINT NOT NULL REFERENCES session_activities(id),
    hint_id BIGINT NOT NULL REFERENCES content_hints(id),
    hint_number INTEGER NOT NULL CHECK (hint_number > 0),
    display_time TIMESTAMPTZ NOT NULL,
    penalty DOUBLE NOT NULL CHECK (penalty >= 0),
    UNIQUE (activity_id, hint_id)
);

CREATE TABLE session_events (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    session_id BIGINT NOT NULL REFERENCES learning_sessions(id),
    event_type VARCHAR NOT NULL CHECK (event_type IN ('SESSION_CREATED','SESSION_READY','SESSION_STARTED','ACTIVITY_STARTED','ANSWER_MODIFIED','ANSWER_SUBMITTED','HINT_OPENED','PAUSE','RESUME','ASSESSMENT_COMPLETED','MASTERY_UPDATED','SESSION_COMPLETED','SESSION_ABANDONED','SESSION_FAILED','SESSION_ARCHIVED')),
    event_timestamp TIMESTAMPTZ NOT NULL,
    payload JSON NOT NULL DEFAULT '{}',
    correlation_id VARCHAR NOT NULL,
    idempotency_key VARCHAR NOT NULL UNIQUE
);

CREATE TABLE session_checkpoints (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    session_id BIGINT NOT NULL REFERENCES learning_sessions(id),
    activity_id BIGINT REFERENCES session_activities(id),
    current_question_id BIGINT REFERENCES content_questions(id),
    remaining_time_seconds INTEGER NOT NULL CHECK (remaining_time_seconds >= 0),
    last_answer_id BIGINT REFERENCES student_answers(id),
    autosave_timestamp TIMESTAMPTZ NOT NULL,
    checkpoint_version INTEGER NOT NULL DEFAULT 1 CHECK (checkpoint_version > 0),
    UNIQUE (session_id, checkpoint_version)
);

CREATE TABLE session_summaries (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    session_id BIGINT NOT NULL UNIQUE REFERENCES learning_sessions(id),
    completion_rate DOUBLE NOT NULL CHECK (completion_rate BETWEEN 0 AND 100),
    average_time_ms DOUBLE NOT NULL CHECK (average_time_ms >= 0),
    total_score DOUBLE NOT NULL CHECK (total_score BETWEEN 0 AND 100),
    mastery_gain DOUBLE NOT NULL CHECK (mastery_gain BETWEEN -100 AND 100),
    strengths JSON NOT NULL DEFAULT '[]',
    weaknesses JSON NOT NULL DEFAULT '[]',
    recommended_next_session VARCHAR,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ
);

CREATE TABLE session_mastery_updates (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    attempt_record_id BIGINT NOT NULL UNIQUE REFERENCES session_attempt_records(id),
    mastery_before DOUBLE NOT NULL CHECK (mastery_before BETWEEN 0 AND 1),
    mastery_after DOUBLE NOT NULL CHECK (mastery_after BETWEEN 0 AND 1),
    update_payload JSON NOT NULL,
    learning_engine_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_learning_session_details_learner_status_created
    ON learning_session_details(status, creation_time);
CREATE INDEX idx_session_activities_session_order
    ON session_activities(session_id, activity_order);
CREATE INDEX idx_student_answers_activity_question
    ON student_answers(activity_id, question_id, attempt_number);
CREATE INDEX idx_session_attempt_records_learner_activity
    ON session_attempt_records(learner_id, activity_id);
CREATE INDEX idx_session_events_session_time
    ON session_events(session_id, event_timestamp);
CREATE INDEX idx_session_checkpoints_session_time
    ON session_checkpoints(session_id, autosave_timestamp);
