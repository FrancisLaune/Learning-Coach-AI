from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from application.experience_controllers import PresentationError, StudentExperienceController
from infrastructure.repositories.experience import DuckDBExperienceReadModel
from services.learning_session.experience import (
    ActivityListItem,
    LearnerExperienceService,
    MasteryView,
    SessionListItem,
)

NOW = datetime(2026, 7, 23, 10, tzinfo=UTC)


class MemoryReadModel:
    def learner_name(self, learner_id: int) -> str:
        return "Alexandre"

    def objective(self, learner_id: int) -> str:
        return "Préparer le brevet"

    def mastery(self, learner_id: int) -> tuple[MasteryView, ...]:
        return (
            MasteryView(10, "Fractions", 80, "MASTERED", "IMPROVING"),
            MasteryView(11, "Géométrie", 40, "FRAGILE", "STABLE"),
        )

    def sessions(self, learner_id: int) -> tuple[SessionListItem, ...]:
        return (
            SessionListItem(2, "PAUSED", NOW, 1500, 0, 0, 25),
            SessionListItem(1, "COMPLETED", NOW, 1200, 80, 5, 100),
        )

    def activities(self, session_id: int) -> tuple[ActivityListItem, ...]:
        return (
            ActivityListItem(1, "Fractions", "exercise", "COMPLETED", 80, 300),
            ActivityListItem(2, "Géométrie", "exercise", "NOT_STARTED", 0, 300),
        )

    def summary(self, session_id: int) -> tuple[tuple[str, ...], tuple[str, ...], str]:
        return ("Fractions",), ("Géométrie",), "Réviser la géométrie."

    def next_revision(self, learner_id: int) -> datetime:
        return NOW

    def learners(self) -> tuple[tuple[int, str], ...]:
        return ((7, "Alexandre"),)


def test_student_dashboard_and_session_are_derived_in_service() -> None:
    service = LearnerExperienceService(MemoryReadModel())
    dashboard = service.dashboard(7)
    assert dashboard.display_name == "Alexandre"
    assert dashboard.current_session and dashboard.current_session.session_id == 2
    assert dashboard.metrics[1].value == "60 %"
    assert dashboard.metrics[3].value == "80 %"
    screen = service.session_screen(7, 2)
    assert screen.completed_activities == 1
    assert screen.elapsed_seconds == 300
    assert screen.remaining_seconds == 1200


def test_session_ownership_is_enforced_before_presentation() -> None:
    service = LearnerExperienceService(MemoryReadModel())
    try:
        service.session_screen(8, 999)
    except PermissionError as error:
        assert "accessible" in str(error)
    else:
        raise AssertionError("Ownership must be checked")


def test_controller_returns_safe_error_without_technical_details() -> None:
    class BrokenReadModel(MemoryReadModel):
        def sessions(self, learner_id: int) -> tuple[SessionListItem, ...]:
            raise OSError("secret database path")

    result = StudentExperienceController(LearnerExperienceService(BrokenReadModel())).dashboard(7)
    assert isinstance(result, PresentationError)
    assert "secret" not in result.message


def test_ui_uses_controllers_instead_of_repositories() -> None:
    source = Path("ui/v2_experience.py").read_text(encoding="utf-8")
    assert "infrastructure.repositories" not in source
    assert "connect_v2" not in source


def test_duckdb_read_model_handles_empty_seed_state() -> None:
    repository = DuckDBExperienceReadModel()
    assert isinstance(repository.learners(), tuple)
    assert repository.sessions(-1) == ()
    assert repository.mastery(-1) == ()
