"""Auto-size subject evaluations (minimum 10 questions, score /20, no hard time cap)."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any

EVALUATION_MIN_QUESTIONS = 10
EVALUATION_MAX_QUESTIONS = 40
EVALUATION_DEFAULT_QUESTIONS = 10
EVALUATION_SCORE_OUT_OF = 20
_DEFAULT_SECONDS_PER_QUESTION = 120
# Kept for display/legacy callers only — duration is not a hard selection budget.
EVALUATION_MAX_MINUTES = 60


def target_evaluation_question_count(
    *,
    preferred: int = EVALUATION_DEFAULT_QUESTIONS,
    max_minutes: int | None = None,
    seconds_per_question: int = _DEFAULT_SECONDS_PER_QUESTION,
) -> int:
    """Desired question count for a full evaluation (at least 10).

    ``max_minutes`` is ignored: evaluations are not capped by a time budget;
    the learner may pause at any time.
    """
    del max_minutes, seconds_per_question
    return max(EVALUATION_MIN_QUESTIONS, min(EVALUATION_MAX_QUESTIONS, int(preferred)))


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
    return _DEFAULT_SECONDS_PER_QUESTION + max(0, difficulty - 2) * 30


def plan_evaluation_from_catalog_rows(
    rows: list[tuple[Any, ...]],
    *,
    min_questions: int = EVALUATION_MIN_QUESTIONS,
    max_questions: int = EVALUATION_MAX_QUESTIONS,
    preferred_questions: int = EVALUATION_DEFAULT_QUESTIONS,
    max_minutes: int | None = None,
) -> EvaluationPlan:
    """Pick a mixed set of questions — at least ``min_questions`` when the catalog allows.

    Duration is estimated for information only; it does not truncate the selection.
    """
    del max_minutes
    if not rows:
        return EvaluationPlan(0, 0, points_per_question=0.0)

    min_q = max(1, int(min_questions))
    max_q = max(min_q, int(max_questions))
    desired = max(min_q, min(max_q, int(preferred_questions)))

    by_diff: dict[int, list[tuple[Any, ...]]] = {}
    for row in rows:
        diff = int(row[3]) if row[3] is not None else 3
        by_diff.setdefault(diff, []).append(row)
    for bucket in by_diff.values():
        bucket.sort(key=lambda item: int(item[0]))

    ordered: list[tuple[Any, ...]] = []
    while any(by_diff.values()) and len(ordered) < max_q:
        progressed = False
        for diff in sorted(by_diff):
            if by_diff[diff]:
                ordered.append(by_diff[diff].pop(0))
                progressed = True
            if len(ordered) >= max_q:
                break
        if not progressed:
            break

    take = min(len(ordered), desired) if len(ordered) >= min_q else len(ordered)
    selected = ordered[:take]
    elapsed = sum(_seconds_for_row(row) for row in selected)
    count = len(selected)
    minutes = max(1, ceil(elapsed / 60)) if count else 0
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
