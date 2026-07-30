"""Readiness computation for LCAI-0019."""

from __future__ import annotations

from dataclasses import dataclass

from domain.pedagogical_intelligence.engine import classify_readiness_band, compute_readiness_score


@dataclass(frozen=True, slots=True)
class ReadinessComputation:
    score: float
    coverage: float
    confidence: float
    critical_score: float
    stability_score: float
    band: str


class ReadinessService:
    @staticmethod
    def compute(
        *,
        mastery_score: float,
        coverage_score: float,
        confidence_score: float,
        critical_score: float,
        stability_score: float,
    ) -> ReadinessComputation:
        score = compute_readiness_score(
            mastery_score=mastery_score,
            coverage_score=coverage_score,
            confidence_score=confidence_score,
            critical_score=critical_score,
            stability_score=stability_score,
        )
        band = classify_readiness_band(score=score * 100, coverage=coverage_score, confidence=confidence_score)
        return ReadinessComputation(
            score=score,
            coverage=coverage_score,
            confidence=confidence_score,
            critical_score=critical_score,
            stability_score=stability_score,
            band=band,
        )
