"""LCAI-0019 Phase 2 tests."""

from __future__ import annotations

from domain.pedagogical_intelligence.engine import classify_readiness_band, compute_readiness_score
from services.pedagogical_intelligence.readiness_service import ReadinessService
from services.pedagogical_intelligence.recommendation_service import PedagogicalRecommendationService


def test_compute_readiness_score_bounded() -> None:
    score = compute_readiness_score(
        mastery_score=0.8,
        coverage_score=0.7,
        confidence_score=0.6,
        critical_score=0.5,
        stability_score=0.5,
    )
    assert 0.0 <= score <= 1.0


def test_readiness_bands_phase2_thresholds() -> None:
    assert classify_readiness_band(score=0.85, coverage=0.6, confidence=0.5) == "READY"
    assert classify_readiness_band(score=0.65, coverage=0.4, confidence=0.4) == "ALMOST_READY"
    assert classify_readiness_band(score=0.4, coverage=0.2, confidence=0.2) == "NOT_READY"


def test_readiness_service_wraps_formula() -> None:
    result = ReadinessService.compute(
        mastery_score=0.7,
        coverage_score=0.6,
        confidence_score=0.5,
        critical_score=0.4,
        stability_score=0.5,
    )
    assert result.band in {"READY", "ALMOST_READY", "NOT_READY"}


def test_recommendations_are_not_duplicated() -> None:
    from domain.pedagogical_intelligence.models import MasterySummaryItem, ReadinessSnapshot

    mastery = (
        MasterySummaryItem(1, "A", 40, "FRAGILE", "STABLE"),
        MasterySummaryItem(1, "A", 42, "FRAGILE", "STABLE"),
    )
    readiness = ReadinessSnapshot("FR_4E_TO_3E", "FR-4E", "FR-3E", 40, 0.3, 0.3, "NOT_READY", 0, 1, 2, ())
    items = PedagogicalRecommendationService().build(readiness=readiness, mastery=mastery, diagnostic_status="COMPLETED")
    keys = {(item.recommendation_type, item.skill_label) for item in items}
    assert len(keys) == len(items)
