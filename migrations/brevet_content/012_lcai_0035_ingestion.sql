-- LCAI-0035 — offline massive archive ingestion tracking

CREATE SEQUENCE IF NOT EXISTS seq_bref_ingest_run START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_ingest_event START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_archive_document START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_archive_asset START 1;

CREATE TABLE IF NOT EXISTS archive_ingestion_runs (
    run_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_ingest_run'),
    ticket VARCHAR NOT NULL DEFAULT 'LCAI-0035',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status VARCHAR NOT NULL DEFAULT 'RUNNING',
    parser_version VARCHAR NOT NULL,
    years_from INTEGER,
    years_to INTEGER,
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    summary_json VARCHAR
);

CREATE TABLE IF NOT EXISTS archive_ingestion_events (
    event_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_ingest_event'),
    run_id BIGINT REFERENCES archive_ingestion_runs(run_id),
    archive_id BIGINT,
    document_id BIGINT,
    event_type VARCHAR NOT NULL,
    status VARCHAR,
    detail VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS exam_archive_documents_ref (
    document_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_archive_document'),
    archive_id BIGINT NOT NULL REFERENCES exam_archives_ref(archive_id),
    exam_identity_key VARCHAR NOT NULL,
    source_provider VARCHAR NOT NULL DEFAULT 'EDUSCOL',
    document_url VARCHAR NOT NULL,
    document_type VARCHAR NOT NULL DEFAULT 'SUBJECT',
    document_variant VARCHAR NOT NULL DEFAULT 'STANDARD',
    local_path VARCHAR,
    source_hash VARCHAR NOT NULL,
    page_count INTEGER,
    download_status VARCHAR NOT NULL DEFAULT 'PENDING',
    parse_status VARCHAR NOT NULL DEFAULT 'PENDING',
    mapping_status VARCHAR NOT NULL DEFAULT 'PENDING',
    validation_status VARCHAR NOT NULL DEFAULT 'REVIEW',
    parser_version VARCHAR,
    extraction_method VARCHAR,
    parser_confidence DOUBLE,
    eduscol_document_id VARCHAR,
    official_exam_code VARCHAR,
    last_checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_hash)
);

CREATE TABLE IF NOT EXISTS exam_archive_assets_ref (
    asset_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_archive_asset'),
    archive_id BIGINT NOT NULL REFERENCES exam_archives_ref(archive_id),
    document_id BIGINT REFERENCES exam_archive_documents_ref(document_id),
    asset_type VARCHAR NOT NULL,
    source_page INTEGER,
    source_hash VARCHAR,
    mime_type VARCHAR,
    local_path VARCHAR,
    alt_text VARCHAR,
    required_for_questions VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS subject_group VARCHAR;
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS exam_identity_key VARCHAR;
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS landing_page_url VARCHAR;
ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS last_ingestion_run_id BIGINT;

ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS question_number VARCHAR;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS subquestion_number VARCHAR;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS official_points DOUBLE;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS estimated_points DOUBLE;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS question_kind VARCHAR;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS shared_context_ref VARCHAR;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS parser_confidence DOUBLE;
ALTER TABLE exam_archive_questions_ref ADD COLUMN IF NOT EXISTS extraction_method VARCHAR;

ALTER TABLE content_items ADD COLUMN IF NOT EXISTS archive_question_id BIGINT;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS source_locator VARCHAR;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS official_exam_code VARCHAR;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS archive_frequency_score DOUBLE;
