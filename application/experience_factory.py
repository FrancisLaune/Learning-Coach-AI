"""Composition root for the optional V2 presentation layer."""

from __future__ import annotations

from application.experience_controllers import ParentExperienceController, StudentExperienceController
from core.config import is_v2_session_execution_enabled
from infrastructure.repositories.experience import DuckDBExperienceReadModel
from infrastructure.repositories.learning import DuckDBLearningRepository
from infrastructure.repositories.learning_session import DuckDBLearningSessionRepository
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from infrastructure.repositories.session_integration import DuckDBSessionIntegrationGateway
from infrastructure.repositories.unified_session_execution import DuckDBUnifiedSessionExecutionRepository
from services.learning.learning_engine_service import LearningEngineService
from services.learning_session.experience import LearnerExperienceService
from services.learning_session.orchestration import ActivityRunner, LearningSessionService
from services.learning_session.submission import SubmissionService
from services.unified_session_execution import DecisionRefreshNotifier, UnifiedSessionExecutionService


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


def build_unified_session_execution_service() -> UnifiedSessionExecutionService:
    sessions = DuckDBLearningSessionRepository()
    execution = DuckDBUnifiedSessionExecutionRepository()
    session_service = LearningSessionService(DuckDBRecommendationRepository(), sessions, sessions)
    submission = SubmissionService(
        sessions,
        LearningEngineService(DuckDBLearningRepository()),
        DecisionRefreshNotifier(execution.enqueue_refresh),
    )
    return UnifiedSessionExecutionService(execution, submission, session_service, ActivityRunner(sessions))
