-- LCAI-0037 — automatic certification journal (no semicolons inside comments)

CREATE SEQUENCE IF NOT EXISTS seq_bref_auto_cert_run START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_auto_cert_decision START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bref_correction_mech START 1;

CREATE TABLE IF NOT EXISTS automatic_certification_runs (
    run_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_auto_cert_run'),
    ticket VARCHAR NOT NULL DEFAULT 'LCAI-0037',
    validator_version VARCHAR NOT NULL,
    curriculum_version_code VARCHAR NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status VARCHAR NOT NULL DEFAULT 'RUNNING',
    summary_json VARCHAR
);

CREATE TABLE IF NOT EXISTS automatic_certification_decisions (
    decision_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_auto_cert_decision'),
    run_id BIGINT REFERENCES automatic_certification_runs(run_id),
    content_id BIGINT NOT NULL,
    previous_validation_status VARCHAR,
    previous_compatibility VARCHAR,
    final_validation_status VARCHAR NOT NULL,
    final_compatibility VARCHAR NOT NULL,
    decision VARCHAR NOT NULL,
    confidence DOUBLE,
    pass_a_summary VARCHAR,
    pass_b_summary VARCHAR,
    reconciliation VARCHAR,
    reason VARCHAR,
    exception_code VARCHAR,
    validator_version VARCHAR,
    model_name VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content_correction_mechanisms (
    mechanism_id BIGINT PRIMARY KEY DEFAULT nextval('seq_bref_correction_mech'),
    content_id BIGINT NOT NULL UNIQUE,
    correction_source VARCHAR NOT NULL,
    correction_text VARCHAR,
    expected_answer VARCHAR,
    grading_mode VARCHAR NOT NULL,
    rubric_json VARCHAR,
    points_max DOUBLE,
    points_are_official BOOLEAN NOT NULL DEFAULT FALSE,
    solution_verified BOOLEAN NOT NULL DEFAULT FALSE,
    grading_rubric_verified BOOLEAN NOT NULL DEFAULT FALSE,
    generator_version VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE content_pedagogical_assessments ADD COLUMN IF NOT EXISTS certification_confidence DOUBLE;
ALTER TABLE content_pedagogical_assessments ADD COLUMN IF NOT EXISTS exception_code VARCHAR;
ALTER TABLE content_pedagogical_assessments ADD COLUMN IF NOT EXISTS solution_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE content_pedagogical_assessments ADD COLUMN IF NOT EXISTS grading_rubric_verified BOOLEAN DEFAULT FALSE;
