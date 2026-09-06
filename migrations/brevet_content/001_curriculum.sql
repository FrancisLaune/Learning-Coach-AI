-- LCAI-0032 — curriculum référentiel 3e / DNB 2027

CREATE SEQUENCE IF NOT EXISTS seq_bref_curriculum_version START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_subject START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_domain START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_chapter START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_skill START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_subskill START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_prerequisite START 1;

CREATE TABLE IF NOT EXISTS bref_schema_migrations (
    version INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    checksum VARCHAR NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS curriculum_versions (
    curriculum_version_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_curriculum_version'),
    code VARCHAR NOT NULL UNIQUE,
    school_level VARCHAR NOT NULL,
    exam_session VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    status VARCHAR NOT NULL,
    source_url VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS subjects (
    subject_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_subject'),
    code VARCHAR NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    terminal_exam BOOLEAN NOT NULL DEFAULT TRUE,
    continuous_assessment BOOLEAN NOT NULL DEFAULT FALSE,
    brevet_exam_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS curriculum_domains (
    domain_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_domain'),
    curriculum_version_id BIGINT NOT NULL REFERENCES curriculum_versions(curriculum_version_id),
    subject_id BIGINT NOT NULL REFERENCES subjects(subject_id),
    code VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description VARCHAR,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (curriculum_version_id, subject_id, code)
);

CREATE TABLE IF NOT EXISTS chapters (
    chapter_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_chapter'),
    domain_id BIGINT NOT NULL REFERENCES curriculum_domains(domain_id),
    code VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description VARCHAR,
    brevet_importance VARCHAR NOT NULL DEFAULT 'MEDIUM',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (domain_id, code)
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_skill'),
    chapter_id BIGINT NOT NULL REFERENCES chapters(chapter_id),
    code VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description VARCHAR,
    expected_level VARCHAR NOT NULL DEFAULT '3E',
    brevet_importance VARCHAR NOT NULL DEFAULT 'MEDIUM',
    auto_gradable BOOLEAN NOT NULL DEFAULT TRUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (chapter_id, code)
);

CREATE TABLE IF NOT EXISTS subskills (
    subskill_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_subskill'),
    skill_id BIGINT NOT NULL REFERENCES skills(skill_id),
    code VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description VARCHAR,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (skill_id, code)
);

CREATE TABLE IF NOT EXISTS prerequisites (
    prerequisite_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_prerequisite'),
    target_skill_id BIGINT NOT NULL REFERENCES skills(skill_id),
    prerequisite_skill_code VARCHAR NOT NULL,
    prerequisite_level VARCHAR NOT NULL,
    strength DOUBLE NOT NULL DEFAULT 0.5,
    remediation_only BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO curriculum_versions(
    curriculum_version_id, code, school_level, exam_session, effective_from, status, source_url
)
SELECT 1, 'FR_3E_DNB_2027_V1', 'FR-3E', 'DNB-2027', DATE '2026-09-01', 'ACTIVE',
       'https://eduscol.education.fr/'
WHERE NOT EXISTS (SELECT 1 FROM curriculum_versions WHERE code = 'FR_3E_DNB_2027_V1');

INSERT INTO subjects(subject_id, code, name, terminal_exam, continuous_assessment, brevet_exam_enabled, sort_order)
SELECT * FROM (VALUES
    (1, 'FRENCH', 'Français', TRUE, TRUE, TRUE, 10),
    (2, 'MATHEMATICS', 'Mathématiques', TRUE, TRUE, TRUE, 20),
    (3, 'HISTORY', 'Histoire', TRUE, TRUE, TRUE, 30),
    (4, 'GEOGRAPHY', 'Géographie', TRUE, TRUE, TRUE, 40),
    (5, 'EMC', 'EMC', TRUE, TRUE, TRUE, 50),
    (6, 'PHYSICS_CHEMISTRY', 'Physique-Chimie', TRUE, TRUE, TRUE, 60),
    (7, 'SVT', 'SVT', TRUE, TRUE, TRUE, 70),
    (8, 'TECHNOLOGY', 'Technologie', TRUE, TRUE, TRUE, 80),
    (9, 'ORAL', 'Oral', TRUE, FALSE, TRUE, 90),
    (10, 'ENGLISH', 'Anglais', FALSE, TRUE, FALSE, 100),
    (11, 'SPANISH', 'Espagnol', FALSE, TRUE, FALSE, 110)
) AS v(subject_id, code, name, terminal_exam, continuous_assessment, brevet_exam_enabled, sort_order)
WHERE NOT EXISTS (SELECT 1 FROM subjects s WHERE s.code = v.code);
