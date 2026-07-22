"""Small repositories for the DuckDB V2 learning-model foundation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infrastructure.database.v2 import connect_v2


def _row_as_dict(cursor: Any, row: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {column[0]: value for column, value in zip(cursor.description, row, strict=True)}


class V2Repository:
    """Base repository carrying only an explicit database path."""

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path


class ReferenceRepositoryV2(V2Repository):
    """Read the versioned program, subject and skill hierarchy."""

    def list_programs(self) -> list[dict[str, Any]]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            cursor = connection.execute(
                "SELECT id,code,version,label,country_code,default_language_code FROM programs ORDER BY code,version"
            )
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            connection.close()

    def skill_catalog(self, program_id: int) -> list[dict[str, Any]]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            cursor = connection.execute(
                "SELECT * FROM v_skill_catalog WHERE program_id=? ORDER BY subject_id,domain_id,skill_id",
                [program_id],
            )
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            connection.close()


class LearnerRepositoryV2(V2Repository):
    """Create and retrieve learners without authentication concerns."""

    def create(self, display_name: str, *, locale: str = "fr-FR", timezone: str = "Europe/Paris") -> int:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                "INSERT INTO learners(display_name,locale,timezone) VALUES (?,?,?) RETURNING id",
                [display_name, locale, timezone],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return the learner identifier")
            return int(row[0])
        finally:
            connection.close()

    def get(self, learner_id: int) -> dict[str, Any] | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            cursor = connection.execute(
                "SELECT id,external_ref,display_name,locale,timezone,created_at,archived_at FROM learners WHERE id=?",
                [learner_id],
            )
            return _row_as_dict(cursor, cursor.fetchone())
        finally:
            connection.close()


class ContentRepositoryV2(V2Repository):
    """Create exercises/questions and their normalized mappings."""

    def create_exercise(
        self,
        subject_id: int,
        code: str,
        title: str,
        objective: str,
        *,
        estimated_seconds: int = 300,
        difficulty: int = 2,
        instructions: str = "Répondre aux questions.",
        evaluation_strategy: dict[str, Any] | None = None,
        language_code: str = "fr-FR",
    ) -> int:
        strategy = evaluation_strategy or {"kind": "weighted_sum"}
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """
                INSERT INTO exercises(
                    subject_id,code,title,objective,estimated_seconds,difficulty,
                    instructions,evaluation_strategy,language_code
                ) VALUES (?,?,?,?,?,?,?,?,?) RETURNING id
                """,
                [
                    subject_id,
                    code,
                    title,
                    objective,
                    estimated_seconds,
                    difficulty,
                    instructions,
                    json.dumps(strategy),
                    language_code,
                ],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return the exercise identifier")
            return int(row[0])
        finally:
            connection.close()

    def create_question(
        self,
        code: str,
        statement: str,
        expected_answer: Any,
        explanation: str,
        *,
        answer_type: str = "text",
        estimated_seconds: int = 60,
        language_code: str = "fr-FR",
    ) -> int:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """
                INSERT INTO questions(
                    code,statement,answer_type,expected_answer,explanation,estimated_seconds,language_code
                ) VALUES (?,?,?,?,?,?,?) RETURNING id
                """,
                [
                    code,
                    statement,
                    answer_type,
                    json.dumps(expected_answer),
                    explanation,
                    estimated_seconds,
                    language_code,
                ],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return the question identifier")
            return int(row[0])
        finally:
            connection.close()

    def add_question(self, exercise_id: int, question_id: int, position: int, *, points: float = 1) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                "INSERT INTO exercise_questions(exercise_id,question_id,position,points) VALUES (?,?,?,?)",
                [exercise_id, question_id, position, points],
            )
        finally:
            connection.close()

    def link_skill(self, question_id: int, skill_id: int, *, weight: float = 1, is_primary: bool = True) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                "INSERT INTO question_skills(question_id,skill_id,weight,is_primary) VALUES (?,?,?,?)",
                [question_id, skill_id, weight, is_primary],
            )
        finally:
            connection.close()


class ObjectiveRepositoryV2(V2Repository):
    """Create learner objectives for future application services."""

    def create(self, learner_id: int, title: str, *, program_id: int | None = None, kind: str = "custom") -> int:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                "INSERT INTO objectives(learner_id,program_id,kind,title) VALUES (?,?,?,?) RETURNING id",
                [learner_id, program_id, kind, title],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return the objective identifier")
            return int(row[0])
        finally:
            connection.close()


class SessionRepositoryV2(V2Repository):
    """Create learning sessions without selecting pedagogical content."""

    def create(self, learner_id: int, *, kind: str = "practice", objective_id: int | None = None) -> int:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                "INSERT INTO learning_sessions(learner_id,objective_id,kind) VALUES (?,?,?) RETURNING id",
                [learner_id, objective_id, kind],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return the session identifier")
            return int(row[0])
        finally:
            connection.close()


class AttemptRepositoryV2(V2Repository):
    """Append immutable question attempts."""

    def create(
        self,
        learner_id: int,
        question_id: int,
        answer: Any,
        *,
        score: float,
        difficulty: int,
        prompt_snapshot: str,
        expected_answer_snapshot: Any,
        is_correct: bool | None = None,
        elapsed_ms: int | None = None,
    ) -> int:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """
                INSERT INTO attempts(
                    learner_id,question_id,answer,is_correct,score,elapsed_ms,
                    difficulty_at_attempt,prompt_snapshot,expected_answer_snapshot
                ) VALUES (?,?,?,?,?,?,?,?,?) RETURNING id
                """,
                [
                    learner_id,
                    question_id,
                    json.dumps(answer),
                    is_correct,
                    score,
                    elapsed_ms,
                    difficulty,
                    prompt_snapshot,
                    json.dumps(expected_answer_snapshot),
                ],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return the attempt identifier")
            return int(row[0])
        finally:
            connection.close()


class MasteryRepositoryV2(V2Repository):
    """Persist current mastery projections; calculation belongs to a later ticket."""

    def upsert(self, learner_id: int, skill_id: int, score: float, confidence: float, model_version: str) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO mastery_current(learner_id,skill_id,score,confidence,model_version)
                VALUES (?,?,?,?,?)
                ON CONFLICT (learner_id,skill_id) DO UPDATE SET
                    score=excluded.score,
                    confidence=excluded.confidence,
                    model_version=excluded.model_version,
                    updated_at=now()
                """,
                [learner_id, skill_id, score, confidence, model_version],
            )
        finally:
            connection.close()

    def get(self, learner_id: int, skill_id: int) -> dict[str, Any] | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            cursor = connection.execute(
                "SELECT * FROM mastery_current WHERE learner_id=? AND skill_id=?",
                [learner_id, skill_id],
            )
            return _row_as_dict(cursor, cursor.fetchone())
        finally:
            connection.close()


class DecisionRepositoryV2(V2Repository):
    """Append externally calculated decisions without implementing the Decision Engine."""

    def create(
        self,
        learner_id: int,
        decision_type: str,
        context_hash: str,
        *,
        engine_version: str,
        ruleset_version: str,
        correlation_id: str,
        selected_entity_type: str = "none",
        selected_entity_id: int | None = None,
    ) -> int:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """
                INSERT INTO learning_decisions(
                    learner_id,decision_type,engine_version,ruleset_version,context_hash,
                    inputs,candidates,selected_entity_type,selected_entity_id,scores,reason_codes,correlation_id
                ) VALUES (?,?,?,?,?,'{}','[]',?,?, '{}','[]',?) RETURNING id
                """,
                [
                    learner_id,
                    decision_type,
                    engine_version,
                    ruleset_version,
                    context_hash,
                    selected_entity_type,
                    selected_entity_id,
                    correlation_id,
                ],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return the decision identifier")
            return int(row[0])
        finally:
            connection.close()


class RecommendationRepositoryV2(V2Repository):
    """Store recommendations produced outside this data-foundation ticket."""

    def create_for_skill(
        self,
        learner_id: int,
        decision_id: int,
        skill_id: int,
        *,
        kind: str,
        priority_score: float,
        reason_code: str,
    ) -> int:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """
                INSERT INTO recommendations(
                    learner_id,decision_id,target_skill_id,kind,priority_score,reason_code,explanation
                ) VALUES (?,?,?,?,?,?,'{}') RETURNING id
                """,
                [learner_id, decision_id, skill_id, kind, priority_score, reason_code],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return the recommendation identifier")
            return int(row[0])
        finally:
            connection.close()
