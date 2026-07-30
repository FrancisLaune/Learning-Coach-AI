"""LCAI-0018B6 — generalized homework AI completion tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from domain.platform_runtime.models import FeatureFlagDefinition
from domain.unified_experience.models import AssignmentType, DifficultyMode, HomeworkRequest
from services.homework.config import HomeworkAiCompletionSettings
from services.homework.eligibility import completion_flags_enabled, is_homework_ai_completion_eligible
from services.platform_runtime import FeatureFlagService


def _request(*, grade_id: int = 11, subject_id: int = 1) -> HomeworkRequest:
    return HomeworkRequest(
        1,
        "PARENT",
        "parent:1",
        AssignmentType.TARGETED,
        subject_id,
        grade_id,
        (1,),
        (),
        DifficultyMode.MEDIUM,
        6,
        30,
        None,
    )


def test_completion_flag_generalizes_beyond_4e_legacy_flag() -> None:
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_completion", True, ("v2.enabled",)),
        )
    )
    assert completion_flags_enabled(flags)


def test_legacy_4e_flag_still_enables_completion() -> None:
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_fallback_4e", True, ("v2.enabled",)),
        )
    )
    repo = MagicMock()
    repo.is_four_e_grade.return_value = True
    settings = HomeworkAiCompletionSettings.from_environment()
    assert is_homework_ai_completion_eligible(
        _request(),
        repo,
        flags=flags,
        settings=settings,
        orchestrator_configured=True,
    )


def test_generalized_completion_accepts_configured_grades() -> None:
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_completion", True, ("v2.enabled",)),
        )
    )
    repo = MagicMock()
    repo.grade_code.return_value = "FR-5E"
    repo.subject_code.return_value = "SPANISH"
    settings = HomeworkAiCompletionSettings(
        allowed_grades=frozenset({"FR-5E"}),
        allowed_subjects=None,
    )
    assert is_homework_ai_completion_eligible(
        _request(grade_id=18),
        repo,
        flags=flags,
        settings=settings,
        orchestrator_configured=True,
    )


def test_completion_rejects_unconfigured_grade() -> None:
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_completion", True, ("v2.enabled",)),
        )
    )
    repo = MagicMock()
    repo.grade_code.return_value = "FR-2NDE"
    repo.subject_code.return_value = "MATH"
    settings = HomeworkAiCompletionSettings(
        allowed_grades=frozenset({"FR-4E"}),
        allowed_subjects=None,
    )
    assert not is_homework_ai_completion_eligible(
        _request(),
        repo,
        flags=flags,
        settings=settings,
        orchestrator_configured=True,
    )


def test_grade_alias_parsing_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMEWORK_AI_COMPLETION_GRADES", "4E,5E")
    settings = HomeworkAiCompletionSettings.from_environment()
    assert "FR-4E" in settings.allowed_grades
    assert "FR-5E" in settings.allowed_grades
