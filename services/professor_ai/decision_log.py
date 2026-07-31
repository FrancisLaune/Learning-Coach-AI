"""Persist Professor AI decision traces (LCAI-0022D)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from services.professor_ai.invariants import assert_no_score_fields_in_payload
from services.professor_ai.models import (
    DecisionLogRecord,
    DecisionTraceEntry,
    ProfessorOperatingMode,
)


class DecisionLogStore(Protocol):
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
    ) -> DecisionLogRecord: ...

    def list_for_learner(self, learner_id: int, *, limit: int = 50) -> tuple[DecisionLogRecord, ...]: ...


def new_correlation_id(prefix: str = "pai") -> str:
    return f"{prefix}:{uuid.uuid4().hex}"


def deficit_from_pairs(pairs: tuple[tuple[str, str], ...]) -> dict[str, object]:
    return {key: value for key, value in pairs}


class ProfessorAIDecisionLogService:
    """Writes orchestrator breadcrumbs to DuckDB without mutating scores."""

    def __init__(self, store: DecisionLogStore) -> None:
        self.store = store

    def record_trace(
        self,
        *,
        learner_id: int,
        mode: ProfessorOperatingMode,
        entries: tuple[DecisionTraceEntry, ...] | list[DecisionTraceEntry],
        correlation_id: str | None = None,
        homework_id: int | None = None,
        session_id: int | None = None,
        context: dict[str, object] | None = None,
    ) -> tuple[DecisionLogRecord, ...]:
        assert_no_score_fields_in_payload(context)
        correlation = correlation_id or new_correlation_id()
        recorded: list[DecisionLogRecord] = []
        for entry in entries:
            deficit = deficit_from_pairs(entry.deficit)
            assert_no_score_fields_in_payload(deficit)
            recorded.append(
                self.store.append(
                    learner_id=learner_id,
                    correlation_id=correlation,
                    operating_mode=mode.value,
                    cycle_step=entry.step,
                    justification=entry.justification,
                    engine_version=entry.engine_version,
                    objective=entry.objective,
                    candidates=entry.candidates,
                    exclusions=entry.exclusions,
                    deficit=deficit,
                    context=context or {},
                    homework_id=homework_id,
                    session_id=session_id,
                )
            )
        return tuple(recorded)

    def list_for_learner(self, learner_id: int, *, limit: int = 50) -> tuple[DecisionLogRecord, ...]:
        return self.store.list_for_learner(learner_id, limit=limit)
