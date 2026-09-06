-- LCAI-0034 — traceability, families, legacy mapping, archive enrichment

ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS source_provider VARCHAR DEFAULT 'EDUSCOL';
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS source_document_url VARCHAR;
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS document_variant VARCHAR DEFAULT 'STANDARD';
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS exam_identity VARCHAR;
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS downloaded_at TIMESTAMPTZ;
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS parser_version VARCHAR;
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS import_status VARCHAR;
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS curriculum_version_id BIGINT;
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS parent_question_id BIGINT;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS statement VARCHAR;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS expected_answer VARCHAR;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS correction VARCHAR;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS support_required BOOLEAN DEFAULT FALSE;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS source_page_start INTEGER;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS source_page_end INTEGER;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS source_locator VARCHAR;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS correction_source VARCHAR DEFAULT 'NONE';
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();

ALTER TABLE content_derivations ADD COLUMN IF NOT EXISTS parent_archive_id BIGINT;
ALTER TABLE content_derivations ADD COLUMN IF NOT EXISTS parent_question_id BIGINT;
ALTER TABLE content_derivations ADD COLUMN IF NOT EXISTS derivation_method VARCHAR;
ALTER TABLE content_derivations ADD COLUMN IF NOT EXISTS generator_version VARCHAR;
ALTER TABLE content_derivations ADD COLUMN IF NOT EXISTS validation_status VARCHAR DEFAULT 'DRAFT';

CREATE SEQUENCE IF NOT EXISTS seq_bref_family START 1;
CREATE TABLE IF NOT EXISTS exercise_families (
    family_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_family'),
    subject_id BIGINT REFERENCES subjects(subject_id),
    skill_id BIGINT REFERENCES skills(skill_id),
    family_type VARCHAR NOT NULL DEFAULT 'SEMANTIC_CLUSTER',
    canonical_pattern VARCHAR,
    source_question_id BIGINT,
    semantic_signature VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (semantic_signature)
);

ALTER TABLE content_items ADD COLUMN IF NOT EXISTS family_id BIGINT;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS semantic_family_id BIGINT;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS canonical_content_id VARCHAR;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS near_duplicate_class VARCHAR;

CREATE SEQUENCE IF NOT EXISTS seq_bref_legacy_map START 1;
CREATE TABLE IF NOT EXISTS legacy_content_mapping (
    mapping_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_legacy_map'),
    canonical_content_id VARCHAR NOT NULL,
    legacy_source VARCHAR NOT NULL,
    legacy_id VARCHAR NOT NULL,
    content_fingerprint VARCHAR,
    semantic_family_id BIGINT,
    migration_class VARCHAR NOT NULL,
    ob_content_id BIGINT REFERENCES content_items(content_id),
    notes VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (legacy_source, legacy_id)
);

CREATE SEQUENCE IF NOT EXISTS seq_bref_event START 1;
CREATE TABLE IF NOT EXISTS referential_events (
    event_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_event'),
    event_type VARCHAR NOT NULL,
    entity_ref VARCHAR,
    detail VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
