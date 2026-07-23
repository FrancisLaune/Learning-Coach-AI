"""Immutable evidence and analytical result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AnalyticsStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    EXCLUDED_INVALID_EVIDENCE = "EXCLUDED_INVALID_EVIDENCE"


class StrengthClassification(StrEnum):
    EMERGING = "EMERGING_STRENGTH"
    ESTABLISHED = "ESTABLISHED_STRENGTH"
    STABLE = "STABLE_STRENGTH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class WeaknessClassification(StrEnum):
    WATCH = "WATCH"
    FRAGILE = "FRAGILE"
    REMEDIATION_REQUIRED = "REMEDIATION_REQUIRED"
    REVISION_OVERDUE = "REVISION_OVERDUE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class DifficultyAction(StrEnum):
    DECREASE = "DECREASE"
    MAINTAIN = "MAINTAIN"
    INCREASE = "INCREASE"
    MIX = "MIX"
    REASSESS = "REASSESS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RevisionState(StrEnum):
    NOT_YET_DUE = "NOT_YET_DUE"
    DUE_SOON = "DUE_SOON"
    DUE = "DUE"
    OVERDUE = "OVERDUE"
    HIGH_PRIORITY_OVERDUE = "HIGH_PRIORITY_OVERDUE"
    REASSESSED = "REASSESSED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class EvidenceWindow:
    window_type: str
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("Evidence window end precedes start")


@dataclass(frozen=True, slots=True)
class LearningEvidence:
    learner_id: int
    session_id: int
    activity_id: int
    attempt_id: int
    assessment_id: int
    skill_id: int
    content_id: int
    content_version_id: int
    difficulty: int
    attempt_number: int
    raw_score: float
    final_score: float
    success: bool
    duration_seconds: float
    expected_duration_seconds: float
    hint_count: int
    hint_penalty: float
    submitted_at: datetime
    mastery_before: float
    mastery_after: float
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class AnalyticsMetrics:
    attempt_count: int
    assessed_attempt_count: int
    success_count: int
    failure_count: int
    accuracy_rate: float
    average_score: float
    median_score: float
    average_duration_seconds: float
    median_duration_seconds: float
    duration_ratio: float
    hint_usage_count: int
    hint_usage_rate: float
    retry_count: int
    first_attempt_success_rate: float
    distinct_sessions: int
    mastery_start: float
    mastery_end: float
    mastery_delta: float


@dataclass(frozen=True, slots=True)
class IndicatorResult:
    indicator_code: str
    learner_id: int
    scope_type: str
    scope_id: int
    window: EvidenceWindow
    value: float | str
    unit: str
    classification: str
    confidence_level: str
    evidence_count: int
    status: AnalyticsStatus
    calculation_version: str
    calculated_at: datetime
    explanation_code: str
    explanation_parameters: tuple[tuple[str, str], ...]
    source_references: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class DecisionEvidenceBundle:
    learner_id: int
    calculated_at: datetime
    weaknesses: tuple[IndicatorResult, ...]
    strengths: tuple[IndicatorResult, ...]
    difficulty_guidance: tuple[IndicatorResult, ...]
    revision_priorities: tuple[IndicatorResult, ...]
    recurring_errors: tuple[IndicatorResult, ...]
    evidence_quality: AnalyticsStatus
    calculation_version: str
