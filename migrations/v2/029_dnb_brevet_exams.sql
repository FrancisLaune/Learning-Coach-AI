-- LCAI-0031 Phase 4 — Brevet templates, archives, mocks, oral (additive).

CREATE TABLE IF NOT EXISTS brevet_exam_templates (
    exam_code VARCHAR PRIMARY KEY,
    label VARCHAR NOT NULL,
    subject_codes JSON NOT NULL,
    duration_minutes INTEGER NOT NULL,
    coefficient DOUBLE NOT NULL,
    sections_json JSON NOT NULL,
    score_out_of DOUBLE NOT NULL DEFAULT 20,
    allows_immediate_hints BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exam_archives (
    id BIGINT PRIMARY KEY,
    archive_code VARCHAR NOT NULL UNIQUE,
    title VARCHAR NOT NULL,
    year INTEGER NOT NULL,
    session VARCHAR NOT NULL,
    zone VARCHAR NOT NULL,
    series VARCHAR NOT NULL,
    exam_code VARCHAR NOT NULL,
    duration_minutes INTEGER NOT NULL,
    provenance VARCHAR NOT NULL,
    source_reference VARCHAR NOT NULL,
    validation_status VARCHAR NOT NULL,
    curriculum_compatibility VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exam_archive_sections (
    id BIGINT PRIMARY KEY,
    archive_id BIGINT NOT NULL REFERENCES exam_archives(id),
    section_code VARCHAR NOT NULL,
    label VARCHAR NOT NULL,
    position INTEGER NOT NULL,
    UNIQUE (archive_id, section_code)
);

CREATE TABLE IF NOT EXISTS exam_archive_questions (
    id BIGINT PRIMARY KEY,
    archive_id BIGINT NOT NULL REFERENCES exam_archives(id),
    section_id BIGINT REFERENCES exam_archive_sections(id),
    position INTEGER NOT NULL,
    prompt VARCHAR NOT NULL,
    max_points DOUBLE,
    source_fingerprint VARCHAR,
    UNIQUE (archive_id, position)
);

CREATE TABLE IF NOT EXISTS exam_archive_skill_links (
    archive_question_id BIGINT NOT NULL REFERENCES exam_archive_questions(id),
    skill_id BIGINT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    confidence DOUBLE NOT NULL DEFAULT 0.5,
    PRIMARY KEY (archive_question_id, skill_id)
);

CREATE TABLE IF NOT EXISTS brevet_mock_exams (
    id BIGINT PRIMARY KEY,
    learner_id BIGINT NOT NULL,
    scope VARCHAR NOT NULL,
    mode VARCHAR NOT NULL,
    exam_codes JSON NOT NULL,
    science_pair JSON,
    status VARCHAR NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oral_projects (
    id BIGINT PRIMARY KEY,
    learner_id BIGINT NOT NULL,
    title VARCHAR NOT NULL,
    problematique VARCHAR NOT NULL,
    outline_json JSON NOT NULL,
    current_stage VARCHAR NOT NULL,
    target_minutes INTEGER NOT NULL,
    status VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oral_simulations (
    id BIGINT PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES oral_projects(id),
    jury_questions_json JSON NOT NULL,
    feedback VARCHAR,
    scores_json JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO brevet_exam_templates(exam_code, label, subject_codes, duration_minutes, coefficient, sections_json, score_out_of, allows_immediate_hints)
VALUES
(
    'MATHEMATICS_WRITTEN',
    'Mathématiques — écrit',
    '["MATHEMATICS"]',
    120,
    2.0,
    '[{"code":"AUTOMATISMS","calculator_allowed":false,"max_points":6},{"code":"REASONING","calculator_allowed":true,"max_points":14}]',
    20,
    FALSE
),
(
    'FRENCH_WRITTEN',
    'Français — écrit',
    '["FRENCH"]',
    180,
    2.0,
    '[{"code":"COMPREHENSION","max_points":10},{"code":"GRAMMAR","max_points":4},{"code":"DICTATION","max_points":2},{"code":"WRITING","max_points":4}]',
    20,
    FALSE
),
(
    'HISTORY_GEOGRAPHY_EMC_WRITTEN',
    'Histoire-Géographie-EMC — écrit',
    '["HISTORY","GEOGRAPHY","EMC"]',
    120,
    2.0,
    '[{"code":"HISTORY_GEOGRAPHY","max_points":15},{"code":"EMC","max_points":5}]',
    20,
    FALSE
),
(
    'SCIENCES_WRITTEN',
    'Sciences — écrit',
    '["PHYSICS_CHEMISTRY","SVT","TECHNOLOGY"]',
    60,
    2.0,
    '[{"code":"SCIENCE_A","max_points":10},{"code":"SCIENCE_B","max_points":10}]',
    20,
    FALSE
),
(
    'ORAL',
    'Oral du DNB — soutenance',
    '["ORAL"]',
    15,
    0.0,
    '[{"code":"PRESENTATION","max_points":10},{"code":"JURY","max_points":10}]',
    20,
    FALSE
)
ON CONFLICT (exam_code) DO NOTHING;

INSERT INTO exam_archives(
    id, archive_code, title, year, session, zone, series, exam_code,
    duration_minutes, provenance, source_reference, validation_status, curriculum_compatibility
)
VALUES
(
    1,
    'DNB-2026-METROPOLE-MATHS',
    'DNB 2026 Métropole — Mathématiques',
    2026,
    'normale',
    'metropole',
    'generale',
    'MATHEMATICS_WRITTEN',
    120,
    'OFFICIAL_EXAM',
    'Éduscol / MEN — annales DNB',
    'REVIEW',
    'FR_3E_2027_TRAINING'
),
(
    2,
    'DNB-2026-METROPOLE-FRANCAIS',
    'DNB 2026 Métropole — Français',
    2026,
    'normale',
    'metropole',
    'generale',
    'FRENCH_WRITTEN',
    180,
    'OFFICIAL_EXAM',
    'Éduscol / MEN — annales DNB',
    'REVIEW',
    'FR_3E_2027_TRAINING'
),
(
    3,
    'DNB-MATHS-SUJET-ZERO-A',
    'Sujet zéro officiel Mathématiques A',
    2026,
    'sujet_zero',
    'national',
    'generale',
    'MATHEMATICS_WRITTEN',
    120,
    'OFFICIAL_ZERO_SUBJECT',
    'Éduscol — sujet zéro',
    'REVIEW',
    'FR_3E_2027_PARTIAL'
)
ON CONFLICT (id) DO NOTHING;
