"""Read-only application service for student and parent experiences."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Metric:
    label: str
    value: str
    help_text: str = ""


@dataclass(frozen=True, slots=True)
class MasteryView:
    skill_id: int
    label: str
    score: float
    level: str
    trend: str


@dataclass(frozen=True, slots=True)
class SessionListItem:
    session_id: int
    status: str
    created_at: datetime
    duration_seconds: int
    score: float
    mastery_gain: float
    completion_rate: float


@dataclass(frozen=True, slots=True)
class ActivityListItem:
    activity_id: int
    title: str
    activity_type: str
    status: str
    score: float
    duration_seconds: int


@dataclass(frozen=True, slots=True)
class StudentDashboard:
    learner_id: int
    display_name: str
    objective: str
    recommended_duration_minutes: int
    metrics: tuple[Metric, ...]
    mastery: tuple[MasteryView, ...]
    recent_sessions: tuple[SessionListItem, ...]
    current_session: SessionListItem | None
    next_revision: datetime | None


@dataclass(frozen=True, slots=True)
class SessionScreen:
    session: SessionListItem
    activities: tuple[ActivityListItem, ...]
    completed_activities: int
    elapsed_seconds: int
    remaining_seconds: int


@dataclass(frozen=True, slots=True)
class SessionSummaryView:
    session: SessionListItem
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    recommendation: str | None


class ExperienceReadModel(Protocol):
    def learner_name(self, learner_id: int) -> str: ...

    def objective(self, learner_id: int) -> str | None: ...

    def mastery(self, learner_id: int) -> tuple[MasteryView, ...]: ...

    def sessions(self, learner_id: int) -> tuple[SessionListItem, ...]: ...

    def activities(self, session_id: int) -> tuple[ActivityListItem, ...]: ...

    def summary(self, session_id: int) -> tuple[tuple[str, ...], tuple[str, ...], str | None] | None: ...

    def next_revision(self, learner_id: int) -> datetime | None: ...

    def learners(self) -> tuple[tuple[int, str], ...]: ...


class LearnerExperienceService:
    def __init__(self, read_model: ExperienceReadModel) -> None:
        self.read_model = read_model

    def dashboard(self, learner_id: int) -> StudentDashboard:
        sessions = self.read_model.sessions(learner_id)
        mastery = self.read_model.mastery(learner_id)
        current = next((item for item in sessions if item.status in {"READY", "RUNNING", "PAUSED"}), None)
        completed = tuple(item for item in sessions if item.status == "COMPLETED")
        study_seconds = sum(item.duration_seconds for item in completed)
        average_score = sum(item.score for item in completed) / len(completed) if completed else 0
        overall_mastery = sum(item.score for item in mastery) / len(mastery) if mastery else 0
        metrics = (
            Metric("Temps d'étude", f"{study_seconds // 60} min"),
            Metric("Maîtrise", f"{overall_mastery:.0f} %"),
            Metric("Séances terminées", str(len(completed))),
            Metric("Score moyen", f"{average_score:.0f} %"),
            Metric("Révisions dues", str(sum(item.level in {"FRAGILE", "NOT_STARTED"} for item in mastery))),
        )
        planned = current.duration_seconds // 60 if current else 25
        return StudentDashboard(
            learner_id,
            self.read_model.learner_name(learner_id),
            self.read_model.objective(learner_id) or "Consolider les acquis du parcours",
            planned,
            metrics,
            mastery,
            completed[:5],
            current,
            self.read_model.next_revision(learner_id),
        )

    def session_screen(self, learner_id: int, session_id: int) -> SessionScreen:
        session = self._owned_session(learner_id, session_id)
        activities = self.read_model.activities(session_id)
        completed = sum(item.status == "COMPLETED" for item in activities)
        elapsed = sum(item.duration_seconds for item in activities if item.status == "COMPLETED")
        return SessionScreen(
            session,
            activities,
            completed,
            elapsed,
            max(0, session.duration_seconds - elapsed),
        )

    def session_summary(self, learner_id: int, session_id: int) -> SessionSummaryView:
        session = self._owned_session(learner_id, session_id)
        stored = self.read_model.summary(session_id)
        if stored is None:
            return SessionSummaryView(session, (), (), None)
        return SessionSummaryView(session, *stored)

    def history(self, learner_id: int) -> tuple[SessionListItem, ...]:
        return tuple(item for item in self.read_model.sessions(learner_id) if item.status == "COMPLETED")

    def learners(self) -> tuple[tuple[int, str], ...]:
        return self.read_model.learners()

    def _owned_session(self, learner_id: int, session_id: int) -> SessionListItem:
        session = next((item for item in self.read_model.sessions(learner_id) if item.session_id == session_id), None)
        if session is None:
            raise PermissionError("Cette séance n'est pas accessible.")
        return session
