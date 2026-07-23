"""Central decision weights and strategy policies."""

from dataclasses import dataclass, field

from domain.decision.enums import ObjectiveKind, PedagogicalStrategy


@dataclass(frozen=True, slots=True)
class DecisionConfiguration:
    blocking_score: float = 100.0
    fragile_score: float = 75.0
    revision_score: float = 60.0
    new_skill_score: float = 40.0
    preferred_subject_bonus: float = 8.0
    weak_subject_bonus: float = 12.0
    deadline_bonus_max: float = 20.0
    variety_bonus: float = 4.0
    vacation_duration_factor: float = 0.65
    minimum_activity_minutes: int = 10
    maximum_activity_minutes: int = 45
    fragile_threshold: float = 0.70
    blocking_threshold: float = 0.45
    confidence_floor: float = 0.25
    objective_strategies: dict[ObjectiveKind, PedagogicalStrategy] = field(
        default_factory=lambda: {
            ObjectiveKind.REVISION: PedagogicalStrategy.SPACED_REVISION,
            ObjectiveKind.CATCH_UP: PedagogicalStrategy.CATCH_UP,
            ObjectiveKind.CONSOLIDATION: PedagogicalStrategy.FOUNDATION_REINFORCEMENT,
            ObjectiveKind.PREPARATION_NEXT_GRADE: PedagogicalStrategy.TRANSITION_PREPARATION,
            ObjectiveKind.PREPARATION_BREVET: PedagogicalStrategy.EXAM_PREPARATION,
            ObjectiveKind.PREPARATION_BAC: PedagogicalStrategy.EXAM_PREPARATION,
            ObjectiveKind.HOMEWORK: PedagogicalStrategy.INTENSIVE_REVISION,
            ObjectiveKind.EXAM: PedagogicalStrategy.EXAM_PREPARATION,
            ObjectiveKind.LONG_TERM_MASTERY: PedagogicalStrategy.BALANCED_LEARNING,
        }
    )
