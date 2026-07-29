"""Build HomeworkService with optional OpenAI runtime fallback (LCAI-0018B)."""

from __future__ import annotations

import logging

from infrastructure.config.openai_settings import OpenAIConfigurationError, configure_openai_environment, load_openai_model
from infrastructure.generators.openai_content import OpenAIContentGenerator
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from services.content.factory import CandidateValidator, ContentFactoryService
from services.homework.ai_fallback import HomeworkAiFallbackOrchestrator
from services.platform_runtime import FeatureFlagService, default_flags
from services.unified_experience import HomeworkService

LOGGER = logging.getLogger(__name__)


def build_homework_service(
    repository: DuckDBUnifiedExperienceRepository | None = None,
    *,
    feature_flags: FeatureFlagService | None = None,
) -> HomeworkService:
    """Wire HomeworkService for Streamlit/runtime using `.streamlit/secrets.toml` when enabled."""
    repo = repository or DuckDBUnifiedExperienceRepository()
    flags = feature_flags or default_flags()
    ai_fallback: HomeworkAiFallbackOrchestrator | None = None

    if flags.enabled("homework_ai_fallback_4e"):
        try:
            configure_openai_environment()
            factory_repo = DuckDBContentFactoryRepository(repo.database_path)
            generator = OpenAIContentGenerator(
                factory_repo,
                model=load_openai_model(),
                candidate_prefix="RUNTIME-0018B-AI",
                specification_version="lcai-0018b-runtime-fallback-v1",
                template_version="lcai-0018b-runtime-fallback-v1",
                metadata={
                    "origin_ticket": "LCAI-0018B",
                    "validation_status": "runtime_only",
                    "publication_status": "RUNTIME_ONLY",
                },
            )
            factory = ContentFactoryService(generator, factory_repo, CandidateValidator())
            ai_fallback = HomeworkAiFallbackOrchestrator(repo, content_factory=factory)
            LOGGER.info("Homework AI fallback enabled for 4e (OpenAI via secrets.toml or OPENAI_API_KEY)")
        except OpenAIConfigurationError:
            LOGGER.warning(
                "homework_ai_fallback_4e is enabled but OpenAI is not configured "
                "(set OPENAI_API_KEY or .streamlit/secrets.toml)"
            )
        except Exception:
            LOGGER.exception("Failed to initialize homework AI fallback")

    return HomeworkService(repo, feature_flags=flags, ai_fallback=ai_fallback)
