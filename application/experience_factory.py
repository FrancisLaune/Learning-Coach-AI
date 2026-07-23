"""Composition root for the optional V2 presentation layer."""

from __future__ import annotations

from application.experience_controllers import ParentExperienceController, StudentExperienceController
from core.config import is_v2_session_execution_enabled
from infrastructure.repositories.experience import DuckDBExperienceReadModel
from infrastructure.repositories.learning_session import DuckDBLearningSessionRepository
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from infrastructure.repositories.session_integration import DuckDBSessionIntegrationGateway
from services.learning_session.experience import LearnerExperienceService
from services.learning_session.orchestration import LearningSessionService


def build_student_experience_controller() -> StudentExperienceController:
    read_model = DuckDBExperienceReadModel()
    sessions = None
    if is_v2_session_execution_enabled():
        repository = DuckDBLearningSessionRepository()
        sessions = LearningSessionService(DuckDBRecommendationRepository(), repository, repository)
    return StudentExperienceController(LearnerExperienceService(read_model), sessions)


def build_parent_experience_controller() -> ParentExperienceController:
    return ParentExperienceController(
        LearnerExperienceService(DuckDBExperienceReadModel()),
        DuckDBSessionIntegrationGateway(),
    )
