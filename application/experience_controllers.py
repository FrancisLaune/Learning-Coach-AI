"""Presentation controllers: the only UI entry point to V2 services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar

from services.learning_session.experience import (
    LearnerExperienceService,
    SessionListItem,
    SessionScreen,
    SessionSummaryView,
    StudentDashboard,
)
from services.learning_session.orchestration import LearningSessionService
from services.unified_experience import HomeworkSessionService

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PresentationError:
    message: str
    recovery: str


class ParentAuthorization(Protocol):
    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool: ...


class StudentExperienceController:
    def __init__(
        self,
        experience: LearnerExperienceService,
        sessions: LearningSessionService | None = None,
        homework_sessions: HomeworkSessionService | None = None,
    ) -> None:
        self.experience = experience
        self.sessions = sessions
        self.homework_sessions = homework_sessions

    def dashboard(self, learner_id: int) -> StudentDashboard | PresentationError:
        return self._safe(lambda: self.experience.dashboard(learner_id))

    def session(self, learner_id: int, session_id: int) -> SessionScreen | PresentationError:
        return self._safe(lambda: self.experience.session_screen(learner_id, session_id))

    def summary(self, learner_id: int, session_id: int) -> SessionSummaryView | PresentationError:
        return self._safe(lambda: self.experience.session_summary(learner_id, session_id))

    def history(self, learner_id: int) -> tuple[SessionListItem, ...] | PresentationError:
        return self._safe(lambda: self.experience.history(learner_id))

    def start(self, session_id: int, now: datetime) -> PresentationError | None:
        return self._action("démarrer", lambda: self._sessions().start_session(session_id, now))

    def pause(self, session_id: int, now: datetime) -> PresentationError | None:
        return self._action("mettre en pause", lambda: self._sessions().pause_session(session_id, now))

    def resume(self, session_id: int, now: datetime) -> PresentationError | None:
        return self._action("reprendre", lambda: self._sessions().resume_session(session_id, now))

    def pause_for_learner(self, learner_id: int, session_id: int, now: datetime) -> PresentationError | None:
        if self.homework_sessions is not None:
            return self._action(
                "mettre en pause",
                lambda: self.homework_sessions.pause_for_learner_session(learner_id, session_id, now),
            )
        return self.pause(session_id, now)

    def resume_for_learner(self, learner_id: int, session_id: int, now: datetime) -> PresentationError | None:
        if self.homework_sessions is not None:
            return self._action(
                "reprendre",
                lambda: self.homework_sessions.resume_for_learner_session(learner_id, session_id, now),
            )
        return self.resume(session_id, now)

    def _sessions(self) -> LearningSessionService:
        if self.sessions is None:
            raise RuntimeError("Le contrôle des séances est indisponible.")
        return self.sessions

    @staticmethod
    def _safe(operation: Callable[[], T]) -> T | PresentationError:
        try:
            return operation()
        except Exception:
            return PresentationError(
                "Les informations ne sont pas disponibles pour le moment.",
                "Réessaie dans quelques instants ou reviens au tableau de bord.",
            )

    @staticmethod
    def _action(label: str, operation: Callable[[], object]) -> PresentationError | None:
        try:
            operation()
            return None
        except Exception as exc:
            return StudentExperienceController._presentation_error_from_exception(exc, label)

    @staticmethod
    def _presentation_error_from_exception(exc: Exception, label: str) -> PresentationError:
        if isinstance(exc, RuntimeError) and "contrôle des séances est indisponible" in str(exc):
            return PresentationError(
                "Le contrôle de séance n'est pas disponible.",
                "Réouvre l'application ou contacte un adulte référent si le problème continue.",
            )
        if isinstance(exc, PermissionError):
            return PresentationError(
                "Cette séance ne t'est pas accessible.",
                "Retourne au tableau de bord et sélectionne la séance ou le devoir en cours.",
            )
        message = str(exc)
        if "Cannot open file" in message or "used by another process" in message:
            return PresentationError(
                "L'application n'arrive pas à accéder à tes données pour le moment.",
                "Ta progression est déjà enregistrée. Attends quelques secondes, puis réessaie sans actualiser la page.",
            )
        if "Expected RUNNING" in message or "mise en pause depuis le statut" in message:
            return PresentationError(
                "Cette séance n'est pas en cours d'exécution.",
                "Utilise « Reprendre » si tu es en pause, ou retourne au tableau de bord pour relancer le devoir.",
            )
        if "Expected PAUSED" in message or "reprise depuis le statut" in message:
            return PresentationError(
                "Cette séance n'est pas en pause.",
                "Continue l'activité en cours ou retourne au tableau de bord.",
            )
        if "modifié dans une autre session" in message:
            return PresentationError(
                "Le devoir a été mis à jour depuis un autre écran.",
                "Retourne à la liste des devoirs pour reprendre au bon endroit.",
            )
        return PresentationError(
            f"Impossible de {label} cette séance.",
            "Ta progression est enregistrée. Réessaie dans quelques instants ou reviens au tableau de bord.",
        )


class ParentExperienceController:
    def __init__(
        self,
        experience: LearnerExperienceService,
        authorization: ParentAuthorization,
        learner_lister: Callable[[str], tuple[tuple[int, str], ...]] | None = None,
    ) -> None:
        self.experience = experience
        self.authorization = authorization
        self._learner_lister = learner_lister

    def learners(self, parent_ref: str) -> tuple[tuple[int, str], ...]:
        if self._learner_lister is not None:
            return self._learner_lister(parent_ref)
        return tuple(
            item for item in self.experience.learners() if self.authorization.parent_authorized(parent_ref, item[0])
        )

    def dashboard(self, parent_ref: str, learner_id: int) -> StudentDashboard | PresentationError:
        denied = self._denied(parent_ref, learner_id)
        if denied:
            return denied
        result = StudentExperienceController(self.experience).dashboard(learner_id)
        return result

    def history(self, parent_ref: str, learner_id: int) -> tuple[SessionListItem, ...] | PresentationError:
        denied = self._denied(parent_ref, learner_id)
        if denied:
            return denied
        try:
            return self.experience.history(learner_id)
        except Exception:
            return PresentationError("L'historique est indisponible.", "Réessaie dans quelques instants.")

    def _denied(self, parent_ref: str, learner_id: int) -> PresentationError | None:
        if self.authorization.parent_authorized(parent_ref, learner_id):
            return None
        return PresentationError(
            "Vous n'avez pas accès à cet apprenant.",
            "Sélectionnez un apprenant autorisé depuis votre tableau de bord.",
        )
