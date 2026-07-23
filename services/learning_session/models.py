"""DTOs crossing Learning Session application-service boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from domain.learning_session.models import AnswerType, AssessmentMethod


@dataclass(frozen=True, slots=True)
class ExecutableActivity:
    proposal_item_id: int
    content_id: int
    content_version_id: int
    title: str
    activity_type: str
    difficulty: int
    estimated_duration_seconds: int
    order: int
    skill_id: int
    approved: bool
    current_version: bool
    question_ids: tuple[int, ...]
    has_assessment: bool
    objective_compatible: bool = True
    prerequisites_satisfied: bool = True


@dataclass(frozen=True, slots=True)
class ExecutionProposal:
    proposal_id: int
    learner_id: int
    journey_version_id: int
    stable_id: str
    available_seconds: int
    objective: str
    decision_engine_version: str
    activities: tuple[ExecutableActivity, ...]
    absence_code: str | None = None


@dataclass(frozen=True, slots=True)
class QuestionView:
    question_id: int
    instructions: str
    context: str | None
    statement: str
    response_type: str
    options: tuple[tuple[str, str], ...]
    hints_available: int
    readonly: bool = False


@dataclass(frozen=True, slots=True)
class AssessmentRequest:
    answer_type: AnswerType
    raw_answer: Any
    expected_answer: Any
    method: AssessmentMethod
    tolerance: float = 0
    correct_options: tuple[str, ...] = ()
    partial_scoring: bool = True
    hint_penalties: tuple[float, ...] = ()
    manual_penalty: float = 0
    time_bonus: float = 0
    difficulty: int = 3
    current_mastery: float = 0
    previous_attempts: int = 0
    feedback: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class AssessmentResult:
    normalized_answer: Any
    raw_score: float
    final_score: float
    correct: bool
    hint_penalty: float
    time_bonus: float
    manual_penalty: float
    mastery_delta: float
    method: AssessmentMethod
    feedback: dict[str, Any]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SubmissionContext:
    learner_id: int
    skill_id: int
    activity_id: int
    question_id: int
    attempt_number: int
    occurred_at: datetime
    elapsed_ms: int
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RecoveryState:
    session_id: int
    learner_id: int
    activity_id: int | None
    question_id: int | None
    answer_id: int | None
    remaining_seconds: int
    restored_at: datetime
    checkpoint_id: int
    integrity_valid: bool


class ActivityExecutionStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    LOADING = "LOADING"
    READY = "READY"
    DISPLAYED = "DISPLAYED"
    ANSWERING = "ANSWERING"
    SUBMITTED = "SUBMITTED"
    ASSESSED = "ASSESSED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True, slots=True)
class ActivityExecutionState:
    activity_id: int
    status: ActivityExecutionStatus
    question_index: int = 0
    answer_locked: bool = False
