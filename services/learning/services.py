"""Small use-case façades over the pure Learning Engine calculators."""

from domain.learning.calculators import (
    apply_forgetting,
    calculate_exam,
    calculate_progress,
    calculate_transition,
    evaluate_attempt,
    evaluate_prerequisites,
    recommend_difficulty,
    update_mastery,
)


class AttemptEvaluationService:
    evaluate = staticmethod(evaluate_attempt)


class ForgettingService:
    adjust = staticmethod(apply_forgetting)


class MasteryService:
    update = staticmethod(update_mastery)


class AdaptiveDifficultyService:
    recommend = staticmethod(recommend_difficulty)


class PrerequisiteService:
    evaluate = staticmethod(evaluate_prerequisites)


class ProgressionService:
    calculate = staticmethod(calculate_progress)


class TransitionReadinessService:
    calculate = staticmethod(calculate_transition)


class ExamReadinessService:
    calculate = staticmethod(calculate_exam)
