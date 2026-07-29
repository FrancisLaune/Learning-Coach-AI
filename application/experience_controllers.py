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
    ) -> None:
        self.experience = experience
        self.sessions = sessions

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
        except Exception:
            return PresentationError(
                f"Impossible de {label} cette séance.",
                "La séance a été conservée. Actualise la page puis réessaie.",
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
