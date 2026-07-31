"""DTOs for the Professor AI Core orchestrator (LCAI-0022A / 0022D)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from application.dto.student_guidance import AIAvailability, StudentDashboardSnapshot, WelcomeGuidance
from domain.unified_experience.models import HomeworkAssignment, HomeworkGenerationResult


class ProfessorOperatingMode(StrEnum):
    """Master Book modes: Professor / Companion / Manual."""

    PROFESSOR = "PROFESSOR"
    COMPANION = "COMPANION"
    MANUAL = "MANUAL"


@dataclass(frozen=True, slots=True)
class DecisionTraceEntry:
    """Decision breadcrumb — persisted to ai_decision_log (LCAI-0022D)."""

    step: str
    justification: str
    engine_version: str = "professor-ai-orchestrator-v1"
    objective: str | None = None
    candidates: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    deficit: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionLogRecord:
    """Persisted decision journal row."""

    id: int
    learner_id: int
    correlation_id: str
    operating_mode: str
    cycle_step: str
    objective: str | None
    justification: str
    engine_version: str
    candidates: tuple[str, ...]
    exclusions: tuple[str, ...]
    deficit: dict[str, object]
    context: dict[str, object]
    homework_id: int | None
    session_id: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SessionPlan:
    """Accueil + diagnostic overview + recommendations for the day."""

    learner_id: int
    mode: ProfessorOperatingMode
    welcome: WelcomeGuidance
    availability: AIAvailability
    dashboard: StudentDashboardSnapshot
    grade_label: str
    diagnostic_status: str
    recommendations: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    decision_trace: tuple[DecisionTraceEntry, ...]
    planned_at: datetime
    correlation_id: str = ""


@dataclass(frozen=True, slots=True)
class HomeworkCompositionResult:
    """Homework created under Professor AI orchestration."""

    mode: ProfessorOperatingMode
    homework: HomeworkAssignment
    generation: HomeworkGenerationResult | None
    decision_trace: tuple[DecisionTraceEntry, ...]
    correlation_id: str = ""


@dataclass(frozen=True, slots=True)
class SessionOpenResult:
    """Homework session materialized and ensured RUNNING."""

    mode: ProfessorOperatingMode
    homework: HomeworkAssignment
    session_id: int
    decision_trace: tuple[DecisionTraceEntry, ...]
    correlation_id: str = ""


@dataclass(frozen=True, slots=True)
class SessionClosureResult:
    """Post-session analysis + optional PI refresh."""

    mode: ProfessorOperatingMode
    learner_id: int
    session_id: int
    explanation_available: bool
    refresh_triggered: bool
    decision_trace: tuple[DecisionTraceEntry, ...]
    correlation_id: str = ""
