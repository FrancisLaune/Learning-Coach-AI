-- LCAI-0035 — official archive coverage views

CREATE OR REPLACE VIEW v_official_archive_coverage_by_year AS
SELECT
    a.year,
    a.session,
    a.zone,
    a.series,
    COALESCE(a.subject_group, sub.code) AS subject_group,
    COUNT(DISTINCT a.archive_id) AS archive_count,
    COUNT(DISTINCT d.document_id) AS document_count,
    COUNT(DISTINCT CASE WHEN d.parse_status IN ('PARSED', 'SEGMENTED', 'IMPORTED') THEN d.document_id END) AS parsed_count,
    COUNT(DISTINCT CASE WHEN c.source_type = 'OFFICIAL_ARCHIVE' THEN c.content_id END) AS official_question_count,
    COUNT(DISTINCT CASE WHEN c.source_type = 'OFFICIAL_ARCHIVE' AND c.validation_status = 'APPROVED' THEN c.content_id END) AS validated_question_count,
    COUNT(DISTINCT CASE WHEN c.source_type = 'OFFICIAL_ARCHIVE' AND c.curriculum_2027_compatible = 'TRUE' THEN c.content_id END) AS compatible_2027_count,
    COUNT(DISTINCT CASE WHEN c.source_type = 'OFFICIAL_ARCHIVE' AND c.validation_status = 'REVIEW' THEN c.content_id END) AS review_count,
    COUNT(DISTINCT CASE WHEN q.validation_status = 'REJECTED' THEN q.archive_question_id END) AS rejected_count,
    COUNT(DISTINCT CASE WHEN q.support_required AND ast.asset_id IS NULL THEN q.archive_question_id END) AS missing_asset_count,
    COUNT(DISTINCT CASE WHEN q.correction_source = 'OFFICIAL' THEN q.archive_question_id END) AS official_correction_count
FROM exam_archives_ref a
JOIN subjects sub ON sub.subject_id = a.subject_id
LEFT JOIN exam_archive_documents_ref d ON d.archive_id = a.archive_id
LEFT JOIN exam_archive_sections_ref s ON s.archive_id = a.archive_id
LEFT JOIN exam_archive_questions_ref q ON q.section_id = s.section_id
LEFT JOIN content_items c ON c.content_id = q.content_id
LEFT JOIN exam_archive_assets_ref ast ON ast.archive_id = a.archive_id
GROUP BY a.year, a.session, a.zone, a.series, COALESCE(a.subject_group, sub.code);

CREATE OR REPLACE VIEW v_official_archive_coverage_by_subject AS
SELECT
    sub.code AS subject,
    COUNT(DISTINCT a.archive_id) AS archives,
    COUNT(DISTINCT CASE WHEN c.source_type = 'OFFICIAL_ARCHIVE' THEN c.content_id END) AS official_questions,
    COUNT(DISTINCT CASE WHEN c.source_type = 'OFFICIAL_ARCHIVE' AND c.validation_status = 'APPROVED' THEN c.content_id END) AS validated,
    COUNT(DISTINCT CASE WHEN c.source_type = 'OFFICIAL_ARCHIVE' AND c.curriculum_2027_compatible = 'TRUE' THEN c.content_id END) AS compatible_2027,
    COUNT(DISTINCT CASE WHEN c.source_type = 'OFFICIAL_ARCHIVE' AND c.validation_status = 'REVIEW' THEN c.content_id END) AS review,
    COUNT(DISTINCT csl.skill_id) AS unique_skills,
    COUNT(DISTINCT c.brevet_format) AS unique_formats,
    COUNT(DISTINCT CASE WHEN q.correction_source = 'OFFICIAL' THEN q.archive_question_id END) AS with_official_correction,
    COUNT(DISTINCT CASE WHEN COALESCE(q.support_required, FALSE) = FALSE OR ast.asset_id IS NOT NULL THEN q.archive_question_id END) AS with_required_assets_complete
FROM subjects sub
LEFT JOIN exam_archives_ref a ON a.subject_id = sub.subject_id
LEFT JOIN exam_archive_sections_ref s ON s.archive_id = a.archive_id
LEFT JOIN exam_archive_questions_ref q ON q.section_id = s.section_id
LEFT JOIN content_items c ON c.content_id = q.content_id
LEFT JOIN content_skill_links csl ON csl.content_id = c.content_id
LEFT JOIN exam_archive_assets_ref ast ON ast.archive_id = a.archive_id
GROUP BY sub.code;
