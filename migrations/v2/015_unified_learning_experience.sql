-- LCAI-0010B: additive unified student, homework, coach and parent experience.

CREATE TABLE learner_experience_profiles (
    learner_id BIGINT PRIMARY KEY REFERENCES learners(id),
    first_name VARCHAR NOT NULL,
    last_name VARCHAR,
    birth_date DATE,
    school_year VARCHAR NOT NULL,
    programme_code VARCHAR NOT NULL,
    preferred_formats JSON NOT NULL DEFAULT '[]',
    error_help_preference VARCHAR NOT NULL DEFAULT 'HINT_FIRST'
        CHECK (error_help_preference IN ('HINT_FIRST','EXPLAIN_METHOD','SHOW_CORRECTION')),
    diagnostic_status VARCHAR NOT NULL DEFAULT 'NOT_OFFERED'
        CHECK (diagnostic_status IN ('NOT_OFFERED','OFFERED','SKIPPED','PLANNED','COMPLETED')),
    onboarding_completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE homework_assignments (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    stable_key VARCHAR NOT NULL UNIQUE,
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    assigned_by_type VARCHAR NOT NULL CHECK (assigned_by_type IN ('STUDENT','PARENT','COACH','SYSTEM')),
    assigned_by_ref VARCHAR NOT NULL,
    mode VARCHAR NOT NULL CHECK (mode IN ('AI_RECOMMENDED','TARGETED','GLOBAL_SUBJECT','FREE_REVISION')),
    status VARCHAR NOT NULL CHECK (status IN ('DRAFT','READY','IN_PROGRESS','PAUSED','COMPLETED','EXPIRED','CANCELLED')),
    subject_id BIGINT REFERENCES subjects(id),
    grade_level_id BIGINT REFERENCES school_levels(id),
    difficulty_mode VARCHAR NOT NULL CHECK (difficulty_mode IN ('EASY','MEDIUM','HARD','ADAPTIVE')),
    requested_exercise_count INTEGER NOT NULL CHECK (requested_exercise_count > 0 AND requested_exercise_count <= 100),
    target_duration_minutes INTEGER CHECK (target_duration_minutes IS NULL OR target_duration_minutes BETWEEN 5 AND 240),
    due_at TIMESTAMPTZ,
    correction_policy VARCHAR NOT NULL DEFAULT 'AFTER_SUBMISSION'
        CHECK (correction_policy IN ('IMMEDIATE','AFTER_EACH_EXERCISE','AFTER_SUBMISSION')),
    selection_filters JSON NOT NULL,
    selected_content JSON NOT NULL,
    session_id BIGINT REFERENCES learning_sessions(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE homework_result_summaries (
    homework_id BIGINT PRIMARY KEY REFERENCES homework_assignments(id),
    overall_score DOUBLE NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    success_rate DOUBLE NOT NULL CHECK (success_rate BETWEEN 0 AND 100),
    time_spent_seconds INTEGER NOT NULL CHECK (time_spent_seconds >= 0),
    hints_used INTEGER NOT NULL CHECK (hints_used >= 0),
    unanswered_count INTEGER NOT NULL CHECK (unanswered_count >= 0),
    mastery_impact DOUBLE NOT NULL CHECK (mastery_impact BETWEEN -100 AND 100),
    chapter_results JSON NOT NULL,
    competency_results JSON NOT NULL,
    error_categories JSON NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    calculation_version VARCHAR NOT NULL
);

CREATE TABLE programme_change_proposals (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    stable_key VARCHAR NOT NULL UNIQUE,
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    level SMALLINT NOT NULL CHECK (level BETWEEN 1 AND 3),
    change_type VARCHAR NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('PROPOSED','AUTO_APPLIED','PENDING_PARENT','ACCEPTED','MODIFIED','REJECTED','EXPIRED')),
    current_state JSON NOT NULL,
    proposed_state JSON NOT NULL,
    reason_codes JSON NOT NULL,
    evidence_references JSON NOT NULL,
    expected_benefit_code VARCHAR NOT NULL,
    correlation_id VARCHAR NOT NULL,
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMPTZ,
    decided_by_ref VARCHAR,
    decision_note VARCHAR
);

CREATE TABLE recommendation_effectiveness (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    recommendation_ref VARCHAR NOT NULL,
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    skill_id BIGINT REFERENCES skills(id),
    baseline_mastery DOUBLE NOT NULL CHECK (baseline_mastery BETWEEN 0 AND 1),
    outcome_mastery DOUBLE CHECK (outcome_mastery IS NULL OR outcome_mastery BETWEEN 0 AND 1),
    status VARCHAR NOT NULL CHECK (status IN ('PENDING','EFFECTIVE','NEUTRAL','INEFFECTIVE','INSUFFICIENT_DATA')),
    measured_at TIMESTAMPTZ,
    evidence_references JSON NOT NULL DEFAULT '[]',
    UNIQUE(recommendation_ref,learner_id,skill_id)
);

CREATE INDEX idx_homework_learner_status_due
    ON homework_assignments(learner_id,status,due_at,created_at);
CREATE INDEX idx_homework_parent_creator
    ON homework_assignments(assigned_by_type,assigned_by_ref,created_at);
CREATE INDEX idx_programme_changes_learner_status
    ON programme_change_proposals(learner_id,status,proposed_at);
CREATE INDEX idx_recommendation_effectiveness_learner
    ON recommendation_effectiveness(learner_id,status,measured_at);
