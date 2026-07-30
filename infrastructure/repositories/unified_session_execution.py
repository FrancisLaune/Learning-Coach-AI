"""DuckDB read/write adapter for interactive V2 question execution."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from domain.learning.models import LearningEngineResult
from infrastructure.database.v2 import connect_v2
from services.unified_session_execution import ExecutableQuestion, QuestionMaterial


class DuckDBUnifiedSessionExecutionRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def current_question(self, learner_id: int, session_id: int) -> QuestionMaterial | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT a.id,e.title,qs.skill_id,q.id,q.instructions,q.context,q.statement,
                q.response_type,q.expected_answer,coalesce(q.tolerance,0),a.difficulty,
                sol.pedagogical_explanation,sol.method,sol.advice,
                coalesce(m.score,0),coalesce(ans.attempts,0),
                row_number() OVER (ORDER BY a.activity_order,q.sequence_order),
                count(*) OVER ()
                FROM learning_sessions ls
                JOIN session_activities a ON a.session_id=ls.id
                JOIN exercises e ON e.id=a.content_id
                JOIN content_versions cv ON cv.id=a.content_version_id AND cv.entity_id=e.id
                JOIN content_questions q ON q.exercise_id=a.content_id
                LEFT JOIN content_solutions sol ON sol.question_id=q.id
                JOIN exercise_questions eq ON eq.exercise_id=e.id
                JOIN question_skills qs ON qs.question_id=eq.question_id AND qs.is_primary
                LEFT JOIN production_learning_catalog c ON c.content_id=a.content_id
                    AND c.content_version_id=a.content_version_id
                LEFT JOIN longitudinal_mastery_current m
                    ON m.learner_id=ls.learner_id AND m.skill_id=qs.skill_id
                LEFT JOIN (
                    SELECT activity_id,question_id,count(*) attempts
                    FROM student_answers WHERE validated GROUP BY activity_id,question_id
                ) ans ON ans.activity_id=a.id AND ans.question_id=q.id
                WHERE ls.id=? AND ls.learner_id=? AND a.status IN ('NOT_STARTED','RUNNING')
                AND coalesce(ans.attempts,0)=0
                ORDER BY a.activity_order,q.sequence_order LIMIT 1""",
                [session_id, learner_id],
            ).fetchone()
            if row is None:
                return None
            options = connection.execute(
                """SELECT stable_code,label FROM content_answer_options
                WHERE question_id=? ORDER BY sequence_order""",
                [int(row[3])],
            ).fetchall()
            hints = connection.execute(
                """SELECT id,text,penalty_weight FROM content_hints
                WHERE question_id=? AND reveals_answer=FALSE ORDER BY sequence_order""",
                [int(row[3])],
            ).fetchall()
            question = ExecutableQuestion(
                session_id,
                int(row[0]),
                str(row[1]),
                int(row[2]),
                int(row[3]),
                str(row[4]),
                None if row[5] is None else str(row[5]),
                str(row[6]),
                str(row[7]),
                tuple((str(item[0]), str(item[1])) for item in options),
                tuple((int(item[0]), str(item[1]), float(item[2])) for item in hints),
                int(row[10]),
                int(row[16]),
                int(row[17]),
            )
            return QuestionMaterial(
                question,
                json.loads(str(row[8])),
                float(row[9]),
                str(row[11] or "Consulte la correction après ta réponse."),
                str(row[12] or ""),
                str(row[13] or ""),
                float(row[14]),
                int(row[15]),
            )
        finally:
            connection.close()

    def used_hint_penalties(self, activity_id: int) -> tuple[float, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            return tuple(
                float(row[0])
                for row in connection.execute(
                    "SELECT penalty FROM hint_usage WHERE activity_id=? ORDER BY hint_number", [activity_id]
                ).fetchall()
            )
        finally:
            connection.close()

    def activity_question_count(self, activity_id: int) -> tuple[int, int]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT count(DISTINCT CASE WHEN ans.validated THEN q.id END),count(DISTINCT q.id)
                FROM session_activities a JOIN content_questions q ON q.exercise_id=a.content_id
                LEFT JOIN student_answers ans ON ans.activity_id=a.id AND ans.question_id=q.id
                WHERE a.id=?""",
                [activity_id],
            ).fetchone()
            return (int(row[0]), int(row[1]))
        finally:
            connection.close()

    def record_hint(self, activity_id: int, hint_id: int, hint_number: int, penalty: float, at: datetime) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """INSERT INTO hint_usage(activity_id,hint_id,hint_number,display_time,penalty)
                VALUES (?,?,?,?,?) ON CONFLICT(activity_id,hint_id) DO NOTHING""",
                [activity_id, hint_id, hint_number, at, penalty],
            )
        finally:
            connection.close()

    def enqueue_refresh(self, result: LearningEngineResult) -> None:
        parts = result.attempt_id.split(":")
        if len(parts) < 2 or not parts[1].isdigit():
            raise ValueError("Cannot derive session correlation from attempt")
        session_id = int(parts[1])
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """INSERT INTO decision_refresh_queue
                (session_id,learner_id,status,correlation_id)
                SELECT ?,?,'PENDING',? WHERE NOT EXISTS (
                    SELECT 1 FROM decision_refresh_queue WHERE session_id=? AND correlation_id=?
                )""",
                [
                    session_id,
                    result.mastery.current.learner_id,
                    result.attempt_id,
                    session_id,
                    result.attempt_id,
                ],
            )
            mastery = result.mastery.current
            if mastery.failure_streak >= 3 and mastery.trend.value == "declining":
                major = bool(mastery.prerequisite_for_future)
                connection.execute(
                    """INSERT INTO programme_change_proposals
                    (stable_key,learner_id,level,change_type,status,current_state,proposed_state,
                     reason_codes,evidence_references,expected_benefit_code,correlation_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(stable_key) DO NOTHING""",
                    [
                        f"mastery:{result.attempt_id}",
                        mastery.learner_id,
                        3 if major else 2,
                        "PREREQUISITE_CONSOLIDATION" if major else "PRACTICE_INCREASE",
                        "PENDING_PARENT" if major else "PROPOSED",
                        json.dumps({"mastery": result.mastery.previous.score}),
                        json.dumps({"additional_sessions": 2, "difficulty": max(1, mastery.last_difficulty - 1)}),
                        json.dumps(["PERSISTENT_WEAKNESS", "DECLINING_TREND"]),
                        json.dumps([f"attempt:{result.attempt_id}", f"skill:{mastery.skill_id}"]),
                        "RESTORE_FOUNDATIONS" if major else "CONSOLIDATE_SKILL",
                        result.attempt_id,
                    ],
                )
        finally:
            connection.close()

    def complete_homework(self, session_id: int) -> None:
        connection = connect_v2(self.database_path)
        try:
            homework = connection.execute(
                "SELECT id FROM homework_assignments WHERE session_id=?", [session_id]
            ).fetchone()
            if homework is None:
                return
            homework_id = int(homework[0])
            connection.execute(
                """UPDATE homework_assignments SET status='COMPLETED',completed_at=now(),updated_at=now()
                WHERE id=?""",
                [homework_id],
            )
            row = connection.execute(
                """SELECT coalesce(avg(aa.score),0),coalesce(avg(CASE WHEN a.success THEN 100 ELSE 0 END),0),
                coalesce(sum(a.duration_ms)/1000,0),coalesce(sum(a.hint_count),0),
                coalesce(sum(a.mastery_after-a.mastery_before),0)
                FROM session_attempt_records a
                JOIN session_activities act ON act.id=a.activity_id
                JOIN answer_assessments aa ON aa.id=a.assessment_id
                WHERE act.session_id=?""",
                [session_id],
            ).fetchone()
            total_questions = int(
                connection.execute(
                    """SELECT count(DISTINCT q.id) FROM session_activities a
                    JOIN content_questions q ON q.exercise_id=a.content_id WHERE a.session_id=?""",
                    [session_id],
                ).fetchone()[0]
            )
            answered = int(
                connection.execute(
                    """SELECT count(*) FROM student_answers ans JOIN session_activities a ON a.id=ans.activity_id
                    WHERE a.session_id=? AND ans.validated""",
                    [session_id],
                ).fetchone()[0]
            )
            connection.execute(
                """INSERT INTO homework_result_summaries
                (homework_id,overall_score,success_rate,time_spent_seconds,hints_used,unanswered_count,
                 mastery_impact,chapter_results,competency_results,error_categories,calculation_version)
                VALUES (?,?,?,?,?,?,?,'{}','{}','{}','homework-summary-v1')
                ON CONFLICT(homework_id) DO NOTHING""",
                [
                    homework_id,
                    float(row[0]),
                    float(row[1]),
                    int(row[2]),
                    int(row[3]),
                    max(0, total_questions - answered),
                    max(-100.0, min(100.0, float(row[4]))),
                ],
            )
        finally:
            connection.close()
