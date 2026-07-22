CREATE VIEW v_skill_catalog AS
SELECT
    p.id AS program_id,
    p.code AS program_code,
    su.id AS subject_id,
    su.code AS subject_code,
    d.id AS domain_id,
    d.code AS domain_code,
    s.id AS skill_id,
    s.code AS skill_code,
    s.default_label AS skill_label,
    ps.expected_mastery,
    ps.priority
FROM programs p
JOIN program_skills ps ON ps.program_id = p.id
JOIN skills s ON s.id = ps.skill_id
JOIN domains d ON d.id = s.domain_id
JOIN subjects su ON su.id = d.subject_id;

CREATE VIEW v_learner_progress AS
SELECT
    l.id AS learner_id,
    l.display_name,
    mc.skill_id,
    s.default_label AS skill_label,
    mc.score,
    mc.confidence,
    mc.last_evidence_at,
    mc.next_review_at,
    mc.model_version
FROM learners l
JOIN mastery_current mc ON mc.learner_id = l.id
JOIN skills s ON s.id = mc.skill_id;

CREATE VIEW v_due_revisions AS
SELECT
    mc.learner_id,
    mc.skill_id,
    s.default_label AS skill_label,
    mc.score,
    mc.confidence,
    mc.next_review_at
FROM mastery_current mc
JOIN skills s ON s.id = mc.skill_id
WHERE mc.next_review_at IS NOT NULL
  AND mc.next_review_at <= CURRENT_TIMESTAMP;
