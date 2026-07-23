"""Parameterized DuckDB V2 adapter for cross-context session contracts."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from application.session_application import SessionCommand
from domain.learning_session.models import LearningSession
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.learning_session import DuckDBLearningSessionRepository


class DuckDBSessionIntegrationGateway:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path
        self.sessions = DuckDBLearningSessionRepository(database_path)

    def learner_is_active(self, learner_id: int) -> bool:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                "SELECT count(*) FROM learners WHERE id=? AND archived_at IS NULL",
                [learner_id],
            ).fetchone()
            return bool(row and row[0])
        finally:
            connection.close()

    def recommendation_owner_and_version(self, recommendation_id: int) -> tuple[int, str] | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT learner_id,recommendation_version FROM personalized_session_proposals
                WHERE id=? AND absence_code IS NULL""",
                [recommendation_id],
            ).fetchone()
            return None if row is None else (int(row[0]), str(row[1]))
        finally:
            connection.close()

    def active_session(self, learner_id: int) -> LearningSession | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT session_id FROM v_active_learning_sessions
                WHERE learner_id=? ORDER BY creation_time DESC LIMIT 1""",
                [learner_id],
            ).fetchone()
        finally:
            connection.close()
        return None if row is None else self.sessions.get(int(row[0]))

    def session_owner(self, session_id: int) -> int | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute("SELECT learner_id FROM learning_sessions WHERE id=?", [session_id]).fetchone()
            return None if row is None else int(row[0])
        finally:
            connection.close()

    def activity_belongs(self, session_id: int, activity_id: int) -> bool:
        return self._exists(
            """SELECT count(*) FROM session_activities
            WHERE id=? AND session_id=? AND archived_at IS NULL""",
            [activity_id, session_id],
        )

    def question_belongs(self, activity_id: int, question_id: int) -> bool:
        return self._exists(
            """SELECT count(*) FROM session_activities a
            JOIN content_questions q ON q.exercise_id=a.content_id
            WHERE a.id=? AND q.id=? AND a.archived_at IS NULL""",
            [activity_id, question_id],
        )

    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool:
        return self._exists(
            """SELECT count(*) FROM learner_guardian_links
            WHERE guardian_external_ref=? AND learner_id=? AND active
            AND revoked_at IS NULL""",
            [parent_ref, learner_id],
        )

    def freeze_session_versions(self, session_id: int) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            activities = connection.execute(
                """SELECT a.id,v.version_number,d.curriculum_version,d.assessment_engine_version
                FROM session_activities a
                JOIN content_versions v ON v.id=a.content_version_id
                JOIN learning_session_details d ON d.session_id=a.session_id
                WHERE a.session_id=?""",
                [session_id],
            ).fetchall()
            for activity_id, version_number, curriculum_version, assessment_version in activities:
                questions = connection.execute(
                    """SELECT q.id,s.id FROM session_activities a
                    JOIN content_questions q ON q.exercise_id=a.content_id
                    LEFT JOIN content_solutions s ON s.question_id=q.id
                    WHERE a.id=? ORDER BY q.sequence_order""",
                    [activity_id],
                ).fetchall()
                connection.execute(
                    """INSERT INTO session_activity_snapshots VALUES (?,?,?,?,?,?,now())
                    ON CONFLICT(activity_id) DO NOTHING""",
                    [
                        activity_id,
                        version_number,
                        json.dumps([int(row[0]) for row in questions]),
                        json.dumps([int(row[1]) for row in questions if row[1] is not None]),
                        curriculum_version,
                        assessment_version,
                    ],
                )
            connection.execute(
                """INSERT INTO session_state_revisions(session_id,state_token)
                VALUES (?,?) ON CONFLICT(session_id) DO NOTHING""",
                [session_id, str(uuid.uuid4())],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def command_result(self, idempotency_key: str, command_type: str) -> dict[str, Any] | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT result_payload FROM session_command_results
                WHERE idempotency_key=? AND command_type=?""",
                [idempotency_key, command_type],
            ).fetchone()
            return None if row is None else dict(json.loads(row[0]))
        finally:
            connection.close()

    def save_command_result(
        self,
        command: SessionCommand,
        command_type: str,
        session_id: int | None,
        payload: dict[str, Any],
    ) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """INSERT INTO session_command_results
                (idempotency_key,session_id,learner_id,command_type,correlation_id,result_payload)
                VALUES (?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                [
                    command.idempotency_key,
                    session_id,
                    command.learner_id,
                    command_type,
                    command.correlation_id,
                    json.dumps(payload, default=str),
                ],
            )
        finally:
            connection.close()

    def _exists(self, query: str, parameters: list[Any]) -> bool:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(query, parameters).fetchone()
            return bool(row and row[0])
        finally:
            connection.close()
