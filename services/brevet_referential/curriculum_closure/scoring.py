"""LCAI-0040 coverage scoring — COMPLETE requires diversity, not only counts."""

from __future__ import annotations

from services.brevet_referential.curriculum_rebuild.thresholds import (
    FAMILY_CATALOG,
    exercise_minima,
    normalize_importance,
    pick_family,
    subskill_minima,
)


def score_coverage_v40(
    *,
    exercise_count: int,
    family_count: int,
    correction_coverage: float,
    importance: str | None,
    playable_ratio: float = 1.0,
    asset_completeness: float = 1.0,
    subskill_ok: bool = True,
) -> str:
    """Final closure scoring: no GOOD on required skills; COMPLETE or PARTIAL/lower."""
    needed = exercise_minima(importance)
    if exercise_count <= 0:
        return "EMPTY"
    if exercise_count < max(8, needed // 4) or correction_coverage < 0.5:
        return "INSUFFICIENT"
    if (
        exercise_count >= needed
        and family_count >= 5
        and correction_coverage >= 0.99
        and playable_ratio >= 0.95
        and asset_completeness >= 0.95
        and subskill_ok
    ):
        return "COMPLETE"
    return "PARTIAL"


def classify_gap(
    *,
    exercise_count: int,
    family_count: int,
    correction_coverage: float,
    importance: str | None,
    playable_ratio: float,
    subskill_ok: bool,
    official_count: int,
    official_mapping_broken: bool = False,
) -> list[str]:
    causes: list[str] = []
    needed = exercise_minima(importance)
    if exercise_count < needed:
        causes.append("INSUFFICIENT_EXERCISE_COUNT")
    if family_count < 5:
        causes.append("INSUFFICIENT_FAMILY_DIVERSITY")
    if correction_coverage < 0.99:
        causes.append("MISSING_CORRECTION")
    if playable_ratio < 0.95:
        causes.append("LOW_PLAYABILITY")
    if not subskill_ok:
        causes.append("MISSING_SUBSKILL_COVERAGE")
    if official_mapping_broken:
        causes.append("OFFICIAL_MAPPING_BROKEN")
    elif official_count == 0:
        causes.append("NO_OFFICIAL_QUESTION_FOUND")
    if not causes:
        causes.append("OTHER")
    return causes


__all__ = [
    "FAMILY_CATALOG",
    "classify_gap",
    "exercise_minima",
    "normalize_importance",
    "pick_family",
    "score_coverage_v40",
    "subskill_minima",
]
