-- LCAI-0034 — coverage view with families / brevet_style / grounding

DROP VIEW IF EXISTS v_content_coverage;

CREATE OR REPLACE VIEW v_content_coverage AS
SELECT
    s.code AS subject,
    ch.name AS chapter,
    sk.code AS skill,
    sk.brevet_importance,
    COUNT(c.content_id) FILTER (
        WHERE c.validation_status IN ('AUTO_VALIDATED', 'APPROVED', 'REVIEW')
    ) AS total_validated,
    COUNT(c.content_id) FILTER (WHERE c.runtime_playable) AS playable_count,
    COUNT(DISTINCT c.family_id) FILTER (WHERE c.family_id IS NOT NULL) AS unique_family_count,
    COUNT(c.content_id) FILTER (WHERE c.source_type = 'OFFICIAL_ARCHIVE') AS official_archive_count,
    COUNT(c.content_id) FILTER (WHERE c.source_type = 'ARCHIVE_DERIVED') AS archive_derived_count,
    COUNT(c.content_id) FILTER (WHERE c.source_type = 'BREVET_STYLE') AS brevet_style_count,
    COUNT(c.content_id) FILTER (WHERE c.source_type = 'AI_GENERATED') AS ai_generated_count,
    COUNT(c.content_id) FILTER (WHERE c.source_type = 'CURATED') AS curated_count,
    COUNT(DISTINCT c.brevet_format) AS unique_formats,
    MIN(c.difficulty_score) AS difficulty_min,
    MAX(c.difficulty_score) AS difficulty_max,
    CASE
        WHEN COUNT(c.content_id) FILTER (WHERE c.runtime_playable) = 0 THEN 0.0
        ELSE CAST(COUNT(c.content_id) FILTER (
            WHERE c.source_type IN ('OFFICIAL_ARCHIVE', 'ARCHIVE_DERIVED') AND c.runtime_playable
        ) AS DOUBLE)
        / CAST(COUNT(c.content_id) FILTER (WHERE c.runtime_playable) AS DOUBLE)
    END AS archive_grounding_rate,
    CASE
        WHEN COUNT(c.content_id) FILTER (WHERE c.runtime_playable) = 0 THEN 'EMPTY'
        WHEN COUNT(c.content_id) FILTER (WHERE c.runtime_playable) < 5 THEN 'CRITICAL_SHORTAGE'
        WHEN COUNT(c.content_id) FILTER (WHERE c.runtime_playable) < 20 THEN 'INSUFFICIENT'
        WHEN COUNT(DISTINCT c.family_id) FILTER (WHERE c.family_id IS NOT NULL) < 8
             AND sk.brevet_importance = 'MEDIUM' THEN 'LOW_DIVERSITY'
        WHEN COUNT(DISTINCT c.family_id) FILTER (WHERE c.family_id IS NOT NULL) < 10
             AND sk.brevet_importance = 'HIGH' THEN 'LOW_DIVERSITY'
        WHEN COUNT(DISTINCT c.family_id) FILTER (WHERE c.family_id IS NOT NULL) < 12
             AND sk.brevet_importance = 'CRITICAL' THEN 'LOW_DIVERSITY'
        WHEN COUNT(c.content_id) FILTER (WHERE c.runtime_playable) < 30 THEN 'USABLE'
        WHEN COUNT(c.content_id) FILTER (WHERE c.runtime_playable) < 40 THEN 'COMPLETE'
        ELSE 'STRONG'
    END AS coverage_status
FROM skills sk
JOIN chapters ch ON ch.chapter_id = sk.chapter_id
JOIN curriculum_domains d ON d.domain_id = ch.domain_id
JOIN subjects s ON s.subject_id = d.subject_id
LEFT JOIN content_skill_links l ON l.skill_id = sk.skill_id
LEFT JOIN content_items c ON c.content_id = l.content_id
WHERE sk.active
GROUP BY s.code, ch.name, sk.code, sk.brevet_importance;
