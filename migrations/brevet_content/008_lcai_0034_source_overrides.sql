-- LCAI-0034 — source_type overrides (DuckDB cannot UPDATE FK-parent rows reliably)

CREATE TABLE IF NOT EXISTS content_source_overrides (
    content_id BIGINT PRIMARY KEY,
    source_type VARCHAR NOT NULL,
    reason VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW v_content_items_effective AS
SELECT
    c.* EXCLUDE (source_type),
    COALESCE(o.source_type, c.source_type) AS source_type
FROM content_items c
LEFT JOIN content_source_overrides o ON o.content_id = c.content_id;
