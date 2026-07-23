"""Pure deterministic analytical policies."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from statistics import mean, median

from domain.learning_intelligence.models import (
    AnalyticsMetrics,
    DifficultyAction,
    LearningEvidence,
    RevisionState,
    StrengthClassification,
    WeaknessClassification,
)
from domain.learning_intelligence.policies import LearningIntelligenceConfiguration


def calculate_metrics(evidence: tuple[LearningEvidence, ...]) -> AnalyticsMetrics:
    if not evidence:
        return AnalyticsMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    assessed = tuple(item for item in evidence if 0 <= item.final_score <= 100)
    successes = sum(item.success for item in assessed)
    scores = [item.final_score for item in assessed]
    durations = [item.duration_seconds for item in assessed]
    expected = sum(item.expected_duration_seconds for item in assessed)
    hinted = sum(item.hint_count > 0 for item in assessed)
    first = tuple(item for item in assessed if item.attempt_number == 1)
    return AnalyticsMetrics(
        len(evidence),
        len(assessed),
        successes,
        len(assessed) - successes,
        successes / len(assessed) if assessed else 0,
        mean(scores) if scores else 0,
        median(scores) if scores else 0,
        mean(durations) if durations else 0,
        median(durations) if durations else 0,
        sum(durations) / expected if expected else 0,
        hinted,
        hinted / len(assessed) if assessed else 0,
        sum(item.attempt_number > 1 for item in assessed),
        sum(item.success for item in first) / len(first) if first else 0,
        len({item.session_id for item in assessed}),
        assessed[0].mastery_before if assessed else 0,
        assessed[-1].mastery_after if assessed else 0,
        assessed[-1].mastery_after - assessed[0].mastery_before if assessed else 0,
    )


def detect_strength(
    metrics: AnalyticsMetrics,
    confidence: float,
    config: LearningIntelligenceConfiguration,
) -> StrengthClassification:
    if metrics.assessed_attempt_count < config.strength_min_attempts:
        return StrengthClassification.INSUFFICIENT_DATA
    if (
        metrics.mastery_end >= config.stable_mastery_threshold
        and metrics.accuracy_rate >= config.stable_accuracy_threshold
        and metrics.hint_usage_rate <= 0.4
        and metrics.distinct_sessions >= 2
    ):
        return StrengthClassification.STABLE
    if (
        metrics.mastery_end >= config.established_mastery_threshold
        and metrics.accuracy_rate >= config.established_accuracy_threshold
        and confidence >= 0.5
        and metrics.distinct_sessions >= 2
    ):
        return StrengthClassification.ESTABLISHED
    if (
        metrics.mastery_end >= config.strength_mastery_threshold
        and metrics.accuracy_rate >= config.strength_accuracy_threshold
    ):
        return StrengthClassification.EMERGING
    return StrengthClassification.INSUFFICIENT_DATA


def detect_weakness(
    metrics: AnalyticsMetrics,
    recurring_error_count: int,
    revision_overdue: bool,
    config: LearningIntelligenceConfiguration,
) -> WeaknessClassification:
    if revision_overdue and metrics.mastery_end >= config.strength_mastery_threshold:
        return WeaknessClassification.REVISION_OVERDUE
    if metrics.assessed_attempt_count < config.weakness_min_attempts:
        return WeaknessClassification.WATCH if metrics.failure_count else WeaknessClassification.INSUFFICIENT_DATA
    if recurring_error_count >= config.recurring_error_min_occurrences:
        return WeaknessClassification.REMEDIATION_REQUIRED
    if (
        metrics.mastery_end < config.weakness_mastery_threshold
        or metrics.accuracy_rate < config.weakness_accuracy_threshold
    ):
        return WeaknessClassification.FRAGILE
    return WeaknessClassification.WATCH


def recurring_errors(
    evidence: tuple[LearningEvidence, ...],
    config: LearningIntelligenceConfiguration,
) -> tuple[tuple[str, int], ...]:
    counts = Counter(item.error_code for item in evidence if item.error_code)
    return tuple(
        sorted(
            ((str(code), count) for code, count in counts.items() if count >= config.recurring_error_min_occurrences),
            key=lambda item: (-item[1], item[0]),
        )
    )


def difficulty_guidance(
    metrics: AnalyticsMetrics,
    confidence: float,
    blocking_prerequisite: bool,
    config: LearningIntelligenceConfiguration,
) -> DifficultyAction:
    if metrics.assessed_attempt_count < 4:
        return DifficultyAction.INSUFFICIENT_DATA
    if blocking_prerequisite or metrics.accuracy_rate < 0.5:
        return DifficultyAction.DECREASE
    if metrics.accuracy_rate >= 0.85 and confidence >= 0.55 and metrics.hint_usage_rate <= 0.4:
        return DifficultyAction.INCREASE
    if metrics.accuracy_rate >= 0.7 and metrics.mastery_end >= config.strength_mastery_threshold:
        return DifficultyAction.MIX if metrics.hint_usage_rate > 0.4 else DifficultyAction.MAINTAIN
    return DifficultyAction.MAINTAIN


def revision_state(
    next_revision_at: datetime | None,
    now: datetime,
    mastery: float,
    config: LearningIntelligenceConfiguration,
) -> RevisionState:
    if next_revision_at is None:
        return RevisionState.NOT_APPLICABLE
    days = (next_revision_at.date() - now.date()).days
    if days > config.revision_due_soon_days:
        return RevisionState.NOT_YET_DUE
    if days > 0:
        return RevisionState.DUE_SOON
    if days == 0:
        return RevisionState.DUE
    if days < -7 and mastery >= config.strength_mastery_threshold:
        return RevisionState.HIGH_PRIORITY_OVERDUE
    return RevisionState.OVERDUE
