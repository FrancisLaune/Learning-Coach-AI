"""Immutable models for journey planning and deterministic decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time

from domain.decision.enums import ActivityKind, ObjectiveKind, PedagogicalStrategy, PriorityBand
from domain.learning.enums import LearningPhase
from domain.learning.models import AcademicYear, ExamReadiness, GradeLevel, MasteryState, TransitionReadiness


@dataclass(frozen=True, slots=True)
class WeeklyAvailability:
    weekday: int
    start_time: time
    duration_minutes: int


@dataclass(frozen=True, slots=True)
class PedagogicalObjective:
    id: str
    kind: ObjectiveKind
    title: str
    target_date: date | None
    priority_weight: float = 1.0
    active: bool = True


@dataclass(frozen=True, slots=True)
class LearnerJourney:
    learner_id: int
    current_grade: GradeLevel
    target_grade: GradeLevel | None
    academic_year: AcademicYear
    current_objective: PedagogicalObjective
    long_term_objective: PedagogicalObjective | None
    exam_objective: PedagogicalObjective | None
    learning_phase: LearningPhase
    target_date: date | None
    preferred_subjects: tuple[int, ...] = ()
    weak_subjects: tuple[int, ...] = ()
    daily_duration_minutes: int = 30
    weekly_schedule: tuple[WeeklyAvailability, ...] = ()
    difficulty_preference: int = 3
    parent_mode: bool = False
    student_mode: bool = True
    learning_rhythm: str = "balanced"
    preferred_revision_days: tuple[int, ...] = ()
    vacation_mode: bool = False
    holiday_planning: bool = True
    transition_planning: bool = True
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CandidateActivity:
    id: str
    skill_id: int
    subject_id: int
    kind: ActivityKind
    estimated_minutes: int
    difficulty: int
    mastery: MasteryState | None = None
    prerequisite_ids: tuple[int, ...] = ()
    revision_due: bool = False
    last_practiced_at: datetime | None = None
    eligible: bool = True


@dataclass(frozen=True, slots=True)
class Blockage:
    skill_id: int
    blocking_skill_ids: tuple[int, ...]
    chain: tuple[int, ...]
    severity: float
    reason: str


@dataclass(frozen=True, slots=True)
class PriorityScore:
    candidate_id: str
    band: PriorityBand
    score: float
    reasons: tuple[str, ...]
    rules: tuple[str, ...]
    prerequisite_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ScheduledActivity:
    candidate_id: str
    skill_id: int
    subject_id: int
    scheduled_for: datetime
    duration_minutes: int
    difficulty: int
    order: int


@dataclass(frozen=True, slots=True)
class DecisionExplanation:
    reason: str
    why_now: tuple[str, ...]
    why_difficulty: tuple[str, ...]
    why_subject: tuple[str, ...]
    why_duration: tuple[str, ...]
    rules: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LearningDecision:
    correlation_id: str
    learner_id: int
    strategy: PedagogicalStrategy
    objective_id: str
    selected: ScheduledActivity | None
    plan: tuple[ScheduledActivity, ...]
    priorities: tuple[PriorityScore, ...]
    blockages: tuple[Blockage, ...]
    explanation: DecisionExplanation
    confidence: float
    created_at: datetime
    context_hash: str
    engine_version: str = "decision-v1"
    ruleset_version: str = "rules-v1"


@dataclass(frozen=True, slots=True)
class DecisionContext:
    journey: LearnerJourney
    candidates: tuple[CandidateActivity, ...]
    mastery: dict[int, MasteryState]
    prerequisite_graph: dict[int, tuple[int, ...]]
    now: datetime
    transition: TransitionReadiness | None = None
    exam: ExamReadiness | None = None
    recent_subject_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class TodayPlan:
    date: date
    activities: tuple[ScheduledActivity, ...]
    total_minutes: int


@dataclass(frozen=True, slots=True)
class WeeklyPlan:
    week_start: date
    activities: tuple[ScheduledActivity, ...]


@dataclass(frozen=True, slots=True)
class CriticalSkills:
    blockages: tuple[Blockage, ...]
    fragile_skill_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class UpcomingExam:
    objective: PedagogicalObjective | None
    readiness: ExamReadiness | None


@dataclass(frozen=True, slots=True)
class JourneyProgress:
    objective_id: str
    completed_ratio: float
    confidence: float


@dataclass(frozen=True, slots=True)
class ReadinessTimeline:
    points: tuple[tuple[date, float], ...] = field(default_factory=tuple)
