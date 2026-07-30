"""Composition root for the optional V2 presentation layer."""

from __future__ import annotations

from application.experience_controllers import ParentExperienceController, StudentExperienceController
from core.config import is_v2_ui_enabled
from infrastructure.repositories.experience import DuckDBExperienceReadModel
from infrastructure.repositories.learning import DuckDBLearningRepository
from infrastructure.repositories.learning_session import DuckDBLearningSessionRepository
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from infrastructure.repositories.session_integration import DuckDBSessionIntegrationGateway
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from infrastructure.repositories.unified_session_execution import DuckDBUnifiedSessionExecutionRepository
from services.learning.learning_engine_service import LearningEngineService
from services.learning_session.experience import LearnerExperienceService
from services.learning_session.orchestration import ActivityRunner, LearningSessionService
from services.learning_session.submission import SubmissionService
from services.unified_experience import HomeworkSessionService
from services.unified_session_execution import UnifiedSessionExecutionService


def _learning_session_service() -> LearningSessionService:
    repository = DuckDBLearningSessionRepository()
    return LearningSessionService(DuckDBRecommendationRepository(), repository, repository)


def build_homework_session_service() -> HomeworkSessionService:
    return HomeworkSessionService(DuckDBUnifiedExperienceRepository(), _learning_session_service())


def build_pedagogical_intelligence_controller() -> "PedagogicalIntelligenceController":
    from application.pedagogical_intelligence_controllers import PedagogicalIntelligenceController
    from infrastructure.repositories.learning_intelligence import DuckDBLearningEvidenceRepository
    from infrastructure.repositories.pedagogical_intelligence import DuckDBPedagogicalIntelligenceRepository
    from infrastructure.repositories.session_integration import DuckDBSessionIntegrationGateway
    from services.learning.learning_engine_service import LearningEngineService
    from services.learning_intelligence import LearningIntelligenceService
    from services.pedagogical_intelligence.adaptive_diagnostic_service import AdaptiveDiagnosticService
    from services.pedagogical_intelligence.dashboard_service import PedagogicalDashboardService
    from services.pedagogical_intelligence.platform_service import PedagogicalIntelligenceService
    from services.pedagogical_intelligence.post_session_refresh import PostSessionPedagogicalRefreshService

    repository = DuckDBPedagogicalIntelligenceRepository()
    learning_engine = LearningEngineService(DuckDBLearningRepository())
    diagnostic = AdaptiveDiagnosticService(repository, learning_engine)
    intelligence = LearningIntelligenceService(DuckDBLearningEvidenceRepository())
    dashboard = PedagogicalDashboardService(repository, intelligence)
    refresh = PostSessionPedagogicalRefreshService(repository, dashboard)
    service = PedagogicalIntelligenceService(repository, diagnostic, dashboard, refresh)
    return PedagogicalIntelligenceController(service, DuckDBSessionIntegrationGateway())


def build_pedagogical_refresh_callback():
    controller = build_pedagogical_intelligence_controller()
    service = controller.service

    def _refresh(*, learner_id: int, session_id: int, correlation_id: str | None = None) -> None:
        service.refresh_after_session(learner_id=learner_id, session_id=session_id, correlation_id=correlation_id)

    return _refresh


def build_student_experience_controller() -> StudentExperienceController:
    read_model = DuckDBExperienceReadModel()
    sessions = None
    homework_sessions = None
    if is_v2_ui_enabled():
        sessions = _learning_session_service()
        homework_sessions = HomeworkSessionService(DuckDBUnifiedExperienceRepository(), sessions)
    return StudentExperienceController(LearnerExperienceService(read_model), sessions, homework_sessions)


def build_parent_experience_controller() -> ParentExperienceController:
    repository = DuckDBUnifiedExperienceRepository()
    return ParentExperienceController(
        LearnerExperienceService(DuckDBExperienceReadModel()),
        DuckDBSessionIntegrationGateway(),
        learner_lister=lambda parent_ref: repository.list_linked_learners(parent_ref, archived=False),
    )


def build_student_guidance_service() -> "StudentGuidanceService":
    from services.homework.factory import build_homework_service
    from services.pedagogical_intelligence.dashboard_service import PedagogicalDashboardService
    from services.student_guidance.service import StudentGuidanceService
    from infrastructure.repositories.learning_intelligence import DuckDBLearningEvidenceRepository
    from infrastructure.repositories.pedagogical_intelligence import DuckDBPedagogicalIntelligenceRepository
    from services.learning_intelligence import LearningIntelligenceService

    repository = DuckDBPedagogicalIntelligenceRepository()
    intelligence = LearningIntelligenceService(DuckDBLearningEvidenceRepository())
    return StudentGuidanceService(
        experience=LearnerExperienceService(DuckDBExperienceReadModel()),
        homework=build_homework_service(),
        pi_dashboard=PedagogicalDashboardService(repository, intelligence),
    )


def build_unified_session_execution_service() -> UnifiedSessionExecutionService:
    from services.pedagogical_intelligence.session_notifier import CompositePedagogicalNotifier

    sessions = DuckDBLearningSessionRepository()
    execution = DuckDBUnifiedSessionExecutionRepository()
    session_service = _learning_session_service()
    pi_refresh = build_pedagogical_refresh_callback()
    submission = SubmissionService(
        sessions,
        LearningEngineService(DuckDBLearningRepository()),
        CompositePedagogicalNotifier(execution.enqueue_refresh, pi_refresh),
    )
    return UnifiedSessionExecutionService(execution, submission, session_service, ActivityRunner(sessions))
