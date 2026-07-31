"""LCAI-0022B — Professor AI banner and operating modes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from domain.virtual_teacher.models import PreferencesPatch, VirtualTeacherPreferences
from infrastructure.repositories.virtual_teacher import DuckDBVirtualTeacherRepository
from migrations.runner import apply_migrations
from services.auth.roles import AuthRole
from services.professor_ai.banner import (
    BannerPresenceState,
    build_banner_view,
    mode_label,
    parse_operating_mode,
)
from services.professor_ai.models import ProfessorOperatingMode
from services.professor_ai.orchestrator import ProfessorAIOrchestrator
from services.virtual_teacher.ai_teacher_preferences_service import AITeacherPreferencesService
from services.virtual_teacher.authorization import VirtualTeacherAccessError
from types import SimpleNamespace
from unittest.mock import MagicMock

from application.dto.student_guidance import (
    AIAvailability,
    AIAvailabilityMode,
    GuidanceSource,
    StudentDashboardSnapshot,
    StudentHomeContext,
    WelcomeGuidance,
)


def test_parse_operating_mode_defaults_to_manual() -> None:
    assert parse_operating_mode(None) is ProfessorOperatingMode.MANUAL
    assert parse_operating_mode("companion") is ProfessorOperatingMode.COMPANION
    assert parse_operating_mode("inconnu") is ProfessorOperatingMode.MANUAL


def test_build_banner_view_forces_manual_when_feature_disabled() -> None:
    banner = build_banner_view(
        learner_id=7,
        teacher_name="Emma",
        mode=ProfessorOperatingMode.PROFESSOR,
        feature_enabled=False,
        parent_locked=False,
        message="Bonjour",
        presence=BannerPresenceState.SPEAKING,
    )
    assert banner.mode is ProfessorOperatingMode.MANUAL
    assert banner.mode_editable is False
    assert "désactivé" in banner.caption.casefold()


def test_build_banner_view_editable_when_unlocked() -> None:
    banner = build_banner_view(
        learner_id=7,
        teacher_name="Lucas",
        mode=ProfessorOperatingMode.COMPANION,
        feature_enabled=True,
        parent_locked=False,
        message="Je t'écoute",
    )
    assert banner.mode_editable is True
    assert mode_label(banner.mode) == "Mode Compagnon"


@pytest.fixture
def vt_db(tmp_path: Path) -> Path:
    path = tmp_path / "vt_0022b.duckdb"
    apply_migrations(path)
    return path


def test_operating_mode_persisted_and_readable(vt_db: Path) -> None:
    repository = DuckDBVirtualTeacherRepository(vt_db)
    from infrastructure.repositories.v2 import LearnerRepositoryV2

    learner_id = LearnerRepositoryV2(vt_db).create("Banner learner")
    prefs = repository.ensure_preferences(learner_id)
    assert prefs.operating_mode == "MANUAL"
    saved = repository.save_preferences(learner_id, feature_enabled=True, operating_mode="PROFESSOR")
    assert saved.feature_enabled is True
    assert saved.operating_mode == "PROFESSOR"
    reloaded = repository.get_preferences(learner_id)
    assert reloaded is not None
    assert reloaded.operating_mode == "PROFESSOR"


def test_student_can_change_operating_mode_when_unlocked(vt_db: Path) -> None:
    from infrastructure.repositories.v2 import LearnerRepositoryV2

    learner_id = LearnerRepositoryV2(vt_db).create("Mode student")
    repository = DuckDBVirtualTeacherRepository(vt_db)
    repository.save_preferences(learner_id, feature_enabled=True, parent_locked=False, operating_mode="PROFESSOR")
    service = AITeacherPreferencesService(repository)
    saved = service.save_for_student(
        user={"role": AuthRole.STUDENT.value, "id": learner_id},
        student_learner_id=learner_id,
        learner_id=learner_id,
        patch=PreferencesPatch(operating_mode="COMPANION", fields={"operating_mode"}),
    )
    assert saved.operating_mode == "COMPANION"


def test_student_cannot_change_mode_when_locked(vt_db: Path) -> None:
    from infrastructure.repositories.v2 import LearnerRepositoryV2

    learner_id = LearnerRepositoryV2(vt_db).create("Locked student")
    repository = DuckDBVirtualTeacherRepository(vt_db)
    repository.save_preferences(learner_id, feature_enabled=True, parent_locked=True, operating_mode="PROFESSOR")
    service = AITeacherPreferencesService(repository)
    with pytest.raises(VirtualTeacherAccessError, match="PREFERENCES_LOCKED"):
        service.save_for_student(
            user={"role": AuthRole.STUDENT.value, "id": learner_id},
            student_learner_id=learner_id,
            learner_id=learner_id,
            patch=PreferencesPatch(operating_mode="MANUAL", fields={"operating_mode"}),
        )


def test_orchestrator_reads_stored_companion_mode() -> None:
    guidance = MagicMock()
    guidance.build_home_guidance.return_value = StudentDashboardSnapshot(
        context=StudentHomeContext(
            learner_id=7,
            display_name="Noa",
            homework_todo=(),
            homework_overdue=(),
            homework_recent=(),
            mastery=(),
            fragile_skills=(),
            strong_skills=(),
            revision_priorities=(),
            recent_score=None,
            success_rate=None,
            objective="x",
            next_revision=None,
        ),
        welcome=WelcomeGuidance(GuidanceSource.DETERMINISTIC, "Bonjour", "Continuer"),
        availability=AIAvailability(
            AIAvailabilityMode.ACTIVE, True, True, True, ""
        ),
    )
    preferences = MagicMock()
    preferences.ensure_preferences.return_value = SimpleNamespace(
        feature_enabled=True,
        operating_mode="COMPANION",
    )
    orch = ProfessorAIOrchestrator(
        guidance=guidance,
        pedagogical=None,
        homework=MagicMock(),
        preferences=preferences,
        availability_resolver=lambda **_: AIAvailability(
            AIAvailabilityMode.ACTIVE, True, True, True, ""
        ),
    )
    assert orch.resolve_mode(7) is ProfessorOperatingMode.COMPANION
