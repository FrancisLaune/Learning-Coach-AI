CREATE TABLE content_versions (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    entity_type VARCHAR NOT NULL CHECK (entity_type IN ('program','subject','domain','skill','subskill','exercise','question','media')),
    entity_id BIGINT NOT NULL,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    payload JSON NOT NULL,
    author VARCHAR NOT NULL CHECK (length(trim(author)) > 0),
    status VARCHAR NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','review','approved','archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (entity_type, entity_id, version_number)
);

CREATE TABLE content_status_events (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    content_version_id BIGINT NOT NULL REFERENCES content_versions(id),
    previous_status VARCHAR CHECK (previous_status IS NULL OR previous_status IN ('draft','review','approved','archived')),
    new_status VARCHAR NOT NULL CHECK (new_status IN ('draft','review','approved','archived')),
    author VARCHAR NOT NULL CHECK (length(trim(author)) > 0),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE media_assets (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    code VARCHAR NOT NULL UNIQUE,
    media_type VARCHAR NOT NULL CHECK (media_type IN ('image','pdf','audio','video','link')),
    uri VARCHAR NOT NULL CHECK (length(trim(uri)) > 0),
    title VARCHAR NOT NULL DEFAULT '',
    mime_type VARCHAR,
    metadata JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ
);

CREATE TABLE tags (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    code VARCHAR NOT NULL UNIQUE,
    label VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_tags (
    entity_type VARCHAR NOT NULL CHECK (entity_type IN ('program','subject','domain','skill','subskill','exercise','question','media')),
    entity_id BIGINT NOT NULL,
    tag_id BIGINT NOT NULL REFERENCES tags(id),
    PRIMARY KEY (entity_type, entity_id, tag_id)
);

CREATE TABLE validation_runs (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    source_name VARCHAR NOT NULL,
    is_valid BOOLEAN NOT NULL,
    error_count INTEGER NOT NULL CHECK (error_count >= 0),
    warning_count INTEGER NOT NULL CHECK (warning_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE validation_issues (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    validation_run_id BIGINT NOT NULL REFERENCES validation_runs(id),
    code VARCHAR NOT NULL,
    severity VARCHAR NOT NULL CHECK (severity IN ('error','warning','info')),
    message VARCHAR NOT NULL,
    entity_type VARCHAR,
    entity_code VARCHAR
);

CREATE INDEX idx_content_versions_entity ON content_versions(entity_type, entity_id, version_number);
CREATE INDEX idx_content_versions_status ON content_versions(status, modified_at);
CREATE INDEX idx_status_events_version ON content_status_events(content_version_id, changed_at);
CREATE INDEX idx_content_tags_tag ON content_tags(tag_id, entity_type);
CREATE INDEX idx_validation_issues_run ON validation_issues(validation_run_id, severity);

