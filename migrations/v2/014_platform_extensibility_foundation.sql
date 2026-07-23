-- LCAI-0010 Part 07: additive local-first platform runtime foundation.

CREATE TABLE platform_plugin_status (
    plugin_id VARCHAR PRIMARY KEY,
    plugin_version VARCHAR NOT NULL,
    contract_version VARCHAR NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    lifecycle_state VARCHAR NOT NULL,
    health_status VARCHAR NOT NULL,
    last_error_code VARCHAR,
    configuration_snapshot_id VARCHAR,
    installed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE platform_configuration_snapshots (
    snapshot_id VARCHAR PRIMARY KEY,
    configuration_version VARCHAR NOT NULL,
    non_secret_values JSON NOT NULL,
    feature_flags JSON NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE platform_event_outbox (
    event_id VARCHAR PRIMARY KEY,
    event_type VARCHAR NOT NULL,
    payload_version INTEGER NOT NULL CHECK (payload_version > 0),
    occurred_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    correlation_id VARCHAR NOT NULL,
    causation_id VARCHAR,
    aggregate_type VARCHAR,
    aggregate_id VARCHAR,
    payload JSON NOT NULL,
    dispatch_status VARCHAR NOT NULL CHECK (dispatch_status IN (
        'PENDING','DISPATCHING','COMPLETED','PARTIALLY_COMPLETED',
        'FAILED_RETRYABLE','FAILED_PERMANENT','SKIPPED_DISABLED_HANDLER','SUPERSEDED'
    )),
    dispatch_attempt_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    last_error_code VARCHAR
);

CREATE TABLE platform_event_deliveries (
    delivery_id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    -- Deliberately not a DuckDB FK: DuckDB rejects parent status updates while
    -- referenced, which conflicts with the outbox lifecycle. Application-level
    -- creation always persists the outbox record first.
    event_id VARCHAR NOT NULL,
    handler_id VARCHAR NOT NULL,
    handler_version VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    first_attempt_at TIMESTAMPTZ,
    last_attempt_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    last_error_code VARCHAR,
    result_reference VARCHAR,
    UNIQUE(event_id,handler_id,handler_version)
);

CREATE TABLE platform_audit_records (
    audit_id VARCHAR PRIMARY KEY,
    category VARCHAR NOT NULL,
    action VARCHAR NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    actor_type VARCHAR NOT NULL,
    actor_id VARCHAR,
    learner_id BIGINT,
    resource_type VARCHAR,
    resource_id VARCHAR,
    outcome VARCHAR NOT NULL,
    correlation_id VARCHAR NOT NULL,
    causation_id VARCHAR,
    policy_version VARCHAR,
    application_version VARCHAR NOT NULL DEFAULT '0.1.0',
    summary_code VARCHAR NOT NULL,
    metadata JSON NOT NULL DEFAULT '{}',
    sensitivity_level VARCHAR NOT NULL DEFAULT 'INTERNAL'
);

CREATE TABLE platform_import_runs (
    import_run_id VARCHAR PRIMARY KEY,
    importer_id VARCHAR NOT NULL,
    source_name VARCHAR NOT NULL,
    source_hash VARCHAR NOT NULL,
    actor_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    dry_run BOOLEAN NOT NULL,
    created_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    contract_version VARCHAR NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    UNIQUE(importer_id,source_hash,contract_version,dry_run)
);

CREATE TABLE platform_export_runs (
    export_request_id VARCHAR PRIMARY KEY,
    exporter_id VARCHAR NOT NULL,
    resource_type VARCHAR NOT NULL,
    requested_by VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    format VARCHAR NOT NULL,
    result_reference VARCHAR,
    record_count INTEGER NOT NULL DEFAULT 0,
    checksum VARCHAR,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE TABLE platform_notification_requests (
    notification_request_id VARCHAR PRIMARY KEY,
    notification_type VARCHAR NOT NULL,
    recipient_type VARCHAR NOT NULL,
    recipient_id VARCHAR NOT NULL,
    channel VARCHAR NOT NULL,
    template_code VARCHAR NOT NULL,
    template_parameters JSON NOT NULL,
    source_event_id VARCHAR NOT NULL,
    correlation_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    policy_version VARCHAR NOT NULL,
    scheduled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_event_id,recipient_type,recipient_id,channel,template_code)
);

CREATE INDEX idx_platform_outbox_status_retry
    ON platform_event_outbox(dispatch_status,next_retry_at,recorded_at);
CREATE INDEX idx_platform_deliveries_status_retry
    ON platform_event_deliveries(status,next_retry_at,last_attempt_at);
CREATE INDEX idx_platform_audit_correlation
    ON platform_audit_records(correlation_id,occurred_at);
CREATE INDEX idx_platform_audit_resource
    ON platform_audit_records(resource_type,resource_id,occurred_at);
CREATE INDEX idx_platform_import_source
    ON platform_import_runs(importer_id,source_hash);
CREATE INDEX idx_platform_notifications_status
    ON platform_notification_requests(status,scheduled_at);
