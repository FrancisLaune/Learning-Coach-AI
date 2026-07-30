"""Centralized mastery band classification for LCAI-0020."""

from __future__ import annotations

from application.dto.student_guidance import MASTERY_BAND_LABELS, MasteryBand


def classify_mastery_band(*, score: float, level: str, trend: str) -> MasteryBand:
    normalized_level = str(level).upper()
    normalized_trend = str(trend).upper()
    if normalized_level in {"NOT_STARTED", "UNKNOWN"} and score <= 0:
        return MasteryBand.UNEVALUATED
    if score >= 90 or normalized_level == "MASTERED":
        return MasteryBand.VERY_HIGH
    if score >= 75 or normalized_level == "PROFICIENT":
        return MasteryBand.HIGH
    if score >= 55 or normalized_level in {"DEVELOPING", "STABLE"}:
        return MasteryBand.MEDIUM
    if normalized_trend in {"DECLINING", "FRAGILE"} or score < 45 or normalized_level in {"EMERGING", "FRAGILE"}:
        if score < 35:
            return MasteryBand.TO_REVISE
        return MasteryBand.FRAGILE
    return MasteryBand.TO_REVISE


def band_label(band: MasteryBand) -> str:
    return MASTERY_BAND_LABELS[band]
