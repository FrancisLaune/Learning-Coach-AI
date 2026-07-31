"""LCAI-0022D — Professor AI decision log and invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
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
from infrastructure.repositories.professor_ai_decision_log import DuckDBProfessorAIDecisionLogRepository
from infrastructure.repositories.v2 import LearnerRepositoryV2
from migrations.runner import apply_migrations
from services.professor_ai.decision_log import ProfessorAIDecisionLogService
from services.professor_ai.invariants import (
    ProfessorAIInvariantError,
    assert_no_score_fields_in_payload,
    assert_score_mutation_forbidden,
    forbid_direct_score_mutation,
)
from services.professor_ai.models import DecisionTraceEntry, ProfessorOperatingMode
from services.professor_ai.orchestrator import ProfessorAIOrchestrator

NOW = datetime(2026, 7, 31, 20, 0, tzinfo=UTC)


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
        (55, 56),
        DifficultyMode.MEDIUM,
        8,
        30,
        NOW,
    )


@pytest.fixture
def decision_db(tmp_path: Path) -> Path:
    path = tmp_path / "decision_0022d.duckdb"
    apply_migrations(path)
    LearnerRepositoryV2(path).create("Decision learner")
    return path


def test_forbid_direct_score_mutation_raises() -> None:
    with pytest.raises(ProfessorAIInvariantError, match="mutation directe"):
        forbid_direct_score_mutation("write_mastery_score")


def test_assert_score_mutation_forbidden_catalogue() -> None:
    assert_score_mutation_forbidden("read_only_overview")
    with pytest.raises(ProfessorAIInvariantError):
        assert_score_mutation_forbidden("write_mastery_score")


def test_assert_no_score_fields_in_payload() -> None:
    assert_no_score_fields_in_payload({"action": "plan_session"})
    with pytest.raises(ProfessorAIInvariantError, match="mastery_score"):
        assert_no_score_fields_in_payload({"mastery_score": 12})


def test_decision_log_repository_persists_and_lists(decision_db: Path) -> None:
    repository = DuckDBProfessorAIDecisionLogRepository(decision_db)
    learner_id = LearnerRepositoryV2(decision_db).create("Log learner")
    saved = repository.append(
        learner_id=learner_id,
        correlation_id="corr-1",
        operating_mode="PROFESSOR",
        cycle_step="CREATION_DEVOIR",
        justification="Devoir créé",
        engine_version="professor-ai-orchestrator-v1",
        objective="devoir maths",
        candidates=("content:101", "content:102"),
        exclusions=("catalog_shortfall:2",),
        deficit={"requested": "8", "catalog": "6"},
        context={"action": "compose_homework"},
        homework_id=42,
        created_at=NOW,
    )
    assert saved.id > 0
    assert saved.candidates == ("content:101", "content:102")
    assert saved.deficit["catalog"] == "6"
    listed = repository.list_for_learner(learner_id)
    assert len(listed) == 1
    assert listed[0].correlation_id == "corr-1"
    by_corr = repository.list_by_correlation("corr-1")
    assert len(by_corr) == 1


def test_decision_log_service_records_trace(decision_db: Path) -> None:
    learner_id = LearnerRepositoryV2(decision_db).create("Trace learner")
    service = ProfessorAIDecisionLogService(DuckDBProfessorAIDecisionLogRepository(decision_db))
    recorded = service.record_trace(
        learner_id=learner_id,
        mode=ProfessorOperatingMode.PROFESSOR,
        correlation_id="corr-trace",
        entries=(
            DecisionTraceEntry(
                "ACCUEIL",
                "Accueil chargé",
                objective="Progresser",
                candidates=("mission:1",),
            ),
            DecisionTraceEntry(
                "DIAGNOSTIC",
                "Diagnostic OK",
                deficit=(("status", "COMPLETED"),),
            ),
        ),
        context={"action": "plan_session"},
    )
    assert len(recorded) == 2
    rows = service.list_for_learner(learner_id)
    assert [row.cycle_step for row in rows] == ["DIAGNOSTIC", "ACCUEIL"]


def test_orchestrator_persists_plan_and_homework_decisions() -> None:
    guidance = MagicMock()
    guidance.build_home_guidance.return_value = _dashboard()
    pedagogical = MagicMock()
    pedagogical.overview.return_value = SimpleNamespace(
        current_grade_label="Sixième",
        diagnostic_status="COMPLETED",
        recommendations=("Réviser",),
        strengths=("Calcul",),
        weaknesses=("Fractions",),
    )
    homework = MagicMock()
    assignment = _homework()
    homework.create_with_diagnostics.return_value = HomeworkGenerationResult(
        assignment,
        8,
        6,
        2,
        2,
        8,
        False,
        None,
        "corr-gen",
        runtime_exercise_ids=(501,),
    )
    decision_log = MagicMock()
    orch = ProfessorAIOrchestrator(
        guidance=guidance,
        pedagogical=pedagogical,
        homework=homework,
        preferences=MagicMock(
            ensure_preferences=MagicMock(return_value=SimpleNamespace(feature_enabled=True, operating_mode="PROFESSOR"))
        ),
        decision_log=decision_log,
        availability_resolver=lambda **_: AIAvailability(
            mode=AIAvailabilityMode.ACTIVE,
            platform_enabled=True,
            learner_feature_enabled=True,
            provider_configured=True,
        ),
    )
    plan = orch.plan_session({"role": "STUDENT"}, 7, now=NOW)
    assert plan.correlation_id.startswith("plan:")
    assert decision_log.record_trace.call_count == 1
    composed = orch.compose_homework(_request())
    assert composed.correlation_id.startswith("hw:")
    assert decision_log.record_trace.call_count == 2
    hw_call = decision_log.record_trace.call_args_list[1]
    entries = hw_call.kwargs["entries"]
    creation = entries[-1]
    assert "content:101" in creation.candidates
    assert "runtime:501" in creation.candidates
    assert creation.exclusions == ("catalog_shortfall:2",)
    assert ("requested", "8") in creation.deficit


def test_decision_log_rejects_score_smuggling(decision_db: Path) -> None:
    learner_id = LearnerRepositoryV2(decision_db).create("Safe learner")
    service = ProfessorAIDecisionLogService(DuckDBProfessorAIDecisionLogRepository(decision_db))
    with pytest.raises(ProfessorAIInvariantError):
        service.record_trace(
            learner_id=learner_id,
            mode=ProfessorOperatingMode.PROFESSOR,
            entries=(DecisionTraceEntry("ACCUEIL", "x"),),
            context={"mastery_score": 99},
        )
