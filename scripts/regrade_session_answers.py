"""Regrade a completed homework session with the current assessment engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

from domain.learning_session.models import AnswerType, AssessmentMethod
from services.learning_session.assessment import DeterministicAssessmentEngine
from services.learning_session.models import AssessmentRequest
from services.unified_session_execution import UnifiedSessionExecutionService

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "learning_coach_v2.duckdb"


def _strategy(response_type: str) -> tuple[AnswerType, AssessmentMethod]:
    return UnifiedSessionExecutionService._strategy(response_type)


def regrade_session(session_id: int) -> None:
    engine = DeterministicAssessmentEngine()
    con = duckdb.connect(str(DB))
    try:
        rows = con.execute(
            """
            SELECT aa.id, sa.raw_answer, cq.response_type, cq.expected_answer, coalesce(cq.tolerance, 0),
                   h.id
            FROM session_attempt_records sar
            JOIN session_activities a ON a.id=sar.activity_id
            JOIN student_answers sa ON sa.id=sar.answer_id
            JOIN answer_assessments aa ON aa.id=sar.assessment_id
            JOIN content_questions cq ON cq.id=sa.question_id
            LEFT JOIN homework_assignments h ON h.session_id=a.session_id
            WHERE a.session_id=?
            ORDER BY aa.id
            """,
            [session_id],
        ).fetchall()
        changed = 0
        scores: list[float] = []
        for assessment_id, raw, response_type, expected_raw, tolerance, homework_id in rows:
            try:
                expected = json.loads(str(expected_raw))
            except Exception:
                expected = expected_raw
            try:
                answer = json.loads(str(raw)) if raw is not None and str(raw).startswith(('"', "[", "{")) else raw
            except Exception:
                answer = raw
            answer_type, method = _strategy(str(response_type))
            try:
                result = engine.assess(
                    AssessmentRequest(
                        answer_type,
                        answer,
                        expected,
                        method,
                        tolerance=float(tolerance or 0),
                    )
                )
            except Exception as exc:
                print(f"assessment {assessment_id}: skip regrade ({exc})")
                continue
            scores.append(result.final_score)
            before = con.execute(
                "SELECT correct, score FROM answer_assessments WHERE id=?", [assessment_id]
            ).fetchone()
            if before and (bool(before[0]) != result.correct or float(before[1]) != result.final_score):
                con.execute(
                    """UPDATE answer_assessments
                    SET correct=?, score=?, assessment_method=?, assessment_engine_version=?
                    WHERE id=?""",
                    [
                        result.correct,
                        result.final_score,
                        result.method.value,
                        f"{engine.version}-regrade",
                        assessment_id,
                    ],
                )
                con.execute(
                    "UPDATE session_attempt_records SET success=? WHERE assessment_id=?",
                    [result.correct, assessment_id],
                )
                changed += 1
                print(
                    f"assessment {assessment_id}: {before[0]}/{before[1]} -> "
                    f"{result.correct}/{result.final_score} | raw={answer!r} expected={expected!r}"
                )
        if scores and rows and rows[0][5] is not None:
            overall = sum(scores) / len(scores)
            homework_id = int(rows[0][5])
            con.execute(
                """UPDATE homework_result_summaries
                SET overall_score=?, success_rate=?, calculation_version='homework-summary-v1-regrade'
                WHERE homework_id=?""",
                [overall, overall, homework_id],
            )
            print(f"homework {homework_id} overall -> {overall:.1f}% ({changed} answers updated)")
        else:
            print(f"session {session_id}: {changed} answers updated, scores={scores}")
    finally:
        con.close()


if __name__ == "__main__":
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 145067
    regrade_session(target)
