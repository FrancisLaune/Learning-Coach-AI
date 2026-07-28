-- LCAI-0017: Virtual Teacher V1 — typed preferences, sessions and audit.

CREATE TABLE virtual_teacher_preferences (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    teacher_profile VARCHAR NOT NULL
        CHECK (teacher_profile IN ('TEACHER_FEMALE_01', 'TEACHER_MALE_01')),
    teacher_name VARCHAR,
    voice_id VARCHAR NOT NULL
        CHECK (voice_id IN ('warm_female', 'warm_male')),
    tone VARCHAR NOT NULL
        CHECK (tone IN ('calm', 'encouraging', 'academic')),
    response_length VARCHAR NOT NULL
        CHECK (response_length IN ('short', 'normal', 'detailed')),
    help_level INTEGER NOT NULL CHECK (help_level BETWEEN 1 AND 3),
    audio_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    feature_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    parent_locked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (learner_id)
);

CREATE TABLE virtual_teacher_sessions (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    actor_type VARCHAR NOT NULL CHECK (actor_type IN ('STUDENT', 'PARENT')),
    actor_ref VARCHAR NOT NULL,
    subject_id BIGINT REFERENCES subjects(id),
    skill_id BIGINT REFERENCES skills(id),
    exercise_ref VARCHAR,
    status VARCHAR NOT NULL CHECK (status IN ('ACTIVE', 'COMPLETED', 'CANCELLED')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE virtual_teacher_messages (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    session_id BIGINT NOT NULL,
    message_role VARCHAR NOT NULL CHECK (message_role IN ('USER', 'ASSISTANT', 'SYSTEM')),
    response_type VARCHAR
        CHECK (response_type IS NULL OR response_type IN (
            'HINT', 'EXPLANATION', 'EXAMPLE', 'REDIRECTION', 'SAFETY'
        )),
    content VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE virtual_teacher_summaries (
    session_id BIGINT PRIMARY KEY,
    skills_worked JSON NOT NULL DEFAULT '[]',
    difficulties JSON NOT NULL DEFAULT '[]',
    successful_elements JSON NOT NULL DEFAULT '[]',
    next_action VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE virtual_teacher_events (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    session_id BIGINT,
    event_type VARCHAR NOT NULL,
    metadata_json JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_virtual_teacher_sessions_learner ON virtual_teacher_sessions(learner_id, status);
CREATE INDEX idx_virtual_teacher_messages_session ON virtual_teacher_messages(session_id, created_at);
CREATE INDEX idx_virtual_teacher_events_learner ON virtual_teacher_events(learner_id, created_at);
