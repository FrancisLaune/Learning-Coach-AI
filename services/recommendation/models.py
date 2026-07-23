from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.decision.enums import ActivityKind
from domain.decision.models import LearningDecision
from domain.learning.models import MasteryState


@dataclass(frozen=True, slots=True)
class ApprovedContent:
    content_id: int
    content_version_id: int
    title: str
    subject_id: int
    domain_id: int
    skill_id: int | None
    subskill_id: int | None
    program_id: int
    grade_code: str
    difficulty: int
    estimated_minutes: int
    activity_type: ActivityKind
    prerequisite_skill_ids: tuple[int, ...] = ()
    tags: tuple[str, ...] = ()
    version_status: str = "approved"
    active: bool = True
    objective_compatibility: tuple[str, ...] = ()
    exam_compatibility: tuple[str, ...] = ()
    transition_markers: tuple[str, ...] = ()
    revision_compatible: bool = True
    recently_used: bool = False


@dataclass(frozen=True, slots=True)
class LearningContentCandidate:
    content_id: int
    content_version_id: int
    stable_id: str
    activity_type: ActivityKind
    title: str
    subject_id: int
    domain_id: int
    skill_id: int
    subskill_id: int | None
    program_id: int
    grade_code: str
    difficulty: int
    estimated_minutes: int
    prerequisite_skill_ids: tuple[int, ...]
    tags: tuple[str, ...]
    objective_compatibility: tuple[str, ...]
    exam_compatibility: tuple[str, ...]
    transition_compatibility: bool
    revision_compatibility: bool
    source_status: str
    mastery: MasteryState | None
    revision_due: bool
    explanation_metadata: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateExclusion:
    content_id: int
    reason: str


@dataclass(frozen=True, slots=True)
class CandidateFilteringReport:
    initial_count: int
    retained_count: int
    excluded_count: int
    exclusions: tuple[CandidateExclusion, ...]
    absence_code: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateSet:
    stable_id: str
    candidates: tuple[LearningContentCandidate, ...]
    report: CandidateFilteringReport
    context_hash: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SessionActivity:
    candidate: LearningContentCandidate
    duration_minutes: int
    difficulty: int
    order: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PersonalizedSessionProposal:
    stable_id: str
    learner_id: int
    journey_version: int
    decision_correlation_id: str | None
    scheduled_for: datetime
    available_minutes: int
    objective: str
    strategy: str | None
    activities: tuple[SessionActivity, ...]
    warnings: tuple[str, ...]
    confidence: float
    alternatives: tuple[str, ...]
    summary_reasons: tuple[str, ...]
    absence_code: str | None = None
    decision: LearningDecision | None = None
