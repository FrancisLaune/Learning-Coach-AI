"""Strongly typed, persistence-independent Learning Session entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any


class SessionStatus(StrEnum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class ActivityStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class AnswerType(StrEnum):
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    TEXT = "TEXT"
    SHORT_TEXT = "SHORT_TEXT"
    LONG_TEXT = "LONG_TEXT"
    BOOLEAN = "BOOLEAN"
    FRACTION = "FRACTION"
    MCQ_SINGLE = "MCQ_SINGLE"
    MCQ_MULTI = "MCQ_MULTI"
    MATCHING = "MATCHING"
    ORDERING = "ORDERING"
    FORMULA = "FORMULA"


class AssessmentMethod(StrEnum):
    EXACT_MATCH = "EXACT_MATCH"
    NUMERIC_EQUALITY = "NUMERIC_EQUALITY"
    NUMERIC_TOLERANCE = "NUMERIC_TOLERANCE"
    FRACTION_SIMPLIFICATION = "FRACTION_SIMPLIFICATION"
    BOOLEAN = "BOOLEAN"
    MCQ = "MCQ"
    MATCHING = "MATCHING"
    ORDERING = "ORDERING"
    FORMULA = "FORMULA"


SESSION_TRANSITIONS = {
    SessionStatus.CREATED: {SessionStatus.READY, SessionStatus.FAILED, SessionStatus.ARCHIVED},
    SessionStatus.READY: {SessionStatus.RUNNING, SessionStatus.ABANDONED, SessionStatus.FAILED},
    SessionStatus.RUNNING: {
        SessionStatus.PAUSED,
        SessionStatus.COMPLETED,
        SessionStatus.ABANDONED,
        SessionStatus.FAILED,
    },
    SessionStatus.PAUSED: {SessionStatus.RUNNING, SessionStatus.ABANDONED, SessionStatus.FAILED},
    SessionStatus.COMPLETED: {SessionStatus.ARCHIVED},
    SessionStatus.ABANDONED: {SessionStatus.ARCHIVED},
    SessionStatus.FAILED: {SessionStatus.ARCHIVED},
    SessionStatus.ARCHIVED: set(),
}


def _percentage(value: float, field: str) -> None:
    if not 0 <= value <= 100:
        raise ValueError(f"{field} must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class LearningSession:
    session_id: int
    learner_id: int
    journey_version_id: int
    recommendation_id: int
    status: SessionStatus
    creation_time: datetime
    planned_duration_seconds: int
    application_version: str
    curriculum_version: str
    content_version: str
    decision_engine_version: str
    assessment_engine_version: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    actual_duration_seconds: int = 0
    estimated_mastery_gain: float = 0
    completion_rate: float = 0
    session_score: float = 0
    session_version: int = 1

    def __post_init__(self) -> None:
        if self.planned_duration_seconds < 0 or self.actual_duration_seconds < 0:
            raise ValueError("Session durations must be non-negative")
        if not -100 <= self.estimated_mastery_gain <= 100:
            raise ValueError("estimated_mastery_gain must be between -100 and 100")
        _percentage(self.completion_rate, "completion_rate")
        _percentage(self.session_score, "session_score")
        if self.session_version < 1:
            raise ValueError("session_version must be positive")

    def transition(self, target: SessionStatus, at: datetime) -> LearningSession:
        if target not in SESSION_TRANSITIONS[self.status]:
            raise ValueError(f"Invalid session transition: {self.status.value} -> {target.value}")
        return replace(
            self,
            status=target,
            start_time=at if target is SessionStatus.RUNNING and self.start_time is None else self.start_time,
            end_time=at
            if target in {SessionStatus.COMPLETED, SessionStatus.ABANDONED, SessionStatus.FAILED}
            else self.end_time,
        )


@dataclass(frozen=True, slots=True)
class SessionActivity:
    activity_id: int
    session_id: int
    content_id: int
    content_version_id: int
    activity_order: int
    activity_type: str
    difficulty: int
    estimated_duration_seconds: int
    status: ActivityStatus = ActivityStatus.NOT_STARTED
    score: float = 0
    mastery_delta: float = 0

    def __post_init__(self) -> None:
        if self.activity_order < 1 or self.estimated_duration_seconds < 0:
            raise ValueError("Activity order must be positive and duration non-negative")
        if not 1 <= self.difficulty <= 5:
            raise ValueError("Activity difficulty must be between 1 and 5")
        _percentage(self.score, "score")
        if not -100 <= self.mastery_delta <= 100:
            raise ValueError("mastery_delta must be between -100 and 100")


@dataclass(frozen=True, slots=True)
class StudentAnswer:
    answer_id: int
    activity_id: int
    question_id: int
    attempt_number: int
    answer_type: AnswerType
    raw_answer: Any
    normalized_answer: Any
    submission_time: datetime
    time_spent_ms: int
    draft: bool
    validated: bool
    idempotency_key: str

    def __post_init__(self) -> None:
        if self.attempt_number < 1 or self.time_spent_ms < 0:
            raise ValueError("Attempt number must be positive and time non-negative")
        if not self.idempotency_key.strip():
            raise ValueError("Answer idempotency key is required")


@dataclass(frozen=True, slots=True)
class Assessment:
    assessment_id: int
    answer_id: int
    correct: bool
    score: float
    penalty: float
    hint_penalty: float
    time_penalty: float
    assessment_method: AssessmentMethod
    feedback_generated: dict[str, Any]
    assessment_engine_version: str

    def __post_init__(self) -> None:
        _percentage(self.score, "score")
        if min(self.penalty, self.hint_penalty, self.time_penalty) < 0:
            raise ValueError("Assessment penalties must be non-negative")


@dataclass(frozen=True, slots=True)
class Attempt:
    attempt_id: int
    learner_id: int
    activity_id: int
    answer_id: int
    assessment_id: int
    success: bool
    mastery_before: float
    mastery_after: float
    duration_ms: int
    hint_count: int

    def __post_init__(self) -> None:
        if not 0 <= self.mastery_before <= 1 or not 0 <= self.mastery_after <= 1:
            raise ValueError("Mastery values must be between 0 and 1")
        if self.duration_ms < 0 or self.hint_count < 0:
            raise ValueError("Attempt duration and hint count must be non-negative")


@dataclass(frozen=True, slots=True)
class HintUsage:
    hint_usage_id: int
    activity_id: int
    hint_id: int
    hint_number: int
    display_time: datetime
    penalty: float


@dataclass(frozen=True, slots=True)
class SessionEvent:
    event_id: int
    session_id: int
    event_type: str
    timestamp: datetime
    payload: dict[str, Any]
    correlation_id: str


@dataclass(frozen=True, slots=True)
class SessionCheckpoint:
    checkpoint_id: int
    session_id: int
    activity_id: int | None
    current_question_id: int | None
    remaining_time_seconds: int
    last_answer_id: int | None
    autosave_timestamp: datetime


@dataclass(frozen=True, slots=True)
class SessionSummary:
    summary_id: int
    session_id: int
    completion_rate: float
    average_time_ms: float
    total_score: float
    mastery_gain: float
    strengths: tuple[int, ...]
    weaknesses: tuple[int, ...]
    recommended_next_session: str | None

    def __post_init__(self) -> None:
        _percentage(self.completion_rate, "completion_rate")
        _percentage(self.total_score, "total_score")
        if self.average_time_ms < 0 or not -100 <= self.mastery_gain <= 100:
            raise ValueError("Summary values are outside allowed ranges")
