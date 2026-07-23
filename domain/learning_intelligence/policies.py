"""Explicit versioned thresholds for Learning Intelligence."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LearningIntelligenceConfiguration:
    version: str = "learning-intelligence-v1"
    configuration_version: str = "learning-intelligence-thresholds-v1"
    strength_min_attempts: int = 5
    weakness_min_attempts: int = 4
    recurring_error_min_occurrences: int = 3
    trend_min_dates: int = 3
    strength_mastery_threshold: float = 0.70
    established_mastery_threshold: float = 0.80
    stable_mastery_threshold: float = 0.85
    strength_accuracy_threshold: float = 0.70
    established_accuracy_threshold: float = 0.80
    stable_accuracy_threshold: float = 0.85
    weakness_mastery_threshold: float = 0.55
    weakness_accuracy_threshold: float = 0.55
    revision_due_soon_days: int = 3

    def __post_init__(self) -> None:
        if (
            min(
                self.strength_min_attempts,
                self.weakness_min_attempts,
                self.recurring_error_min_occurrences,
                self.trend_min_dates,
            )
            < 1
        ):
            raise ValueError("Evidence thresholds must be positive")
