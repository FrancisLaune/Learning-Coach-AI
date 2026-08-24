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
class SubjectHomeworkAvailability:
    subject_id: int
    subject_code: str
    subject_label: str
    production_count: int
    eligible_count: int
    chapters_with_content: int
    chapters_total: int
    availability_status: str
    homework_status_label: str


@dataclass(frozen=True, slots=True)
class HomeworkContentSelection:
    content_ids: tuple[int, ...]
    requested_difficulty: int | None
    applied_difficulty: int | None
    difficulty_relaxed: bool


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
    assignment_kind: str = "HOMEWORK"

    def __post_init__(self) -> None:
        if not 1 <= self.exercise_count <= 100:
            raise ValueError("Le nombre d'exercices doit être compris entre 1 et 100.")
        if self.target_duration_minutes is not None and not 5 <= self.target_duration_minutes <= 240:
            raise ValueError("La durée doit être comprise entre 5 et 240 minutes.")
        if self.correction_policy not in {"IMMEDIATE", "AFTER_EACH_EXERCISE", "AFTER_SUBMISSION"}:
            raise ValueError("Politique de correction invalide.")
        if self.mode is AssignmentType.TARGETED and not (self.chapter_ids or self.skill_ids):
            raise ValueError("Un devoir ciblé nécessite au moins un chapitre ou une compétence.")

    @property
    def is_evaluation(self) -> bool:
        return self.assignment_kind.strip().upper() == ASSIGNMENT_KIND_EVALUATION


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
    correction_policy: str = "AFTER_SUBMISSION"
    assignment_kind: str = "HOMEWORK"

    @property
    def is_evaluation(self) -> bool:
        return self.assignment_kind.strip().upper() == ASSIGNMENT_KIND_EVALUATION


ASSIGNMENT_KIND_EVALUATION = "EVALUATION"
ASSIGNMENT_KIND_HOMEWORK = "HOMEWORK"
HOMEWORK_QUESTION_PRESETS: tuple[int, ...] = (10, 20, 30, 40)


@dataclass(frozen=True, slots=True)
class RuntimeExerciseCandidate:
    temporary_id: str
    title: str
    statement: str
    instructions: str
    expected_answer: str
    correction: str
    explanation: str
    solving_method: str
    hints: tuple[str, ...]
    skill_ids: tuple[int, ...]
    sub_skill_ids: tuple[int, ...]
    prerequisite_ids: tuple[int, ...]
    difficulty: int
    exercise_type: str
    estimated_duration: int
    common_mistakes: tuple[str, ...]
    success_criteria: tuple[str, ...]
    source: str
    generator_model: str | None
    prompt_template_version: str | None
    content_fingerprint: str
    validation_result: dict[str, object]
    generated_at: datetime
    correlation_id: str
    publication_status: str = "RUNTIME_ONLY"


@dataclass(frozen=True, slots=True)
class GeneratedHomeworkExerciseResult:
    exercise_id: str
    content_version_id: str | None
    subject_id: str
    chapter_id: str
    skill_id: str
    exercise_type: str
    difficulty: str
    statement: str
    expected_answer: object
    correction: str | None
    source: str
    provider: str | None
    model: str | None
    generation_metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class HomeworkGenerationResult:
    homework: HomeworkAssignment
    requested_count: int
    catalog_count: int
    ai_requested_count: int
    ai_accepted_count: int
    final_count: int
    degraded_mode: bool
    degradation_reason: str | None
    correlation_id: str
    runtime_exercise_ids: tuple[int, ...] = ()
    generated_exercises: tuple[GeneratedHomeworkExerciseResult, ...] = ()


@dataclass(frozen=True, slots=True)
class LearnerPedagogicalContext:
    learner_id: int
    grade_code: str
    subject_id: int
    subject_code: str
    chapter_ids: tuple[int, ...]
    skill_ids: tuple[int, ...]
    mastery_profile: str
    target_difficulty: int
    difficulty_band: tuple[int, int]
    recent_content_fingerprints: tuple[str, ...]
    recent_content_ids: tuple[int, ...]
    correlation_id: str


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
