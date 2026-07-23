"""Autosave, pause/resume and deterministic recovery services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.learning_session.models import (
    LearningSession,
    SessionCheckpoint,
    SessionEvent,
    SessionStatus,
    StudentAnswer,
)
from domain.learning_session.repositories import AutoSaveRepository, LearningSessionRepository, SessionAuditRepository
from services.learning_session.models import RecoveryState


@dataclass(frozen=True, slots=True)
class RecoveryConfiguration:
    heartbeat_seconds: int = 15
    maximum_buffered_answers: int = 100


class OfflineBuffer:
    def __init__(self, maximum: int = 100) -> None:
        self.maximum = maximum
        self._answers: dict[str, StudentAnswer] = {}

    def put(self, answer: StudentAnswer) -> None:
        if answer.idempotency_key not in self._answers and len(self._answers) >= self.maximum:
            raise RuntimeError("Offline recovery buffer is full")
        self._answers[answer.idempotency_key] = answer

    def pending(self) -> tuple[StudentAnswer, ...]:
        return tuple(self._answers[key] for key in sorted(self._answers))

    def acknowledge(self, idempotency_key: str) -> None:
        self._answers.pop(idempotency_key, None)


class AutoSaveService:
    def __init__(
        self,
        repository: AutoSaveRepository,
        buffer: OfflineBuffer | None = None,
        configuration: RecoveryConfiguration | None = None,
    ) -> None:
        self.repository = repository
        self.configuration = configuration or RecoveryConfiguration()
        self.buffer = buffer or OfflineBuffer(self.configuration.maximum_buffered_answers)

    def save(
        self,
        session: LearningSession,
        answer: StudentAnswer,
        checkpoint: SessionCheckpoint,
        now: datetime,
    ) -> StudentAnswer:
        if session.status not in {SessionStatus.RUNNING, SessionStatus.PAUSED}:
            raise ValueError("Autosave requires an active or paused session")
        event = SessionEvent(0, session.session_id, "ANSWER_MODIFIED", now, {}, answer.idempotency_key)
        try:
            saved = self.repository.autosave(answer, checkpoint, event)
            self.buffer.acknowledge(answer.idempotency_key)
            return saved
        except Exception:
            self.buffer.put(answer)
            raise

    def synchronize(self, session: LearningSession, checkpoint: SessionCheckpoint, now: datetime) -> int:
        synchronized = 0
        for answer in self.buffer.pending():
            self.save(session, answer, checkpoint, now)
            synchronized += 1
        return synchronized


class ResumeService:
    def __init__(self, sessions: LearningSessionRepository, audit: SessionAuditRepository) -> None:
        self.sessions = sessions
        self.audit = audit

    def resume(self, learner_id: int, now: datetime) -> RecoveryState:
        session = self.sessions.find_resumable(learner_id)
        if session is None:
            raise KeyError("No resumable session")
        if session.learner_id != learner_id or session.status is not SessionStatus.PAUSED:
            raise PermissionError("Session ownership or status prevents resume")
        checkpoint = self.audit.latest_checkpoint(session.session_id)
        if checkpoint is None or checkpoint.autosave_timestamp > now:
            raise ValueError("Checkpoint integrity validation failed")
        self.sessions.transition(session.session_id, SessionStatus.PAUSED, SessionStatus.RUNNING, now)
        return RecoveryState(
            session.session_id,
            learner_id,
            checkpoint.activity_id,
            checkpoint.current_question_id,
            checkpoint.last_answer_id,
            checkpoint.remaining_time_seconds,
            now,
            checkpoint.checkpoint_id,
            True,
        )


class RecoveryService(ResumeService):
    pass
