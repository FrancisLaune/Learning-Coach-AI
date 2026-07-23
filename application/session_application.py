"""Cross-context façade coordinating validated Part 03 session services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from domain.learning_session.errors import SessionApplicationError, SessionErrorCode
from domain.learning_session.models import HintUsage, LearningSession, SessionStatus
from services.learning_session.experience import (
    LearnerExperienceService,
    SessionScreen,
    SessionSummaryView,
)
from services.learning_session.models import (
    AssessmentRequest,
    RecoveryState,
    SubmissionContext,
)
from services.learning_session.orchestration import ActivityRunner, LearningSessionService
from services.learning_session.recovery import ResumeService
from services.learning_session.submission import SubmissionService


class ActorRole(StrEnum):
    STUDENT = "student"
    PARENT = "parent"
    ADMINISTRATOR = "administrator"


@dataclass(frozen=True, slots=True)
class Actor:
    actor_ref: str
    role: ActorRole
    learner_id: int | None = None


@dataclass(frozen=True, slots=True)
class SessionCommand:
    actor: Actor
    learner_id: int
    idempotency_key: str
    correlation_id: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class CreateSessionCommand(SessionCommand):
    recommendation_id: int
    expected_recommendation_version: str | None = None


@dataclass(frozen=True, slots=True)
class SessionTargetCommand(SessionCommand):
    session_id: int


@dataclass(frozen=True, slots=True)
class SubmitAnswerCommand(SessionTargetCommand):
    submission: SubmissionContext
    assessment: AssessmentRequest


@dataclass(frozen=True, slots=True)
class OpenHintCommand(SessionTargetCommand):
    activity_id: int
    question_id: int
    hint_id: int
    hint_number: int
    penalty: float


class SessionIntegrationGateway(Protocol):
    def learner_is_active(self, learner_id: int) -> bool: ...

    def recommendation_owner_and_version(self, recommendation_id: int) -> tuple[int, str] | None: ...

    def active_session(self, learner_id: int) -> LearningSession | None: ...

    def session_owner(self, session_id: int) -> int | None: ...

    def activity_belongs(self, session_id: int, activity_id: int) -> bool: ...

    def question_belongs(self, activity_id: int, question_id: int) -> bool: ...

    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool: ...

    def freeze_session_versions(self, session_id: int) -> None: ...

    def command_result(self, idempotency_key: str, command_type: str) -> dict[str, Any] | None: ...

    def save_command_result(
        self,
        command: SessionCommand,
        command_type: str,
        session_id: int | None,
        payload: dict[str, Any],
    ) -> None: ...


class SessionApplicationService:
    """Use-case façade; validated Part 03 services retain their behavior."""

    def __init__(
        self,
        gateway: SessionIntegrationGateway,
        sessions: LearningSessionService,
        runner: ActivityRunner,
        recovery: ResumeService,
        submission: SubmissionService,
        experience: LearnerExperienceService,
        hint_repository: Any,
    ) -> None:
        self.gateway = gateway
        self.sessions = sessions
        self.runner = runner
        self.recovery = recovery
        self.submission = submission
        self.experience = experience
        self.hint_repository = hint_repository

    def create_session_from_recommendation(self, command: CreateSessionCommand) -> LearningSession:
        cached = self._cached(command, "CREATE_SESSION")
        if cached:
            return self._required_session(int(cached["session_id"]))
        self._authorize(command.actor, command.learner_id, mutate=True)
        if not self.gateway.learner_is_active(command.learner_id):
            raise self._error(command, SessionErrorCode.SESSION_ACCESS_DENIED, "Ce profil apprenant est inactif.")
        recommendation = self.gateway.recommendation_owner_and_version(command.recommendation_id)
        if recommendation is None or recommendation[0] != command.learner_id:
            raise self._error(command, SessionErrorCode.SESSION_ACCESS_DENIED, "Cette recommandation est inaccessible.")
        if command.expected_recommendation_version and recommendation[1] != command.expected_recommendation_version:
            raise self._error(command, SessionErrorCode.STATE_CONFLICT, "La recommandation a été actualisée.")
        active = self.gateway.active_session(command.learner_id)
        if active:
            raise self._error(
                command,
                SessionErrorCode.ACTIVE_SESSION_EXISTS,
                f"Une séance {active.status.value.lower()} existe déjà.",
            )
        created = self.sessions.create_session(command.recommendation_id, command.occurred_at)
        self.gateway.freeze_session_versions(created.session_id)
        self.gateway.save_command_result(
            command, "CREATE_SESSION", created.session_id, {"session_id": created.session_id}
        )
        return created

    def start_session(self, command: SessionTargetCommand) -> LearningSession:
        return self._transition(command, "START_SESSION", self.sessions.start_session)

    def pause_session(self, command: SessionTargetCommand) -> LearningSession:
        return self._transition(command, "PAUSE_SESSION", self.sessions.pause_session)

    def resume_session(self, command: SessionTargetCommand) -> LearningSession:
        return self._transition(command, "RESUME_SESSION", self.sessions.resume_session)

    def abandon_session(self, command: SessionTargetCommand) -> LearningSession:
        return self._transition(command, "ABANDON_SESSION", self.sessions.cancel_session)

    def get_active_session(self, actor: Actor, learner_id: int) -> LearningSession | None:
        self._authorize(actor, learner_id, mutate=False)
        return self.gateway.active_session(learner_id)

    def get_session_state(self, actor: Actor, learner_id: int, session_id: int) -> SessionScreen:
        self._authorize(actor, learner_id, mutate=False)
        self._authorize_session(learner_id, session_id, "query")
        return self.experience.session_screen(learner_id, session_id)

    def get_session_summary(self, actor: Actor, learner_id: int, session_id: int) -> SessionSummaryView:
        self._authorize(actor, learner_id, mutate=False)
        self._authorize_session(learner_id, session_id, "summary")
        return self.experience.session_summary(learner_id, session_id)

    def submit_answer(self, command: SubmitAnswerCommand) -> tuple[Any, ...]:
        cached = self._cached(command, "SUBMIT_ANSWER")
        if cached:
            raise self._error(
                command,
                SessionErrorCode.ANSWER_ALREADY_SUBMITTED,
                "Cette réponse a déjà été enregistrée.",
            )
        self._authorize(command.actor, command.learner_id, mutate=True)
        session = self._authorize_session(command.learner_id, command.session_id, "submission")
        if session.status is not SessionStatus.RUNNING:
            raise self._error(command, SessionErrorCode.INVALID_SESSION_STATE, "La séance n'est pas active.")
        if not self.gateway.activity_belongs(command.session_id, command.submission.activity_id):
            raise self._error(command, SessionErrorCode.INVALID_ACTIVITY_STATE, "Cette activité est inaccessible.")
        if not self.gateway.question_belongs(command.submission.activity_id, command.submission.question_id):
            raise self._error(command, SessionErrorCode.QUESTION_UNAVAILABLE, "Cette question est inaccessible.")
        result = self.submission.submit(command.submission, command.assessment)
        self.gateway.save_command_result(
            command,
            "SUBMIT_ANSWER",
            command.session_id,
            {"attempt_id": result[0].attempt_id, "score": result[1].final_score},
        )
        return result

    def request_hint(self, command: OpenHintCommand) -> HintUsage:
        cached = self._cached(command, "OPEN_HINT")
        if cached:
            return HintUsage(
                int(cached["hint_usage_id"]),
                command.activity_id,
                command.hint_id,
                command.hint_number,
                command.occurred_at,
                command.penalty,
            )
        self._authorize(command.actor, command.learner_id, mutate=True)
        self._authorize_session(command.learner_id, command.session_id, "hint")
        if not self.gateway.activity_belongs(command.session_id, command.activity_id):
            raise self._error(command, SessionErrorCode.INVALID_ACTIVITY_STATE, "Cette activité est inaccessible.")
        if not self.gateway.question_belongs(command.activity_id, command.question_id):
            raise self._error(command, SessionErrorCode.QUESTION_UNAVAILABLE, "Cette question est inaccessible.")
        usage = self.hint_repository.save_hint(
            HintUsage(
                0, command.activity_id, command.hint_id, command.hint_number, command.occurred_at, command.penalty
            )
        )
        self.gateway.save_command_result(
            command,
            "OPEN_HINT",
            command.session_id,
            {"hint_usage_id": usage.hint_usage_id},
        )
        return usage

    def complete_activity(
        self,
        command: SessionTargetCommand,
        activity_id: int,
        score: float,
        mastery_delta: float,
    ) -> Any:
        self._authorize(command.actor, command.learner_id, mutate=True)
        session = self._authorize_session(command.learner_id, command.session_id, "activity completion")
        return self.runner.complete(session, activity_id, score, mastery_delta)

    def complete_session(self, command: SessionTargetCommand) -> Any:
        cached = self._cached(command, "COMPLETE_SESSION")
        if cached:
            return self.experience.session_summary(command.learner_id, command.session_id)
        self._authorize(command.actor, command.learner_id, mutate=True)
        self._authorize_session(command.learner_id, command.session_id, "completion")
        result = self.sessions.close_session(command.session_id, command.occurred_at)
        self.gateway.save_command_result(
            command, "COMPLETE_SESSION", command.session_id, {"summary_id": result.summary_id}
        )
        return result

    def recover_session(self, command: SessionTargetCommand) -> RecoveryState:
        self._authorize(command.actor, command.learner_id, mutate=True)
        self._authorize_session(command.learner_id, command.session_id, "recovery")
        return self.recovery.resume(command.learner_id, command.occurred_at)

    def _transition(
        self,
        command: SessionTargetCommand,
        command_type: str,
        operation: Any,
    ) -> LearningSession:
        cached = self._cached(command, command_type)
        if cached:
            return self._required_session(command.session_id)
        self._authorize(command.actor, command.learner_id, mutate=True)
        self._authorize_session(command.learner_id, command.session_id, command_type)
        result = operation(command.session_id, command.occurred_at)
        self.gateway.save_command_result(command, command_type, command.session_id, {"status": result.status.value})
        return result

    def _authorize(self, actor: Actor, learner_id: int, *, mutate: bool) -> None:
        if actor.role is ActorRole.STUDENT and actor.learner_id == learner_id:
            return
        if (
            not mutate
            and actor.role is ActorRole.PARENT
            and self.gateway.parent_authorized(actor.actor_ref, learner_id)
        ):
            return
        if actor.role is ActorRole.ADMINISTRATOR:
            return
        code = (
            SessionErrorCode.PARENT_ACCESS_DENIED
            if actor.role is ActorRole.PARENT
            else SessionErrorCode.SESSION_ACCESS_DENIED
        )
        raise SessionApplicationError(
            code,
            "Vous n'avez pas accès à ces informations.",
            "Actor-to-learner authorization rejected",
            False,
            False,
            "authorization",
            "Revenez à votre tableau de bord.",
        )

    def _authorize_session(self, learner_id: int, session_id: int, operation: str) -> LearningSession:
        if self.gateway.session_owner(session_id) != learner_id:
            raise SessionApplicationError(
                SessionErrorCode.SESSION_ACCESS_DENIED,
                "Cette séance n'est pas accessible.",
                f"Ownership rejected during {operation}",
                False,
                False,
                operation,
                "Revenez à votre tableau de bord.",
            )
        return self._required_session(session_id)

    def _required_session(self, session_id: int) -> LearningSession:
        session = self.sessions.repository.get(session_id)
        if session is None:
            raise KeyError(f"Unknown session {session_id}")
        return session

    def _cached(self, command: SessionCommand, command_type: str) -> dict[str, Any] | None:
        return self.gateway.command_result(command.idempotency_key, command_type)

    @staticmethod
    def _error(
        command: SessionCommand,
        code: SessionErrorCode,
        message: str,
    ) -> SessionApplicationError:
        return SessionApplicationError(
            code,
            message,
            f"{code.value} for learner {command.learner_id}",
            code in {SessionErrorCode.STATE_CONFLICT, SessionErrorCode.ACTIVE_SESSION_EXISTS},
            code is SessionErrorCode.STATE_CONFLICT,
            command.correlation_id,
            "Actualisez les informations puis réessayez.",
        )
