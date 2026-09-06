-- LCAI-0032 — exam archives model (referential)

CREATE SEQUENCE IF NOT EXISTS seq_bref_archive START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_archive_section START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_archive_question START 1;

CREATE TABLE IF NOT EXISTS exam_archives_ref (
    archive_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_archive'),
    year INTEGER NOT NULL,
    session VARCHAR NOT NULL,
    zone VARCHAR NOT NULL,
    series VARCHAR NOT NULL,
    subject_id BIGINT NOT NULL REFERENCES subjects(subject_id),
    exam_date DATE,
    duration_minutes INTEGER,
    official_title VARCHAR NOT NULL,
    official_source_url VARCHAR,
    official_document_ref VARCHAR,
    correction_source_url VARCHAR,
    source_hash VARCHAR,
    base_exam_identifier VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'DISCOVERED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (year, session, zone, series, subject_id, base_exam_identifier)
);

CREATE TABLE IF NOT EXISTS exam_archive_sections_ref (
    section_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_archive_section'),
    archive_id BIGINT NOT NULL REFERENCES exam_archives_ref(archive_id),
    position INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    section_type VARCHAR,
    points DOUBLE,
    calculator_allowed BOOLEAN,
    duration_minutes INTEGER,
    UNIQUE (archive_id, position)
);

CREATE TABLE IF NOT EXISTS exam_archive_questions_ref (
    archive_question_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_archive_question'),
    section_id BIGINT NOT NULL REFERENCES exam_archive_sections_ref(section_id),
    position INTEGER NOT NULL,
    original_question_reference VARCHAR,
    content_id BIGINT REFERENCES content_items(content_id),
    points DOUBLE,
    curriculum_2027_compatible VARCHAR NOT NULL DEFAULT 'REVIEW',
    compatibility_reason VARCHAR,
    extraction_status VARCHAR NOT NULL DEFAULT 'PENDING',
    validation_status VARCHAR NOT NULL DEFAULT 'DRAFT',
    UNIQUE (section_id, position)
);

CREATE TABLE IF NOT EXISTS archive_import_events (
    event_id BIGINT PRIMARY KEY,
    archive_id BIGINT REFERENCES exam_archives_ref(archive_id),
    event_type VARCHAR NOT NULL,
    detail VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
