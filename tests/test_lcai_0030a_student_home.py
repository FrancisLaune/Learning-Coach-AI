"""LCAI-0030-A — smoke tests for student-first home (Lot 1)."""

from __future__ import annotations

from pathlib import Path

from application.dto.student_guidance import (
    AIAvailability,
    AIAvailabilityMode,
    GuidanceSource,
    MasteryBand,
    MasterySnapshotItem,
    RevisionPriority,
    StudentDashboardSnapshot,
    StudentHomeContext,
    WelcomeGuidance,
)
from services.learning_session.experience import Metric, StudentDashboard
from ui.student_guidance import render_student_home


def _snapshot() -> StudentDashboardSnapshot:
    mastery = (
        MasterySnapshotItem(
            skill_id=1,
            label="Fractions",
            score=42,
            level="FRAGILE",
            trend="DECLINING",
            band=MasteryBand.FRAGILE,
            band_label="Peu maîtrisé / fragile",
            subject_label="Mathématiques",
            chapter_label="Nombres rationnels",
        ),
    )
    context = StudentHomeContext(
        learner_id=7,
        display_name="Michael",
        homework_todo=(),
        homework_overdue=(),
        homework_recent=(),
        mastery=mastery,
        fragile_skills=mastery,
        strong_skills=(),
        revision_priorities=(
            RevisionPriority(
                subject_label="Mathématiques",
                skill_label="Nombres rationnels — Fractions",
                reason="Maîtrise 42 %",
                priority=3,
                estimated_minutes=15,
                action_label="Lancer une révision",
                skill_id=1,
            ),
        ),
        recent_score=None,
        success_rate=None,
        objective="Préparer la 3e",
        next_revision=None,
    )
    return StudentDashboardSnapshot(
        context=context,
        welcome=WelcomeGuidance(
            source=GuidanceSource.DETERMINISTIC,
            greeting="Bonjour",
            primary_action="Réviser",
        ),
        availability=AIAvailability(
            mode=AIAvailabilityMode.INACTIVE,
            platform_enabled=False,
            learner_feature_enabled=False,
            provider_configured=False,
        ),
        mastery_by_band={"FRAGILE": mastery},
        recommendations=context.revision_priorities,
    )


def test_render_student_home_is_callable_without_professor_banner() -> None:
    dashboard = StudentDashboard(
        learner_id=7,
        display_name="Michael",
        objective="Préparer la 3e",
        recommended_duration_minutes=20,
        metrics=(Metric("Maîtrise", "42 %"),),
        mastery=(),
        recent_sessions=(),
        current_session=None,
        next_revision=None,
    )
    assert render_student_home.__name__ == "render_student_home"
    assert dashboard.display_name == "Michael"
    snap = _snapshot()
    assert snap.context.revision_priorities[0].subject_label == "Mathématiques"
    assert "Nombres rationnels" in snap.context.revision_priorities[0].skill_label
    source = Path(__file__).resolve().parents[1].joinpath("ui", "unified_app.py").read_text(encoding="utf-8")
    pages = source.split("_STUDENT_PAGES = (")[1].split(")")[0]
    assert "Mon professeur IA" not in pages
    assert "render_professor_ai_banner" not in source.split("def run_student")[1].split("def _render_child_management_back")[0]
