"""LCAI-0039 coverage thresholds and status scoring."""

from __future__ import annotations

from typing import Any


def normalize_importance(value: str | None) -> str:
    raw = str(value or "MEDIUM").upper()
    if raw in {"CRITICAL", "HIGH"}:
        return raw
    if raw in {"STANDARD", "MEDIUM", "LOW"}:
        return "MEDIUM" if raw != "STANDARD" else "MEDIUM"
    return "MEDIUM"


def exercise_minima(importance: str | None) -> int:
    """Minimum validated exercises per active skill (ticket §17)."""
    key = normalize_importance(importance)
    if key == "CRITICAL":
        return 50
    if key == "HIGH":
        return 40
    return 30


def subskill_minima() -> int:
    return 8


def score_coverage(
    *,
    exercise_count: int,
    family_count: int,
    official_count: int,
    correction_coverage: float,
    importance: str | None,
    playable_ratio: float = 1.0,
) -> str:
    needed = exercise_minima(importance)
    if exercise_count <= 0:
        return "EMPTY"
    if exercise_count < max(8, needed // 4) or correction_coverage < 0.5:
        return "INSUFFICIENT"
    if exercise_count < needed or family_count < 3 or playable_ratio < 0.9:
        return "PARTIAL"
    if exercise_count >= needed and family_count >= 4 and correction_coverage >= 0.95:
        if official_count > 0 or family_count >= 5:
            return "COMPLETE"
        return "GOOD"
    return "GOOD"


def difficulty_bucket(label: str | None, score: float | None) -> str:
    text = str(label or "").casefold()
    if "brevet" in text or (score is not None and score >= 0.85):
        return "BREVET"
    if "difficile" in text or "stretch" in text or (score is not None and score >= 0.7):
        return "STRETCH"
    if "facile" in text or "consol" in text or (score is not None and score <= 0.35):
        return "CONSOLIDATION"
    return "CURRENT_LEVEL"


FAMILY_CATALOG = (
    "DIRECT_APPLICATION",
    "MULTI_STEP",
    "PROBLEM_SOLVING",
    "DOCUMENT_ANALYSIS",
    "JUSTIFICATION",
    "REASONING",
    "BREVET_STYLE",
    "OFFICIAL_ARCHIVE",
    "REMEDIATION",
    "TRANSFER",
    "AUTOMATISM",
    "OPEN_RESPONSE",
)


def pick_family(index: int, *, open_response: bool = False) -> str:
    if open_response:
        return "OPEN_RESPONSE"
    return FAMILY_CATALOG[index % len(FAMILY_CATALOG)]


def as_dict_row(keys: list[str], row: tuple[Any, ...]) -> dict[str, Any]:
    return {k: row[i] for i, k in enumerate(keys)}
