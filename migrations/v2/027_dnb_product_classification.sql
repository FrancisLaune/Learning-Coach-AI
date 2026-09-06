-- LCAI-0031 Phase 2 — classify grades/subjects for DNB recentrage (additive, no DELETE).

ALTER TABLE school_levels ADD COLUMN IF NOT EXISTS product_role VARCHAR;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS assessment_role VARCHAR;

UPDATE school_levels
SET product_role = 'terminal'
WHERE code = 'FR-3E' AND (product_role IS NULL OR product_role = '');

UPDATE school_levels
SET product_role = 'remediation'
WHERE code IN ('FR-CM1', 'FR-CM2', 'FR-6E', 'FR-5E', 'FR-4E')
  AND (product_role IS NULL OR product_role = '');

UPDATE school_levels
SET product_role = 'out_of_scope'
WHERE code IN ('FR-2NDE', 'FR-1ERE', 'FR-TERM')
  AND (product_role IS NULL OR product_role = '');

UPDATE subjects
SET assessment_role = 'continuous'
WHERE code IN ('ENGLISH', 'SPANISH')
  AND (assessment_role IS NULL OR assessment_role = '');

UPDATE subjects
SET assessment_role = 'terminal'
WHERE code IN (
    'FRENCH',
    'MATHEMATICS',
    'HISTORY',
    'GEOGRAPHY',
    'EMC',
    'PHYSICS_CHEMISTRY',
    'SVT',
    'TECHNOLOGY'
)
  AND (assessment_role IS NULL OR assessment_role = '');

CREATE TABLE IF NOT EXISTS subject_dnb_capabilities (
    subject_id BIGINT PRIMARY KEY REFERENCES subjects(id),
    terminal_exam BOOLEAN NOT NULL,
    continuous_assessment BOOLEAN NOT NULL,
    supports_brevet_exam BOOLEAN NOT NULL,
    supports_revision BOOLEAN NOT NULL,
    supports_ai_generation BOOLEAN NOT NULL,
    supports_long_answer BOOLEAN NOT NULL,
    supports_oral BOOLEAN NOT NULL DEFAULT FALSE,
    in_science_pool BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO subject_dnb_capabilities (
    subject_id,
    terminal_exam,
    continuous_assessment,
    supports_brevet_exam,
    supports_revision,
    supports_ai_generation,
    supports_long_answer,
    supports_oral,
    in_science_pool
)
SELECT s.id, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, FALSE,
       s.code IN ('PHYSICS_CHEMISTRY', 'SVT', 'TECHNOLOGY')
FROM subjects s
WHERE s.code IN (
    'FRENCH', 'MATHEMATICS', 'HISTORY', 'GEOGRAPHY', 'EMC',
    'PHYSICS_CHEMISTRY', 'SVT', 'TECHNOLOGY'
)
ON CONFLICT (subject_id) DO UPDATE SET
    terminal_exam = EXCLUDED.terminal_exam,
    continuous_assessment = EXCLUDED.continuous_assessment,
    supports_brevet_exam = EXCLUDED.supports_brevet_exam,
    supports_revision = EXCLUDED.supports_revision,
    supports_ai_generation = EXCLUDED.supports_ai_generation,
    supports_long_answer = EXCLUDED.supports_long_answer,
    supports_oral = EXCLUDED.supports_oral,
    in_science_pool = EXCLUDED.in_science_pool,
    updated_at = now();

INSERT INTO subject_dnb_capabilities (
    subject_id,
    terminal_exam,
    continuous_assessment,
    supports_brevet_exam,
    supports_revision,
    supports_ai_generation,
    supports_long_answer,
    supports_oral,
    in_science_pool
)
SELECT s.id, FALSE, TRUE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE
FROM subjects s
WHERE s.code IN ('ENGLISH', 'SPANISH')
ON CONFLICT (subject_id) DO UPDATE SET
    terminal_exam = EXCLUDED.terminal_exam,
    continuous_assessment = EXCLUDED.continuous_assessment,
    supports_brevet_exam = EXCLUDED.supports_brevet_exam,
    supports_revision = EXCLUDED.supports_revision,
    supports_ai_generation = EXCLUDED.supports_ai_generation,
    supports_long_answer = EXCLUDED.supports_long_answer,
    supports_oral = EXCLUDED.supports_oral,
    in_science_pool = EXCLUDED.in_science_pool,
    updated_at = now();

CREATE TABLE IF NOT EXISTS curriculum_versions (
    id BIGINT PRIMARY KEY,
    code VARCHAR NOT NULL UNIQUE,
    grade_code VARCHAR NOT NULL,
    session_code VARCHAR NOT NULL,
    label VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'active',
    effective_from DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO curriculum_versions(id, code, grade_code, session_code, label, status, effective_from)
VALUES (
    1,
    'FR_3E_2027_V1',
    'FR-3E',
    'DNB-2027',
    'Curriculum 3e — Objectif Brevet 2027 V1',
    'active',
    DATE '2026-09-01'
)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS program_product_links (
    product_program_id BIGINT NOT NULL REFERENCES programs(id),
    curriculum_program_id BIGINT NOT NULL REFERENCES programs(id),
    link_role VARCHAR NOT NULL,
    PRIMARY KEY (product_program_id, curriculum_program_id, link_role)
);

INSERT INTO program_product_links(product_program_id, curriculum_program_id, link_role)
SELECT b.id, c.id, 'curriculum_source'
FROM programs b
JOIN programs c ON c.code = 'FR-CYCLE4-3E'
WHERE b.code = 'BREVET' AND b.version = '2027'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS content_migration_classifications (
    content_id BIGINT NOT NULL,
    grade_code VARCHAR NOT NULL,
    subject_code VARCHAR NOT NULL,
    classification VARCHAR NOT NULL,
    reason VARCHAR NOT NULL,
    classified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (content_id, grade_code)
);
