"""Non-blocking homework exercise ranking and panachage (LCAI-0021 / LCAI-0030-C)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.unified_experience.models import AssignmentType, HomeworkRequest

CatalogRow = tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class HomeworkSelectionStrategy:
    consolidation_share: float = 0.30
    current_level_share: float = 0.40
    stretch_share: float = 0.20
    revision_share: float = 0.10


@dataclass(frozen=True, slots=True)
class LearnerOutcomeSignals:
    """Recent mastery signals used to adapt exercise mix (LCAI-0030-C)."""

    avg_score: float | None = None
    success_streak: int = 0
    failure_streak: int = 0
    avg_last_difficulty: float | None = None


def strategy_from_outcomes(signals: LearnerOutcomeSignals | None) -> HomeworkSelectionStrategy:
    """More consolidation after failures; more stretch after successes."""
    if signals is None:
        return HomeworkSelectionStrategy()
    score = signals.avg_score
    if signals.failure_streak >= 2 or (score is not None and score < 0.45):
        return HomeworkSelectionStrategy(
            consolidation_share=0.50,
            current_level_share=0.35,
            stretch_share=0.05,
            revision_share=0.10,
        )
    if signals.success_streak >= 3 or (score is not None and score >= 0.75):
        return HomeworkSelectionStrategy(
            consolidation_share=0.15,
            current_level_share=0.35,
            stretch_share=0.40,
            revision_share=0.10,
        )
    return HomeworkSelectionStrategy()


def target_difficulty_from_outcomes(signals: LearnerOutcomeSignals | None, *, default: int = 3) -> int:
    """Raise/lower target difficulty from streaks and recent mastery."""
    base = default
    if signals is not None and signals.avg_last_difficulty is not None:
        base = max(1, min(5, round(float(signals.avg_last_difficulty))))
    if signals is None:
        return base
    recommended = base
    if signals.failure_streak >= 2 or (signals.avg_score is not None and signals.avg_score < 0.45):
        recommended -= 1
    elif signals.success_streak >= 3 and (signals.avg_score is None or signals.avg_score >= 0.70):
        recommended += 1
    return max(1, min(5, recommended))


def difficulty_fit_score(row_difficulty: int, target: int | None) -> float:
    if target is None:
        return 0.5
    distance = abs(int(row_difficulty) - int(target))
    return max(0.0, 1.0 - distance * 0.25)


def categorize_row(row_difficulty: int, target: int | None) -> str:
    if target is None:
        return "CURRENT_LEVEL"
    delta = int(row_difficulty) - int(target)
    if delta <= -1:
        return "CONSOLIDATION"
    if delta == 0:
        return "CURRENT_LEVEL"
    return "STRETCH"


def rank_catalog_rows(rows: list[CatalogRow], target: int | None) -> list[CatalogRow]:
    return sorted(
        rows,
        key=lambda row: (
            -difficulty_fit_score(int(row[3]), target),
            int(row[1]),
            int(row[2]),
            int(row[3]),
            int(row[0]),
        ),
    )


def _bucket_targets(exercise_count: int, strategy: HomeworkSelectionStrategy) -> dict[str, int]:
    raw = {
        "CONSOLIDATION": round(exercise_count * strategy.consolidation_share),
        "CURRENT_LEVEL": round(exercise_count * strategy.current_level_share),
        "STRETCH": round(exercise_count * strategy.stretch_share),
    }
    total = sum(raw.values())
    if total > exercise_count:
        largest = max(raw, key=raw.__getitem__)
        raw[largest] -= total - exercise_count
    if total < exercise_count:
        raw["CURRENT_LEVEL"] += exercise_count - total
    return raw


def panachage_select(
    rows: list[CatalogRow],
    *,
    target: int | None,
    exercise_count: int,
    strategy: HomeworkSelectionStrategy | None = None,
) -> list[CatalogRow]:
    if not rows or exercise_count <= 0:
        return []
    strategy = strategy or HomeworkSelectionStrategy()
    ranked = rank_catalog_rows(rows, target)
    buckets: dict[str, list[CatalogRow]] = {
        "CONSOLIDATION": [],
        "CURRENT_LEVEL": [],
        "STRETCH": [],
    }
    for row in ranked:
        buckets[categorize_row(int(row[3]), target)].append(row)

    selected: list[CatalogRow] = []
    seen: set[int] = set()

    def take(bucket: str, limit: int) -> None:
        for row in buckets[bucket]:
            if limit <= 0 or len(selected) >= exercise_count:
                return
            content_id = int(row[0])
            if content_id in seen:
                continue
            selected.append(row)
            seen.add(content_id)
            limit -= 1

    for bucket, limit in _bucket_targets(exercise_count, strategy).items():
        take(bucket, limit)

    for row in ranked:
        if len(selected) >= exercise_count:
            break
        content_id = int(row[0])
        if content_id not in seen:
            selected.append(row)
            seen.add(content_id)
    return selected


def balance_by_chapter(rows: list[CatalogRow]) -> list[CatalogRow]:
    groups: dict[int, list[CatalogRow]] = {}
    for row in rows:
        groups.setdefault(int(row[1]), []).append(row)
    balanced: list[CatalogRow] = []
    while any(groups.values()):
        for chapter_id in sorted(groups):
            if groups[chapter_id]:
                balanced.append(groups[chapter_id].pop(0))
    return balanced


def uses_mixed_difficulties(rows: list[CatalogRow], target: int | None) -> bool:
    if not rows:
        return False
    difficulties = {int(row[3]) for row in rows}
    if len(difficulties) > 1:
        return True
    if target is None:
        return False
    return any(int(row[3]) != int(target) for row in rows)


class HomeworkExerciseSelectionService:
    def prepare_catalog_rows(
        self,
        rows: list[CatalogRow],
        *,
        request: HomeworkRequest,
        target_difficulty: int | None,
        strategy: HomeworkSelectionStrategy | None = None,
        outcome_signals: LearnerOutcomeSignals | None = None,
    ) -> list[CatalogRow]:
        if not rows:
            return []
        resolved_strategy = strategy or strategy_from_outcomes(outcome_signals)
        pool_size = max(request.exercise_count * 3, request.exercise_count)
        prepared = panachage_select(
            rows,
            target=target_difficulty,
            exercise_count=pool_size,
            strategy=resolved_strategy,
        )
        if request.mode is AssignmentType.GLOBAL_SUBJECT:
            prepared = balance_by_chapter(prepared)
        return prepared

    def selection_uses_mixed_difficulties(
        self,
        prepared: list[CatalogRow],
        *,
        target_difficulty: int | None,
        exercise_count: int,
    ) -> bool:
        selected = prepared[:exercise_count]
        return uses_mixed_difficulties(selected, target_difficulty)
