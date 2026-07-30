"""Presentation controllers for LCAI-0019 pedagogical intelligence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from application.dto.pedagogical_intelligence import (
    DiagnosticAnswerResultDTO,
    DiagnosticRunDTO,
    PedagogicalDashboardDTO,
)
from application.experience_controllers import PresentationError
from domain.pedagogical_intelligence.models import PedagogicalIntelligenceOverview, ReadinessPathCode
from services.pedagogical_intelligence.platform_service import PedagogicalIntelligenceService

T = TypeVar("T")


class ParentAuthorization(Protocol):
    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool: ...


class PedagogicalIntelligenceController:
    def __init__(
        self,
        service: PedagogicalIntelligenceService,
        authorization: ParentAuthorization | None = None,
    ) -> None:
        self.service = service
        self.authorization = authorization

    def student_overview(self, learner_id: int) -> PedagogicalIntelligenceOverview | PresentationError:
        return self._safe(lambda: self.service.overview(learner_id))

    def parent_overview(self, parent_ref: str, learner_id: int) -> PedagogicalIntelligenceOverview | PresentationError:
        if self.authorization is not None and not self.authorization.parent_authorized(parent_ref, learner_id):
            return PresentationError(
                "Accès refusé à cette fiche élève.",
                "Vérifie le lien parent-enfant ou contacte le support.",
            )
        return self._safe(lambda: self.service.overview(learner_id))

    def student_dashboard(
        self,
        learner_id: int,
        *,
        cache_version: str | None = None,
    ) -> PedagogicalDashboardDTO | PresentationError:
        return self._safe(lambda: self.service.dashboard(learner_id, cache_version=cache_version))

    def parent_dashboard(
        self,
        parent_ref: str,
        learner_id: int,
        *,
        cache_version: str | None = None,
    ) -> PedagogicalDashboardDTO | PresentationError:
        if self.authorization is not None and not self.authorization.parent_authorized(parent_ref, learner_id):
            return PresentationError(
                "Accès refusé à cette fiche élève.",
                "Vérifie le lien parent-enfant ou contacte le support.",
            )
        return self._safe(lambda: self.service.dashboard(learner_id, cache_version=cache_version))

    def start_diagnostic(self, learner_id: int, path_code: ReadinessPathCode) -> DiagnosticRunDTO | PresentationError:
        return self._safe(lambda: self.service.start_diagnostic(learner_id, path_code))

    def submit_diagnostic_answer(
        self,
        *,
        run_id: int,
        learner_id: int,
        exercise_id: int,
        answer: object,
        elapsed_ms: int = 0,
    ) -> DiagnosticAnswerResultDTO | PresentationError:
        return self._safe(
            lambda: self.service.submit_diagnostic_answer(
                run_id=run_id,
                learner_id=learner_id,
                exercise_id=exercise_id,
                answer=answer,
                elapsed_ms=elapsed_ms,
            )
        )

    @staticmethod
    def _safe(operation: Callable[[], T]) -> T | PresentationError:
        try:
            return operation()
        except Exception:
            return PresentationError(
                "Les informations pédagogiques ne sont pas disponibles pour le moment.",
                "Réessaie dans quelques instants ou reviens au tableau de bord.",
            )
