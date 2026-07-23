"""Persistence ports for the Learning Session bounded context."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from domain.learning_session.models import (
    Assessment,
    Attempt,
    HintUsage,
    LearningSession,
    SessionActivity,
    SessionCheckpoint,
    SessionEvent,
    SessionStatus,
    SessionSummary,
    StudentAnswer,
)


class LearningSessionRepository(Protocol):
    def create(self, session: LearningSession) -> LearningSession: ...
    def get(self, session_id: int) -> LearningSession | None: ...
    def transition(self, session_id: int, expected: SessionStatus, target: SessionStatus, at: datetime) -> None: ...
    def add_activity(self, activity: SessionActivity) -> SessionActivity: ...
    def list_activities(self, session_id: int) -> tuple[SessionActivity, ...]: ...
    def update_activity(self, activity: SessionActivity) -> None: ...
    def find_resumable(self, learner_id: int) -> LearningSession | None: ...


class AnswerRepository(Protocol):
    def save(self, answer: StudentAnswer) -> StudentAnswer: ...


class AssessmentRepository(Protocol):
    def save_cycle(
        self,
        answer: StudentAnswer,
        assessment: Assessment,
        attempt: Attempt,
        mastery_payload: dict[str, object],
    ) -> Attempt: ...


class AttemptRepository(AssessmentRepository, Protocol): ...


class HintRepository(Protocol):
    def save_hint(self, usage: HintUsage) -> HintUsage: ...


class SessionAuditRepository(Protocol):
    def save_event(self, event: SessionEvent) -> SessionEvent: ...
    def save_checkpoint(self, checkpoint: SessionCheckpoint) -> SessionCheckpoint: ...
    def save_summary(self, summary: SessionSummary) -> SessionSummary: ...
    def latest_checkpoint(self, session_id: int) -> SessionCheckpoint | None: ...


class AutoSaveRepository(Protocol):
    def autosave(self, answer: StudentAnswer, checkpoint: SessionCheckpoint, event: SessionEvent) -> StudentAnswer: ...
