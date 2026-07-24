from dataclasses import dataclass, field

from domain.decision.enums import ObjectiveKind
from domain.onboarding.enums import CompatibilityStatus
from domain.onboarding.models import GoalCompatibility


def _matrix() -> tuple[GoalCompatibility, ...]:
    common = (
        ObjectiveKind.REVISION,
        ObjectiveKind.CATCH_UP,
        ObjectiveKind.CONSOLIDATION,
        ObjectiveKind.HOMEWORK,
        ObjectiveKind.LONG_TERM_MASTERY,
    )
    rows = [
        GoalCompatibility(grade, kind, CompatibilityStatus.ALLOWED)
        for grade in ("FR-CM1", "FR-CM2", "FR-6E", "FR-5E", "FR-4E", "FR-3E", "FR-2NDE", "FR-1ERE", "FR-TERM")
        for kind in common
    ]
    rows += [
        GoalCompatibility("FR-CM1", ObjectiveKind.PREPARATION_NEXT_GRADE, CompatibilityStatus.RECOMMENDED, True),
        GoalCompatibility("FR-CM2", ObjectiveKind.PREPARATION_NEXT_GRADE, CompatibilityStatus.RECOMMENDED, True),
        GoalCompatibility("FR-6E", ObjectiveKind.PREPARATION_NEXT_GRADE, CompatibilityStatus.RECOMMENDED, True),
        GoalCompatibility("FR-5E", ObjectiveKind.PREPARATION_NEXT_GRADE, CompatibilityStatus.RECOMMENDED, True),
        GoalCompatibility("FR-4E", ObjectiveKind.PREPARATION_NEXT_GRADE, CompatibilityStatus.RECOMMENDED, True),
        GoalCompatibility("FR-4E", ObjectiveKind.PREPARATION_BREVET, CompatibilityStatus.ANTICIPATION, False, True),
        GoalCompatibility("FR-3E", ObjectiveKind.PREPARATION_BREVET, CompatibilityStatus.RECOMMENDED, False, True),
        GoalCompatibility("FR-3E", ObjectiveKind.PREPARATION_NEXT_GRADE, CompatibilityStatus.ALLOWED, True),
        GoalCompatibility("FR-2NDE", ObjectiveKind.PREPARATION_NEXT_GRADE, CompatibilityStatus.ALLOWED, True),
        GoalCompatibility("FR-2NDE", ObjectiveKind.PREPARATION_BAC, CompatibilityStatus.ANTICIPATION, False, True),
        GoalCompatibility("FR-1ERE", ObjectiveKind.PREPARATION_BAC, CompatibilityStatus.RECOMMENDED, False, True),
        GoalCompatibility("FR-1ERE", ObjectiveKind.PREPARATION_NEXT_GRADE, CompatibilityStatus.ALLOWED, True),
        GoalCompatibility("FR-TERM", ObjectiveKind.PREPARATION_BAC, CompatibilityStatus.RECOMMENDED, False, True),
    ]
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class OnboardingConfiguration:
    goal_matrix: tuple[GoalCompatibility, ...] = field(default_factory=_matrix)
    minimum_activity_minutes: int = 10
    maximum_activity_minutes: int = 45
    budget_tolerance_minutes: int = 2
    maximum_candidates: int = 50
    maximum_session_activities: int = 4
    v2_ui_enabled: bool = False
    presentation_languages: tuple[str, ...] = ("fr-FR", "en-GB")
    onboarding_version: str = "onboarding-v1"
    recommendation_version: str = "recommendation-v1"
    candidate_adapter_version: str = "candidate-adapter-v1"
    ruleset_version: str = "onboarding-rules-v1"
