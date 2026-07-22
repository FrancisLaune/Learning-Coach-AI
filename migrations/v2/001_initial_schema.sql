-- DuckDB V2 normalized learning-model foundation.
CREATE SEQUENCE global_entity_id_seq START 100000;

CREATE TABLE schema_versions (
    version INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    checksum VARCHAR NOT NULL UNIQUE,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    execution_ms INTEGER NOT NULL CHECK (execution_ms >= 0)
);

CREATE TABLE school_levels (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    code VARCHAR NOT NULL UNIQUE,
    label VARCHAR NOT NULL,
    rank INTEGER NOT NULL CHECK (rank >= 0),
    country_code VARCHAR NOT NULL CHECK (length(country_code) = 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ
);

CREATE TABLE programs (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    code VARCHAR NOT NULL,
    version VARCHAR NOT NULL,
    label VARCHAR NOT NULL,
    country_code VARCHAR NOT NULL CHECK (length(country_code) = 2),
    jurisdiction VARCHAR NOT NULL,
    exam_type VARCHAR,
    default_language_code VARCHAR NOT NULL CHECK (length(default_language_code) BETWEEN 2 AND 10),
    valid_from DATE,
    valid_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ,
    UNIQUE (code, version, country_code),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE TABLE subjects (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    code VARCHAR NOT NULL UNIQUE,
    default_label VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ
);

CREATE TABLE program_subjects (
    program_id BIGINT NOT NULL REFERENCES programs(id),
    subject_id BIGINT NOT NULL REFERENCES subjects(id),
    school_level_id BIGINT NOT NULL REFERENCES school_levels(id),
    display_order INTEGER NOT NULL CHECK (display_order > 0),
    weight DOUBLE NOT NULL DEFAULT 1 CHECK (weight > 0),
    PRIMARY KEY (program_id, subject_id, school_level_id),
    UNIQUE (program_id, school_level_id, display_order)
);

CREATE TABLE domains (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    subject_id BIGINT NOT NULL REFERENCES subjects(id),
    code VARCHAR NOT NULL,
    default_label VARCHAR NOT NULL,
    description VARCHAR,
    display_order INTEGER NOT NULL CHECK (display_order > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ,
    UNIQUE (subject_id, code),
    UNIQUE (subject_id, display_order)
);

CREATE TABLE skills (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    domain_id BIGINT NOT NULL REFERENCES domains(id),
    code VARCHAR NOT NULL,
    default_label VARCHAR NOT NULL,
    description VARCHAR,
    display_order INTEGER NOT NULL CHECK (display_order > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ,
    UNIQUE (domain_id, code),
    UNIQUE (domain_id, display_order)
);

CREATE TABLE subskills (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    code VARCHAR NOT NULL,
    default_label VARCHAR NOT NULL,
    description VARCHAR,
    display_order INTEGER NOT NULL CHECK (display_order > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ,
    UNIQUE (skill_id, code),
    UNIQUE (skill_id, display_order)
);

CREATE TABLE program_skills (
    program_id BIGINT NOT NULL REFERENCES programs(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    expected_mastery DOUBLE NOT NULL DEFAULT 0.8 CHECK (expected_mastery BETWEEN 0 AND 1),
    priority DOUBLE NOT NULL DEFAULT 1 CHECK (priority > 0),
    display_order INTEGER NOT NULL CHECK (display_order > 0),
    PRIMARY KEY (program_id, skill_id),
    UNIQUE (program_id, display_order)
);

CREATE TABLE skill_prerequisites (
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    prerequisite_skill_id BIGINT NOT NULL REFERENCES skills(id),
    weight DOUBLE NOT NULL DEFAULT 1 CHECK (weight > 0),
    PRIMARY KEY (skill_id, prerequisite_skill_id),
    CHECK (skill_id <> prerequisite_skill_id)
);

CREATE TABLE reference_translations (
    entity_type VARCHAR NOT NULL CHECK (entity_type IN ('program', 'school_level', 'subject', 'domain', 'skill', 'subskill')),
    entity_id BIGINT NOT NULL,
    language_code VARCHAR NOT NULL CHECK (length(language_code) BETWEEN 2 AND 10),
    label VARCHAR NOT NULL,
    description VARCHAR,
    PRIMARY KEY (entity_type, entity_id, language_code)
);

CREATE TABLE learners (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    external_ref VARCHAR UNIQUE,
    display_name VARCHAR NOT NULL,
    locale VARCHAR NOT NULL DEFAULT 'fr-FR',
    timezone VARCHAR NOT NULL DEFAULT 'Europe/Paris',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ
);

CREATE TABLE learner_profiles (
    learner_id BIGINT PRIMARY KEY REFERENCES learners(id),
    school_level_id BIGINT REFERENCES school_levels(id),
    preferred_learning_modality VARCHAR,
    learning_speed DOUBLE CHECK (learning_speed BETWEEN 0 AND 1),
    retention_capability DOUBLE CHECK (retention_capability BETWEEN 0 AND 1),
    confidence_stability DOUBLE CHECK (confidence_stability BETWEEN 0 AND 1),
    fatigue_sensitivity DOUBLE CHECK (fatigue_sensitivity BETWEEN 0 AND 1),
    regularity DOUBLE CHECK (regularity BETWEEN 0 AND 1),
    error_recurrence DOUBLE CHECK (error_recurrence BETWEEN 0 AND 1),
    motivation_trend DOUBLE CHECK (motivation_trend BETWEEN 0 AND 1),
    forgetting_resistance DOUBLE CHECK (forgetting_resistance BETWEEN 0 AND 1),
    average_response_ms BIGINT CHECK (average_response_ms >= 0),
    indicators_confidence JSON NOT NULL DEFAULT '{}',
    model_version VARCHAR NOT NULL DEFAULT 'uncomputed',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE objectives (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    program_id BIGINT REFERENCES programs(id),
    kind VARCHAR NOT NULL CHECK (kind IN ('program', 'exam', 'skill', 'habit', 'custom')),
    title VARCHAR NOT NULL,
    target_date DATE,
    target_score DOUBLE CHECK (target_score BETWEEN 0 AND 1),
    status VARCHAR NOT NULL DEFAULT 'active' CHECK (status IN ('draft', 'active', 'completed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE TABLE objective_skills (
    objective_id BIGINT NOT NULL REFERENCES objectives(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    weight DOUBLE NOT NULL DEFAULT 1 CHECK (weight > 0),
    target_mastery DOUBLE NOT NULL DEFAULT 0.8 CHECK (target_mastery BETWEEN 0 AND 1),
    PRIMARY KEY (objective_id, skill_id)
);

CREATE TABLE exercises (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    subject_id BIGINT NOT NULL REFERENCES subjects(id),
    code VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    objective VARCHAR NOT NULL,
    estimated_seconds INTEGER NOT NULL CHECK (estimated_seconds > 0),
    difficulty SMALLINT NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
    instructions VARCHAR NOT NULL,
    evaluation_strategy JSON NOT NULL,
    language_code VARCHAR NOT NULL CHECK (length(language_code) BETWEEN 2 AND 10),
    content_version INTEGER NOT NULL DEFAULT 1 CHECK (content_version > 0),
    status VARCHAR NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ,
    UNIQUE (code, language_code, content_version)
);

CREATE TABLE questions (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    code VARCHAR NOT NULL,
    statement VARCHAR NOT NULL,
    answer_type VARCHAR NOT NULL CHECK (answer_type IN ('text', 'number', 'choice', 'boolean', 'structured')),
    expected_answer JSON NOT NULL,
    explanation VARCHAR NOT NULL,
    hints JSON NOT NULL DEFAULT '[]',
    estimated_seconds INTEGER NOT NULL CHECK (estimated_seconds > 0),
    language_code VARCHAR NOT NULL CHECK (length(language_code) BETWEEN 2 AND 10),
    content_version INTEGER NOT NULL DEFAULT 1 CHECK (content_version > 0),
    status VARCHAR NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (code, language_code, content_version)
);

CREATE TABLE exercise_questions (
    exercise_id BIGINT NOT NULL REFERENCES exercises(id),
    question_id BIGINT NOT NULL REFERENCES questions(id),
    position INTEGER NOT NULL CHECK (position > 0),
    points DOUBLE NOT NULL DEFAULT 1 CHECK (points > 0),
    required BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (exercise_id, question_id),
    UNIQUE (exercise_id, position)
);

CREATE TABLE question_skills (
    question_id BIGINT NOT NULL REFERENCES questions(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    weight DOUBLE NOT NULL DEFAULT 1 CHECK (weight > 0),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (question_id, skill_id)
);

CREATE TABLE question_subskills (
    question_id BIGINT NOT NULL REFERENCES questions(id),
    subskill_id BIGINT NOT NULL REFERENCES subskills(id),
    weight DOUBLE NOT NULL DEFAULT 1 CHECK (weight > 0),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (question_id, subskill_id)
);

CREATE TABLE learning_sessions (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    objective_id BIGINT REFERENCES objectives(id),
    kind VARCHAR NOT NULL CHECK (kind IN ('practice', 'revision', 'exam', 'lesson')),
    status VARCHAR NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'active', 'completed', 'abandoned')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    planned_duration_seconds INTEGER CHECK (planned_duration_seconds > 0),
    engine_version VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at)
);

CREATE TABLE learning_decisions (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    session_id BIGINT REFERENCES learning_sessions(id),
    decision_type VARCHAR NOT NULL,
    engine_version VARCHAR NOT NULL,
    ruleset_version VARCHAR NOT NULL,
    context_hash VARCHAR NOT NULL,
    inputs JSON NOT NULL,
    candidates JSON NOT NULL,
    selected_entity_type VARCHAR NOT NULL CHECK (selected_entity_type IN ('exercise', 'skill', 'subskill', 'revision', 'none')),
    selected_entity_id BIGINT,
    scheduled_for TIMESTAMPTZ,
    difficulty SMALLINT CHECK (difficulty BETWEEN 1 AND 5),
    duration_seconds INTEGER CHECK (duration_seconds > 0),
    scores JSON NOT NULL,
    reason_codes JSON NOT NULL,
    correlation_id VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE session_exercises (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    session_id BIGINT NOT NULL REFERENCES learning_sessions(id),
    exercise_id BIGINT NOT NULL REFERENCES exercises(id),
    decision_id BIGINT REFERENCES learning_decisions(id),
    position INTEGER NOT NULL CHECK (position > 0),
    presented_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE (session_id, position)
);

CREATE TABLE attempts (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    session_exercise_id BIGINT REFERENCES session_exercises(id),
    question_id BIGINT NOT NULL REFERENCES questions(id),
    attempt_number INTEGER NOT NULL DEFAULT 1 CHECK (attempt_number > 0),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    answer JSON NOT NULL,
    is_correct BOOLEAN,
    score DOUBLE NOT NULL CHECK (score BETWEEN 0 AND 1),
    elapsed_ms BIGINT CHECK (elapsed_ms >= 0),
    difficulty_at_attempt SMALLINT NOT NULL CHECK (difficulty_at_attempt BETWEEN 1 AND 5),
    prompt_snapshot VARCHAR NOT NULL,
    expected_answer_snapshot JSON NOT NULL,
    UNIQUE (session_exercise_id, question_id, attempt_number)
);

CREATE TABLE error_categories (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    code VARCHAR NOT NULL UNIQUE,
    label VARCHAR NOT NULL,
    description VARCHAR
);

CREATE TABLE attempt_skill_results (
    attempt_id BIGINT NOT NULL REFERENCES attempts(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    evidence_score DOUBLE NOT NULL CHECK (evidence_score BETWEEN 0 AND 1),
    weight DOUBLE NOT NULL DEFAULT 1 CHECK (weight > 0),
    error_category_id BIGINT REFERENCES error_categories(id),
    PRIMARY KEY (attempt_id, skill_id)
);

CREATE TABLE mastery_current (
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    score DOUBLE NOT NULL CHECK (score BETWEEN 0 AND 1),
    confidence DOUBLE NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    last_evidence_at TIMESTAMPTZ,
    next_review_at TIMESTAMPTZ,
    half_life_days DOUBLE CHECK (half_life_days > 0),
    model_version VARCHAR NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (learner_id, skill_id)
);

CREATE TABLE mastery_events (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    attempt_id BIGINT REFERENCES attempts(id),
    event_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    previous_score DOUBLE CHECK (previous_score BETWEEN 0 AND 1),
    new_score DOUBLE NOT NULL CHECK (new_score BETWEEN 0 AND 1),
    evidence DOUBLE NOT NULL CHECK (evidence BETWEEN 0 AND 1),
    model_version VARCHAR NOT NULL,
    factors JSON NOT NULL
);

CREATE TABLE recommendations (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    decision_id BIGINT NOT NULL REFERENCES learning_decisions(id),
    target_skill_id BIGINT REFERENCES skills(id),
    target_exercise_id BIGINT REFERENCES exercises(id),
    kind VARCHAR NOT NULL,
    priority_score DOUBLE NOT NULL CHECK (priority_score BETWEEN 0 AND 1),
    reason_code VARCHAR NOT NULL,
    explanation JSON NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'dismissed', 'expired', 'completed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,
    CHECK (target_skill_id IS NOT NULL OR target_exercise_id IS NOT NULL)
);

CREATE TABLE progress_snapshots (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    program_id BIGINT REFERENCES programs(id),
    objective_id BIGINT REFERENCES objectives(id),
    progress_score DOUBLE NOT NULL CHECK (progress_score BETWEEN 0 AND 1),
    mastered_skills INTEGER NOT NULL DEFAULT 0 CHECK (mastered_skills >= 0),
    total_skills INTEGER NOT NULL DEFAULT 0 CHECK (total_skills >= 0),
    metrics JSON NOT NULL,
    model_version VARCHAR NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (mastered_skills <= total_skills)
);

CREATE TABLE study_calendar (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    objective_id BIGINT REFERENCES objectives(id),
    skill_id BIGINT REFERENCES skills(id),
    scheduled_for TIMESTAMPTZ NOT NULL,
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    status VARCHAR NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'completed', 'skipped', 'cancelled')),
    source VARCHAR NOT NULL CHECK (source IN ('manual', 'scheduler', 'objective', 'migration')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE revision_history (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    session_id BIGINT REFERENCES learning_sessions(id),
    attempt_id BIGINT REFERENCES attempts(id),
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    outcome_score DOUBLE NOT NULL CHECK (outcome_score BETWEEN 0 AND 1),
    previous_interval_days DOUBLE CHECK (previous_interval_days >= 0),
    next_interval_days DOUBLE CHECK (next_interval_days > 0),
    model_version VARCHAR NOT NULL
);

CREATE TABLE ai_conversation_memory (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    decision_id BIGINT REFERENCES learning_decisions(id),
    purpose VARCHAR NOT NULL,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    summary JSON NOT NULL,
    source_references JSON NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    model_version VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (window_end IS NULL OR window_start IS NULL OR window_end >= window_start)
);

CREATE TABLE learning_metrics (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    session_id BIGINT REFERENCES learning_sessions(id),
    metric_name VARCHAR NOT NULL,
    metric_value DOUBLE NOT NULL,
    dimensions JSON NOT NULL DEFAULT '{}',
    measured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (learner_id, session_id, metric_name, measured_at)
);
