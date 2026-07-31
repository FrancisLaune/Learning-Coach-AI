"""LCAI-0022A — Professor AI Core orchestrator unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from application.dto.student_guidance import (
    AIAvailability,
    AIAvailabilityMode,
    GuidanceSource,
    StudentDashboardSnapshot,
    StudentHomeContext,
    WelcomeGuidance,
)
from domain.unified_experience.models import (
    AssignmentStatus,
    AssignmentType,
    DifficultyMode,
    HomeworkAssignment,
    HomeworkGenerationResult,
    HomeworkRequest,
)
from services.professor_ai.models import ProfessorOperatingMode
from services.professor_ai.orchestrator import ProfessorAIOrchestrator

NOW = datetime(2026, 7, 31, 16, 0, tzinfo=UTC)


def _welcome() -> WelcomeGuidance:
    return WelcomeGuidance(
        source=GuidanceSource.DETERMINISTIC,
        greeting="Bonjour Noa",
        primary_action="Commencer la séance",
        mission_label="Consolider les fractions",
    )


def _dashboard() -> StudentDashboardSnapshot:
    context = StudentHomeContext(
        learner_id=7,
        display_name="Noa",
        homework_todo=(),
        homework_overdue=(),
        homework_recent=(),
        mastery=(),
        fragile_skills=(),
        strong_skills=(),
        revision_priorities=(),
        recent_score=None,
        success_rate=None,
        objective="Progresser en maths",
        next_revision=None,
    )
    return StudentDashboardSnapshot(
        context=context,
        welcome=_welcome(),
        availability=AIAvailability(
            mode=AIAvailabilityMode.ACTIVE,
            platform_enabled=True,
            learner_feature_enabled=True,
            provider_configured=True,
            reason="",
        ),
    )


def _homework(homework_id: int = 11, session_id: int | None = None) -> HomeworkAssignment:
    return HomeworkAssignment(
        homework_id,
        7,
        AssignmentType.GLOBAL_SUBJECT,
        AssignmentStatus.READY,
        3,
        "Mathématiques",
        DifficultyMode.MEDIUM,
        8,
        30,
        NOW,
        (101, 102),
        session_id,
        "STUDENT",
        NOW,
    )


def _request() -> HomeworkRequest:
    return HomeworkRequest(
        7,
        "STUDENT",
        "student:7",
        AssignmentType.GLOBAL_SUBJECT,
        3,
        4,
        (),
        (),
        DifficultyMode.MEDIUM,
        8,
        30,
        NOW,
    )


def _availability(*, active: bool = True) -> AIAvailability:
    if active:
        return AIAvailability(
            mode=AIAvailabilityMode.ACTIVE,
            platform_enabled=True,
            learner_feature_enabled=True,
            provider_configured=True,
            reason="",
        )
    return AIAvailability(
        mode=AIAvailabilityMode.INACTIVE,
        platform_enabled=True,
        learner_feature_enabled=False,
        provider_configured=True,
        reason="désactivé",
    )


def _orchestrator(
    *,
    ai_active: bool = True,
    with_pi: bool = True,
    with_sessions: bool = True,
) -> tuple[ProfessorAIOrchestrator, dict[str, Any]]:
    guidance = MagicMock()
    guidance.build_home_guidance.return_value = _dashboard()
    guidance.explain_session_result.return_value = SimpleNamespace(homework_id=11)

    pedagogical = None
    if with_pi:
        pedagogical = MagicMock()
        pedagogical.overview.return_value = SimpleNamespace(
            current_grade_label="Quatrième",
            diagnostic_status="COMPLETED",
            recommendations=("Réviser les relatifs",),
            strengths=("Calculs",),
            weaknesses=("Fractions",),
        )
        pedagogical.refresh_after_session.return_value = SimpleNamespace(ok=True)

    homework = MagicMock()
    assignment = _homework()
    homework.create.return_value = assignment
    homework.create_with_diagnostics.return_value = HomeworkGenerationResult(
        assignment,
        8,
        6,
        2,
        2,
        8,
        False,
        None,
        "corr-1",
    )

    sessions = None
    if with_sessions:
        sessions = MagicMock()
        sessions.open_for_learner.return_value = _homework(session_id=99)

    preferences = MagicMock()
    preferences.ensure_preferences.return_value = SimpleNamespace(
        feature_enabled=ai_active,
        operating_mode="PROFESSOR" if ai_active else "MANUAL",
    )

    orch = ProfessorAIOrchestrator(
        guidance=guidance,
        pedagogical=pedagogical,
        homework=homework,
        homework_sessions=sessions,
        preferences=preferences,
        availability_resolver=lambda **_: _availability(active=ai_active),
    )
    return orch, {
        "guidance": guidance,
        "pedagogical": pedagogical,
        "homework": homework,
        "sessions": sessions,
        "preferences": preferences,
    }


def test_resolve_mode_professor_when_feature_enabled() -> None:
    orch, _ = _orchestrator(ai_active=True)
    assert orch.resolve_mode(7) is ProfessorOperatingMode.PROFESSOR


def test_resolve_mode_manual_when_feature_disabled() -> None:
    orch, _ = _orchestrator(ai_active=False)
    assert orch.resolve_mode(7) is ProfessorOperatingMode.MANUAL


def test_plan_session_loads_welcome_and_diagnostic() -> None:
    orch, deps = _orchestrator()
    plan = orch.plan_session({"role": "STUDENT", "resolved_learner_id": 7}, 7, now=NOW)
    assert plan.mode is ProfessorOperatingMode.PROFESSOR
    assert plan.welcome.greeting == "Bonjour Noa"
    assert plan.grade_label == "Quatrième"
    assert plan.recommendations == ("Réviser les relatifs",)
    assert [item.step for item in plan.decision_trace] == ["ACCUEIL", "DIAGNOSTIC"]
    deps["guidance"].build_home_guidance.assert_called_once()
    deps["pedagogical"].overview.assert_called_once_with(7)


def test_plan_session_skips_diagnostic_in_manual_mode() -> None:
    orch, deps = _orchestrator(ai_active=False)
    plan = orch.plan_session({"role": "STUDENT", "resolved_learner_id": 7}, 7, mode=ProfessorOperatingMode.MANUAL)
    assert plan.mode is ProfessorOperatingMode.MANUAL
    assert plan.recommendations == ()
    deps["pedagogical"].overview.assert_not_called()


def test_compose_homework_uses_existing_homework_service() -> None:
    orch, deps = _orchestrator()
    result = orch.compose_homework(_request())
    assert result.homework.homework_id == 11
    assert result.generation is not None
    assert result.generation.final_count == 8
    deps["homework"].create_with_diagnostics.assert_called_once()


def test_companion_mode_cannot_create_homework() -> None:
    orch, _ = _orchestrator()
    with pytest.raises(PermissionError, match="Compagnon"):
        orch.compose_homework(_request(), mode=ProfessorOperatingMode.COMPANION)


def test_open_session_materializes_running_session() -> None:
    orch, deps = _orchestrator()
    opened = orch.open_session(7, 11, now=NOW)
    assert opened.session_id == 99
    deps["sessions"].open_for_learner.assert_called_once_with(7, 11, NOW)


def test_close_session_cycle_explains_and_refreshes() -> None:
    orch, deps = _orchestrator()
    actor = {"role": "STUDENT", "resolved_learner_id": 7}
    closed = orch.close_session_cycle(actor, 7, 99)
    assert closed.explanation_available is True
    assert closed.refresh_triggered is True
    deps["guidance"].explain_session_result.assert_called_once_with(actor, 7, 99)
    deps["pedagogical"].refresh_after_session.assert_called_once()


def test_close_session_cycle_manual_skips_refresh() -> None:
    orch, deps = _orchestrator(ai_active=False)
    closed = orch.close_session_cycle(
        {"role": "STUDENT", "resolved_learner_id": 7},
        7,
        99,
        mode=ProfessorOperatingMode.MANUAL,
    )
    assert closed.refresh_triggered is False
    deps["pedagogical"].refresh_after_session.assert_not_called()
