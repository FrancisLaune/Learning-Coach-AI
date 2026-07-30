"""Domain models for pedagogical intelligence V1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ReadinessPathCode = Literal["CM1_TO_CM2", "FR_4E_TO_3E"]
ReadinessBand = Literal["READY", "ALMOST_READY", "NOT_READY"]
DiagnosticRunStatus = Literal["IN_PROGRESS", "COMPLETED", "ABANDONED"]


@dataclass(frozen=True, slots=True)
class ReadinessPathDefinition:
    code: ReadinessPathCode
    label: str
    source_grade_code: str
    target_grade_code: str
    objective_ref: str


@dataclass(frozen=True, slots=True)
class ReadinessSnapshot:
    path_code: ReadinessPathCode
    source_grade_code: str
    target_grade_code: str
    score: float
    coverage: float
    confidence: float
    band: ReadinessBand
    acquired_count: int
    fragile_count: int
    blocking_count: int
    explanations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MasterySummaryItem:
    skill_id: int
    label: str
    score: float
    level: str
    trend: str


@dataclass(frozen=True, slots=True)
class DiagnosticQuestion:
    run_id: int
    skill_id: int
    skill_label: str
    question_index: int
    remaining_estimate: int


@dataclass(frozen=True, slots=True)
class DiagnosticRun:
    id: int
    learner_id: int
    path_code: ReadinessPathCode
    status: DiagnosticRunStatus
    questions_asked: int
    target_skill_ids: tuple[int, ...]
    assessed_skill_ids: tuple[int, ...]
    current_skill_id: int | None
    confidence_by_skill: dict[int, float]
    started_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class PlannerHighlight:
    label: str
    scheduled_for: datetime | None
    duration_minutes: int
    reason: str


@dataclass(frozen=True, slots=True)
class PedagogicalIntelligenceOverview:
    learner_id: int
    display_name: str
    current_grade_code: str
    current_grade_label: str
    diagnostic_status: str
    active_path: ReadinessPathDefinition | None
    readiness: ReadinessSnapshot | None
    mastery: tuple[MasterySummaryItem, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    planner_highlights: tuple[PlannerHighlight, ...]
    recommendations: tuple[str, ...]
    active_diagnostic: DiagnosticRun | None
