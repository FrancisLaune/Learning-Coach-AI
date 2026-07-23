CREATE TABLE learner_functional_profiles (
    learner_id BIGINT PRIMARY KEY REFERENCES learners(id), stable_id VARCHAR NOT NULL UNIQUE,
    birth_date DATE, creator_role VARCHAR NOT NULL CHECK (creator_role IN ('parent','student','administrator')),
    profile_version INTEGER NOT NULL DEFAULT 1 CHECK (profile_version > 0), updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE onboarding_sessions (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'), stable_id VARCHAR NOT NULL UNIQUE,
    learner_id BIGINT NOT NULL REFERENCES learners(id), onboarding_version VARCHAR NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('started','completed','failed')), context_hash VARCHAR NOT NULL,
    correlation_id VARCHAR NOT NULL UNIQUE, request_snapshot JSON NOT NULL, validation_snapshot JSON NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, completed_at TIMESTAMPTZ
);
CREATE TABLE learner_journey_versions (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'), learner_id BIGINT NOT NULL REFERENCES learners(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0), journey_snapshot JSON NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL, changed_by_role VARCHAR NOT NULL,
    change_reason VARCHAR, context_hash VARCHAR NOT NULL, correlation_id VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(learner_id,version_number), UNIQUE(correlation_id)
);
CREATE TABLE onboarding_domain_events (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'), correlation_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL, learner_id BIGINT REFERENCES learners(id), payload JSON NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL, UNIQUE(correlation_id,event_type)
);
CREATE TABLE content_candidate_snapshots (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'), stable_id VARCHAR NOT NULL UNIQUE,
    learner_id BIGINT NOT NULL REFERENCES learners(id), journey_version_id BIGINT NOT NULL REFERENCES learner_journey_versions(id),
    adapter_version VARCHAR NOT NULL, ruleset_version VARCHAR NOT NULL, context_hash VARCHAR NOT NULL,
    candidates JSON NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE content_candidate_filter_events (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'), candidate_snapshot_id BIGINT NOT NULL REFERENCES content_candidate_snapshots(id),
    content_id BIGINT, reason_code VARCHAR NOT NULL, details JSON NOT NULL DEFAULT '{}'
);
CREATE TABLE personalized_session_proposals (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'), stable_id VARCHAR NOT NULL UNIQUE,
    learner_id BIGINT NOT NULL REFERENCES learners(id), journey_version_id BIGINT NOT NULL REFERENCES learner_journey_versions(id),
    decision_id BIGINT REFERENCES learning_decisions(id), recommendation_version VARCHAR NOT NULL,
    scheduled_for TIMESTAMPTZ NOT NULL, available_minutes INTEGER NOT NULL CHECK (available_minutes > 0),
    objective_ref VARCHAR NOT NULL, strategy VARCHAR, confidence DOUBLE NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    absence_code VARCHAR, result_snapshot JSON NOT NULL, context_hash VARCHAR NOT NULL,
    correlation_id VARCHAR NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE personalized_session_items (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'), proposal_id BIGINT NOT NULL REFERENCES personalized_session_proposals(id),
    candidate_stable_id VARCHAR NOT NULL, content_id BIGINT NOT NULL, content_version_id BIGINT NOT NULL,
    skill_id BIGINT NOT NULL REFERENCES skills(id), subject_id BIGINT NOT NULL REFERENCES subjects(id),
    position INTEGER NOT NULL CHECK(position>0), duration_minutes INTEGER NOT NULL CHECK(duration_minutes>0),
    difficulty SMALLINT NOT NULL CHECK(difficulty BETWEEN 1 AND 5), explanation JSON NOT NULL,
    UNIQUE(proposal_id,position), UNIQUE(proposal_id,candidate_stable_id)
);
CREATE INDEX idx_onboarding_learner_created ON onboarding_sessions(learner_id,created_at);
CREATE INDEX idx_journey_versions_learner_version ON learner_journey_versions(learner_id,version_number);
CREATE INDEX idx_onboarding_events_learner_time ON onboarding_domain_events(learner_id,occurred_at);
CREATE INDEX idx_candidate_snapshots_learner_time ON content_candidate_snapshots(learner_id,created_at);
CREATE INDEX idx_filter_events_snapshot_reason ON content_candidate_filter_events(candidate_snapshot_id,reason_code);
CREATE INDEX idx_session_proposals_learner_time ON personalized_session_proposals(learner_id,scheduled_for);

