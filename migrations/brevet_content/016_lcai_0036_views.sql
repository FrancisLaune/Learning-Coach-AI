-- LCAI-0036 — indexes + certified coverage / review views

CREATE INDEX IF NOT EXISTS idx_bref_ped_assess_status
ON content_pedagogical_assessments(pedagogical_validation_status);

CREATE INDEX IF NOT EXISTS idx_bref_ped_assess_compat
ON content_pedagogical_assessments(curriculum_2027_compatible);

CREATE INDEX IF NOT EXISTS idx_bref_ped_assess_reliability
ON content_pedagogical_assessments(reliability_class);

CREATE INDEX IF NOT EXISTS idx_bref_ped_history_content
ON pedagogical_validation_history(content_id);

CREATE OR REPLACE VIEW v_official_pedagogical_effective AS
SELECT
    c.content_id,
    c.source_type,
    c.subject_id,
    c.title,
    c.statement,
    c.brevet_format,
    c.fingerprint,
    COALESCE(vo.pedagogical_validation_status, a.pedagogical_validation_status, c.validation_status) AS pedagogical_validation_status,
    COALESCE(vo.curriculum_2027_compatible, a.curriculum_2027_compatible, c.curriculum_2027_compatible) AS curriculum_2027_compatible,
    COALESCE(vo.compatibility_reason, a.compatibility_reason) AS compatibility_reason,
    COALESCE(po.runtime_playable, a.runtime_playable_recommended, c.runtime_playable) AS runtime_playable,
    a.subject_group,
    a.discipline,
    a.pedagogical_content_type,
    a.primary_skill_code,
    a.mapping_confidence,
    a.segmentation_confidence,
    a.assets_complete,
    a.correction_source,
    a.correction_quality_status,
    a.pedagogical_reliability_score,
    a.reliability_class,
    a.review_priority,
    a.warnings,
    a.requires_human_review,
    a.archive_id,
    a.archive_question_id,
    a.curriculum_version_id,
    a.compatibility_confidence,
    a.validator_version,
    a.ruleset_version
FROM content_items c
LEFT JOIN content_pedagogical_assessments a ON a.content_id = c.content_id
LEFT JOIN content_validation_overrides vo ON vo.content_id = c.content_id
LEFT JOIN content_playability_overrides po ON po.content_id = c.content_id
WHERE c.source_type = 'OFFICIAL_ARCHIVE';

CREATE OR REPLACE VIEW v_pedagogical_review_queue AS
SELECT
    e.content_id AS question_id,
    COALESCE(sub.code, e.subject_group) AS subject,
    ar.year,
    e.primary_skill_code AS skill,
    e.warnings AS issue_type,
    e.review_priority AS priority,
    e.mapping_confidence,
    e.compatibility_confidence,
    e.pedagogical_reliability_score AS reliability_score,
    e.warnings,
    e.pedagogical_validation_status,
    e.curriculum_2027_compatible
FROM v_official_pedagogical_effective e
LEFT JOIN subjects sub ON sub.subject_id = e.subject_id
LEFT JOIN exam_archives_ref ar ON ar.archive_id = e.archive_id
WHERE COALESCE(e.pedagogical_validation_status, 'REVIEW') IN ('PENDING', 'AUTO_CHECKED', 'REVIEW', 'REJECTED')
   OR COALESCE(e.curriculum_2027_compatible, 'REVIEW') <> 'TRUE'
   OR COALESCE(e.requires_human_review, TRUE) = TRUE;
