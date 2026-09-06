-- LCAI-0032 — content_items + links + assets + derivations

CREATE SEQUENCE IF NOT EXISTS seq_bref_content START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_content_skill START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_asset START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_derivation START 1;

CREATE TABLE IF NOT EXISTS content_items (
    content_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_content'),
    content_type VARCHAR NOT NULL,
    source_type VARCHAR NOT NULL,
    subject_id BIGINT NOT NULL REFERENCES subjects(subject_id),
    chapter_id BIGINT REFERENCES chapters(chapter_id),
    title VARCHAR NOT NULL,
    statement VARCHAR NOT NULL,
    answer_type VARCHAR NOT NULL DEFAULT 'SHORT_TEXT',
    expected_answer VARCHAR,
    accepted_answers_json VARCHAR,
    correction VARCHAR,
    hint VARCHAR,
    difficulty_score DOUBLE,
    difficulty_label VARCHAR,
    estimated_seconds INTEGER,
    brevet_format VARCHAR,
    curriculum_2027_compatible VARCHAR NOT NULL DEFAULT 'TRUE',
    runtime_playable BOOLEAN NOT NULL DEFAULT TRUE,
    validation_status VARCHAR NOT NULL DEFAULT 'DRAFT',
    quality_score DOUBLE,
    fingerprint VARCHAR NOT NULL,
    semantic_fingerprint VARCHAR,
    usage_policy VARCHAR NOT NULL DEFAULT 'AVAILABLE_FOR_PRACTICE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_content_items_fingerprint ON content_items(fingerprint);
CREATE INDEX IF NOT EXISTS idx_content_items_subject ON content_items(subject_id);
CREATE INDEX IF NOT EXISTS idx_content_items_chapter ON content_items(chapter_id);
CREATE INDEX IF NOT EXISTS idx_content_items_source ON content_items(source_type);
CREATE INDEX IF NOT EXISTS idx_content_items_status ON content_items(validation_status);

CREATE TABLE IF NOT EXISTS content_skill_links (
    content_id BIGINT NOT NULL REFERENCES content_items(content_id),
    skill_id BIGINT NOT NULL REFERENCES skills(skill_id),
    subskill_id BIGINT REFERENCES subskills(subskill_id),
    relation_type VARCHAR NOT NULL DEFAULT 'PRIMARY',
    weight DOUBLE NOT NULL DEFAULT 1.0,
    PRIMARY KEY (content_id, skill_id, relation_type)
);

CREATE TABLE IF NOT EXISTS content_assets (
    asset_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_asset'),
    content_id BIGINT NOT NULL REFERENCES content_items(content_id),
    asset_type VARCHAR NOT NULL,
    file_path VARCHAR,
    source_url VARCHAR,
    copyright_status VARCHAR,
    alt_text VARCHAR,
    checksum VARCHAR
);

CREATE TABLE IF NOT EXISTS content_derivations (
    derived_content_id BIGINT NOT NULL REFERENCES content_items(content_id),
    source_content_id BIGINT NOT NULL REFERENCES content_items(content_id),
    derivation_type VARCHAR NOT NULL,
    transformation_version VARCHAR NOT NULL DEFAULT 'v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (derived_content_id, source_content_id)
);
