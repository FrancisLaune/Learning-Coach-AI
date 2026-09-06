-- LCAI-0036 — pedagogical validation metadata (additive, no FK-parent UPDATEs required)

CREATE SEQUENCE IF NOT EXISTS seq_bref_ped_assessment START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_ped_history START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_ped_run START 1;

CREATE TABLE IF NOT EXISTS pedagogical_validation_runs (
    run_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_ped_run'),
    ticket VARCHAR NOT NULL DEFAULT 'LCAI-0036',
    validator_version VARCHAR NOT NULL,
    ruleset_version VARCHAR NOT NULL,
    curriculum_version_code VARCHAR NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status VARCHAR NOT NULL DEFAULT 'RUNNING',
    summary_json VARCHAR
);

CREATE TABLE IF NOT EXISTS content_pedagogical_assessments (
    assessment_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_ped_assessment'),
    content_id BIGINT NOT NULL UNIQUE,
    archive_question_id BIGINT,
    archive_id BIGINT,
    run_id BIGINT REFERENCES pedagogical_validation_runs(run_id),
    subject_group VARCHAR,
    discipline VARCHAR,
    pedagogical_content_type VARCHAR,
    primary_skill_code VARCHAR,
    secondary_skill_codes VARCHAR,
    mapping_confidence DOUBLE,
    mapping_method VARCHAR,
    mapping_status VARCHAR,
    segmentation_ok BOOLEAN,
    segmentation_confidence DOUBLE,
    assets_required BOOLEAN DEFAULT FALSE,
    assets_complete BOOLEAN DEFAULT TRUE,
    required_asset_count INTEGER DEFAULT 0,
    available_asset_count INTEGER DEFAULT 0,
    correction_source VARCHAR DEFAULT 'NONE',
    correction_quality_status VARCHAR DEFAULT 'MISSING',
    grading_mode VARCHAR,
    curriculum_2027_compatible VARCHAR NOT NULL DEFAULT 'REVIEW',
    compatibility_reason VARCHAR,
    compatibility_method VARCHAR,
    compatibility_confidence DOUBLE,
    compatibility_checked_at TIMESTAMPTZ,
    curriculum_version_id BIGINT,
    pedagogical_validation_status VARCHAR NOT NULL DEFAULT 'REVIEW',
    pedagogical_reliability_score DOUBLE,
    reliability_class VARCHAR,
    runtime_playable_recommended BOOLEAN DEFAULT FALSE,
    historical_automatism_like BOOLEAN DEFAULT FALSE,
    suitable_for_2027_automatism_training VARCHAR DEFAULT 'REVIEW',
    review_priority DOUBLE DEFAULT 0,
    issue_types VARCHAR,
    warnings VARCHAR,
    requires_human_review BOOLEAN NOT NULL DEFAULT TRUE,
    validator_version VARCHAR,
    ruleset_version VARCHAR,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pedagogical_validation_history (
    history_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_ped_history'),
    content_id BIGINT NOT NULL,
    field_name VARCHAR NOT NULL,
    old_value VARCHAR,
    new_value VARCHAR,
    actor_type VARCHAR NOT NULL,
    actor_id VARCHAR,
    reason VARCHAR,
    curriculum_version_code VARCHAR,
    validator_version VARCHAR,
    ruleset_version VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Optional runtime playability override without updating content_items parents.
CREATE TABLE IF NOT EXISTS content_playability_overrides (
    content_id BIGINT PRIMARY KEY,
    runtime_playable BOOLEAN NOT NULL,
    reason VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content_validation_overrides (
    content_id BIGINT PRIMARY KEY,
    pedagogical_validation_status VARCHAR,
    curriculum_2027_compatible VARCHAR,
    compatibility_reason VARCHAR,
    reason VARCHAR NOT NULL,
    actor_type VARCHAR NOT NULL DEFAULT 'HUMAN_REVIEWER',
    actor_id VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
