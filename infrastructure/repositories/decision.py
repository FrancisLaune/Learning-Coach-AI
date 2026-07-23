"""DuckDB persistence adapter for journeys and deterministic decisions."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import time
from pathlib import Path
from typing import Any

from domain.decision.enums import ObjectiveKind
from domain.decision.models import (
    DecisionContext,
    LearnerJourney,
    LearningDecision,
    PedagogicalObjective,
    WeeklyAvailability,
)
from domain.learning.enums import LearningPhase
from domain.learning.models import AcademicYear, GradeLevel
from infrastructure.database.v2 import connect_v2


class DuckDBDecisionRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def save_objective(self, learner_id: int, objective: PedagogicalObjective) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO pedagogical_objectives(id,learner_id,kind,title,target_date,priority_weight,active)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,title=excluded.title,
                target_date=excluded.target_date,priority_weight=excluded.priority_weight,active=excluded.active,
                updated_at=now()
                """,
                [
                    objective.id,
                    learner_id,
                    objective.kind.value,
                    objective.title,
                    objective.target_date,
                    objective.priority_weight,
                    objective.active,
                ],
            )
        finally:
            connection.close()

    def save_journey(self, journey: LearnerJourney) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            current_id = self._level_id(connection, journey.current_grade.code)
            target_id = self._level_id(connection, journey.target_grade.code) if journey.target_grade else None
            connection.execute(
                """
                INSERT INTO learner_journeys(learner_id,current_school_level_id,target_school_level_id,
                academic_year_start,program_id,learning_phase,examination_code,examination_date)
                VALUES (?,?,?,?,NULL,?,?,NULL) ON CONFLICT(learner_id) DO UPDATE SET
                current_school_level_id=excluded.current_school_level_id,target_school_level_id=excluded.target_school_level_id,
                academic_year_start=excluded.academic_year_start,learning_phase=excluded.learning_phase,
                examination_code=excluded.examination_code,updated_at=now()
                """,
                [
                    journey.learner_id,
                    current_id,
                    target_id,
                    journey.academic_year.start_year,
                    journey.learning_phase.value,
                    journey.exam_objective.id if journey.exam_objective else None,
                ],
            )
            schedule = [
                {
                    "weekday": slot.weekday,
                    "start_time": slot.start_time.isoformat(),
                    "duration_minutes": slot.duration_minutes,
                }
                for slot in journey.weekly_schedule
            ]
            connection.execute(
                """
                INSERT INTO learner_journey_preferences VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,now())
                ON CONFLICT(learner_id) DO UPDATE SET current_objective_ref=excluded.current_objective_ref,
                long_term_objective_ref=excluded.long_term_objective_ref,exam_objective_ref=excluded.exam_objective_ref,
                target_date=excluded.target_date,preferred_subject_ids=excluded.preferred_subject_ids,
                weak_subject_ids=excluded.weak_subject_ids,daily_duration_minutes=excluded.daily_duration_minutes,
                weekly_schedule=excluded.weekly_schedule,difficulty_preference=excluded.difficulty_preference,
                parent_mode=excluded.parent_mode,student_mode=excluded.student_mode,learning_rhythm=excluded.learning_rhythm,
                preferred_revision_days=excluded.preferred_revision_days,vacation_mode=excluded.vacation_mode,
                holiday_planning=excluded.holiday_planning,transition_planning=excluded.transition_planning,updated_at=now()
                """,
                [
                    journey.learner_id,
                    journey.current_objective.id,
                    journey.long_term_objective.id if journey.long_term_objective else None,
                    journey.exam_objective.id if journey.exam_objective else None,
                    journey.target_date,
                    json.dumps(journey.preferred_subjects),
                    json.dumps(journey.weak_subjects),
                    journey.daily_duration_minutes,
                    json.dumps(schedule),
                    journey.difficulty_preference,
                    journey.parent_mode,
                    journey.student_mode,
                    journey.learning_rhythm,
                    json.dumps(journey.preferred_revision_days),
                    journey.vacation_mode,
                    journey.holiday_planning,
                    journey.transition_planning,
                ],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    @staticmethod
    def _level_id(connection: Any, code: str) -> int:
        row = connection.execute("SELECT id FROM school_levels WHERE code=?", [code]).fetchone()
        if row is None:
            raise KeyError(f"Unknown school level: {code}")
        return int(row[0])

    def load_journey(self, learner_id: int) -> LearnerJourney:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT c.code,c.rank,c.label,t.code,t.rank,t.label,j.academic_year_start,j.learning_phase,
                p.current_objective_ref,p.long_term_objective_ref,p.exam_objective_ref,p.target_date,
                p.preferred_subject_ids,p.weak_subject_ids,p.daily_duration_minutes,p.weekly_schedule,
                p.difficulty_preference,p.parent_mode,p.student_mode,p.learning_rhythm,p.preferred_revision_days,
                p.vacation_mode,p.holiday_planning,p.transition_planning,p.updated_at
                FROM learner_journeys j JOIN learner_journey_preferences p ON p.learner_id=j.learner_id
                JOIN school_levels c ON c.id=j.current_school_level_id
                LEFT JOIN school_levels t ON t.id=j.target_school_level_id WHERE j.learner_id=?
                """,
                [learner_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"No decision journey for learner {learner_id}")
            current = GradeLevel(row[0], int(row[1]), row[2])
            target = None if row[3] is None else GradeLevel(row[3], int(row[4]), row[5])
            current_objective = self._objective(connection, row[8])
            long_term = self._objective(connection, row[9]) if row[9] else None
            exam = self._objective(connection, row[10]) if row[10] else None
            schedule = tuple(
                WeeklyAvailability(
                    int(item["weekday"]), time.fromisoformat(item["start_time"]), int(item["duration_minutes"])
                )
                for item in json.loads(row[15])
            )
            return LearnerJourney(
                learner_id,
                current,
                target,
                AcademicYear(int(row[6]), int(row[6]) + 1),
                current_objective,
                long_term,
                exam,
                LearningPhase(row[7]),
                row[11],
                tuple(json.loads(row[12])),
                tuple(json.loads(row[13])),
                int(row[14]),
                schedule,
                int(row[16]),
                bool(row[17]),
                bool(row[18]),
                row[19],
                tuple(json.loads(row[20])),
                bool(row[21]),
                bool(row[22]),
                bool(row[23]),
                row[24],
            )
        finally:
            connection.close()

    @staticmethod
    def _objective(connection: Any, objective_id: str) -> PedagogicalObjective:
        row = connection.execute(
            "SELECT id,kind,title,target_date,priority_weight,active FROM pedagogical_objectives WHERE id=?",
            [objective_id],
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown objective: {objective_id}")
        return PedagogicalObjective(row[0], ObjectiveKind(row[1]), row[2], row[3], float(row[4]), bool(row[5]))

    def save_decision(self, context: DecisionContext, decision: LearningDecision) -> int:
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            selected = decision.selected
            row = connection.execute(
                """INSERT INTO learning_decisions(learner_id,decision_type,engine_version,ruleset_version,
                context_hash,inputs,candidates,selected_entity_type,selected_entity_id,scheduled_for,difficulty,
                duration_seconds,scores,reason_codes,correlation_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                [
                    decision.learner_id,
                    "next_activity",
                    decision.engine_version,
                    decision.ruleset_version,
                    decision.context_hash,
                    json.dumps(asdict(context), default=str),
                    json.dumps([asdict(candidate) for candidate in context.candidates], default=str),
                    "skill" if selected else "none",
                    selected.skill_id if selected else None,
                    selected.scheduled_for if selected else None,
                    selected.difficulty if selected else None,
                    selected.duration_minutes * 60 if selected else None,
                    json.dumps([asdict(item) for item in decision.priorities], default=str),
                    json.dumps(decision.explanation.rules),
                    decision.correlation_id,
                ],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return a decision identifier")
            decision_id = int(row[0])
            for item in decision.plan:
                connection.execute(
                    "INSERT INTO decision_plan_items(decision_id,candidate_ref,skill_id,subject_id,scheduled_for,duration_minutes,difficulty,position) VALUES (?,?,?,?,?,?,?,?)",
                    [
                        decision_id,
                        item.candidate_id,
                        item.skill_id,
                        item.subject_id,
                        item.scheduled_for,
                        item.duration_minutes,
                        item.difficulty,
                        item.order,
                    ],
                )
            connection.execute(
                "INSERT INTO decision_result_snapshots(decision_id,correlation_id,result) VALUES (?,?,?)",
                [decision_id, decision.correlation_id, json.dumps(asdict(decision), default=str)],
            )
            connection.execute("COMMIT")
            return decision_id
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def get_decision_payload(self, correlation_id: str) -> dict[str, Any] | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                "SELECT result FROM decision_result_snapshots WHERE correlation_id=?", [correlation_id]
            ).fetchone()
            return None if row is None else json.loads(row[0])
        finally:
            connection.close()
