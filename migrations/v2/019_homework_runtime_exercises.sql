-- LCAI-0018B: runtime AI-generated homework exercises (not Approved catalogue content).

CREATE TABLE homework_runtime_exercises (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    homework_id BIGINT NOT NULL REFERENCES homework_assignments(id),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    position INTEGER NOT NULL CHECK (position > 0),
    stable_key VARCHAR NOT NULL,
    source VARCHAR NOT NULL DEFAULT 'ai_runtime_fallback'
        CHECK (source IN ('ai_runtime_fallback')),
    publication_status VARCHAR NOT NULL DEFAULT 'RUNTIME_ONLY'
        CHECK (publication_status IN ('RUNTIME_ONLY', 'DRAFT')),
    subject_id BIGINT REFERENCES subjects(id),
    skill_ids JSON NOT NULL DEFAULT '[]',
    exercise_payload JSON NOT NULL,
    content_fingerprint VARCHAR NOT NULL,
    generator_model VARCHAR,
    prompt_template_version VARCHAR,
    correlation_id VARCHAR,
    validation_result JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (homework_id, position),
    UNIQUE (homework_id, stable_key)
);

CREATE INDEX idx_homework_runtime_exercises_learner_created
    ON homework_runtime_exercises(learner_id, created_at DESC);

CREATE INDEX idx_homework_runtime_exercises_fingerprint
    ON homework_runtime_exercises(content_fingerprint, learner_id);
