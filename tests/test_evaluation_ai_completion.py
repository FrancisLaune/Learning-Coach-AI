"""AI completion must fill thin catalogs for homework and evaluations."""

from __future__ import annotations

from services.homework.config import HomeworkAiFallbackSettings
from services.homework.evaluation_sizing import (
    EVALUATION_DEFAULT_QUESTIONS,
    EVALUATION_MIN_QUESTIONS,
    target_evaluation_question_count,
)


def test_target_evaluation_question_count_is_at_least_10() -> None:
    count = target_evaluation_question_count(preferred=EVALUATION_DEFAULT_QUESTIONS, max_minutes=1)
    assert count == EVALUATION_MIN_QUESTIONS
    assert target_evaluation_question_count(preferred=5) == EVALUATION_MIN_QUESTIONS
    assert target_evaluation_question_count(preferred=25) == 25


def test_ai_generation_cap_allows_homework_presets() -> None:
    settings = HomeworkAiFallbackSettings(max_generated_per_request=40, allow_degraded_result=False)
    assert settings.generation_cap(10) == 10
    assert settings.generation_cap(40) == 40
    assert settings.generation_cap(41) == 0


def test_evaluation_ai_sizing_desires_min_10_when_catalog_thin() -> None:
    from unittest.mock import MagicMock

    from domain.unified_experience.models import (
        ASSIGNMENT_KIND_EVALUATION,
        AssignmentType,
        DifficultyMode,
        HomeworkGenerationResult,
        HomeworkRequest,
    )
    from services.platform_runtime import FeatureFlagDefinition, FeatureFlagService
    from services.unified_experience import HomeworkService

    request = HomeworkRequest(
        1,
        "STUDENT",
        "learner:1",
        AssignmentType.GLOBAL_SUBJECT,
        3,
        4,
        (),
        (),
        DifficultyMode.ADAPTIVE,
        40,
        45,
        None,
        "AFTER_SUBMISSION",
        ASSIGNMENT_KIND_EVALUATION,
    )
    repo = MagicMock()
    repo.list_catalog_rows_for_selection.return_value = [
        (101, 1, 1, 2, "exercise", 5),
        (102, 1, 1, 3, "exercise", 5),
    ]
    repo.grade_code.return_value = "FR-4E"
    repo.subject_code.return_value = "MATH"
    captured: dict[str, HomeworkRequest] = {}

    class _Fallback:
        def generate(self, sized: HomeworkRequest, *, correlation_id: str | None = None):
            captured["request"] = sized
            homework = MagicMock()
            homework.selected_content_ids = (101, 102)
            homework.exercise_count = sized.exercise_count
            homework.target_duration_minutes = sized.target_duration_minutes
            return HomeworkGenerationResult(
                homework,
                sized.exercise_count,
                2,
                sized.exercise_count - 2,
                sized.exercise_count - 2,
                sized.exercise_count,
                False,
                None,
                "corr",
            )

    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True, ()),
            FeatureFlagDefinition("homework_ai_completion", True, ("v2.enabled",)),
        )
    )
    service = HomeworkService(repo, feature_flags=flags, ai_fallback=_Fallback())
    result = service.create_with_diagnostics(request)
    assert captured["request"].exercise_count == EVALUATION_MIN_QUESTIONS
    assert captured["request"].target_duration_minutes is None
    assert captured["request"].is_evaluation is True
    assert result.ai_accepted_count == captured["request"].exercise_count - 2
