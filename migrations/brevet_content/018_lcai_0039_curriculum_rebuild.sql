-- LCAI-0039 — curriculum rebuild support tables (additive, idempotent)

ALTER TABLE chapters ADD COLUMN IF NOT EXISTS curriculum_role VARCHAR DEFAULT 'CANONICAL_3E';
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS curriculum_status VARCHAR DEFAULT 'ACTIVE';
ALTER TABLE skills ADD COLUMN IF NOT EXISTS curriculum_role VARCHAR DEFAULT 'CANONICAL_3E';
ALTER TABLE skills ADD COLUMN IF NOT EXISTS coverage_status VARCHAR DEFAULT 'EMPTY';
ALTER TABLE subskills ADD COLUMN IF NOT EXISTS curriculum_role VARCHAR DEFAULT 'CANONICAL_3E';

CREATE SEQUENCE IF NOT EXISTS seq_bref_curriculum_node_mapping START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_curriculum_rebuild_run START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_content_factory_run START 1;

CREATE TABLE IF NOT EXISTS curriculum_node_mappings (
    mapping_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_curriculum_node_mapping'),
    legacy_node_type VARCHAR NOT NULL,
    legacy_curriculum_node_id BIGINT NOT NULL,
    canonical_node_type VARCHAR NOT NULL,
    canonical_curriculum_node_id BIGINT NOT NULL,
    mapping_type VARCHAR NOT NULL,
    mapping_reason VARCHAR,
    subject_code VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (legacy_node_type, legacy_curriculum_node_id, canonical_node_type, canonical_curriculum_node_id, mapping_type)
);

CREATE TABLE IF NOT EXISTS curriculum_coverage_status (
    skill_id BIGINT PRIMARY KEY REFERENCES skills(skill_id),
    coverage_status VARCHAR NOT NULL,
    exercise_count INTEGER NOT NULL DEFAULT 0,
    family_count INTEGER NOT NULL DEFAULT 0,
    context_count INTEGER NOT NULL DEFAULT 0,
    format_count INTEGER NOT NULL DEFAULT 0,
    official_count INTEGER NOT NULL DEFAULT 0,
    archive_derived_count INTEGER NOT NULL DEFAULT 0,
    brevet_style_count INTEGER NOT NULL DEFAULT 0,
    ai_generated_count INTEGER NOT NULL DEFAULT 0,
    correction_coverage DOUBLE NOT NULL DEFAULT 0.0,
    asset_completeness DOUBLE NOT NULL DEFAULT 1.0,
    difficulty_span INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS curriculum_rebuild_runs (
    run_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_curriculum_rebuild_run'),
    mode VARCHAR NOT NULL,
    subject_filter VARCHAR,
    dry_run BOOLEAN NOT NULL DEFAULT TRUE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    db_sha256_before VARCHAR,
    db_sha256_after VARCHAR,
    stats_json VARCHAR,
    verdicts_json VARCHAR
);

CREATE TABLE IF NOT EXISTS content_factory_runs (
    run_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_content_factory_run'),
    subject_filter VARCHAR,
    dry_run BOOLEAN NOT NULL DEFAULT TRUE,
    created_count INTEGER NOT NULL DEFAULT 0,
    reused_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    report_json VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_curriculum_node_mappings_legacy
    ON curriculum_node_mappings(legacy_node_type, legacy_curriculum_node_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_node_mappings_canonical
    ON curriculum_node_mappings(canonical_node_type, canonical_curriculum_node_id);
CREATE INDEX IF NOT EXISTS idx_chapters_curriculum_role ON chapters(curriculum_role);
CREATE INDEX IF NOT EXISTS idx_skills_coverage_status ON skills(coverage_status);
