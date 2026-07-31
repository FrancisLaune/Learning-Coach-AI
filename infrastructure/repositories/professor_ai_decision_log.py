"""DuckDB persistence for Professor AI decision journal (LCAI-0022D)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from infrastructure.database.v2 import connect_v2
from services.professor_ai.models import DecisionLogRecord


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.fromisoformat(str(value)).replace(tzinfo=UTC)


def _as_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        return ()
    return tuple(str(item) for item in parsed)


def _as_dict(value: Any) -> dict[str, object]:
    if value is None:
        return {}
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        return {}
    return {str(key): parsed[key] for key in parsed}


class DuckDBProfessorAIDecisionLogRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def append(
        self,
        *,
        learner_id: int,
        correlation_id: str,
        operating_mode: str,
        cycle_step: str,
        justification: str,
        engine_version: str,
        objective: str | None = None,
        candidates: tuple[str, ...] = (),
        exclusions: tuple[str, ...] = (),
        deficit: dict[str, object] | None = None,
        context: dict[str, object] | None = None,
        homework_id: int | None = None,
        session_id: int | None = None,
        created_at: datetime | None = None,
    ) -> DecisionLogRecord:
        stamped = created_at or datetime.now(tz=UTC)
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """INSERT INTO ai_decision_log (
                    learner_id, correlation_id, operating_mode, cycle_step, objective,
                    justification, engine_version, candidates_json, exclusions_json,
                    deficit_json, context_json, homework_id, session_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id, learner_id, correlation_id, operating_mode, cycle_step, objective,
                    justification, engine_version, candidates_json, exclusions_json,
                    deficit_json, context_json, homework_id, session_id, created_at""",
                [
                    learner_id,
                    correlation_id,
                    operating_mode,
                    cycle_step,
                    objective,
                    justification,
                    engine_version,
                    json.dumps(list(candidates), ensure_ascii=False),
                    json.dumps(list(exclusions), ensure_ascii=False),
                    json.dumps(deficit or {}, ensure_ascii=False),
                    json.dumps(context or {}, ensure_ascii=False),
                    homework_id,
                    session_id,
                    stamped,
                ],
            ).fetchone()
        finally:
            connection.close()
        assert row is not None
        return self._from_row(row)

    def list_for_learner(self, learner_id: int, *, limit: int = 50) -> tuple[DecisionLogRecord, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT id, learner_id, correlation_id, operating_mode, cycle_step, objective,
                    justification, engine_version, candidates_json, exclusions_json,
                    deficit_json, context_json, homework_id, session_id, created_at
                FROM ai_decision_log
                WHERE learner_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT ?""",
                [learner_id, max(1, int(limit))],
            ).fetchall()
        finally:
            connection.close()
        return tuple(self._from_row(row) for row in rows)

    def list_by_correlation(self, correlation_id: str) -> tuple[DecisionLogRecord, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT id, learner_id, correlation_id, operating_mode, cycle_step, objective,
                    justification, engine_version, candidates_json, exclusions_json,
                    deficit_json, context_json, homework_id, session_id, created_at
                FROM ai_decision_log
                WHERE correlation_id=?
                ORDER BY created_at ASC, id ASC""",
                [correlation_id],
            ).fetchall()
        finally:
            connection.close()
        return tuple(self._from_row(row) for row in rows)

    @staticmethod
    def _from_row(row: tuple[Any, ...]) -> DecisionLogRecord:
        return DecisionLogRecord(
            id=int(row[0]),
            learner_id=int(row[1]),
            correlation_id=str(row[2]),
            operating_mode=str(row[3]),
            cycle_step=str(row[4]),
            objective=None if row[5] is None else str(row[5]),
            justification=str(row[6]),
            engine_version=str(row[7]),
            candidates=_as_list(row[8]),
            exclusions=_as_list(row[9]),
            deficit=_as_dict(row[10]),
            context=_as_dict(row[11]),
            homework_id=None if row[12] is None else int(row[12]),
            session_id=None if row[13] is None else int(row[13]),
            created_at=_parse_ts(row[14]),
        )
