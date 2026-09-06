-- LCAI-0032 — coverage view

CREATE OR REPLACE VIEW v_content_coverage AS
SELECT
    sub.code AS subject,
    ch.name AS chapter,
    sk.code AS skill,
    sk.brevet_importance AS brevet_importance,
    COUNT(DISTINCT ci.content_id) FILTER (
        WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
    ) AS total_validated,
    COUNT(DISTINCT ci.content_id) FILTER (
        WHERE ci.source_type = 'OFFICIAL_ARCHIVE'
          AND ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
    ) AS official_archive_count,
    COUNT(DISTINCT ci.content_id) FILTER (
        WHERE ci.source_type = 'ARCHIVE_DERIVED'
          AND ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
    ) AS archive_derived_count,
    COUNT(DISTINCT ci.content_id) FILTER (
        WHERE ci.source_type = 'AI_GENERATED'
          AND ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
    ) AS ai_generated_count,
    COUNT(DISTINCT ci.content_id) FILTER (
        WHERE ci.source_type IN ('CURATED', 'LEGACY_BANK')
          AND ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
    ) AS curated_count,
    COUNT(DISTINCT ci.brevet_format) FILTER (
        WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
    ) AS unique_formats,
    MIN(ci.difficulty_score) FILTER (
        WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
    ) AS difficulty_min,
    MAX(ci.difficulty_score) FILTER (
        WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
    ) AS difficulty_max,
    CASE
        WHEN COUNT(DISTINCT ci.content_id) FILTER (
            WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
        ) = 0 THEN 'EMPTY'
        WHEN COUNT(DISTINCT ci.content_id) FILTER (
            WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
        ) < 10 THEN 'INSUFFICIENT'
        WHEN COUNT(DISTINCT ci.content_id) FILTER (
            WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
        ) < 20 THEN 'PARTIAL'
        WHEN COUNT(DISTINCT ci.content_id) FILTER (
            WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
        ) < 40 THEN 'COMPLETE'
        ELSE 'STRONG'
    END AS coverage_status
FROM skills sk
JOIN chapters ch ON ch.chapter_id = sk.chapter_id
JOIN curriculum_domains d ON d.domain_id = ch.domain_id
JOIN subjects sub ON sub.subject_id = d.subject_id
LEFT JOIN content_skill_links csl ON csl.skill_id = sk.skill_id
LEFT JOIN content_items ci ON ci.content_id = csl.content_id
WHERE sk.active
GROUP BY sub.code, ch.name, sk.code, sk.brevet_importance;
