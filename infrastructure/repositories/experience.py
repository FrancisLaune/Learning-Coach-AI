"""DuckDB V2 read model for presentation application services."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from infrastructure.database.v2 import connect_v2
from services.learning_session.experience import ActivityListItem, MasteryView, SessionListItem


class DuckDBExperienceReadModel:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def _one(self, query: str, parameters: list[Any]) -> tuple[Any, ...] | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            return connection.execute(query, parameters).fetchone()
        finally:
            connection.close()

    def learner_name(self, learner_id: int) -> str:
        row = self._one("SELECT display_name FROM learners WHERE id=? AND archived_at IS NULL", [learner_id])
        return str(row[0]) if row else f"Apprenant {learner_id}"

    def objective(self, learner_id: int) -> str | None:
        row = self._one(
            """SELECT objective_ref FROM personalized_session_proposals
            WHERE learner_id=? ORDER BY created_at DESC LIMIT 1""",
            [learner_id],
        )
        return None if row is None else str(row[0])

    def mastery(self, learner_id: int) -> tuple[MasteryView, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT m.skill_id,s.default_label,m.score,m.level,m.trend
                FROM longitudinal_mastery_current m JOIN skills s ON s.id=m.skill_id
                WHERE m.learner_id=? ORDER BY m.score,s.default_label""",
                [learner_id],
            ).fetchall()
            return tuple(
                MasteryView(int(row[0]), str(row[1]), float(row[2]) * 100, str(row[3]), str(row[4])) for row in rows
            )
        finally:
            connection.close()

    def sessions(self, learner_id: int) -> tuple[SessionListItem, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT d.session_id,d.status,d.creation_time,
                CASE WHEN d.actual_duration_seconds>0 THEN d.actual_duration_seconds
                     ELSE d.planned_duration_seconds END,
                d.session_score,d.estimated_mastery_gain,d.completion_rate
                FROM learning_session_details d JOIN learning_sessions s ON s.id=d.session_id
                WHERE s.learner_id=? AND d.archived_at IS NULL
                ORDER BY d.creation_time DESC""",
                [learner_id],
            ).fetchall()
            return tuple(
                SessionListItem(
                    int(row[0]),
                    str(row[1]),
                    row[2],
                    int(row[3]),
                    float(row[4]),
                    float(row[5]),
                    float(row[6]),
                )
                for row in rows
            )
        finally:
            connection.close()

    def activities(self, session_id: int) -> tuple[ActivityListItem, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT a.id,e.title,a.activity_type,a.status,a.score,a.estimated_duration_seconds
                FROM session_activities a JOIN exercises e ON e.id=a.content_id
                WHERE a.session_id=? AND a.archived_at IS NULL ORDER BY a.activity_order""",
                [session_id],
            ).fetchall()
            return tuple(
                ActivityListItem(int(row[0]), str(row[1]), str(row[2]), str(row[3]), float(row[4]), int(row[5]))
                for row in rows
            )
        finally:
            connection.close()

    def summary(self, session_id: int) -> tuple[tuple[str, ...], tuple[str, ...], str | None] | None:
        row = self._one(
            """SELECT strengths,weaknesses,recommended_next_session FROM session_summaries
            WHERE session_id=? AND archived_at IS NULL""",
            [session_id],
        )
        if row is None:
            return None
        return (
            tuple(str(item) for item in json.loads(row[0])),
            tuple(str(item) for item in json.loads(row[1])),
            None if row[2] is None else str(row[2]),
        )

    def next_revision(self, learner_id: int) -> datetime | None:
        row = self._one(
            "SELECT min(next_review_at) FROM mastery_current WHERE learner_id=? AND next_review_at IS NOT NULL",
            [learner_id],
        )
        return None if row is None else row[0]

    def learners(self) -> tuple[tuple[int, str], ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                "SELECT id,display_name FROM learners WHERE archived_at IS NULL ORDER BY display_name"
            ).fetchall()
            return tuple((int(row[0]), str(row[1])) for row in rows)
        finally:
            connection.close()
