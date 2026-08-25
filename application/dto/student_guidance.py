"""LCAI-0020 — DTOs for student guidance and dashboard snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class GuidanceSource(StrEnum):
    AI = "AI"
    DETERMINISTIC = "DETERMINISTIC"


class MasteryBand(StrEnum):
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    FRAGILE = "FRAGILE"
    UNEVALUATED = "UNEVALUATED"
    TO_REVISE = "TO_REVISE"


MASTERY_BAND_LABELS: dict[MasteryBand, str] = {
    MasteryBand.VERY_HIGH: "Très bien maîtrisé",
    MasteryBand.HIGH: "Bien maîtrisé",
    MasteryBand.MEDIUM: "Moyennement maîtrisé",
    MasteryBand.FRAGILE: "Peu maîtrisé / fragile",
    MasteryBand.UNEVALUATED: "À découvrir / données insuffisantes",
    MasteryBand.TO_REVISE: "À réviser",
}


class AIAvailabilityMode(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class AIAvailability:
    mode: AIAvailabilityMode
    platform_enabled: bool
    learner_feature_enabled: bool
    provider_configured: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class HomeworkSummaryItem:
    homework_id: int
    subject_label: str
    status: str
    due_at: datetime | None
    exercise_count: int
    target_duration_minutes: int | None
    is_evaluation: bool = False


@dataclass(frozen=True, slots=True)
class MasterySnapshotItem:
    skill_id: int
    label: str
    score: float
    level: str
    trend: str
    band: MasteryBand
    band_label: str
    subject_label: str = ""
    chapter_label: str = ""


@dataclass(frozen=True, slots=True)
class RevisionPriority:
    subject_label: str
    skill_label: str
    reason: str
    priority: int
    estimated_minutes: int
    action_label: str
    homework_id: int | None = None
    skill_id: int | None = None


@dataclass(frozen=True, slots=True)
class EvaluationProgressItem:
    homework_id: int
    subject_label: str
    exercise_count: int
    overall_score: float | None
    needs_retake: bool
    session_id: int | None = None


@dataclass(frozen=True, slots=True)
class HomeAssignmentCard:
    homework_id: int
    subject_label: str
    status: str
    is_evaluation: bool
    exercise_count: int
    session_id: int | None
    score_percent: float | None
    score_out_of_20: float | None
    can_delete: bool
    can_open: bool
    can_retake: bool
    can_view_corrections: bool


@dataclass(frozen=True, slots=True)
class SubjectHomeBoard:
    subject_label: str
    average_out_of_20: float | None
    assignment_count: int
    assignments: tuple[HomeAssignmentCard, ...]


@dataclass(frozen=True, slots=True)
class StudentHomeContext:
    learner_id: int
    display_name: str
    homework_todo: tuple[HomeworkSummaryItem, ...]
    homework_overdue: tuple[HomeworkSummaryItem, ...]
    homework_recent: tuple[HomeworkSummaryItem, ...]
    mastery: tuple[MasterySnapshotItem, ...]
    fragile_skills: tuple[MasterySnapshotItem, ...]
    strong_skills: tuple[MasterySnapshotItem, ...]
    revision_priorities: tuple[RevisionPriority, ...]
    recent_score: str | None
    success_rate: str | None
    objective: str
    next_revision: datetime | None
    evaluation_progress: tuple[EvaluationProgressItem, ...] = ()
    overall_average_out_of_20: float | None = None
    subject_boards: tuple[SubjectHomeBoard, ...] = ()


@dataclass(frozen=True, slots=True)
class WelcomeGuidance:
    source: GuidanceSource
    greeting: str
    primary_action: str
    secondary_actions: tuple[str, ...] = ()
    mission_label: str = ""
    degraded_notice: str = ""


@dataclass(frozen=True, slots=True)
class StudentDashboardSnapshot:
    context: StudentHomeContext
    welcome: WelcomeGuidance
    availability: AIAvailability
    mastery_by_band: dict[str, tuple[MasterySnapshotItem, ...]] = field(default_factory=dict)
    recommendations: tuple[RevisionPriority, ...] = ()


@dataclass(frozen=True, slots=True)
class HomeworkGuidanceContext:
    homework_id: int
    subject_label: str
    objective: str
    estimated_minutes: int | None
    exercise_count: int
    status: str
    advice_before: str


@dataclass(frozen=True, slots=True)
class HomeworkGuidanceResponse:
    source: GuidanceSource
    phase: str
    message: str
    help_level: int | None = None
    suggested_actions: tuple[str, ...] = ()
    degraded_notice: str = ""


@dataclass(frozen=True, slots=True)
class ResultExplanationContext:
    homework_id: int
    subject_label: str
    score_summary: str
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    deterministic_recommendation: str


@dataclass(frozen=True, slots=True)
class RevisionGuidanceContext:
    priority: RevisionPriority
    source: GuidanceSource
    message: str
    degraded_notice: str = ""
