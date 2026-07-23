"""Immutable, persistence-independent models for the Learning Engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from domain.learning.enums import LearningPhase, MasteryLevel, PrerequisiteCondition, Trend


@dataclass(frozen=True, slots=True)
class AcademicYear:
    start_year: int
    end_year: int

    def __post_init__(self) -> None:
        if self.end_year != self.start_year + 1:
            raise ValueError("An academic year must span two consecutive years")


@dataclass(frozen=True, slots=True)
class GradeLevel:
    code: str
    rank: int
    label: str = ""


CurrentGradeLevel = GradeLevel
TargetGradeLevel = GradeLevel


@dataclass(frozen=True, slots=True)
class ExaminationObjective:
    code: str
    program_id: int
    examination_date: date | None = None


@dataclass(frozen=True, slots=True)
class CurriculumPosition:
    program_id: int
    covered_weight: float
    total_weight: float


@dataclass(frozen=True, slots=True)
class LearnerJourneyContext:
    learner_id: int
    current_grade: GradeLevel
    target_grade: GradeLevel | None
    academic_year: AcademicYear
    phase: LearningPhase
    program_id: int | None = None
    examination: ExaminationObjective | None = None


@dataclass(frozen=True, slots=True)
class CurriculumContext:
    skill_id: int
    subject_id: int
    program_id: int
    origin_grade: GradeLevel
    expected_difficulty: int = 3
    weight: float = 1.0
    required: bool = False


@dataclass(frozen=True, slots=True)
class LearnerAttempt:
    stable_id: str
    learner_id: int
    skill_id: int
    occurred_at: datetime
    correctness: float
    difficulty: int
    attempt_number: int = 1
    elapsed_seconds: float | None = None
    expected_seconds: float | None = None
    hints_used: int = 0
    solution_revealed: bool = False
    abandoned: bool = False
    declared_confidence: float | None = None
    is_revision: bool = False


@dataclass(frozen=True, slots=True)
class AttemptEvaluation:
    score: float
    quality_effect: float
    difficulty_effect: float
    time_effect: float
    hint_effect: float
    attempt_effect: float
    phase_effect: float
    confidence: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MasteryState:
    learner_id: int
    skill_id: int
    score: float = 0.0
    level: MasteryLevel = MasteryLevel.NOT_STARTED
    observations: int = 0
    successes: int = 0
    failures: int = 0
    success_streak: int = 0
    failure_streak: int = 0
    last_activity_at: datetime | None = None
    last_success_at: datetime | None = None
    last_difficulty: int = 1
    last_grade_code: str | None = None
    confidence: float = 0.0
    trend: Trend = Trend.STABLE
    stability: float = 0.0
    origin_grade_code: str | None = None
    prerequisite_for_future: bool = False


@dataclass(frozen=True, slots=True)
class MasteryUpdate:
    previous: MasteryState
    current: MasteryState
    signal: AttemptEvaluation
    delta: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MasterySnapshot:
    learner_id: int
    states: tuple[MasteryState, ...]
    calculated_at: datetime


@dataclass(frozen=True, slots=True)
class ForgettingAdjustment:
    observed_score: float
    adjusted_score: float
    degradation: float
    next_revision_at: datetime
    confidence: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DifficultyRecommendation:
    previous: int
    recommended: int
    reason: str
    signals: tuple[str, ...]
    positive_factors: tuple[str, ...]
    negative_factors: tuple[str, ...]
    confidence: float
    alerts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PrerequisiteStatus:
    skill_id: int
    condition: PrerequisiteCondition
    score: float | None
    confidence: float
    origin_grade_code: str | None = None


@dataclass(frozen=True, slots=True)
class ProgressState:
    scope_type: str
    scope_id: int
    score: float
    coverage: float
    confidence: float
    mastered: int
    fragile: int
    not_evaluated: int
    trend: Trend
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TransitionReadiness:
    current_grade_code: str
    target_grade_code: str
    score: float
    coverage: float
    confidence: float
    acquired_skills: tuple[int, ...]
    fragile_skills: tuple[int, ...]
    blocking_skills: tuple[int, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExamReadiness:
    examination_code: str
    score: float
    subject_scores: dict[int, float]
    coverage: float
    mastered_skills: tuple[int, ...]
    fragile_skills: tuple[int, ...]
    not_evaluated_skills: tuple[int, ...]
    confidence: float
    trend: Trend
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LearningSignal:
    code: str
    value: float
    explanation: str


@dataclass(frozen=True, slots=True)
class LearningEngineMetrics:
    duration_ms: int
    events_produced: int
    updates: int
    calculations: int
    errors: int = 0


@dataclass(frozen=True, slots=True)
class LearningEngineResult:
    attempt_id: str
    evaluation: AttemptEvaluation
    forgetting: ForgettingAdjustment
    mastery: MasteryUpdate
    difficulty: DifficultyRecommendation
    progress: ProgressState | None
    transition: TransitionReadiness | None
    exam: ExamReadiness | None
    events: tuple[Any, ...]
    metrics: LearningEngineMetrics
    already_processed: bool = False
