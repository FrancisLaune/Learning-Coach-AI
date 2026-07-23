"""Application services for journey configuration, planning and decisions."""

from __future__ import annotations

from domain.decision.engine import build_plan, decide, detect_blockages, next_window, prioritize, select_candidates
from domain.decision.models import DecisionContext, LearnerJourney, LearningDecision, PedagogicalObjective
from domain.decision.policies import DecisionConfiguration
from domain.decision.repositories import DecisionRepository


class LearnerJourneyService:
    def __init__(self, repository: DecisionRepository) -> None:
        self.repository = repository

    def save(self, journey: LearnerJourney) -> None:
        self.repository.save_objective(journey.learner_id, journey.current_objective)
        if journey.long_term_objective:
            self.repository.save_objective(journey.learner_id, journey.long_term_objective)
        if journey.exam_objective:
            self.repository.save_objective(journey.learner_id, journey.exam_objective)
        self.repository.save_journey(journey)

    def load(self, learner_id: int) -> LearnerJourney:
        return self.repository.load_journey(learner_id)

    def change_objective(self, journey: LearnerJourney, objective: PedagogicalObjective) -> LearnerJourney:
        from dataclasses import replace

        updated = replace(journey, current_objective=objective)
        self.save(updated)
        return updated


class PlanningService:
    schedule = staticmethod(next_window)
    build = staticmethod(build_plan)


class PrioritizationService:
    prioritize = staticmethod(prioritize)


class BlockageDetectionService:
    detect = staticmethod(detect_blockages)


class CandidateSelectorService:
    select = staticmethod(select_candidates)


class DecisionEngineService:
    def __init__(
        self, repository: DecisionRepository | None = None, configuration: DecisionConfiguration | None = None
    ) -> None:
        self.repository = repository
        self.configuration = configuration or DecisionConfiguration()

    def decide(self, context: DecisionContext, *, persist: bool = True) -> LearningDecision:
        decision = decide(context, self.configuration)
        if persist and self.repository is not None:
            self.repository.save_decision(context, decision)
        return decision
