"""Typed product contracts for homework, coaching and programme approval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class AssignmentType(StrEnum):
    AI_RECOMMENDED = "AI_RECOMMENDED"
    TARGETED = "TARGETED"
    GLOBAL_SUBJECT = "GLOBAL_SUBJECT"
    FREE_REVISION = "FREE_REVISION"


class AssignmentStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class DifficultyMode(StrEnum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    ADAPTIVE = "ADAPTIVE"


@dataclass(frozen=True, slots=True)
class LearnerManagementProfile:
    learner_id: int
    external_ref: str
    first_name: str
    last_name: str | None
    birth_date: date | None
    current_grade_id: int
    target_grade_id: int | None
    school_year: str
    objective: str
    subject_ids: tuple[int, ...]
    daily_duration_minutes: int
    availability: tuple[tuple[int, int, str], ...]
    difficulty_preference: int
    preferred_formats: tuple[str, ...]
    error_help_preference: str
    diagnostic_status: str
    email: str | None = None

    @property
    def age(self) -> int | None:
        if self.birth_date is None:
            return None
        today = date.today()
        return (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )


@dataclass(frozen=True, slots=True)
class HomeworkRequest:
    learner_id: int
    assigned_by_type: str
    assigned_by_ref: str
    mode: AssignmentType
    subject_id: int
    grade_level_id: int | None
    chapter_ids: tuple[int, ...]
    skill_ids: tuple[int, ...]
    difficulty: DifficultyMode
    exercise_count: int
    target_duration_minutes: int | None
    due_at: datetime | None
    correction_policy: str = "AFTER_SUBMISSION"

    def __post_init__(self) -> None:
        if not 1 <= self.exercise_count <= 100:
            raise ValueError("Le nombre d'exercices doit être compris entre 1 et 100.")
        if self.target_duration_minutes is not None and not 5 <= self.target_duration_minutes <= 240:
            raise ValueError("La durée doit être comprise entre 5 et 240 minutes.")
        if self.mode is AssignmentType.TARGETED and not (self.chapter_ids or self.skill_ids):
            raise ValueError("Un devoir ciblé nécessite au moins un chapitre ou une compétence.")


@dataclass(frozen=True, slots=True)
class HomeworkAssignment:
    homework_id: int
    learner_id: int
    mode: AssignmentType
    status: AssignmentStatus
    subject_id: int | None
    subject_label: str
    difficulty: DifficultyMode
    exercise_count: int
    target_duration_minutes: int | None
    due_at: datetime | None
    selected_content_ids: tuple[int, ...]
    session_id: int | None
    assigned_by_type: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CoachAdvice:
    title: str
    summary: str
    reason_codes: tuple[str, ...]
    evidence_references: tuple[str, ...]
    expected_benefit: str
    priority: int


@dataclass(frozen=True, slots=True)
class ProgrammeChange:
    proposal_id: int
    learner_id: int
    level: int
    change_type: str
    status: str
    current_state: dict[str, object]
    proposed_state: dict[str, object]
    reason_codes: tuple[str, ...]
    evidence_references: tuple[str, ...]
    expected_benefit: str
    proposed_at: datetime
