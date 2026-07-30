"""Build HomeworkService with optional OpenAI runtime fallback (LCAI-0018B)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from services.platform_runtime import FeatureFlagService, default_flags
from services.unified_experience import HomeworkService

if TYPE_CHECKING:
    from services.homework.ai_fallback import HomeworkAiFallbackOrchestrator

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

    if flags.enabled("homework_ai_completion") or flags.enabled("homework_ai_fallback_4e"):
        try:
            from infrastructure.config.openai_settings import (
                OpenAIConfigurationError,
                configure_openai_environment,
                load_openai_model,
            )
            from infrastructure.generators.openai_content import OpenAIContentGenerator
            from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
            from services.content.factory import CandidateValidator, ContentFactoryService
            from services.homework.completion import HomeworkContentCompletionService

            configure_openai_environment()
            factory_repo = DuckDBContentFactoryRepository(repo.database_path)
            generator = OpenAIContentGenerator(
                factory_repo,
                model=load_openai_model(),
                candidate_prefix="RUNTIME-0018B6-AI",
                specification_version="lcai-0018b6-runtime-completion-v1",
                template_version="lcai-0018b6-runtime-completion-v1",
                metadata={
                    "origin_ticket": "LCAI-0018B6",
                    "validation_status": "runtime_only",
                    "publication_status": "RUNTIME_ONLY",
                },
            )
            factory = ContentFactoryService(generator, factory_repo, CandidateValidator())
            ai_fallback = HomeworkContentCompletionService(repo, content_factory=factory)
            LOGGER.info("Homework AI completion enabled (OpenAI via secrets.toml or OPENAI_API_KEY)")
        except ImportError as exc:
            LOGGER.warning(
                "homework AI completion is enabled but optional dependencies are missing (%s). "
                "Install requirements.txt (pydantic, openai).",
                exc,
            )
        except OpenAIConfigurationError:
            LOGGER.warning(
                "homework AI completion is enabled but OpenAI is not configured "
                "(set OPENAI_API_KEY or .streamlit/secrets.toml)"
            )
        except Exception:
            LOGGER.exception("Failed to initialize homework AI completion")

    return HomeworkService(repo, feature_flags=flags, ai_fallback=ai_fallback)
