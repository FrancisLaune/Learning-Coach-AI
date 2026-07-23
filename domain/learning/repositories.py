"""Persistence ports consumed by the orchestration service."""

from __future__ import annotations

from typing import Any, Protocol

from domain.learning.events import LearningEvent
from domain.learning.models import (
    CurriculumContext,
    ExamReadiness,
    LearnerAttempt,
    LearnerJourneyContext,
    MasteryState,
    ProgressState,
    TransitionReadiness,
)


class LearningRepository(Protocol):
    def is_processed(self, stable_attempt_id: str) -> bool: ...
    def get_cached_result(self, stable_attempt_id: str) -> Any: ...
    def load_mastery(self, learner_id: int, skill_id: int) -> MasteryState | None: ...
    def load_all_mastery(self, learner_id: int) -> dict[int, MasteryState]: ...
    def load_journey(self, learner_id: int) -> LearnerJourneyContext: ...
    def load_curriculum(self, journey: LearnerJourneyContext) -> tuple[CurriculumContext, ...]: ...
    def load_prerequisite_ids(self, skill_id: int) -> tuple[int, ...]: ...
    def save_cycle(
        self,
        attempt: LearnerAttempt,
        mastery: MasteryState,
        events: tuple[LearningEvent, ...],
        progress: ProgressState | None,
        transition: TransitionReadiness | None,
        exam: ExamReadiness | None,
        result_payload: dict,
    ) -> None: ...


AttemptRepository = LearningRepository
MasteryRepository = LearningRepository
LearningEventRepository = LearningRepository
ProgressRepository = LearningRepository
PrerequisiteRepository = LearningRepository
LearnerJourneyRepository = LearningRepository
TransitionReadinessRepository = LearningRepository
ExamReadinessRepository = LearningRepository
