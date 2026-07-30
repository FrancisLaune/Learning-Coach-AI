"""DuckDB persistence for LCAI-0019 pedagogical intelligence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from domain.pedagogical_intelligence.models import (
    DiagnosticRun,
    MasterySummaryItem,
    PlannerHighlight,
    ReadinessPathCode,
)
from domain.pedagogical_intelligence.paths import path_by_code
from infrastructure.database.v2 import connect_v2


class DuckDBPedagogicalIntelligenceRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def learner_context(self, learner_id: int) -> dict[str, Any]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT l.display_name, c.code, c.label,
                       COALESCE(e.diagnostic_status, 'NOT_OFFERED')
                FROM learners l
                LEFT JOIN learner_journeys j ON j.learner_id=l.id
                LEFT JOIN school_levels c ON c.id=j.current_school_level_id
                LEFT JOIN learner_experience_profiles e ON e.learner_id=l.id
                WHERE l.id=? AND l.archived_at IS NULL
                """,
                [learner_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown learner {learner_id}")
            return {
                "display_name": str(row[0]),
                "current_grade_code": None if row[1] is None else str(row[1]),
                "current_grade_label": None if row[2] is None else str(row[2]),
                "diagnostic_status": str(row[3]),
            }
        finally:
            connection.close()

    def transition_readiness(self, learner_id: int, target_grade_code: str) -> dict[str, Any] | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT target_grade_code, score, coverage, confidence, details
                FROM transition_readiness_current
                WHERE learner_id=? AND target_grade_code=?
                """,
                [learner_id, target_grade_code],
            ).fetchone()
            if row is None:
                return None
            details = json.loads(str(row[4])) if row[4] else {}
            source_grade = details.get("source_grade_code") or details.get("current_grade_code")
            if not source_grade:
                source_row = connection.execute(
                    """
                    SELECT sl.code FROM learner_journeys j
                    JOIN school_levels sl ON sl.id=j.current_school_level_id
                    WHERE j.learner_id=?
                    LIMIT 1
                    """,
                    [learner_id],
                ).fetchone()
                source_grade = str(source_row[0]) if source_row else str(row[0])
            return {
                "source_grade_code": str(source_grade),
                "target_grade_code": str(row[0]),
                "score": float(row[1]) * 100 if float(row[1]) <= 1 else float(row[1]),
                "coverage": float(row[2]),
                "confidence": float(row[3]),
                "acquired_skill_ids": tuple(details.get("acquired_skills") or details.get("acquired_skill_ids") or ()),
                "fragile_skill_ids": tuple(details.get("fragile_skills") or details.get("fragile_skill_ids") or ()),
                "blocking_skill_ids": tuple(details.get("blocking_skills") or details.get("blocking_skill_ids") or ()),
            }
        finally:
            connection.close()

    def mastery_summary(self, learner_id: int, *, limit: int = 8) -> tuple[MasterySummaryItem, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """
                SELECT m.skill_id, s.default_label, m.score, m.level, m.trend
                FROM longitudinal_mastery_current m
                JOIN skills s ON s.id=m.skill_id
                WHERE m.learner_id=?
                ORDER BY m.score ASC, s.default_label
                LIMIT ?
                """,
                [learner_id, limit],
            ).fetchall()
            return tuple(
                MasterySummaryItem(
                    int(row[0]),
                    str(row[1]),
                    float(row[2]) * 100 if float(row[2]) <= 1 else float(row[2]),
                    str(row[3]),
                    str(row[4]),
                )
                for row in rows
            )
        finally:
            connection.close()

    def target_skills_for_grade(self, grade_code: str, *, limit: int = 12) -> tuple[int, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """
                SELECT DISTINCT c.skill_id
                FROM production_learning_catalog c
                JOIN school_levels sl ON sl.code=c.grade_code
                WHERE c.grade_code=?
                ORDER BY c.skill_id
                LIMIT ?
                """,
                [grade_code, limit],
            ).fetchall()
            if rows:
                return tuple(int(row[0]) for row in rows)
            rows = connection.execute(
                """
                SELECT DISTINCT csd.skill_id
                FROM curriculum_chapters cc
                JOIN school_levels sl ON sl.id=cc.grade_level_id
                JOIN curriculum_skill_details csd
                    ON csd.chapter_id=cc.id AND csd.grade_level_id=cc.grade_level_id
                WHERE sl.code=? AND cc.status='approved' AND csd.status='approved'
                ORDER BY csd.skill_id
                LIMIT ?
                """,
                [grade_code, limit],
            ).fetchall()
            return tuple(int(row[0]) for row in rows)
        finally:
            connection.close()

    def skill_label(self, skill_id: int) -> str:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute("SELECT default_label FROM skills WHERE id=?", [skill_id]).fetchone()
            return str(row[0]) if row else f"Compétence {skill_id}"
        finally:
            connection.close()

    def planner_highlights(self, learner_id: int, *, limit: int = 5) -> tuple[PlannerHighlight, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """
                SELECT s.default_label, p.scheduled_for, p.duration_minutes, d.reason_codes
                FROM decision_plan_items p
                JOIN learning_decisions d ON d.id=p.decision_id
                JOIN skills s ON s.id=p.skill_id
                WHERE d.learner_id=?
                ORDER BY COALESCE(p.scheduled_for, d.created_at) ASC, p.position ASC
                LIMIT ?
                """,
                [learner_id, limit],
            ).fetchall()
            highlights: list[PlannerHighlight] = []
            for row in rows:
                reasons = json.loads(str(row[3])) if row[3] else []
                highlights.append(
                    PlannerHighlight(
                        str(row[0]),
                        row[1],
                        int(row[2]),
                        str(reasons[0]) if reasons else "Priorité pédagogique",
                    )
                )
            return tuple(highlights)
        finally:
            connection.close()

    def active_diagnostic_run(self, learner_id: int) -> DiagnosticRun | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT id, learner_id, path_code, status, questions_asked, target_skill_ids,
                       assessed_skill_ids, confidence_by_skill, current_skill_id, started_at, completed_at
                FROM pedagogical_intelligence_diagnostic_runs
                WHERE learner_id=? AND status='IN_PROGRESS'
                ORDER BY started_at DESC LIMIT 1
                """,
                [learner_id],
            ).fetchone()
            return None if row is None else self._run_from_row(row)
        finally:
            connection.close()

    def create_diagnostic_run(
        self,
        *,
        learner_id: int,
        path_code: ReadinessPathCode,
        target_skill_ids: tuple[int, ...],
        current_skill_id: int | None,
        confidence_by_skill: dict[int, float],
    ) -> DiagnosticRun:
        now = datetime.now(UTC)
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            row = connection.execute(
                """
                INSERT INTO pedagogical_intelligence_diagnostic_runs(
                    learner_id, path_code, status, questions_asked, target_skill_ids,
                    assessed_skill_ids, confidence_by_skill, current_skill_id, started_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id
                """,
                [
                    learner_id,
                    path_code,
                    "IN_PROGRESS",
                    0,
                    json.dumps(list(target_skill_ids)),
                    json.dumps([]),
                    json.dumps({str(key): value for key, value in confidence_by_skill.items()}),
                    current_skill_id,
                    now,
                    now,
                ],
            ).fetchone()
            connection.execute("COMMIT")
            assert row is not None
            return DiagnosticRun(
                int(row[0]),
                learner_id,
                path_code,
                "IN_PROGRESS",
                0,
                target_skill_ids,
                (),
                current_skill_id,
                confidence_by_skill,
                now,
                None,
            )
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def save_diagnostic_run(self, run: DiagnosticRun) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """
                UPDATE pedagogical_intelligence_diagnostic_runs
                SET status=?, questions_asked=?, assessed_skill_ids=?, confidence_by_skill=?,
                    current_skill_id=?, completed_at=?, updated_at=?
                WHERE id=?
                """,
                [
                    run.status,
                    run.questions_asked,
                    json.dumps(list(run.assessed_skill_ids)),
                    json.dumps({str(key): value for key, value in run.confidence_by_skill.items()}),
                    run.current_skill_id,
                    run.completed_at,
                    datetime.now(UTC),
                    run.id,
                ],
            )
        finally:
            connection.close()

    def set_diagnostic_status(self, learner_id: int, status: str) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """
                UPDATE learner_experience_profiles
                SET diagnostic_status=?, updated_at=now()
                WHERE learner_id=?
                """,
                [status, learner_id],
            )
        finally:
            connection.close()

    def load_diagnostic_exercise(self, exercise_id: int) -> Any:
        from services.pedagogical_intelligence.diagnostic_content_selector import DiagnosticContentCandidate

        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT c.content_id, c.content_version_id, c.skill_id, c.chapter_id,
                       c.content_type, c.payload, q.statement, q.response_type, q.expected_answer
                FROM production_learning_catalog c
                JOIN exercises e ON e.id=c.content_id
                JOIN content_questions q ON q.exercise_id=e.id AND q.sequence_order=1
                WHERE c.content_id=?
                LIMIT 1
                """,
                [exercise_id],
            ).fetchone()
            if row is None:
                return None
            payload = json.loads(str(row[5])) if row[5] else {}
            return DiagnosticContentCandidate(
                int(row[0]),
                int(row[1]),
                int(row[2]),
                int(row[3]),
                str(row[6]),
                str(row[4]),
                str(row[7]),
                row[8],
                payload,
            )
        finally:
            connection.close()

    def load_diagnostic_answer(self, idempotency_key: str) -> dict[str, Any] | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT correct, normalized_score FROM pedagogical_intelligence_diagnostic_answers
                WHERE idempotency_key=?
                """,
                [idempotency_key],
            ).fetchone()
            if row is None:
                return None
            return {"correct": bool(row[0]), "normalized_score": float(row[1])}
        finally:
            connection.close()

    def load_diagnostic_run(self, run_id: int) -> DiagnosticRun | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT id, learner_id, path_code, status, questions_asked, target_skill_ids,
                       assessed_skill_ids, confidence_by_skill, current_skill_id, started_at, completed_at
                FROM pedagogical_intelligence_diagnostic_runs WHERE id=?
                """,
                [run_id],
            ).fetchone()
            return None if row is None else self._run_from_row(row)
        finally:
            connection.close()

    def load_diagnostic_content(
        self,
        *,
        skill_id: int,
        grade_code: str,
        excluded_exercise_ids: tuple[int, ...],
        preferred_types: tuple[str, ...],
    ) -> Any:
        from services.pedagogical_intelligence.diagnostic_content_selector import DiagnosticContentCandidate

        connection = connect_v2(self.database_path, read_only=True)
        try:
            placeholders = ",".join("?" * len(preferred_types))
            exclude = excluded_exercise_ids or (-1,)
            row = connection.execute(
                f"""
                SELECT c.content_id, c.content_version_id, c.skill_id, c.chapter_id,
                       c.content_type, c.payload, q.statement, q.response_type, q.expected_answer
                FROM production_learning_catalog c
                JOIN exercises e ON e.id=c.content_id
                JOIN content_questions q ON q.exercise_id=e.id AND q.sequence_order=1
                WHERE c.skill_id=? AND c.grade_code=?
                  AND c.content_type IN ({placeholders})
                  AND c.content_id NOT IN ({",".join("?" * len(exclude))})
                ORDER BY CASE c.content_type
                    WHEN 'diagnostic_activity' THEN 0
                    WHEN 'exercise' THEN 1
                    ELSE 2 END, c.content_id
                LIMIT 1
                """,
                [skill_id, grade_code, *preferred_types, *exclude],
            ).fetchone()
            if row is None:
                return None
            payload = json.loads(str(row[5])) if row[5] else {}
            return DiagnosticContentCandidate(
                int(row[0]),
                int(row[1]),
                int(row[2]),
                int(row[3]),
                str(row[6]),
                str(row[4]),
                str(row[7]),
                row[8],
                payload,
            )
        finally:
            connection.close()

    def used_diagnostic_exercises(self, run_id: int) -> tuple[int, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                "SELECT exercise_id FROM pedagogical_intelligence_diagnostic_answers WHERE run_id=? ORDER BY sequence_number",
                [run_id],
            ).fetchall()
            return tuple(int(row[0]) for row in rows)
        finally:
            connection.close()

    def save_diagnostic_answer(
        self,
        *,
        run_id: int,
        learner_id: int,
        skill_id: int,
        exercise_id: int,
        sequence_number: int,
        normalized_score: float,
        correct: bool,
        elapsed_ms: int,
        answer_payload: dict[str, Any],
        idempotency_key: str,
    ) -> bool:
        connection = connect_v2(self.database_path)
        try:
            existing = connection.execute(
                "SELECT id FROM pedagogical_intelligence_diagnostic_answers WHERE idempotency_key=?",
                [idempotency_key],
            ).fetchone()
            if existing:
                return False
            connection.execute(
                """
                INSERT INTO pedagogical_intelligence_diagnostic_answers(
                    run_id, learner_id, skill_id, exercise_id, sequence_number,
                    normalized_score, correct, elapsed_ms, answer_payload, idempotency_key
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    run_id,
                    learner_id,
                    skill_id,
                    exercise_id,
                    sequence_number,
                    normalized_score,
                    correct,
                    elapsed_ms,
                    json.dumps(answer_payload),
                    idempotency_key,
                ],
            )
            return True
        finally:
            connection.close()

    def update_diagnostic_run_exercise(self, run_id: int, *, exercise_id: int | None, skill_id: int | None) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """
                UPDATE pedagogical_intelligence_diagnostic_runs
                SET current_exercise_id=?, current_skill_id=?, updated_at=?
                WHERE id=?
                """,
                [exercise_id, skill_id, datetime.now(UTC), run_id],
            )
        finally:
            connection.close()

    def load_session_summary(self, session_id: int) -> dict[str, Any] | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT d.status, d.completion_rate, s.learner_id
                FROM learning_session_details d
                JOIN learning_sessions s ON s.id=d.session_id
                WHERE d.session_id=?
                """,
                [session_id],
            ).fetchone()
            if row is None:
                return None
            return {"status": str(row[0]), "completion_rate": float(row[1]), "learner_id": int(row[2])}
        finally:
            connection.close()

    def load_refresh_run(
        self,
        *,
        learner_id: int,
        session_id: int,
        pathway_code: str,
        refresh_version: str,
    ) -> dict[str, Any] | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT status, result_snapshot FROM pedagogical_intelligence_refresh_runs
                WHERE learner_id=? AND session_id=? AND pathway_code=? AND refresh_version=?
                """,
                [learner_id, session_id, pathway_code, refresh_version],
            ).fetchone()
            if row is None:
                return None
            snapshot = json.loads(str(row[1])) if row[1] else {}
            snapshot["status"] = str(row[0])
            return snapshot
        finally:
            connection.close()

    def persist_refresh_run(
        self,
        *,
        learner_id: int,
        session_id: int,
        pathway_code: str,
        refresh_version: str,
        status: str,
        correlation_id: str,
        snapshot: dict[str, Any],
    ) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO pedagogical_intelligence_refresh_runs(
                    learner_id, session_id, pathway_code, refresh_version, status, correlation_id, result_snapshot
                ) VALUES (?,?,?,?,?,?,?)
                ON CONFLICT (learner_id, session_id, pathway_code, refresh_version) DO UPDATE SET
                    status=excluded.status,
                    correlation_id=excluded.correlation_id,
                    result_snapshot=excluded.result_snapshot
                """,
                [
                    learner_id,
                    session_id,
                    pathway_code,
                    refresh_version,
                    status,
                    correlation_id,
                    json.dumps(snapshot),
                ],
            )
        finally:
            connection.close()

    @staticmethod
    def _run_from_row(row: tuple[Any, ...]) -> DiagnosticRun:
        target_skill_ids = tuple(int(item) for item in json.loads(str(row[5])))
        assessed_skill_ids = tuple(int(item) for item in json.loads(str(row[6])))
        raw_confidence = json.loads(str(row[7]))
        confidence_by_skill = {int(key): float(value) for key, value in raw_confidence.items()}
        path = path_by_code(row[2])
        return DiagnosticRun(
            int(row[0]),
            int(row[1]),
            path.code,
            row[3],
            int(row[4]),
            target_skill_ids,
            assessed_skill_ids,
            None if row[8] is None else int(row[8]),
            confidence_by_skill,
            row[9],
            row[10],
        )
