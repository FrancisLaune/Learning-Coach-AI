from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime

from domain.decision.models import CandidateActivity, LearnerJourney
from domain.learning.models import MasteryState
from domain.onboarding.policies import OnboardingConfiguration
from services.recommendation.models import (
    ApprovedContent,
    CandidateExclusion,
    CandidateFilteringReport,
    CandidateSet,
    LearningContentCandidate,
)

TRANSITION_MARKERS = {"transition_ready", "introductory", "prerequisite_bridge", "next_grade_preparation"}
GRADE_SEQUENCE = {"FR-5E": -1, "FR-4E": 0, "FR-3E": 1, "FR-2NDE": 2, "FR-1ERE": 3, "FR-TERM": 4}


class ContentCandidateService:
    def __init__(self, config: OnboardingConfiguration | None = None) -> None:
        self.config = config or OnboardingConfiguration()

    def build(
        self,
        journey: LearnerJourney,
        contents: tuple[ApprovedContent, ...],
        mastery: dict[int, MasteryState],
        now: datetime,
        allowed_subject_ids: set[int] | None = None,
    ) -> CandidateSet:
        exclusions: list[CandidateExclusion] = []
        retained: list[LearningContentCandidate] = []
        allowed_subject_ids = allowed_subject_ids or {c.subject_id for c in contents}
        for content in contents:
            reason = self._exclude(journey, content, allowed_subject_ids)
            if reason:
                exclusions.append(CandidateExclusion(content.content_id, reason))
                continue
            assert content.skill_id is not None
            raw = f"{content.content_id}:{content.content_version_id}:{journey.current_objective.id}:{content.skill_id}"
            stable = hashlib.sha256(raw.encode()).hexdigest()[:24]
            state = mastery.get(content.skill_id)
            retained.append(
                LearningContentCandidate(
                    content.content_id,
                    content.content_version_id,
                    stable,
                    content.activity_type,
                    content.title,
                    content.subject_id,
                    content.domain_id,
                    content.skill_id,
                    content.subskill_id,
                    content.program_id,
                    content.grade_code,
                    content.difficulty,
                    content.estimated_minutes,
                    content.prerequisite_skill_ids,
                    content.tags,
                    content.objective_compatibility,
                    content.exam_compatibility,
                    bool(TRANSITION_MARKERS & set(content.transition_markers)),
                    content.revision_compatible,
                    content.version_status,
                    state,
                    bool(state and state.last_activity_at and (now - state.last_activity_at).days >= 30),
                    ("approved_content", "learning_signals_reused"),
                )
            )
        retained.sort(key=lambda item: (item.subject_id, item.skill_id, item.content_version_id))
        retained = retained[: self.config.maximum_candidates]
        absence = self._absence(contents, exclusions, retained)
        report = CandidateFilteringReport(len(contents), len(retained), len(exclusions), tuple(exclusions), absence)
        snapshot = json.dumps(
            {"journey": journey.current_objective.id, "candidates": [asdict(c) for c in retained]},
            default=str,
            sort_keys=True,
        )
        context_hash = hashlib.sha256(snapshot.encode()).hexdigest()
        return CandidateSet(context_hash[:24], tuple(retained), report, context_hash, now)

    def _exclude(self, journey: LearnerJourney, content: ApprovedContent, allowed_subject_ids: set[int]) -> str | None:
        if content.version_status != "approved":
            return "NOT_APPROVED"
        if not content.active:
            return "NOT_ACTIVE"
        if content.subject_id not in allowed_subject_ids:
            return "NO_CONTENT_FOR_SUBJECT"
        if content.skill_id is None:
            return "NO_CONTENT_FOR_SKILL"
        if not 1 <= content.difficulty <= 5:
            return "DIFFICULTY_INCOMPATIBLE"
        if content.estimated_minutes > journey.daily_duration_minutes:
            return "NO_CONTENT_WITHIN_DURATION"
        objective = journey.current_objective.kind.value
        if content.objective_compatibility and objective not in content.objective_compatibility:
            return "NO_CONTENT_FOR_OBJECTIVE"
        if content.grade_code == journey.current_grade.code:
            return None
        if journey.target_grade and content.grade_code == journey.target_grade.code:
            return (
                None if TRANSITION_MARKERS & set(content.transition_markers) else "NEXT_GRADE_NOT_EXPLICITLY_COMPATIBLE"
            )
        content_position = GRADE_SEQUENCE.get(content.grade_code)
        current_position = GRADE_SEQUENCE.get(journey.current_grade.code)
        is_prior_grade = (
            content_position is not None and current_position is not None and content_position < current_position
        )
        if is_prior_grade and ("remediation" in content.tags or "prerequisite_bridge" in content.transition_markers):
            return None
        return "NO_CONTENT_FOR_GRADE"

    @staticmethod
    def _absence(
        contents: tuple[ApprovedContent, ...],
        exclusions: list[CandidateExclusion],
        retained: list[LearningContentCandidate],
    ) -> str | None:
        if retained:
            return None
        if not contents:
            return "NO_APPROVED_CONTENT"
        reasons = {item.reason for item in exclusions}
        for code in (
            "NOT_APPROVED",
            "NO_CONTENT_FOR_GRADE",
            "NO_CONTENT_FOR_SUBJECT",
            "NO_CONTENT_FOR_SKILL",
            "NO_CONTENT_FOR_OBJECTIVE",
            "NO_CONTENT_WITHIN_DURATION",
            "BLOCKED_BY_PREREQUISITE",
        ):
            if code in reasons:
                return code
        return "NO_APPROVED_CONTENT"

    @staticmethod
    def to_decision_candidates(candidate_set: CandidateSet) -> tuple[CandidateActivity, ...]:
        return tuple(
            CandidateActivity(
                c.stable_id,
                c.skill_id,
                c.subject_id,
                c.activity_type,
                c.estimated_minutes,
                c.difficulty,
                c.mastery,
                c.prerequisite_skill_ids,
                c.revision_due,
            )
            for c in candidate_set.candidates
        )
