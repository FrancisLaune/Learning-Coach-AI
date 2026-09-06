-- LCAI-0034 — family links without updating content_items parent rows

CREATE TABLE IF NOT EXISTS content_family_links (
    content_id BIGINT PRIMARY KEY,
    family_id BIGINT,
    near_duplicate_class VARCHAR,
    canonical_content_id VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_content_family_links_family ON content_family_links(family_id);
