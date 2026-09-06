-- LCAI-0035 — indexes for ingestion tables (separate from schema ALTERs)

CREATE INDEX IF NOT EXISTS idx_bref_archive_docs_identity
ON exam_archive_documents_ref(exam_identity_key);

CREATE INDEX IF NOT EXISTS idx_bref_archive_docs_archive
ON exam_archive_documents_ref(archive_id);

CREATE INDEX IF NOT EXISTS idx_bref_archive_docs_status
ON exam_archive_documents_ref(parse_status);

CREATE INDEX IF NOT EXISTS idx_bref_ingest_events_run
ON archive_ingestion_events(run_id);

CREATE INDEX IF NOT EXISTS idx_bref_content_archive_q
ON content_items(archive_question_id);

CREATE INDEX IF NOT EXISTS idx_bref_archives_identity_key
ON exam_archives_ref(exam_identity_key);
