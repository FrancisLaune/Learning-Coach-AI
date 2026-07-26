CREATE TABLE content_production_gates (
    content_version_id BIGINT PRIMARY KEY REFERENCES content_versions(id),
    production_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    production_tier VARCHAR NOT NULL CHECK (
        production_tier IN ('PRODUCTION_READY','LIMITED_PRODUCTION','BLOCKED')
    ),
    reason VARCHAR NOT NULL,
    enabled_by VARCHAR NOT NULL,
    enabled_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO content_production_gates(
    content_version_id,production_enabled,production_tier,reason,enabled_by
)
SELECT content_version_id,TRUE,'LIMITED_PRODUCTION',
       'Historical Approved catalog preserved during LCAI-0012D2 migration.',
       'lcai-0012d2-migration'
FROM approved_learning_catalog
ON CONFLICT(content_version_id) DO NOTHING;

CREATE VIEW production_learning_catalog AS
SELECT approved.*
FROM approved_learning_catalog approved
JOIN content_production_gates gate
  ON gate.content_version_id=approved.content_version_id
 AND gate.production_enabled;
