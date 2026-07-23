CREATE TABLE curriculum_chapters (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    stable_code VARCHAR NOT NULL UNIQUE,
    program_id BIGINT NOT NULL REFERENCES programs(id),
    subject_id BIGINT NOT NULL REFERENCES subjects(id),
    domain_id BIGINT NOT NULL REFERENCES domains(id),
    grade_level_id BIGINT NOT NULL REFERENCES school_levels(id),
    title VARCHAR NOT NULL CHECK (length(trim(title)) > 0),
    description VARCHAR NOT NULL,
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    expected_duration_minutes INTEGER NOT NULL CHECK (expected_duration_minutes > 0),
    difficulty_min SMALLINT NOT NULL CHECK (difficulty_min BETWEEN 1 AND 5),
    difficulty_max SMALLINT NOT NULL CHECK (difficulty_max BETWEEN 1 AND 5),
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    is_exam_relevant BOOLEAN NOT NULL DEFAULT FALSE,
    is_transition_relevant BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR NOT NULL CHECK (status IN ('draft','review','approved','archived')),
    version INTEGER NOT NULL CHECK (version > 0),
    effective_from DATE NOT NULL,
    effective_to DATE,
    CHECK (difficulty_min <= difficulty_max),
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    UNIQUE (program_id, grade_level_id, subject_id, sequence_order)
);

CREATE TABLE curriculum_skill_details (
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    chapter_id BIGINT NOT NULL REFERENCES curriculum_chapters(id),
    grade_level_id BIGINT NOT NULL REFERENCES school_levels(id),
    reference_difficulty SMALLINT NOT NULL CHECK (reference_difficulty BETWEEN 1 AND 5),
    importance DOUBLE NOT NULL CHECK (importance BETWEEN 0 AND 1),
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    is_exam_relevant BOOLEAN NOT NULL DEFAULT FALSE,
    is_transition_relevant BOOLEAN NOT NULL DEFAULT FALSE,
    pedagogical_tags JSON NOT NULL DEFAULT '[]',
    status VARCHAR NOT NULL CHECK (status IN ('draft','review','approved','archived')),
    version INTEGER NOT NULL CHECK (version > 0),
    PRIMARY KEY (skill_id, grade_level_id, version)
);

CREATE TABLE learning_objectives (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    stable_code VARCHAR NOT NULL UNIQUE,
    chapter_id BIGINT NOT NULL REFERENCES curriculum_chapters(id),
    title VARCHAR NOT NULL CHECK (length(trim(title)) > 0),
    description VARCHAR NOT NULL,
    observable_outcome VARCHAR NOT NULL CHECK (length(trim(observable_outcome)) > 0),
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    status VARCHAR NOT NULL CHECK (status IN ('draft','review','approved','archived')),
    version INTEGER NOT NULL CHECK (version > 0),
    UNIQUE (chapter_id, sequence_order)
);

CREATE TABLE skill_learning_objectives (
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    learning_objective_id BIGINT NOT NULL REFERENCES learning_objectives(id),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (skill_id, learning_objective_id)
);

CREATE TABLE curriculum_skill_relations (
    prerequisite_skill_id BIGINT NOT NULL REFERENCES skills(id),
    target_skill_id BIGINT NOT NULL REFERENCES skills(id),
    relation_type VARCHAR NOT NULL CHECK (relation_type IN ('required','recommended','remediation','transition','exam_dependency')),
    progression_role VARCHAR NOT NULL CHECK (progression_role IN ('current_level','prior_grade_remediation','next_grade_preparation','exam_preparation','long_term_foundation')),
    strength DOUBLE NOT NULL CHECK (strength BETWEEN 0 AND 1),
    mandatory BOOLEAN NOT NULL DEFAULT FALSE,
    minimum_mastery_threshold DOUBLE NOT NULL CHECK (minimum_mastery_threshold BETWEEN 0 AND 1),
    rationale VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (prerequisite_skill_id <> target_skill_id),
    PRIMARY KEY (prerequisite_skill_id, target_skill_id, relation_type, version)
);

CREATE TABLE exam_references (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    code VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    grade_level_id BIGINT NOT NULL REFERENCES school_levels(id),
    applicable_subject_codes JSON NOT NULL,
    competency_weights JSON NOT NULL DEFAULT '{}',
    mandatory_domain_codes JSON NOT NULL DEFAULT '[]',
    preparation_phases JSON NOT NULL DEFAULT '[]',
    effective_year INTEGER NOT NULL CHECK (effective_year >= 2000),
    source_reference VARCHAR NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('draft','review','approved','archived')),
    version INTEGER NOT NULL CHECK (version > 0),
    UNIQUE (code, effective_year, version)
);

CREATE TABLE exam_skill_references (
    exam_reference_id BIGINT NOT NULL REFERENCES exam_references(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    relevance DOUBLE NOT NULL CHECK (relevance BETWEEN 0 AND 1),
    rationale VARCHAR NOT NULL,
    PRIMARY KEY (exam_reference_id, skill_id)
);

CREATE TABLE learning_content_metadata (
    exercise_id BIGINT PRIMARY KEY REFERENCES exercises(id),
    chapter_id BIGINT NOT NULL REFERENCES curriculum_chapters(id),
    subskill_id BIGINT REFERENCES subskills(id),
    content_type VARCHAR NOT NULL CHECK (content_type IN ('exercise','quiz','multiple_choice_question','open_question','problem','revision_sheet','method_sheet','worked_example','diagnostic_activity','remediation_activity','transition_activity','exam_practice','mini_assessment')),
    summary VARCHAR NOT NULL,
    author_source VARCHAR NOT NULL,
    license_or_origin VARCHAR NOT NULL,
    created_on DATE NOT NULL,
    last_reviewed_on DATE NOT NULL,
    min_duration_minutes INTEGER NOT NULL CHECK (min_duration_minutes > 0),
    max_duration_minutes INTEGER NOT NULL CHECK (max_duration_minutes >= min_duration_minutes),
    difficulty_rationale JSON NOT NULL,
    expected_attempts INTEGER NOT NULL CHECK (expected_attempts > 0),
    allowed_hints INTEGER NOT NULL CHECK (allowed_hints >= 0),
    calculator_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    material_required VARCHAR,
    compatibility JSON NOT NULL,
    pedagogical_strategy VARCHAR NOT NULL,
    cognitive_demand VARCHAR NOT NULL,
    expected_response_type VARCHAR NOT NULL,
    source_identifier VARCHAR NOT NULL,
    current_version INTEGER NOT NULL CHECK (current_version > 0),
    UNIQUE (source_identifier, current_version)
);

CREATE TABLE content_learning_objectives (
    exercise_id BIGINT NOT NULL REFERENCES exercises(id),
    learning_objective_id BIGINT NOT NULL REFERENCES learning_objectives(id),
    PRIMARY KEY (exercise_id, learning_objective_id)
);

CREATE TABLE content_questions (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    exercise_id BIGINT NOT NULL REFERENCES exercises(id),
    stable_code VARCHAR NOT NULL UNIQUE,
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    instructions VARCHAR NOT NULL,
    context VARCHAR,
    statement VARCHAR NOT NULL CHECK (length(trim(statement)) > 0),
    response_type VARCHAR NOT NULL CHECK (response_type IN ('short_text','long_text','integer','decimal','fraction','mathematical_expression','single_choice','multiple_choice','true_false','matching','ordering','structured')),
    expected_answer JSON,
    tolerance DOUBLE CHECK (tolerance IS NULL OR tolerance >= 0),
    unit VARCHAR,
    points DOUBLE NOT NULL CHECK (points > 0),
    is_evaluative BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (exercise_id, sequence_order)
);

CREATE TABLE content_answer_options (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    question_id BIGINT NOT NULL REFERENCES content_questions(id),
    stable_code VARCHAR NOT NULL,
    label VARCHAR NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT FALSE,
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    UNIQUE (question_id, stable_code),
    UNIQUE (question_id, sequence_order)
);

CREATE TABLE content_solutions (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    question_id BIGINT NOT NULL UNIQUE REFERENCES content_questions(id),
    correct_answer JSON NOT NULL,
    pedagogical_explanation VARCHAR NOT NULL CHECK (length(trim(pedagogical_explanation)) > 0),
    method VARCHAR NOT NULL,
    common_mistakes JSON NOT NULL DEFAULT '[]',
    advice VARCHAR NOT NULL DEFAULT '',
    accepted_variants JSON NOT NULL DEFAULT '[]',
    rubric JSON NOT NULL DEFAULT '{}'
);

CREATE TABLE content_solution_steps (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    solution_id BIGINT NOT NULL REFERENCES content_solutions(id),
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    explanation VARCHAR NOT NULL CHECK (length(trim(explanation)) > 0),
    UNIQUE (solution_id, sequence_order)
);

CREATE TABLE content_hints (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    question_id BIGINT NOT NULL REFERENCES content_questions(id),
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    text VARCHAR NOT NULL CHECK (length(trim(text)) > 0),
    penalty_weight DOUBLE NOT NULL CHECK (penalty_weight BETWEEN 0 AND 1),
    disclosure_level SMALLINT NOT NULL CHECK (disclosure_level BETWEEN 1 AND 3),
    related_skill_id BIGINT REFERENCES skills(id),
    reveals_answer BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (question_id, sequence_order)
);

CREATE TABLE content_common_errors (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    error_code VARCHAR NOT NULL UNIQUE,
    subject_id BIGINT NOT NULL REFERENCES subjects(id),
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    description VARCHAR NOT NULL,
    detection_rule VARCHAR,
    remediation_skill_id BIGINT REFERENCES skills(id),
    remediation_content_id BIGINT REFERENCES exercises(id),
    severity VARCHAR NOT NULL CHECK (severity IN ('low','medium','high')),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE content_quality_assessments (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    content_version_id BIGINT NOT NULL REFERENCES content_versions(id),
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    quality_level VARCHAR NOT NULL CHECK (quality_level IN ('insufficient','developing','publishable','excellent')),
    passed_criteria JSON NOT NULL,
    missing_criteria JSON NOT NULL,
    blocking_errors JSON NOT NULL,
    warnings JSON NOT NULL,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assessor VARCHAR NOT NULL,
    UNIQUE (content_version_id, assessor)
);

CREATE TABLE editorial_reviews (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    content_version_id BIGINT NOT NULL REFERENCES content_versions(id),
    reviewer VARCHAR NOT NULL,
    decision VARCHAR NOT NULL CHECK (decision IN ('accepted','changes_requested')),
    notes VARCHAR NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (content_version_id, reviewer)
);

CREATE TABLE editorial_approvals (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    content_version_id BIGINT NOT NULL REFERENCES content_versions(id),
    approver VARCHAR NOT NULL,
    approved BOOLEAN NOT NULL,
    validation_run_id BIGINT NOT NULL REFERENCES validation_runs(id),
    quality_assessment_id BIGINT NOT NULL REFERENCES content_quality_assessments(id),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (content_version_id, active)
);

CREATE TABLE content_import_batches (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    import_identifier VARCHAR NOT NULL UNIQUE,
    source_path VARCHAR NOT NULL,
    source_checksum VARCHAR NOT NULL,
    dry_run BOOLEAN NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('started','completed','failed','conflict')),
    rows_read INTEGER NOT NULL DEFAULT 0 CHECK (rows_read >= 0),
    created_count INTEGER NOT NULL DEFAULT 0 CHECK (created_count >= 0),
    updated_count INTEGER NOT NULL DEFAULT 0 CHECK (updated_count >= 0),
    ignored_count INTEGER NOT NULL DEFAULT 0 CHECK (ignored_count >= 0),
    error_count INTEGER NOT NULL DEFAULT 0 CHECK (error_count >= 0),
    warning_count INTEGER NOT NULL DEFAULT 0 CHECK (warning_count >= 0),
    report JSON NOT NULL DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE TABLE curriculum_domain_events (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    event_type VARCHAR NOT NULL,
    aggregate_type VARCHAR NOT NULL,
    aggregate_code VARCHAR NOT NULL,
    payload JSON NOT NULL DEFAULT '{}',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIEW approved_learning_catalog AS
SELECT e.id AS content_id, cv.id AS content_version_id, e.code AS stable_code,
       e.title, e.subject_id, d.id AS domain_id, qs.skill_id, lcm.subskill_id,
       cc.program_id, sl.code AS grade_code, e.difficulty,
       CAST(ceil(e.estimated_seconds / 60.0) AS INTEGER) AS estimated_minutes,
       lcm.content_type, cv.payload, lcm.chapter_id
FROM exercises e
JOIN learning_content_metadata lcm ON lcm.exercise_id = e.id
JOIN curriculum_chapters cc ON cc.id = lcm.chapter_id
JOIN school_levels sl ON sl.id = cc.grade_level_id
JOIN content_versions cv ON cv.entity_type = 'exercise' AND cv.entity_id = e.id
    AND cv.version_number = e.content_version
JOIN editorial_approvals ea ON ea.content_version_id = cv.id AND ea.active
JOIN exercise_questions eq ON eq.exercise_id = e.id
JOIN question_skills qs ON qs.question_id = eq.question_id AND qs.is_primary
JOIN skills sk ON sk.id = qs.skill_id
JOIN domains d ON d.id = sk.domain_id
WHERE e.status = 'active' AND e.archived_at IS NULL AND cv.status = 'approved';

CREATE INDEX idx_curriculum_chapters_grade_subject ON curriculum_chapters(grade_level_id, subject_id, sequence_order);
CREATE INDEX idx_skill_details_chapter ON curriculum_skill_details(chapter_id, grade_level_id);
CREATE INDEX idx_learning_objectives_chapter ON learning_objectives(chapter_id, sequence_order);
CREATE INDEX idx_curriculum_relations_target ON curriculum_skill_relations(target_skill_id, active);
CREATE INDEX idx_exam_skills_skill ON exam_skill_references(skill_id);
CREATE INDEX idx_content_metadata_chapter ON learning_content_metadata(chapter_id, content_type);
CREATE INDEX idx_content_questions_exercise ON content_questions(exercise_id, sequence_order);
CREATE INDEX idx_content_hints_question ON content_hints(question_id, sequence_order);
CREATE INDEX idx_content_quality_version ON content_quality_assessments(content_version_id);
CREATE INDEX idx_editorial_approvals_version ON editorial_approvals(content_version_id, active);
