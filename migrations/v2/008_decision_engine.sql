CREATE TABLE learner_journey_preferences (
    learner_id BIGINT PRIMARY KEY REFERENCES learners(id),
    current_objective_ref VARCHAR NOT NULL,
    long_term_objective_ref VARCHAR,
    exam_objective_ref VARCHAR,
    target_date DATE,
    preferred_subject_ids JSON NOT NULL DEFAULT '[]',
    weak_subject_ids JSON NOT NULL DEFAULT '[]',
    daily_duration_minutes INTEGER NOT NULL DEFAULT 30 CHECK (daily_duration_minutes BETWEEN 5 AND 240),
    weekly_schedule JSON NOT NULL DEFAULT '[]',
    difficulty_preference SMALLINT NOT NULL DEFAULT 3 CHECK (difficulty_preference BETWEEN 1 AND 5),
    parent_mode BOOLEAN NOT NULL DEFAULT FALSE,
    student_mode BOOLEAN NOT NULL DEFAULT TRUE,
    learning_rhythm VARCHAR NOT NULL DEFAULT 'balanced',
    preferred_revision_days JSON NOT NULL DEFAULT '[]',
    vacation_mode BOOLEAN NOT NULL DEFAULT FALSE,
    holiday_planning BOOLEAN NOT NULL DEFAULT TRUE,
    transition_planning BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pedagogical_objectives (
    id VARCHAR PRIMARY KEY,
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    kind VARCHAR NOT NULL CHECK (kind IN ('revision','catch_up','consolidation','preparation_next_grade','preparation_brevet','preparation_bac','homework','exam','long_term_mastery')),
    title VARCHAR NOT NULL,
    target_date DATE,
    priority_weight DOUBLE NOT NULL DEFAULT 1 CHECK (priority_weight > 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (learner_id, id)
);

CREATE TABLE decision_plan_items (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    decision_id BIGINT NOT NULL REFERENCES learning_decisions(id),
    candidate_ref VARCHAR NOT NULL,
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    subject_id BIGINT NOT NULL REFERENCES subjects(id),
    scheduled_for TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    difficulty SMALLINT NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
    position INTEGER NOT NULL CHECK (position > 0),
    UNIQUE (decision_id, position),
    UNIQUE (decision_id, candidate_ref)
);

CREATE TABLE decision_result_snapshots (
    decision_id BIGINT PRIMARY KEY REFERENCES learning_decisions(id),
    correlation_id VARCHAR NOT NULL UNIQUE,
    result JSON NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_objectives_learner_active_date ON pedagogical_objectives(learner_id, active, target_date);
CREATE INDEX idx_plan_items_schedule ON decision_plan_items(scheduled_for, subject_id);
CREATE INDEX idx_decision_results_created ON decision_result_snapshots(created_at);

