"""LCAI-0031 Phase 3 — pedagogical engine unit tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from domain.dnb.planner import build_brevet_study_plan
from domain.dnb.prioritizer import (
    BrevetImportance,
    SkillPriorityInput,
    prioritize_skills,
    score_skill,
)
from domain.dnb.readiness import compute_brevet_readiness
from domain.dnb.remediation import PrerequisiteGap, build_remediation_plan
from domain.pedagogical_intelligence.paths import brevet_baseline_path_code, path_for_source_grade
from migrations.runner import apply_migrations
from services import dnb as dnb_service


def test_baseline_diagnostic_path_for_3e() -> None:
    path = path_for_source_grade("FR-3E")
    assert path is not None
    assert path.code == brevet_baseline_path_code()
    assert path.source_grade_code == "FR-3E"
    assert path.target_grade_code == "FR-3E"
    assert dnb_service.baseline_diagnostic_path_code() == "FR_3E_DNB_BASELINE"


def test_prioritizer_orders_fragile_critical_first() -> None:
    items = (
        SkillPriorityInput(1, "Thalès", 90, BrevetImportance.CRITICAL),
        SkillPriorityInput(2, "Équations", 35, BrevetImportance.CRITICAL, prerequisite_impact=0.8),
        SkillPriorityInput(3, "Vocabulaire", 40, BrevetImportance.LOW),
    )
    ranked = prioritize_skills(items, days_until_exam=60, limit=3)
    assert ranked[0].skill_id == 2
    assert "fragile" in ranked[0].reason or "importante" in ranked[0].reason


def test_prioritizer_reason_is_explainable() -> None:
    result = score_skill(
        SkillPriorityInput(9, "Proportionnalité", 30, BrevetImportance.HIGH, prerequisite_impact=0.7),
        days_until_exam=20,
    )
    assert "prioritaire" in result.reason.casefold()
    assert result.priority > 0


def test_remediation_plan_is_short_and_measurable() -> None:
    plan = build_remediation_plan(
        PrerequisiteGap(
            target_skill_id=10,
            target_label="Thalès",
            prerequisite_skill_id=3,
            prerequisite_label="Proportionnalité",
            prerequisite_grade_code="FR-4E",
        )
    )
    assert plan.estimated_minutes <= 25
    assert len(plan.steps) == 4
    assert "70 %" in plan.exit_criterion


def test_study_plan_uses_calendar_countdown() -> None:
    priorities = prioritize_skills(
        (SkillPriorityInput(1, "Équations", 40, BrevetImportance.CRITICAL),),
        days_until_exam=100,
    )
    plan = build_brevet_study_plan(
        priorities=priorities,
        weekly_minutes=200,
        today=date(2027, 3, 1),
    )
    assert plan.days_until_first_exam is not None
    assert plan.days_until_first_exam > 0
    assert plan.focuses[0].label == "Équations"
    assert "Brevet blanc" in plan.mock_exam_hint or "blanc" in plan.mock_exam_hint.casefold()


def test_readiness_not_plain_average() -> None:
    low = compute_brevet_readiness(mastery=0.9, coverage=0.9, critical_gap_ratio=0.8)
    high = compute_brevet_readiness(mastery=0.9, coverage=0.9, critical_gap_ratio=0.0)
    assert low.score < high.score
    assert low.band in {"AT_RISK", "ON_TRACK", "READY"}


def test_dnb_service_facade_pipeline() -> None:
    ranked = dnb_service.priorities_from_mastery_rows(
        (
            {"skill_id": 1, "label": "Fractions", "mastery_score": 42, "subject_code": "MATHEMATICS"},
            {"skill_id": 2, "label": "Dictée", "mastery_score": 70, "subject_code": "FRENCH"},
        ),
        today=date(2027, 1, 15),
        limit=2,
    )
    plan = dnb_service.study_plan(ranked, weekly_minutes=150, today=date(2027, 1, 15), readiness_score=0.4)
    assert plan.focuses
    readiness = dnb_service.readiness_score(mastery=0.4, coverage=0.5, critical_gap_ratio=0.3)
    assert 0.0 <= readiness.score <= 1.0


def test_migration_028_pedagogy_tables(tmp_path: Path) -> None:
    from infrastructure.database.v2 import connect_v2

    path = tmp_path / "p3.duckdb"
    applied = apply_migrations(path)
    assert any(item.version == 28 for item in applied)
    connection = connect_v2(path, read_only=True)
    try:
        for table in (
            "brevet_readiness_snapshots",
            "prerequisite_remediation_runs",
            "pedagogical_decision_log",
        ):
            row = connection.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name=?",
                [table],
            ).fetchone()
            assert int(row[0]) == 1
    finally:
        connection.close()
