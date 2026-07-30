"""LCAI-0019 presentation DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class SkillInsightDTO:
    skill_id: str
    skill_code: str
    label: str
    mastery_score: float
    confidence_score: float
    status: str
    priority: int
    reason: str


@dataclass(frozen=True, slots=True)
class RecommendationDTO:
    recommendation_type: str
    priority: int
    reason: str
    skill_label: str
    chapter_label: str
    activity_type: str
    target_duration_minutes: int
    due_at: datetime | None
    status: str
    decision_version: str


@dataclass(frozen=True, slots=True)
class LearningPlanDTO:
    highlights: tuple[str, ...]
    session_count: int
    horizon_days: int


@dataclass(frozen=True, slots=True)
class PedagogicalDashboardDTO:
    student_id: str
    pathway_code: str
    readiness_status: str
    readiness_score: float
    coverage_score: float
    confidence_score: float
    strong_skills: tuple[SkillInsightDTO, ...]
    fragile_skills: tuple[SkillInsightDTO, ...]
    critical_gaps: tuple[SkillInsightDTO, ...]
    recommendations: tuple[RecommendationDTO, ...]
    current_plan: LearningPlanDTO | None
    progression_7d: float | None
    progression_30d: float | None
    last_computed_at: datetime
    data_sources: tuple[str, ...]
    pedagogical_message: str


@dataclass(frozen=True, slots=True)
class DiagnosticItemDTO:
    run_id: str
    exercise_id: str
    skill_id: str
    chapter_id: str
    prompt: str
    exercise_type: str
    response_type: str
    payload: dict[str, Any]
    sequence_number: int


@dataclass(frozen=True, slots=True)
class DiagnosticRunDTO:
    run_id: str
    student_id: str
    pathway_code: str
    status: str
    current_item: DiagnosticItemDTO | None
    questions_answered: int
    target_confidence: float


@dataclass(frozen=True, slots=True)
class DiagnosticAnswerResultDTO:
    correct: bool
    normalized_score: float
    feedback: str
    mastery_delta: float
    confidence_delta: float
    should_continue: bool
    next_item: DiagnosticItemDTO | None


@dataclass(frozen=True, slots=True)
class DiagnosticSummaryDTO:
    run_id: str
    student_id: str
    pathway_code: str
    status: str
    questions_answered: int
    correct_answers: int
    readiness_score: float
    confidence_score: float
    weak_skills: tuple[str, ...]
    strong_skills: tuple[str, ...]
    completed_at: datetime
    stop_reason: str


@dataclass(frozen=True, slots=True)
class PostSessionRefreshResult:
    learner_id: int
    session_id: int
    pathway_code: str
    status: str
    readiness_score: float
    recommendation_count: int
    cache_version: str
    correlation_id: str
    already_processed: bool
