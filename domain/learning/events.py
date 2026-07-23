"""In-process domain events; no external event bus is assumed."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class LearningEvent:
    learner_id: int
    skill_id: int | None
    payload: dict[str, Any]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class AttemptEvaluated(LearningEvent):
    pass


@dataclass(frozen=True, slots=True)
class MasteryUpdated(LearningEvent):
    pass


@dataclass(frozen=True, slots=True)
class MasteryLevelChanged(LearningEvent):
    pass


@dataclass(frozen=True, slots=True)
class DifficultyRecommendationChanged(LearningEvent):
    pass


@dataclass(frozen=True, slots=True)
class PrerequisiteGapDetected(LearningEvent):
    pass


@dataclass(frozen=True, slots=True)
class LearningRegressionDetected(LearningEvent):
    pass


@dataclass(frozen=True, slots=True)
class MasteryAchieved(LearningEvent):
    pass


@dataclass(frozen=True, slots=True)
class RevisionDueDetected(LearningEvent):
    pass


@dataclass(frozen=True, slots=True)
class TransitionReadinessChanged(LearningEvent):
    pass


@dataclass(frozen=True, slots=True)
class ExamReadinessChanged(LearningEvent):
    pass


@dataclass(frozen=True, slots=True)
class CurriculumCoverageChanged(LearningEvent):
    pass
