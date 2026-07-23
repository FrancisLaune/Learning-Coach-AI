from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from domain.decision.models import DecisionContext
from domain.onboarding.models import OnboardingResult
from services.decision import DecisionEngineService
from services.recommendation.candidate_service import ContentCandidateService
from services.recommendation.models import ApprovedContent, PersonalizedSessionProposal, SessionActivity


class PersonalizedSessionService:
    def __init__(
        self,
        candidate_service: ContentCandidateService | None = None,
        decision_repository: Any = None,
        learning_repository: Any = None,
        session_repository: Any = None,
    ) -> None:
        self.candidate_service = candidate_service or ContentCandidateService()
        self.decision_repository = decision_repository
        self.learning_repository = learning_repository
        self.session_repository = session_repository

    def generate(
        self, onboarding: OnboardingResult, contents: tuple[ApprovedContent, ...], now: datetime
    ) -> PersonalizedSessionProposal:
        mastery = self.learning_repository.load_all_mastery(onboarding.learner_id) if self.learning_repository else {}
        allowed_subjects = set(onboarding.journey.preferred_subjects) or None
        candidate_set = self.candidate_service.build(
            onboarding.journey, contents, mastery, now, allowed_subject_ids=allowed_subjects
        )
        budget = onboarding.summary.available_minutes
        stable = hashlib.sha256(
            f"{onboarding.context_hash}:{candidate_set.context_hash}:{now.isoformat()}".encode()
        ).hexdigest()[:24]
        if not candidate_set.candidates:
            proposal = PersonalizedSessionProposal(
                stable,
                onboarding.learner_id,
                onboarding.journey_version,
                None,
                now,
                budget,
                onboarding.summary.objective,
                None,
                (),
                candidate_set.report.warnings,
                0,
                (),
                ("Aucun contenu compatible; aucun contenu fictif généré.",),
                candidate_set.report.absence_code,
            )
        else:
            decision_candidates = self.candidate_service.to_decision_candidates(candidate_set)
            graph = {item.skill_id: item.prerequisite_ids for item in decision_candidates}
            ctx = DecisionContext(onboarding.journey, decision_candidates, mastery, graph, now)
            already_persisted = bool(
                self.session_repository
                and hasattr(self.session_repository, "has_proposal")
                and self.session_repository.has_proposal(stable)
            )
            decision_repository = None if already_persisted else self.decision_repository
            decision = DecisionEngineService(decision_repository).decide(ctx, persist=decision_repository is not None)
            by_id = {item.stable_id: item for item in candidate_set.candidates}
            activities = tuple(
                SessionActivity(
                    by_id[item.candidate_id],
                    item.duration_minutes,
                    item.difficulty,
                    item.order,
                    decision.explanation.why_now,
                )
                for item in decision.plan
                if item.candidate_id in by_id
            )
            proposal = PersonalizedSessionProposal(
                stable,
                onboarding.learner_id,
                onboarding.journey_version,
                decision.correlation_id,
                decision.selected.scheduled_for if decision.selected else now,
                budget,
                onboarding.summary.objective,
                decision.strategy.value,
                activities,
                (),
                decision.confidence,
                tuple(item.candidate_id for item in decision.plan[1:]),
                (decision.explanation.reason,),
                None,
                decision,
            )
        if self.session_repository:
            self.session_repository.save(candidate_set, proposal)
        return proposal
