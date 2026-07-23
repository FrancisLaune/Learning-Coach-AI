INSERT INTO school_levels(id, code, label, country_code, rank) VALUES
    (11, 'FR-4E', 'Quatrième', 'FR', 4),
    (12, 'FR-2NDE', 'Seconde', 'FR', 6),
    (13, 'FR-1ERE', 'Première', 'FR', 7),
    (14, 'FR-TERM', 'Terminale', 'FR', 8);

CREATE TABLE learner_journeys (
    learner_id BIGINT PRIMARY KEY REFERENCES learners(id),
    current_school_level_id BIGINT NOT NULL REFERENCES school_levels(id),
    target_school_level_id BIGINT REFERENCES school_levels(id),
    academic_year_start INTEGER NOT NULL CHECK (academic_year_start BETWEEN 2000 AND 2200),
    program_id BIGINT REFERENCES programs(id),
    learning_phase VARCHAR NOT NULL CHECK (learning_phase IN ('diagnostic','remediation','pre_year_preparation','current_learning','consolidation','practice','spaced_revision','assessment_preparation','exam_preparation','transition_preparation')),
    examination_code VARCHAR,
    examination_date DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE learning_attempt_inputs (
    stable_id VARCHAR PRIMARY KEY,
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    occurred_at TIMESTAMPTZ NOT NULL,
    input_snapshot JSON NOT NULL,
    result_snapshot JSON NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE longitudinal_mastery_current (
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    score DOUBLE NOT NULL CHECK (score BETWEEN 0 AND 1),
    level VARCHAR NOT NULL CHECK (level IN ('not_started','emerging','developing','proficient','mastered')),
    observations INTEGER NOT NULL CHECK (observations >= 0),
    successes INTEGER NOT NULL CHECK (successes >= 0),
    failures INTEGER NOT NULL CHECK (failures >= 0),
    success_streak INTEGER NOT NULL CHECK (success_streak >= 0),
    failure_streak INTEGER NOT NULL CHECK (failure_streak >= 0),
    last_activity_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_difficulty SMALLINT NOT NULL CHECK (last_difficulty BETWEEN 1 AND 5),
    last_grade_code VARCHAR,
    confidence DOUBLE NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    trend VARCHAR NOT NULL CHECK (trend IN ('improving','stable','declining')),
    stability DOUBLE NOT NULL CHECK (stability BETWEEN 0 AND 1),
    origin_grade_code VARCHAR,
    prerequisite_for_future BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (learner_id, skill_id)
);

CREATE TABLE longitudinal_mastery_events (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    stable_attempt_id VARCHAR NOT NULL UNIQUE REFERENCES learning_attempt_inputs(stable_id),
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    previous_score DOUBLE NOT NULL CHECK (previous_score BETWEEN 0 AND 1),
    current_score DOUBLE NOT NULL CHECK (current_score BETWEEN 0 AND 1),
    explanation JSON NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE learning_domain_events (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    stable_attempt_id VARCHAR NOT NULL REFERENCES learning_attempt_inputs(stable_id),
    event_type VARCHAR NOT NULL,
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    skill_id BIGINT REFERENCES skills(id),
    payload JSON NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    UNIQUE (stable_attempt_id, event_type, skill_id)
);

CREATE TABLE transition_readiness_current (
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    target_grade_code VARCHAR NOT NULL,
    score DOUBLE NOT NULL CHECK (score BETWEEN 0 AND 1),
    coverage DOUBLE NOT NULL CHECK (coverage BETWEEN 0 AND 1),
    confidence DOUBLE NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    details JSON NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (learner_id, target_grade_code)
);

CREATE TABLE exam_readiness_current (
    learner_id BIGINT NOT NULL REFERENCES learners(id),
    examination_code VARCHAR NOT NULL,
    score DOUBLE NOT NULL CHECK (score BETWEEN 0 AND 1),
    coverage DOUBLE NOT NULL CHECK (coverage BETWEEN 0 AND 1),
    confidence DOUBLE NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    details JSON NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (learner_id, examination_code)
);

CREATE INDEX idx_learning_attempts_learner_time ON learning_attempt_inputs(learner_id, occurred_at);
CREATE INDEX idx_longitudinal_mastery_review ON longitudinal_mastery_current(learner_id, last_activity_at);
CREATE INDEX idx_longitudinal_events_skill_time ON longitudinal_mastery_events(learner_id, skill_id, occurred_at);
CREATE INDEX idx_learning_domain_events_learner_time ON learning_domain_events(learner_id, occurred_at);
