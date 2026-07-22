CREATE TABLE content_media (
    entity_type VARCHAR NOT NULL CHECK (entity_type IN ('program','subject','domain','skill','subskill','exercise','question')),
    entity_id BIGINT NOT NULL,
    media_id BIGINT NOT NULL REFERENCES media_assets(id),
    position INTEGER NOT NULL DEFAULT 1 CHECK (position > 0),
    PRIMARY KEY (entity_type, entity_id, media_id),
    UNIQUE (entity_type, entity_id, position)
);

CREATE INDEX idx_content_media_asset ON content_media(media_id, entity_type);
