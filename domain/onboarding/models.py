from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from domain.decision.enums import ObjectiveKind, PedagogicalStrategy
from domain.decision.models import LearnerJourney
from domain.learning.models import AcademicYear, GradeLevel
from domain.onboarding.enums import (
    CompatibilityStatus,
    ContentFormat,
    CreatorRole,
    DifficultyPreference,
    StudyBalance,
    ValidationSeverity,
)


@dataclass(frozen=True, slots=True)
class LearnerProfile:
    stable_id: str
    display_name: str
    creator_role: CreatorRole
    locale: str = "fr-FR"
    timezone: str = "Europe/Paris"
    birth_date: date | None = None
    learner_id: int | None = None


@dataclass(frozen=True, slots=True)
class AvailabilitySlot:
    weekday: int
    duration_minutes: int
    start_time: time = time(17)


@dataclass(frozen=True, slots=True)
class SubjectPreference:
    subject_id: int
    priority: bool = False
    declared_weak: bool = False
    temporarily_excluded: bool = False


@dataclass(frozen=True, slots=True)
class StudyPreferences:
    daily_duration_minutes: int = 30
    availability: tuple[AvailabilitySlot, ...] = ()
    preferred_revision_days: tuple[int, ...] = ()
    difficulty: DifficultyPreference = DifficultyPreference.STANDARD
    rhythm: str = "regular"
    balance: StudyBalance = StudyBalance.BALANCED
    preferred_format: ContentFormat = ContentFormat.MIXED
    vacation_mode: bool = False
    today_duration_minutes: int | None = None


@dataclass(frozen=True, slots=True)
class LearnerGoalConfiguration:
    objective: ObjectiveKind
    target_grade: GradeLevel | None = None
    examination_code: str | None = None
    target_date: date | None = None


@dataclass(frozen=True, slots=True)
class OnboardingRequest:
    stable_id: str
    profile: LearnerProfile
    academic_year: AcademicYear
    current_grade: GradeLevel
    goal: LearnerGoalConfiguration
    subjects: tuple[SubjectPreference, ...]
    study: StudyPreferences
    changed_by_role: CreatorRole
    change_reason: str | None = None


@dataclass(frozen=True, slots=True)
class GoalCompatibility:
    grade_code: str
    objective: ObjectiveKind
    status: CompatibilityStatus
    target_grade_required: bool = False
    examination_required: bool = False


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: ValidationSeverity
    field: str
    message: str
    rule: str
    suggestion: str | None = None


@dataclass(frozen=True, slots=True)
class OnboardingValidationResult:
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.severity is ValidationSeverity.ERROR for issue in self.issues)


@dataclass(frozen=True, slots=True)
class OnboardingSummary:
    grade: str
    objective: str
    target_grade: str | None
    examination: str | None
    target_date: date | None
    priority_subject_ids: tuple[int, ...]
    weak_subject_ids: tuple[int, ...]
    available_minutes: int
    strategy: PedagogicalStrategy
    constraints: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OnboardingResult:
    learner_id: int
    journey: LearnerJourney
    journey_version: int
    summary: OnboardingSummary
    validation: OnboardingValidationResult
    correlation_id: str
    context_hash: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OnboardingState:
    request: OnboardingRequest
    completed_steps: tuple[str, ...] = ()


OnboardingStep = str
