"""Auto-size subject evaluations from catalog durations (max 45 min, score /20)."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any

EVALUATION_MAX_MINUTES = 45
EVALUATION_SCORE_OUT_OF = 20
_DEFAULT_SECONDS_PER_QUESTION = 120
_MIN_QUESTIONS = 5
_MAX_QUESTIONS = 40


@dataclass(frozen=True, slots=True)
class EvaluationPlan:
    exercise_count: int
    estimated_minutes: int
    score_out_of: int = EVALUATION_SCORE_OUT_OF
    points_per_question: float = 0.0
    content_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.exercise_count > 0 and self.points_per_question <= 0:
            object.__setattr__(
                self,
                "points_per_question",
                round(self.score_out_of / self.exercise_count, 2),
            )


def _seconds_for_row(row: tuple[Any, ...]) -> int:
    """Catalog rows: (content_id, chapter_id, skill_id, difficulty[, content_type[, estimated_minutes]])."""
    if len(row) > 5 and row[5] is not None:
        minutes = max(1, int(row[5]))
        return minutes * 60
    difficulty = int(row[3]) if len(row) > 3 and row[3] is not None else 3
    # Harder items get a slightly longer default slot.
    return _DEFAULT_SECONDS_PER_QUESTION + max(0, difficulty - 2) * 30


def plan_evaluation_from_catalog_rows(
    rows: list[tuple[Any, ...]],
    *,
    max_minutes: int = EVALUATION_MAX_MINUTES,
) -> EvaluationPlan:
    """Pick a mixed set of questions whose estimated duration stays within max_minutes."""
    if not rows:
        return EvaluationPlan(0, 0, points_per_question=0.0)

    budget = max(1, max_minutes) * 60
    # Prefer a difficulty mix: sort by (difficulty bucket, content_id) then round-robin.
    by_diff: dict[int, list[tuple[Any, ...]]] = {}
    for row in rows:
        diff = int(row[3]) if row[3] is not None else 3
        by_diff.setdefault(diff, []).append(row)
    for bucket in by_diff.values():
        bucket.sort(key=lambda item: int(item[0]))

    ordered: list[tuple[Any, ...]] = []
    while any(by_diff.values()) and len(ordered) < _MAX_QUESTIONS:
        progressed = False
        for diff in sorted(by_diff):
            if by_diff[diff]:
                ordered.append(by_diff[diff].pop(0))
                progressed = True
            if len(ordered) >= _MAX_QUESTIONS:
                break
        if not progressed:
            break

    selected: list[tuple[Any, ...]] = []
    elapsed = 0
    for row in ordered:
        seconds = _seconds_for_row(row)
        if selected and elapsed + seconds > budget:
            continue
        if not selected and seconds > budget:
            # Always keep at least one question even if longer than budget.
            selected.append(row)
            elapsed = seconds
            break
        selected.append(row)
        elapsed += seconds
        if len(selected) >= _MAX_QUESTIONS:
            break
        if elapsed >= budget:
            break

    if len(selected) < _MIN_QUESTIONS and len(ordered) >= _MIN_QUESTIONS:
        # Fill up to minimum if budget allowed too few short items.
        for row in ordered:
            if row in selected:
                continue
            selected.append(row)
            elapsed += _seconds_for_row(row)
            if len(selected) >= _MIN_QUESTIONS:
                break

    count = len(selected)
    minutes = max(1, min(max_minutes, ceil(elapsed / 60))) if count else 0
    return EvaluationPlan(
        exercise_count=count,
        estimated_minutes=minutes,
        score_out_of=EVALUATION_SCORE_OUT_OF,
        points_per_question=round(EVALUATION_SCORE_OUT_OF / count, 2) if count else 0.0,
        content_ids=tuple(int(row[0]) for row in selected),
    )


def score_percent_to_out_of_20(overall_score: float | None) -> float | None:
    if overall_score is None:
        return None
    return round(max(0.0, min(100.0, float(overall_score))) / 5.0, 1)
