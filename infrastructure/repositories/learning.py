"""Transactional DuckDB adapter for the longitudinal Learning Engine."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from domain.learning.models import LearningEngineResult

from domain.learning.enums import LearningPhase, MasteryLevel, Trend
from domain.learning.events import LearningEvent
from domain.learning.models import (
    AcademicYear,
    CurriculumContext,
    ExaminationObjective,
    ExamReadiness,
    GradeLevel,
    LearnerAttempt,
    LearnerJourneyContext,
    MasteryState,
    ProgressState,
    TransitionReadiness,
)
from infrastructure.database.v2 import connect_v2
from services.learning.result_snapshot import restore_learning_engine_result


class DuckDBLearningRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def is_processed(self, stable_attempt_id: str) -> bool:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            return (
                connection.execute(
                    "SELECT count(*) FROM learning_attempt_inputs WHERE stable_id=?", [stable_attempt_id]
                ).fetchone()[0]
                > 0
            )
        finally:
            connection.close()

    def get_cached_result(self, stable_attempt_id: str) -> LearningEngineResult:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                "SELECT result_snapshot FROM learning_attempt_inputs WHERE stable_id=?",
                [stable_attempt_id],
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise KeyError(f"Unknown learning attempt {stable_attempt_id}")
        payload = json.loads(str(row[0]))
        return restore_learning_engine_result(payload)

    def load_mastery(self, learner_id: int, skill_id: int) -> MasteryState | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                "SELECT learner_id,skill_id,score,level,observations,successes,failures,success_streak,failure_streak,last_activity_at,last_success_at,last_difficulty,last_grade_code,confidence,trend,stability,origin_grade_code,prerequisite_for_future FROM longitudinal_mastery_current WHERE learner_id=? AND skill_id=?",
                [learner_id, skill_id],
            ).fetchone()
            return None if row is None else self._mastery(row)
        finally:
            connection.close()

    def load_all_mastery(self, learner_id: int) -> dict[int, MasteryState]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                "SELECT learner_id,skill_id,score,level,observations,successes,failures,success_streak,failure_streak,last_activity_at,last_success_at,last_difficulty,last_grade_code,confidence,trend,stability,origin_grade_code,prerequisite_for_future FROM longitudinal_mastery_current WHERE learner_id=?",
                [learner_id],
            ).fetchall()
            return {int(row[1]): self._mastery(row) for row in rows}
        finally:
            connection.close()

    @staticmethod
    def _mastery(row: tuple[Any, ...]) -> MasteryState:
        return MasteryState(
            int(row[0]),
            int(row[1]),
            float(row[2]),
            MasteryLevel(row[3]),
            int(row[4]),
            int(row[5]),
            int(row[6]),
            int(row[7]),
            int(row[8]),
            row[9],
            row[10],
            int(row[11]),
            row[12],
            float(row[13]),
            Trend(row[14]),
            float(row[15]),
            row[16],
            bool(row[17]),
        )

    def load_journey(self, learner_id: int) -> LearnerJourneyContext:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT lj.learner_id,c.code,c.rank,c.label,t.code,t.rank,t.label,lj.academic_year_start,lj.learning_phase,lj.program_id,lj.examination_code,lj.examination_date FROM learner_journeys lj JOIN school_levels c ON c.id=lj.current_school_level_id LEFT JOIN school_levels t ON t.id=lj.target_school_level_id WHERE lj.learner_id=?""",
                [learner_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"No journey for learner {learner_id}")
            target = None if row[4] is None else GradeLevel(row[4], int(row[5]), row[6])
            exam = None if row[10] is None else ExaminationObjective(row[10], int(row[9] or 0), row[11])
            return LearnerJourneyContext(
                int(row[0]),
                GradeLevel(row[1], int(row[2]), row[3]),
                target,
                AcademicYear(int(row[7]), int(row[7]) + 1),
                LearningPhase(row[8]),
                row[9],
                exam,
            )
        finally:
            connection.close()

    def load_curriculum(self, journey: LearnerJourneyContext) -> tuple[CurriculumContext, ...]:
        if journey.program_id is None:
            return ()
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT ps.skill_id,d.subject_id,ps.program_id,sl.code,sl.rank,sl.label,coalesce(ps.priority,1),coalesce(ps.expected_mastery,0.7) FROM program_skills ps JOIN skills s ON s.id=ps.skill_id JOIN domains d ON d.id=s.domain_id JOIN program_subjects psub ON psub.program_id=ps.program_id AND psub.subject_id=d.subject_id JOIN school_levels sl ON sl.id=psub.school_level_id WHERE ps.program_id=?""",
                [journey.program_id],
            ).fetchall()
            return tuple(
                CurriculumContext(
                    int(r[0]),
                    int(r[1]),
                    int(r[2]),
                    GradeLevel(r[3], int(r[4]), r[5]),
                    3,
                    float(r[6]),
                    float(r[7]) >= 0.7,
                )
                for r in rows
            )
        finally:
            connection.close()

    def load_prerequisite_ids(self, skill_id: int) -> tuple[int, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            return tuple(
                int(r[0])
                for r in connection.execute(
                    "SELECT prerequisite_skill_id FROM skill_prerequisites WHERE skill_id=?", [skill_id]
                ).fetchall()
            )
        finally:
            connection.close()

    def set_journey(
        self,
        learner_id: int,
        current_level_id: int,
        target_level_id: int | None,
        year: int,
        phase: LearningPhase,
        program_id: int | None = None,
        examination_code: str | None = None,
    ) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                "INSERT INTO learner_journeys VALUES (?,?,?,?,?,?,?,NULL,now()) ON CONFLICT(learner_id) DO UPDATE SET current_school_level_id=excluded.current_school_level_id,target_school_level_id=excluded.target_school_level_id,academic_year_start=excluded.academic_year_start,program_id=excluded.program_id,learning_phase=excluded.learning_phase,examination_code=excluded.examination_code,updated_at=now()",
                [learner_id, current_level_id, target_level_id, year, program_id, phase.value, examination_code],
            )
        finally:
            connection.close()

    def save_cycle(
        self,
        attempt: LearnerAttempt,
        mastery: MasteryState,
        events: tuple[LearningEvent, ...],
        progress: ProgressState | None,
        transition: TransitionReadiness | None,
        exam: ExamReadiness | None,
        result_payload: dict,
    ) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            connection.execute(
                "INSERT INTO learning_attempt_inputs VALUES (?,?,?,?,?,?,now())",
                [
                    attempt.stable_id,
                    attempt.learner_id,
                    attempt.skill_id,
                    attempt.occurred_at,
                    json.dumps(asdict(attempt), default=str),
                    json.dumps(result_payload, default=str),
                ],
            )
            connection.execute(
                """INSERT INTO longitudinal_mastery_current VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,now()) ON CONFLICT(learner_id,skill_id) DO UPDATE SET score=excluded.score,level=excluded.level,observations=excluded.observations,successes=excluded.successes,failures=excluded.failures,success_streak=excluded.success_streak,failure_streak=excluded.failure_streak,last_activity_at=excluded.last_activity_at,last_success_at=excluded.last_success_at,last_difficulty=excluded.last_difficulty,last_grade_code=excluded.last_grade_code,confidence=excluded.confidence,trend=excluded.trend,stability=excluded.stability,origin_grade_code=excluded.origin_grade_code,prerequisite_for_future=excluded.prerequisite_for_future,updated_at=now()""",
                [
                    mastery.learner_id,
                    mastery.skill_id,
                    mastery.score,
                    mastery.level.value,
                    mastery.observations,
                    mastery.successes,
                    mastery.failures,
                    mastery.success_streak,
                    mastery.failure_streak,
                    mastery.last_activity_at,
                    mastery.last_success_at,
                    mastery.last_difficulty,
                    mastery.last_grade_code,
                    mastery.confidence,
                    mastery.trend.value,
                    mastery.stability,
                    mastery.origin_grade_code,
                    mastery.prerequisite_for_future,
                ],
            )
            connection.execute(
                "INSERT INTO longitudinal_mastery_events(stable_attempt_id,learner_id,skill_id,previous_score,current_score,explanation,occurred_at) VALUES (?,?,?,?,?,?,?)",
                [
                    attempt.stable_id,
                    attempt.learner_id,
                    attempt.skill_id,
                    result_payload["mastery"]["previous"]["score"],
                    mastery.score,
                    json.dumps(result_payload["mastery"], default=str),
                    attempt.occurred_at,
                ],
            )
            for event in events:
                connection.execute(
                    "INSERT INTO learning_domain_events(stable_attempt_id,event_type,learner_id,skill_id,payload,occurred_at) VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                    [
                        attempt.stable_id,
                        type(event).__name__,
                        event.learner_id,
                        event.skill_id,
                        json.dumps(event.payload),
                        event.occurred_at,
                    ],
                )
            if transition:
                connection.execute(
                    "INSERT INTO transition_readiness_current VALUES (?,?,?,?,?,?,now()) ON CONFLICT(learner_id,target_grade_code) DO UPDATE SET score=excluded.score,coverage=excluded.coverage,confidence=excluded.confidence,details=excluded.details,calculated_at=now()",
                    [
                        attempt.learner_id,
                        transition.target_grade_code,
                        transition.score,
                        transition.coverage,
                        transition.confidence,
                        json.dumps(asdict(transition)),
                    ],
                )
            if exam:
                connection.execute(
                    "INSERT INTO exam_readiness_current VALUES (?,?,?,?,?,?,now()) ON CONFLICT(learner_id,examination_code) DO UPDATE SET score=excluded.score,coverage=excluded.coverage,confidence=excluded.confidence,details=excluded.details,calculated_at=now()",
                    [
                        attempt.learner_id,
                        exam.examination_code,
                        exam.score,
                        exam.coverage,
                        exam.confidence,
                        json.dumps(asdict(exam), default=str),
                    ],
                )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
