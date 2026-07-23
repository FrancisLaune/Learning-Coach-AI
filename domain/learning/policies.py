"""Validated and centralized Learning Engine configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.learning.enums import LearningPhase


@dataclass(frozen=True, slots=True)
class LearningEngineConfiguration:
    emerging_threshold: float = 0.20
    developing_threshold: float = 0.45
    proficient_threshold: float = 0.70
    mastered_threshold: float = 0.88
    mastery_learning_rate: float = 0.28
    mastery_error_rate: float = 0.14
    hint_penalty: float = 0.10
    retry_penalty: float = 0.08
    solution_cap: float = 0.25
    abandonment_cap: float = 0.10
    fast_time_floor_ratio: float = 0.18
    slow_time_ratio: float = 2.0
    forgetting_daily_rate: float = 0.012
    forgetting_floor: float = 0.35
    forgetting_enabled: bool = True
    difficulty_up_observations: int = 3
    difficulty_down_failures: int = 2
    minimum_confidence_to_raise: float = 0.55
    transition_threshold: float = 0.70
    exam_threshold: float = 0.72
    coverage_weight: float = 0.30
    prerequisite_weight: float = 0.25
    phase_multipliers: dict[LearningPhase, float] = field(
        default_factory=lambda: {
            LearningPhase.DIAGNOSTIC: 0.90,
            LearningPhase.REMEDIATION: 1.05,
            LearningPhase.SPACED_REVISION: 1.08,
            LearningPhase.EXAM_PREPARATION: 1.02,
            LearningPhase.TRANSITION_PREPARATION: 1.03,
        }
    )

    def __post_init__(self) -> None:
        ordered = (
            self.emerging_threshold,
            self.developing_threshold,
            self.proficient_threshold,
            self.mastered_threshold,
        )
        if not all(0 <= value <= 1 for value in ordered) or tuple(sorted(ordered)) != ordered:
            raise ValueError("Mastery thresholds must be ordered within [0,1]")
        if not 0 <= self.forgetting_floor <= 1 or self.forgetting_daily_rate < 0:
            raise ValueError("Invalid forgetting configuration")
