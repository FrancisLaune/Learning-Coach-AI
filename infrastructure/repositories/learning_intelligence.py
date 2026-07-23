"""DuckDB evidence and rebuildable snapshot adapter."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from domain.learning_intelligence.models import EvidenceWindow, LearningEvidence
from infrastructure.database.v2 import connect_v2


class DuckDBLearningEvidenceRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def for_learner_window(self, learner_id: int, window: EvidenceWindow) -> tuple[LearningEvidence, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT r.learner_id,a.session_id,r.activity_id,r.id,r.assessment_id,
                qs.skill_id,a.content_id,a.content_version_id,a.difficulty,ans.attempt_number,
                aa.score+aa.penalty+aa.hint_penalty+aa.time_penalty,aa.score,r.success,
                r.duration_ms/1000.0,a.estimated_duration_seconds,r.hint_count,aa.hint_penalty,
                ans.submission_time,r.mastery_before,r.mastery_after,
                json_extract_string(aa.feedback_generated,'$.error_code')
                FROM session_attempt_records r
                JOIN session_activities a ON a.id=r.activity_id
                JOIN student_answers ans ON ans.id=r.answer_id
                JOIN answer_assessments aa ON aa.id=r.assessment_id
                JOIN attempts legacy ON legacy.id=r.legacy_attempt_id
                JOIN question_skills qs ON qs.question_id=legacy.question_id AND qs.is_primary
                WHERE r.learner_id=? AND ans.submission_time BETWEEN ? AND ?
                AND r.archived_at IS NULL AND ans.draft=FALSE AND ans.validated=TRUE
                ORDER BY ans.submission_time,r.id""",
                [learner_id, window.start, window.end],
            ).fetchall()
            return tuple(
                LearningEvidence(
                    int(row[0]),
                    int(row[1]),
                    int(row[2]),
                    int(row[3]),
                    int(row[4]),
                    int(row[5]),
                    int(row[6]),
                    int(row[7]),
                    int(row[8]),
                    int(row[9]),
                    min(100, float(row[10])),
                    float(row[11]),
                    bool(row[12]),
                    float(row[13]),
                    float(row[14]),
                    int(row[15]),
                    float(row[16]),
                    row[17],
                    float(row[18]),
                    float(row[19]),
                    row[20],
                )
                for row in rows
            )
        finally:
            connection.close()

    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT count(*) FROM learner_guardian_links
                WHERE guardian_external_ref=? AND learner_id=? AND active AND revoked_at IS NULL""",
                [parent_ref, learner_id],
            ).fetchone()
            return bool(row and row[0])
        finally:
            connection.close()


class DuckDBAnalyticsSnapshotRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    @staticmethod
    def stable_key(
        learner_id: int,
        calculation_type: str,
        scope_id: int,
        window: EvidenceWindow,
        calculation_version: str,
        source_cutoff: datetime,
    ) -> str:
        value = (
            f"{learner_id}|{calculation_type}|{scope_id}|{window.start.isoformat()}|"
            f"{window.end.isoformat()}|{calculation_version}|{source_cutoff.isoformat()}"
        )
        return hashlib.sha256(value.encode()).hexdigest()

    def save(
        self,
        *,
        learner_id: int,
        calculation_type: str,
        scope_id: int,
        window: EvidenceWindow,
        calculation_version: str,
        configuration_version: str,
        source_cutoff: datetime,
        facts: dict[str, Any],
        indicators: dict[str, Any],
    ) -> int:
        key = self.stable_key(learner_id, calculation_type, scope_id, window, calculation_version, source_cutoff)
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            existing = connection.execute(
                "SELECT id FROM learning_analytics_snapshots WHERE stable_key=?", [key]
            ).fetchone()
            if existing:
                connection.execute("ROLLBACK")
                return int(existing[0])
            run_id = int(
                connection.execute(
                    """INSERT INTO analytics_calculation_runs
                    (stable_key,learner_id,calculation_type,window_start,window_end,
                     calculation_version,configuration_version,source_cutoff_at,
                     completed_at,status,result_count)
                    VALUES (?,?,?,?,?,?,?,?,now(),'COMPLETED',1) RETURNING id""",
                    [
                        f"run-{key}",
                        learner_id,
                        calculation_type,
                        window.start,
                        window.end,
                        calculation_version,
                        configuration_version,
                        source_cutoff,
                    ],
                ).fetchone()[0]
            )
            snapshot_id = int(
                connection.execute(
                    """INSERT INTO learning_analytics_snapshots
                    (stable_key,run_id,learner_id,scope_type,scope_id,window_start,window_end,
                     calculation_version,source_cutoff_at,facts,indicators)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                    [
                        key,
                        run_id,
                        learner_id,
                        calculation_type,
                        scope_id,
                        window.start,
                        window.end,
                        calculation_version,
                        source_cutoff,
                        json.dumps(facts, default=str),
                        json.dumps(indicators, default=str),
                    ],
                ).fetchone()[0]
            )
            connection.execute("COMMIT")
            return snapshot_id
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def count(self, learner_id: int) -> int:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            return int(
                connection.execute(
                    "SELECT count(*) FROM learning_analytics_snapshots WHERE learner_id=?", [learner_id]
                ).fetchone()[0]
            )
        finally:
            connection.close()
