"""Grade/subject eligibility for generalized homework AI completion (LCAI-0018B6)."""

from __future__ import annotations

from domain.unified_experience.models import HomeworkRequest
from services.homework.config import HomeworkAiCompletionSettings
from services.platform_runtime import FeatureFlagService


class HomeworkCompletionRepository:
    def is_four_e_grade(self, grade_level_id: int | None) -> bool: ...

    def grade_code(self, grade_level_id: int | None) -> str | None: ...

    def subject_code(self, subject_id: int) -> str | None: ...


def completion_flags_enabled(flags: FeatureFlagService) -> bool:
    return flags.enabled("homework_ai_completion") or flags.enabled("homework_ai_fallback_4e")


def is_homework_ai_completion_eligible(
    request: HomeworkRequest,
    repository: HomeworkCompletionRepository,
    *,
    flags: FeatureFlagService,
    settings: HomeworkAiCompletionSettings,
    orchestrator_configured: bool,
) -> bool:
    if not orchestrator_configured:
        return False
    if not completion_flags_enabled(flags):
        return False
    if flags.enabled("homework_ai_completion"):
        grade_code = repository.grade_code(request.grade_level_id)
        subject_code = repository.subject_code(request.subject_id)
        return settings.grade_allowed(grade_code) and settings.subject_allowed(subject_code)
    if flags.enabled("homework_ai_fallback_4e"):
        return repository.is_four_e_grade(request.grade_level_id)
    return False
