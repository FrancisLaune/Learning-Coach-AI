"""Tests for LCAI-0019 pedagogical intelligence."""

from __future__ import annotations

from datetime import UTC, datetime

from domain.pedagogical_intelligence.engine import (
    classify_readiness_band,
    select_next_diagnostic_skill,
    should_stop_diagnostic,
    update_diagnostic_confidence,
)
from domain.pedagogical_intelligence.models import DiagnosticRun, MasterySummaryItem
from domain.pedagogical_intelligence.paths import path_for_source_grade
from services.pedagogical_intelligence.platform_service import PedagogicalIntelligenceService


class MemoryPIRepository:
    def __init__(self) -> None:
        self.context = {
            "display_name": "Léa",
            "current_grade_code": "FR-4E",
            "current_grade_label": "Quatrième",
            "diagnostic_status": "OFFERED",
        }
        self.transition = {
            "source_grade_code": "FR-4E",
            "target_grade_code": "FR-3E",
            "score": 68.0,
            "coverage": 0.62,
            "confidence": 0.71,
            "acquired_skill_ids": (1, 2, 3),
            "fragile_skill_ids": (4,),
            "blocking_skill_ids": (5, 6),
        }
        self.mastery = (
            MasterySummaryItem(1, "Fractions", 82, "MASTERED", "IMPROVING"),
            MasterySummaryItem(5, "Géométrie", 42, "FRAGILE", "STABLE"),
        )

    def learner_context(self, learner_id: int) -> dict:
        return dict(self.context)

    def transition_readiness(self, learner_id: int, target_grade_code: str):
        return dict(self.transition)

    def mastery_summary(self, learner_id: int, *, limit: int = 8):
        return self.mastery

    def planner_highlights(self, learner_id: int, *, limit: int = 5):
        return ()

    def active_diagnostic_run(self, learner_id: int):
        return None


def test_readiness_paths_for_supported_grades() -> None:
    assert path_for_source_grade("FR-CM1") is not None
    assert path_for_source_grade("FR-4E") is not None
    assert path_for_source_grade("FR-3E") is not None
    assert path_for_source_grade("FR-3E").code == "FR_3E_DNB_BASELINE"
    assert path_for_source_grade("FR-CM2") is None


def test_classify_readiness_band_thresholds() -> None:
    assert classify_readiness_band(score=80, coverage=0.75, confidence=0.7) == "READY"
    assert classify_readiness_band(score=60, coverage=0.5, confidence=0.5) == "ALMOST_READY"
    assert classify_readiness_band(score=40, coverage=0.2, confidence=0.3) == "NOT_READY"


def test_adaptive_diagnostic_skill_selection_and_stop() -> None:
    target = (10, 20, 30)
    confidence = {10: 0.2, 20: 0.5, 30: 0.9}
    assert select_next_diagnostic_skill(target, confidence, ()) == 10
    assert select_next_diagnostic_skill(target, confidence, (10,)) == 20
    assert not should_stop_diagnostic(
        questions_asked=2,
        confidence_by_skill=confidence,
        target_skill_ids=target,
        assessed_skill_ids=(10,),
    )
    assert should_stop_diagnostic(
        questions_asked=5,
        confidence_by_skill={10: 0.9, 20: 0.88, 30: 0.91},
        target_skill_ids=target,
        assessed_skill_ids=(10, 20, 30),
    )


def test_update_diagnostic_confidence_is_bounded() -> None:
    updated = update_diagnostic_confidence(0.2, 1.0)
    assert 0.0 <= updated <= 1.0
    assert updated > 0.2


def test_platform_overview_builds_readiness_and_recommendations() -> None:
    service = PedagogicalIntelligenceService(MemoryPIRepository())
    overview = service.overview(7)
    assert overview.active_path is not None
    assert overview.readiness is not None
    assert overview.readiness.band == "ALMOST_READY"
    assert overview.strengths
    assert overview.weaknesses
    assert overview.recommendations


def test_diagnostic_run_model_fields() -> None:
    run = DiagnosticRun(
        1,
        7,
        "FR_4E_TO_3E",
        "IN_PROGRESS",
        2,
        (10, 20),
        (10,),
        20,
        {10: 0.7, 20: 0.0},
        datetime(2026, 7, 30, tzinfo=UTC),
        None,
    )
    assert run.current_skill_id == 20
