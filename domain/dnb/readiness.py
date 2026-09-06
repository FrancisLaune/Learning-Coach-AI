"""LCAI-0031 — Brevet readiness score (configurable stub aligned with ticket §27)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BrevetReadinessComponents:
    mastery: float
    coverage: float
    stability: float
    exam_performance: float
    critical_gap_penalty: float


@dataclass(frozen=True, slots=True)
class BrevetReadinessScore:
    score: float  # 0..1
    components: BrevetReadinessComponents
    band: str
    explanation: str


def compute_brevet_readiness(
    *,
    mastery: float,
    coverage: float,
    stability: float = 0.5,
    exam_performance: float = 0.0,
    critical_gap_ratio: float = 0.0,
) -> BrevetReadinessScore:
    """Readiness = weighted product with critical-gap penalty (not a plain mean)."""
    m = max(0.0, min(1.0, mastery))
    c = max(0.0, min(1.0, coverage))
    s = max(0.0, min(1.0, stability))
    e = max(0.0, min(1.0, exam_performance))
    penalty = max(0.35, 1.0 - max(0.0, min(1.0, critical_gap_ratio)))
    raw = (0.40 * m + 0.20 * c + 0.15 * s + 0.25 * e) * penalty
    score = round(max(0.0, min(1.0, raw)), 4)
    if score >= 0.8:
        band = "READY"
    elif score >= 0.55:
        band = "ON_TRACK"
    else:
        band = "AT_RISK"
    explanation = (
        f"Score {score:.0%} (maîtrise {m:.0%}, couverture {c:.0%}, "
        f"stabilité {s:.0%}, examens {e:.0%}, pénalité lacunes critiques ×{penalty:.2f})."
    )
    return BrevetReadinessScore(
        score=score,
        components=BrevetReadinessComponents(m, c, s, e, penalty),
        band=band,
        explanation=explanation,
    )
