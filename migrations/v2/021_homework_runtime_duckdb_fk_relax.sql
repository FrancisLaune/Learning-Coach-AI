-- LCAI-0018B5: DuckDB cannot UPDATE homework_assignments while homework_runtime_exercises
-- enforces a foreign key on homework_id. Recreate the table without that FK.

CREATE TABLE homework_runtime_exercises__b5 (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    homework_id BIGINT NOT NULL,
    learner_id BIGINT NOT NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    stable_key VARCHAR NOT NULL,
    source VARCHAR NOT NULL DEFAULT 'ai_runtime_fallback'
        CHECK (source IN ('ai_runtime_fallback')),
    publication_status VARCHAR NOT NULL DEFAULT 'RUNTIME_ONLY'
        CHECK (publication_status IN ('RUNTIME_ONLY', 'DRAFT')),
    subject_id BIGINT,
    skill_ids JSON NOT NULL DEFAULT '[]',
    exercise_payload JSON NOT NULL,
    content_fingerprint VARCHAR NOT NULL,
    generator_model VARCHAR,
    prompt_template_version VARCHAR,
    correlation_id VARCHAR,
    validation_result JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    content_id BIGINT,
    content_version_id BIGINT,
    chapter_id BIGINT,
    skill_id BIGINT,
    UNIQUE (homework_id, position),
    UNIQUE (homework_id, stable_key)
);

INSERT INTO homework_runtime_exercises__b5
SELECT * FROM homework_runtime_exercises;

DROP TABLE homework_runtime_exercises;

ALTER TABLE homework_runtime_exercises__b5 RENAME TO homework_runtime_exercises;

CREATE INDEX IF NOT EXISTS idx_homework_runtime_exercises_learner_created
    ON homework_runtime_exercises(learner_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_homework_runtime_exercises_fingerprint
    ON homework_runtime_exercises(content_fingerprint, learner_id);

CREATE INDEX IF NOT EXISTS idx_homework_runtime_exercises_content
    ON homework_runtime_exercises(content_id, content_version_id);
