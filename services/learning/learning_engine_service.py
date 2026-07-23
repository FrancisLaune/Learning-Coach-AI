"""Transactional orchestration of one deterministic learning cycle."""

from __future__ import annotations

import logging
from dataclasses import asdict, replace
from time import monotonic

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
from domain.learning.enums import MasteryLevel, PrerequisiteCondition, Trend
from domain.learning.events import (
    AttemptEvaluated,
    CurriculumCoverageChanged,
    DifficultyRecommendationChanged,
    ExamReadinessChanged,
    LearningEvent,
    LearningRegressionDetected,
    MasteryAchieved,
    MasteryLevelChanged,
    MasteryUpdated,
    PrerequisiteGapDetected,
    RevisionDueDetected,
    TransitionReadinessChanged,
)
from domain.learning.models import (
    DifficultyRecommendation,
    ExamReadiness,
    ForgettingAdjustment,
    LearnerAttempt,
    LearningEngineMetrics,
    LearningEngineResult,
    MasteryState,
    MasteryUpdate,
    PrerequisiteStatus,
    ProgressState,
    TransitionReadiness,
)
from domain.learning.policies import LearningEngineConfiguration
from domain.learning.repositories import LearningRepository

logger = logging.getLogger(__name__)


class LearningEngineService:
    def __init__(self, repository: LearningRepository, config: LearningEngineConfiguration | None = None) -> None:
        self.repository = repository
        self.config = config or LearningEngineConfiguration()
        self._cache: dict[str, LearningEngineResult] = {}

    def process(self, attempt: LearnerAttempt) -> LearningEngineResult:
        started = monotonic()
        if attempt.stable_id in self._cache:
            return replace(self._cache[attempt.stable_id], already_processed=True)
        if self.repository.is_processed(attempt.stable_id):
            logger.info("learning_attempt_already_processed", extra={"attempt_id": attempt.stable_id})
            cached = self.repository.get_cached_result(attempt.stable_id)
            return cached
        journey = self.repository.load_journey(attempt.learner_id)
        previous = self.repository.load_mastery(attempt.learner_id, attempt.skill_id) or MasteryState(
            attempt.learner_id, attempt.skill_id, origin_grade_code=journey.current_grade.code
        )
        states = self.repository.load_all_mastery(attempt.learner_id)
        prerequisite_ids = self.repository.load_prerequisite_ids(attempt.skill_id)
        prerequisites = evaluate_prerequisites(states, prerequisite_ids, self.config)
        evaluation = evaluate_attempt(attempt, journey, self.config)
        forgetting = apply_forgetting(previous, attempt.occurred_at, self.config)
        mastery = update_mastery(previous, evaluation, attempt, journey, forgetting, self.config)
        states[attempt.skill_id] = mastery.current
        difficulty = recommend_difficulty(mastery.current, forgetting, prerequisites, journey, self.config)
        curriculum = self.repository.load_curriculum(journey)
        progress = (
            calculate_progress("program", journey.program_id or 0, curriculum, states, self.config)
            if curriculum
            else None
        )
        transition = calculate_transition(journey, curriculum, states, self.config) if curriculum else None
        exam = (
            calculate_exam(journey.examination.code, curriculum, states, self.config)
            if journey.examination and curriculum
            else None
        )
        events = self._events(attempt, mastery, difficulty, prerequisites, forgetting, progress, transition, exam)
        metrics = LearningEngineMetrics(round((monotonic() - started) * 1000), len(events), 1, 7)
        result = LearningEngineResult(
            attempt.stable_id, evaluation, forgetting, mastery, difficulty, progress, transition, exam, events, metrics
        )
        self.repository.save_cycle(attempt, mastery.current, events, progress, transition, exam, asdict(result))
        self._cache[attempt.stable_id] = result
        logger.info(
            "learning_cycle_completed",
            extra={"attempt_id": attempt.stable_id, "events": len(events), "duration_ms": metrics.duration_ms},
        )
        return result

    def _events(
        self,
        attempt: LearnerAttempt,
        mastery: MasteryUpdate,
        difficulty: DifficultyRecommendation,
        prerequisites: tuple[PrerequisiteStatus, ...],
        forgetting: ForgettingAdjustment,
        progress: ProgressState | None,
        transition: TransitionReadiness | None,
        exam: ExamReadiness | None,
    ) -> tuple[LearningEvent, ...]:
        base = {"stable_attempt_id": attempt.stable_id}
        events: list[LearningEvent] = [
            AttemptEvaluated(attempt.learner_id, attempt.skill_id, {**base, "score": mastery.signal.score}),
            MasteryUpdated(
                attempt.learner_id,
                attempt.skill_id,
                {**base, "previous": mastery.previous.score, "current": mastery.current.score},
            ),
        ]
        if mastery.previous.level != mastery.current.level:
            events.append(
                MasteryLevelChanged(
                    attempt.learner_id,
                    attempt.skill_id,
                    {**base, "from": mastery.previous.level.value, "to": mastery.current.level.value},
                )
            )
        if mastery.current.level is MasteryLevel.MASTERED and mastery.previous.level is not MasteryLevel.MASTERED:
            events.append(MasteryAchieved(attempt.learner_id, attempt.skill_id, base))
        if mastery.current.trend is Trend.DECLINING:
            events.append(LearningRegressionDetected(attempt.learner_id, attempt.skill_id, base))
        if difficulty.previous != difficulty.recommended:
            events.append(
                DifficultyRecommendationChanged(
                    attempt.learner_id,
                    attempt.skill_id,
                    {**base, "from": difficulty.previous, "to": difficulty.recommended},
                )
            )
        for prerequisite in prerequisites:
            if prerequisite.condition in (PrerequisiteCondition.FRAGILE, PrerequisiteCondition.NOT_ACQUIRED):
                events.append(PrerequisiteGapDetected(attempt.learner_id, prerequisite.skill_id, base))
        if forgetting.degradation > 0.1:
            events.append(RevisionDueDetected(attempt.learner_id, attempt.skill_id, base))
        if progress:
            events.append(
                CurriculumCoverageChanged(attempt.learner_id, attempt.skill_id, {**base, "score": progress.score})
            )
        if transition:
            events.append(
                TransitionReadinessChanged(attempt.learner_id, attempt.skill_id, {**base, "score": transition.score})
            )
        if exam:
            events.append(ExamReadinessChanged(attempt.learner_id, attempt.skill_id, {**base, "score": exam.score}))
        return tuple(events)
