from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from domain.onboarding.events import OnboardingEvent
from domain.onboarding.models import OnboardingRequest, OnboardingResult
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.decision import DuckDBDecisionRepository
from services.decision import LearnerJourneyService


class DuckDBOnboardingRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def known_subject_ids(self) -> set[int]:
        con = connect_v2(self.database_path, read_only=True)
        try:
            return {int(row[0]) for row in con.execute("SELECT id FROM subjects").fetchall()}
        finally:
            con.close()

    def complete(
        self, request: OnboardingRequest, result: OnboardingResult, events: tuple[OnboardingEvent, ...]
    ) -> OnboardingResult:
        con = connect_v2(self.database_path)
        try:
            con.execute("BEGIN")
            existing = con.execute(
                "SELECT learner_id FROM learner_functional_profiles WHERE stable_id=?", [request.profile.stable_id]
            ).fetchone()
            if existing:
                learner_id = int(existing[0])
            else:
                row = con.execute(
                    "INSERT INTO learners(external_ref,display_name,locale,timezone) VALUES (?,?,?,?) RETURNING id",
                    [
                        request.profile.stable_id,
                        request.profile.display_name,
                        request.profile.locale,
                        request.profile.timezone,
                    ],
                ).fetchone()
                learner_id = int(row[0])
                con.execute(
                    "INSERT INTO learner_functional_profiles VALUES (?,?,?,?,1,now())",
                    [
                        learner_id,
                        request.profile.stable_id,
                        request.profile.birth_date,
                        request.profile.creator_role.value,
                    ],
                )
            prior = con.execute("SELECT id FROM onboarding_sessions WHERE stable_id=?", [request.stable_id]).fetchone()
            if prior:
                version = int(
                    con.execute(
                        "SELECT max(version_number) FROM learner_journey_versions WHERE learner_id=?", [learner_id]
                    ).fetchone()[0]
                )
                con.execute("ROLLBACK")
                return replace(
                    result,
                    learner_id=learner_id,
                    journey=replace(result.journey, learner_id=learner_id),
                    journey_version=version,
                )
            version = int(
                con.execute(
                    "SELECT coalesce(max(version_number),0)+1 FROM learner_journey_versions WHERE learner_id=?",
                    [learner_id],
                ).fetchone()[0]
            )
            journey = replace(result.journey, learner_id=learner_id)
            con.execute(
                "INSERT INTO onboarding_sessions(stable_id,learner_id,onboarding_version,status,context_hash,correlation_id,request_snapshot,validation_snapshot,completed_at) VALUES (?,?,?,'completed',?,?,?,?,now())",
                [
                    request.stable_id,
                    learner_id,
                    "onboarding-v1",
                    result.context_hash,
                    result.correlation_id,
                    json.dumps(asdict(request), default=str),
                    json.dumps(asdict(result.validation), default=str),
                ],
            )
            con.execute(
                "INSERT INTO learner_journey_versions(learner_id,version_number,journey_snapshot,effective_from,changed_by_role,change_reason,context_hash,correlation_id) VALUES (?,?,?,?,?,?,?,?)",
                [
                    learner_id,
                    version,
                    json.dumps(asdict(journey), default=str),
                    result.created_at,
                    request.changed_by_role.value,
                    request.change_reason,
                    result.context_hash,
                    result.correlation_id,
                ],
            )
            for event in events:
                con.execute(
                    "INSERT INTO onboarding_domain_events(correlation_id,event_type,learner_id,payload,occurred_at) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
                    [event.correlation_id, event.event_type, learner_id, json.dumps(event.payload), event.occurred_at],
                )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        LearnerJourneyService(DuckDBDecisionRepository(self.database_path)).save(journey)
        return replace(result, learner_id=learner_id, journey=journey, journey_version=version)
