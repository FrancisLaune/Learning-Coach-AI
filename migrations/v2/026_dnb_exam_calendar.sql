-- LCAI-0031 Phase 1 — versioned DNB exam calendar (additive, no data destruction).

CREATE TABLE IF NOT EXISTS exam_calendar (
    id BIGINT PRIMARY KEY,
    version VARCHAR NOT NULL UNIQUE,
    session_code VARCHAR NOT NULL,
    timezone VARCHAR NOT NULL DEFAULT 'Europe/Paris',
    source_reference VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exam_session (
    id BIGINT PRIMARY KEY,
    calendar_id BIGINT NOT NULL REFERENCES exam_calendar(id),
    session_code VARCHAR NOT NULL,
    label VARCHAR NOT NULL,
    UNIQUE (calendar_id, session_code)
);

CREATE TABLE IF NOT EXISTS exam_date (
    id BIGINT PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES exam_session(id),
    exam_code VARCHAR NOT NULL,
    label VARCHAR NOT NULL,
    exam_date DATE NOT NULL,
    duration_minutes INTEGER,
    coefficient DOUBLE,
    subject_codes JSON NOT NULL,
    UNIQUE (session_id, exam_code)
);

INSERT INTO exam_calendar(id, version, session_code, timezone, source_reference, effective_from)
VALUES (
    1,
    'DNB-2027-METROPOLE-V1',
    'DNB-2027',
    'Europe/Paris',
    'Calendrier prévisionnel session normale DNB 2027 — métropole (écrits)',
    DATE '2026-09-01'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO exam_session(id, calendar_id, session_code, label)
VALUES (1, 1, 'DNB-2027', 'Diplôme National du Brevet — session 2027')
ON CONFLICT (id) DO NOTHING;

INSERT INTO exam_date(id, session_id, exam_code, label, exam_date, duration_minutes, coefficient, subject_codes)
VALUES
    (1, 1, 'FRENCH_WRITTEN', 'Français — écrit', DATE '2027-06-24', 180, 2.0, '["FRENCH"]'),
    (2, 1, 'HISTORY_GEOGRAPHY_EMC_WRITTEN', 'Histoire-Géographie-EMC — écrit', DATE '2027-06-25', 120, 2.0, '["HISTORY","GEOGRAPHY","EMC"]'),
    (3, 1, 'SCIENCES_WRITTEN', 'Sciences — écrit', DATE '2027-06-28', 60, 2.0, '["PHYSICS_CHEMISTRY","SVT","TECHNOLOGY"]'),
    (4, 1, 'MATHEMATICS_WRITTEN', 'Mathématiques — écrit', DATE '2027-06-28', 120, 2.0, '["MATHEMATICS"]')
ON CONFLICT (id) DO NOTHING;
