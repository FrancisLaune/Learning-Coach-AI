"""Structured, domain-safe Learning Session errors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SessionErrorCode(StrEnum):
    INVALID_ANSWER_FORMAT = "INVALID_ANSWER_FORMAT"
    INVALID_SESSION_STATE = "INVALID_SESSION_STATE"
    INVALID_ACTIVITY_STATE = "INVALID_ACTIVITY_STATE"
    SESSION_ACCESS_DENIED = "SESSION_ACCESS_DENIED"
    PARENT_ACCESS_DENIED = "PARENT_ACCESS_DENIED"
    ACTIVE_SESSION_EXISTS = "ACTIVE_SESSION_EXISTS"
    STATE_CONFLICT = "STATE_CONFLICT"
    ANSWER_ALREADY_SUBMITTED = "ANSWER_ALREADY_SUBMITTED"
    CONTENT_NOT_APPROVED = "CONTENT_NOT_APPROVED"
    CONTENT_VERSION_UNAVAILABLE = "CONTENT_VERSION_UNAVAILABLE"
    QUESTION_UNAVAILABLE = "QUESTION_UNAVAILABLE"
    ASSESSMENT_FAILED = "ASSESSMENT_FAILED"
    MASTERY_UPDATE_FAILED = "MASTERY_UPDATE_FAILED"
    CHECKPOINT_NOT_FOUND = "CHECKPOINT_NOT_FOUND"
    SESSION_NOT_RESUMABLE = "SESSION_NOT_RESUMABLE"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    FEATURE_DISABLED = "FEATURE_DISABLED"


@dataclass(frozen=True, slots=True)
class SessionApplicationError(Exception):
    code: SessionErrorCode
    user_message: str
    technical_message: str
    recoverable: bool
    retry_allowed: bool
    correlation_id: str
    recommended_action: str

    def __str__(self) -> str:
        return f"{self.code.value}: {self.user_message}"
