from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from domain.decision.enums import ActivityKind
from infrastructure.database.v2 import connect_v2
from services.recommendation.models import ApprovedContent, CandidateSet, PersonalizedSessionProposal


class DuckDBRecommendationRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def has_proposal(self, stable_id: str) -> bool:
        con = connect_v2(self.database_path, read_only=True)
        try:
            return (
                con.execute(
                    "SELECT count(*) FROM personalized_session_proposals WHERE stable_id=?", [stable_id]
                ).fetchone()[0]
                > 0
            )
        finally:
            con.close()

    def load_approved_contents(self) -> tuple[ApprovedContent, ...]:
        """Return only active exercises whose latest content status is approved."""
        con = connect_v2(self.database_path, read_only=True)
        try:
            rows = con.execute(
                """
                SELECT content_id,content_version_id,title,subject_id,domain_id,skill_id,subskill_id,
                       program_id,grade_code,difficulty,estimated_minutes,payload
                FROM approved_learning_catalog
                ORDER BY content_id,skill_id
                """
            ).fetchall()
            result = []
            for row in rows:
                payload = json.loads(row[11]) if row[11] else {}
                result.append(
                    ApprovedContent(
                        int(row[0]),
                        int(row[1]),
                        row[2],
                        int(row[3]),
                        int(row[4]),
                        int(row[5]),
                        None if row[6] is None else int(row[6]),
                        int(row[7]),
                        row[8],
                        int(row[9]),
                        int(row[10]),
                        ActivityKind(payload.get("activity_type", "learning")),
                        tuple(payload.get("prerequisite_skill_ids", [])),
                        tuple(payload.get("tags", [])),
                        "approved",
                        True,
                        tuple(payload.get("objective_compatibility", [])),
                        tuple(payload.get("exam_compatibility", [])),
                        tuple(payload.get("transition_markers", [])),
                        bool(payload.get("revision_compatible", True)),
                        False,
                    )
                )
            return tuple(result)
        finally:
            con.close()

    def save(self, candidates: CandidateSet, proposal: PersonalizedSessionProposal) -> int:
        con = connect_v2(self.database_path)
        try:
            con.execute("BEGIN")
            version_row = con.execute(
                "SELECT id FROM learner_journey_versions WHERE learner_id=? AND version_number=?",
                [proposal.learner_id, proposal.journey_version],
            ).fetchone()
            journey_version_id = int(version_row[0])
            decision_row = (
                con.execute(
                    "SELECT id FROM learning_decisions WHERE correlation_id=?", [proposal.decision_correlation_id]
                ).fetchone()
                if proposal.decision_correlation_id
                else None
            )
            decision_id = int(decision_row[0]) if decision_row else None
            existing = con.execute(
                "SELECT id FROM personalized_session_proposals WHERE stable_id=?", [proposal.stable_id]
            ).fetchone()
            if existing:
                con.execute("ROLLBACK")
                return int(existing[0])
            snap = con.execute(
                "INSERT INTO content_candidate_snapshots(stable_id,learner_id,journey_version_id,adapter_version,ruleset_version,context_hash,candidates) VALUES (?,?,?,?,?,?,?) RETURNING id",
                [
                    candidates.stable_id,
                    proposal.learner_id,
                    journey_version_id,
                    "candidate-adapter-v1",
                    "onboarding-rules-v1",
                    candidates.context_hash,
                    json.dumps([asdict(c) for c in candidates.candidates], default=str),
                ],
            ).fetchone()
            snap_id = int(snap[0])
            for exclusion in candidates.report.exclusions:
                con.execute(
                    "INSERT INTO content_candidate_filter_events(candidate_snapshot_id,content_id,reason_code) VALUES (?,?,?)",
                    [snap_id, exclusion.content_id, exclusion.reason],
                )
            row = con.execute(
                "INSERT INTO personalized_session_proposals(stable_id,learner_id,journey_version_id,decision_id,recommendation_version,scheduled_for,available_minutes,objective_ref,strategy,confidence,absence_code,result_snapshot,context_hash,correlation_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
                [
                    proposal.stable_id,
                    proposal.learner_id,
                    journey_version_id,
                    decision_id,
                    "recommendation-v1",
                    proposal.scheduled_for,
                    proposal.available_minutes,
                    proposal.objective,
                    proposal.strategy,
                    proposal.confidence,
                    proposal.absence_code,
                    json.dumps(asdict(proposal), default=str),
                    candidates.context_hash,
                    proposal.stable_id,
                ],
            ).fetchone()
            proposal_id = int(row[0])
            for item in proposal.activities:
                con.execute(
                    "INSERT INTO personalized_session_items(proposal_id,candidate_stable_id,content_id,content_version_id,skill_id,subject_id,position,duration_minutes,difficulty,explanation) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [
                        proposal_id,
                        item.candidate.stable_id,
                        item.candidate.content_id,
                        item.candidate.content_version_id,
                        item.candidate.skill_id,
                        item.candidate.subject_id,
                        item.order,
                        item.duration_minutes,
                        item.difficulty,
                        json.dumps(item.reasons),
                    ],
                )
            con.execute("COMMIT")
            return proposal_id
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
