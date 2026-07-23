from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime

from domain.decision.models import LearnerJourney, PedagogicalObjective, WeeklyAvailability
from domain.decision.policies import DecisionConfiguration
from domain.learning.enums import LearningPhase
from domain.onboarding.events import OnboardingEvent
from domain.onboarding.models import OnboardingRequest, OnboardingResult, OnboardingSummary
from domain.onboarding.policies import OnboardingConfiguration
from domain.onboarding.repositories import OnboardingRepository
from domain.onboarding.validators import validate_onboarding


class OnboardingValidationError(ValueError):
    pass


class OnboardingService:
    def __init__(self, repository: OnboardingRepository, config: OnboardingConfiguration | None = None) -> None:
        self.repository = repository
        self.config = config or OnboardingConfiguration()

    def complete(self, request: OnboardingRequest, now: datetime | None = None) -> OnboardingResult:
        now = now or datetime.now(UTC)
        validation = validate_onboarding(request, self.repository.known_subject_ids(), self.config, now.date())
        raw = json.dumps(asdict(request), default=str, sort_keys=True)
        context_hash = hashlib.sha256(raw.encode()).hexdigest()
        correlation_id = hashlib.sha256(f"{request.stable_id}:{context_hash}".encode()).hexdigest()[:24]
        if not validation.valid:
            raise OnboardingValidationError("; ".join(issue.code for issue in validation.issues))
        learner_id = request.profile.learner_id or 0
        priority = tuple(
            item.subject_id for item in request.subjects if item.priority and not item.temporarily_excluded
        )
        weak = tuple(
            item.subject_id for item in request.subjects if item.declared_weak and not item.temporarily_excluded
        )
        schedule = tuple(
            WeeklyAvailability(slot.weekday, slot.start_time, slot.duration_minutes)
            for slot in request.study.availability
        )
        goal = PedagogicalObjective(
            request.stable_id + ":goal", request.goal.objective, request.goal.objective.value, request.goal.target_date
        )
        phase = (
            LearningPhase.TRANSITION_PREPARATION
            if request.goal.objective.value == "preparation_next_grade"
            else LearningPhase.EXAM_PREPARATION
            if "preparation_" in request.goal.objective.value
            else LearningPhase.PRACTICE
        )
        journey = LearnerJourney(
            learner_id,
            request.current_grade,
            request.goal.target_grade,
            request.academic_year,
            goal,
            None,
            None,
            phase,
            request.goal.target_date,
            priority,
            weak,
            request.study.daily_duration_minutes,
            schedule,
            {"progressive": 2, "standard": 3, "challenge": 4}[request.study.difficulty.value],
            request.profile.creator_role.value == "parent",
            request.profile.creator_role.value == "student",
            request.study.rhythm,
            request.study.preferred_revision_days,
            request.study.vacation_mode,
            True,
            True,
            now,
        )
        strategy = DecisionConfiguration().objective_strategies[request.goal.objective]
        summary = OnboardingSummary(
            request.current_grade.label,
            request.goal.objective.value,
            request.goal.target_grade.label if request.goal.target_grade else None,
            request.goal.examination_code,
            request.goal.target_date,
            priority,
            weak,
            request.study.today_duration_minutes or request.study.daily_duration_minutes,
            strategy,
            tuple(issue.code for issue in validation.issues),
        )
        provisional = OnboardingResult(learner_id, journey, 1, summary, validation, correlation_id, context_hash, now)
        events = (
            OnboardingEvent(
                "OnboardingCompleted", learner_id or None, correlation_id, {"context_hash": context_hash}, now
            ),
        )
        return self.repository.complete(request, provisional, events)
