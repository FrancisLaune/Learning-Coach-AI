"""LCAI-0022C — guided Professor AI cycle Accueil → Synthèse."""

from __future__ import annotations

from datetime import UTC, datetime

from application.dto.student_guidance import (
    AIAvailability,
    AIAvailabilityMode,
    GuidanceSource,
    HomeworkSummaryItem,
    StudentDashboardSnapshot,
    StudentHomeContext,
    WelcomeGuidance,
)
from services.professor_ai.guided_cycle import (
    GuidedCycleStep,
    diagnostic_required,
    progress_caption,
    resolve_guided_cycle,
)
from services.professor_ai.models import ProfessorOperatingMode, SessionPlan
from ui.navigation import NAVIGATION_REQUEST_KEY
from ui.professor_ai_guided_cycle import apply_guided_cycle_cta, build_cycle_snapshot, mark_cycle_synthesis_closed

NOW = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)


def _plan(
    *,
    mode: ProfessorOperatingMode = ProfessorOperatingMode.PROFESSOR,
    diagnostic_status: str = "COMPLETED",
    homework_todo: tuple[HomeworkSummaryItem, ...] = (),
    homework_overdue: tuple[HomeworkSummaryItem, ...] = (),
    primary_action: str = "Consulter ton tableau de bord",
) -> SessionPlan:
    context = StudentHomeContext(
        learner_id=7,
        display_name="Noa",
        homework_todo=homework_todo,
        homework_overdue=homework_overdue,
        homework_recent=(),
        mastery=(),
        fragile_skills=(),
        strong_skills=(),
        revision_priorities=(),
        recent_score=None,
        success_rate=None,
        objective="Progresser",
        next_revision=None,
    )
    welcome = WelcomeGuidance(
        source=GuidanceSource.DETERMINISTIC,
        greeting="Bonjour Noa",
        primary_action=primary_action,
    )
    dashboard = StudentDashboardSnapshot(
        context=context,
        welcome=welcome,
        availability=AIAvailability(
            mode=AIAvailabilityMode.ACTIVE,
            platform_enabled=True,
            learner_feature_enabled=True,
            provider_configured=True,
        ),
    )
    return SessionPlan(
        learner_id=7,
        mode=mode,
        welcome=welcome,
        availability=dashboard.availability,
        dashboard=dashboard,
        grade_label="6e",
        diagnostic_status=diagnostic_status,
        recommendations=(),
        strengths=(),
        weaknesses=(),
        decision_trace=(),
        planned_at=NOW,
    )


def _hw(homework_id: int, subject: str = "Mathématiques") -> HomeworkSummaryItem:
    return HomeworkSummaryItem(
        homework_id=homework_id,
        subject_label=subject,
        status="READY",
        due_at=None,
        exercise_count=3,
        target_duration_minutes=20,
    )


def test_diagnostic_required_skips_manual_and_done_statuses() -> None:
    assert diagnostic_required("OFFERED", mode=ProfessorOperatingMode.PROFESSOR) is True
    assert diagnostic_required("COMPLETED", mode=ProfessorOperatingMode.PROFESSOR) is False
    assert diagnostic_required("OFFERED", mode=ProfessorOperatingMode.MANUAL) is False
    assert diagnostic_required("UNKNOWN", mode=ProfessorOperatingMode.PROFESSOR) is False


def test_resolve_prioritizes_active_session() -> None:
    plan = _plan(diagnostic_status="OFFERED", homework_todo=(_hw(3),))
    snap = resolve_guided_cycle(plan, active_session_id=42, active_session_status="RUNNING")
    assert snap.step is GuidedCycleStep.SEANCE
    assert snap.page == "S'entraîner"
    assert snap.session_id == 42


def test_resolve_synthesis_until_closed() -> None:
    plan = _plan()
    open_snap = resolve_guided_cycle(plan, active_session_id=9, active_session_status="COMPLETED")
    assert open_snap.step is GuidedCycleStep.SYNTHESE
    closed = resolve_guided_cycle(
        plan,
        active_session_id=9,
        active_session_status="COMPLETED",
        synthesis_closed_for_session=9,
    )
    assert closed.step is GuidedCycleStep.ACCUEIL


def test_resolve_diagnostic_then_devoir() -> None:
    diag = resolve_guided_cycle(_plan(diagnostic_status="OFFERED"))
    assert diag.step is GuidedCycleStep.DIAGNOSTIC
    assert diag.focus_diagnostic is True
    assert diag.page == "Accueil"

    devoir = resolve_guided_cycle(_plan(homework_todo=(_hw(15, "Français"),)))
    assert devoir.step is GuidedCycleStep.DEVOIR
    assert devoir.homework_id == 15
    assert "Français" in devoir.cta_label


def test_resolve_overdue_before_todo() -> None:
    snap = resolve_guided_cycle(
        _plan(
            homework_todo=(_hw(1, "Histoire"),),
            homework_overdue=(_hw(2, "Mathématiques"),),
        )
    )
    assert snap.step is GuidedCycleStep.DEVOIR
    assert snap.homework_id == 2
    assert "Mathématiques" in snap.cta_label


def test_progress_caption_format() -> None:
    assert progress_caption(GuidedCycleStep.DEVOIR) == "Étape 3/5 — Devoir"


def test_apply_guided_cycle_cta_sets_navigation_and_focus() -> None:
    state: dict = {}
    snap = resolve_guided_cycle(_plan(diagnostic_status="OFFERED"))
    apply_guided_cycle_cta(state, snap)
    assert state[NAVIGATION_REQUEST_KEY]["page"] == "Accueil"
    assert state["professor_ai_focus_diagnostic"] is True
    assert state["professor_ai_cycle_step"] == GuidedCycleStep.DIAGNOSTIC.value


def test_build_cycle_snapshot_reads_session_state() -> None:
    state = {"v2_session_id": 77, "professor_ai_active_session_status": "PAUSED"}
    snap = build_cycle_snapshot(_plan(), state)
    assert snap.step is GuidedCycleStep.SEANCE
    assert state["professor_ai_cycle_step"] == GuidedCycleStep.SEANCE.value


def test_mark_cycle_synthesis_closed() -> None:
    state: dict = {}
    mark_cycle_synthesis_closed(state, 12)
    assert state["professor_ai_cycle_closed_12"] is True
    assert state["professor_ai_cycle_step"] == "SYNTHESE"
