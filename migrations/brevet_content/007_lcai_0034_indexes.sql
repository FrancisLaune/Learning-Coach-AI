-- LCAI-0034 — missing source_provider + indexes

ALTER TABLE exam_archives_ref ADD COLUMN IF NOT EXISTS source_provider VARCHAR DEFAULT 'EDUSCOL';

UPDATE exam_archives_ref
SET source_provider = COALESCE(source_provider, 'EDUSCOL');

UPDATE exam_archives_ref
SET exam_identity = COALESCE(exam_identity, base_exam_identifier)
WHERE exam_identity IS NULL;

CREATE INDEX IF NOT EXISTS idx_content_items_family ON content_items(family_id);
CREATE INDEX IF NOT EXISTS idx_content_items_canonical ON content_items(canonical_content_id);
CREATE INDEX IF NOT EXISTS idx_legacy_map_ob ON legacy_content_mapping(ob_content_id);
CREATE INDEX IF NOT EXISTS idx_archives_exam_identity ON exam_archives_ref(exam_identity);
CREATE INDEX IF NOT EXISTS idx_archives_provider ON exam_archives_ref(source_provider);
CREATE INDEX IF NOT EXISTS idx_derivations_parent_q ON content_derivations(parent_question_id);
CREATE INDEX IF NOT EXISTS idx_derivations_parent_a ON content_derivations(parent_archive_id);
