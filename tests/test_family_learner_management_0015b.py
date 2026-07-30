from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from domain.decision.enums import ObjectiveKind
from domain.learning.models import AcademicYear, GradeLevel
from domain.onboarding.enums import CreatorRole, DifficultyPreference
from domain.onboarding.models import (
    AvailabilitySlot,
    LearnerGoalConfiguration,
    LearnerProfile,
    OnboardingRequest,
    StudyPreferences,
    SubjectPreference,
)
from domain.virtual_teacher.models import PedagogicalContext, PreferencesPatch
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.curriculum import DuckDBCurriculumRepository
from infrastructure.repositories.onboarding import DuckDBOnboardingRepository
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from infrastructure.repositories.virtual_teacher import DuckDBVirtualTeacherRepository
from migrations.runner import apply_migrations
from services.auth.roles import AuthRole
from services.curriculum import CurriculumImportService
from services.family_data_diagnostic import FamilyDataDiagnosticService
from services.family_learner_management import FamilyLearnerManagementService
from services.learner_session import cached_learner_id_if_valid, learner_cache_key
from services.onboarding import OnboardingService
from services.parent_ref import parent_ref_from_user
from services.unified_experience import (
    LearnerProfileManagementService,
    OnboardingProfileInput,
    UnifiedOnboardingProfileService,
)
from services.virtual_teacher.ai_conversation_orchestrator import AIConversationOrchestrator
from services.virtual_teacher.ai_teacher_preferences_service import AITeacherPreferencesService
from services.virtual_teacher.ai_teacher_service import AITeacherService
from services.virtual_teacher.authorization import VirtualTeacherAccessError
from services.virtual_teacher.llm_service import DeterministicLLMService
from services.virtual_teacher.pedagogical_guardrails import PedagogicalGuardrails
from services.virtual_teacher.tts_service import ConsoleTTSService


@pytest.fixture
def family_db(tmp_path: Path) -> tuple[Path, int, str]:
    path = tmp_path / "family.duckdb"
    apply_migrations(path)
    source = Path(__file__).parents[1] / "resources" / "catalog" / "lcai_0009_catalog.json"
    CurriculumImportService(DuckDBCurriculumRepository(path)).import_file(source, dry_run=False)
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student:family','Alex') RETURNING id"
            ).fetchone()[0]
        )
        other_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student:other','Other') RETURNING id"
            ).fetchone()[0]
        )
        connection.execute(
            "INSERT INTO learner_guardian_links(guardian_external_ref,learner_id,active) VALUES ('42',?,TRUE)",
            [learner_id],
        )
        connection.execute(
            "INSERT INTO learner_guardian_links(guardian_external_ref,learner_id,active) VALUES ('99',?,TRUE)",
            [other_id],
        )
    finally:
        connection.close()
    return path, learner_id, "42"


def _complete_profile(path: Path, learner_id: int) -> None:
    connection = connect_v2(path)
    try:
        subject_id, grade_id = connection.execute(
            """SELECT subject_id, grade_level_id FROM curriculum_chapters
            WHERE status='approved' ORDER BY id LIMIT 1"""
        ).fetchone()
        program_id = int(connection.execute("SELECT id FROM programs ORDER BY id LIMIT 1").fetchone()[0])
        grade = connection.execute(
            "SELECT code,rank,label FROM school_levels WHERE id=?",
            [grade_id],
        ).fetchone()
        connection.execute(
            """INSERT INTO learner_functional_profiles
            VALUES (?,'student:family','2012-01-01','parent',1,now())
            ON CONFLICT(learner_id) DO NOTHING""",
            [learner_id],
        )
        connection.execute(
            """INSERT INTO learner_journeys
            (learner_id,current_school_level_id,academic_year_start,program_id,learning_phase)
            VALUES (?,?,2026,?,'current_learning')""",
            [learner_id, grade_id, program_id],
        )
        connection.execute(
            """INSERT INTO learner_journey_versions
            (learner_id,version_number,journey_snapshot,effective_from,changed_by_role,context_hash,correlation_id)
            VALUES (?,1,'{}',now(),'parent','ctx','corr')""",
            [learner_id],
        )
    finally:
        connection.close()
    request = OnboardingRequest(
        f"mgmt:{learner_id}",
        LearnerProfile("student:family", "Alex", CreatorRole.PARENT, birth_date=date(2012, 1, 1), learner_id=learner_id),
        AcademicYear(2026, 2027),
        GradeLevel(str(grade[0]), int(grade[1]), str(grade[2])),
        LearnerGoalConfiguration(ObjectiveKind.LONG_TERM_MASTERY),
        (SubjectPreference(int(subject_id), priority=True),),
        StudyPreferences(30, (AvailabilitySlot(1, 30),), difficulty=DifficultyPreference.STANDARD),
        CreatorRole.PARENT,
    )
    repository = DuckDBUnifiedExperienceRepository(path)
    OnboardingService(DuckDBOnboardingRepository(path)).complete(request)
    UnifiedOnboardingProfileService(repository).save(
        OnboardingProfileInput(
            learner_id,
            "Alex",
            "Martin",
            date(2012, 1, 1),
            "2026-2027",
            "FR-NATIONAL",
            ("Exercices progressifs",),
            "HINT_FIRST",
            True,
        )
    )


def test_wizard_step2_requires_matching_password_of_min_length() -> None:
    from ui.parent_child_wizard import _validate_step

    objectives = {"Révision globale": ObjectiveKind.REVISION}
    data = {
        "student_username": "Michael",
        "student_password": "13091309",
        "student_password_confirmation": "13091309",
    }
    assert _validate_step(2, data, {1: "6e"}, {1: "Maths"}, objectives) is None
    short = {**data, "student_password": "123", "student_password_confirmation": "123"}
    assert _validate_step(2, short, {1: "6e"}, {1: "Maths"}, objectives) == (
        "Le mot de passe doit contenir au moins 4 caractères."
    )
    mismatch = {**data, "student_password_confirmation": "13091308"}
    assert _validate_step(2, mismatch, {1: "6e"}, {1: "Maths"}, objectives) == (
        "La confirmation du mot de passe ne correspond pas."
    )


def test_parent_sees_all_owned_learners(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, parent_ref = family_db
    _complete_profile(path, learner_id)
    repository = DuckDBUnifiedExperienceRepository(path)
    assert repository.list_linked_learners(parent_ref, archived=False) == ((learner_id, "Alex"),)


def test_parent_never_sees_other_family_learner(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, parent_ref = family_db
    _complete_profile(path, learner_id)
    repository = DuckDBUnifiedExperienceRepository(path)
    manager = LearnerProfileManagementService(repository)
    with pytest.raises(PermissionError):
        manager.get("99", learner_id)


def test_parent_cannot_mutate_unowned_learner(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, _ = family_db
    _complete_profile(path, learner_id)
    repository = DuckDBUnifiedExperienceRepository(path)
    with pytest.raises(PermissionError):
        repository.archive_learner("99", learner_id)


def test_parent_can_archive_and_restore_learner(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, parent_ref = family_db
    _complete_profile(path, learner_id)
    repository = DuckDBUnifiedExperienceRepository(path)
    manager = LearnerProfileManagementService(repository)
    family = FamilyLearnerManagementService(repository, manager)
    family.archive(parent_ref, learner_id, int(parent_ref))
    assert repository.learner_is_archived(learner_id)
    assert family.list_active_learners(parent_ref) == ()
    family.restore(parent_ref, learner_id)
    assert not repository.learner_is_archived(learner_id)
    assert family.list_active_learners(parent_ref) == ((learner_id, "Alex"),)


def test_parent_can_delete_owned_learner(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, parent_ref = family_db
    _complete_profile(path, learner_id)
    manager = LearnerProfileManagementService(DuckDBUnifiedExperienceRepository(path))
    manager.delete(parent_ref, learner_id, "Alex", True)
    connection = connect_v2(path, read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM learners WHERE id=?", [learner_id]).fetchone()[0] == 0
    finally:
        connection.close()


def test_delete_denied_for_unowned_learner(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, _ = family_db
    _complete_profile(path, learner_id)
    manager = LearnerProfileManagementService(DuckDBUnifiedExperienceRepository(path))
    with pytest.raises(PermissionError):
        manager.delete("99", learner_id, "Alex", True)


def test_virtual_teacher_preferences_created_per_learner(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, _ = family_db
    vt_repo = DuckDBVirtualTeacherRepository(path)
    prefs = vt_repo.ensure_preferences(learner_id)
    assert prefs.feature_enabled is False


def test_parent_can_configure_virtual_teacher(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, parent_ref = family_db
    vt_repo = DuckDBVirtualTeacherRepository(path)
    preferences = AITeacherPreferencesService(vt_repo)
    user = {"id": int(parent_ref), "name": "Parent", "role": AuthRole.PARENT.value}
    preferences.save_for_parent(
        user=user,
        parent_ref=parent_ref,
        learner_id=learner_id,
        patch=PreferencesPatch(feature_enabled=True, fields={"feature_enabled"}),
    )
    assert vt_repo.get_preferences(learner_id).feature_enabled is True


def test_student_teacher_menu_visible_when_disabled(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, _ = family_db
    vt_repo = DuckDBVirtualTeacherRepository(path)
    teacher = AITeacherService(
        vt_repo,
        AITeacherPreferencesService(vt_repo),
        AIConversationOrchestrator(llm=DeterministicLLMService(), guardrails=PedagogicalGuardrails()),
        ConsoleTTSService(),
    )
    user = {"id": 10, "name": "Alex", "role": AuthRole.STUDENT.value}
    with pytest.raises(VirtualTeacherAccessError, match="FEATURE_DISABLED"):
        teacher.start_session(
            user=user,
            learner_id=learner_id,
            student_learner_id=learner_id,
            actor_type="STUDENT",
            actor_ref="10",
            context=PedagogicalContext(learner_id=learner_id, learner_display_name="Alex"),
        )


def test_student_can_use_virtual_teacher_when_enabled(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, parent_ref = family_db
    vt_repo = DuckDBVirtualTeacherRepository(path)
    preferences = AITeacherPreferencesService(vt_repo)
    user = {"id": int(parent_ref), "name": "Parent", "role": AuthRole.PARENT.value}
    preferences.save_for_parent(
        user=user,
        parent_ref=parent_ref,
        learner_id=learner_id,
        patch=PreferencesPatch(feature_enabled=True, fields={"feature_enabled"}),
    )
    teacher = AITeacherService(
        vt_repo,
        preferences,
        AIConversationOrchestrator(llm=DeterministicLLMService(), guardrails=PedagogicalGuardrails()),
        ConsoleTTSService(),
    )
    student = {"id": 10, "name": "Alex", "role": AuthRole.STUDENT.value}
    session = teacher.start_session(
        user=student,
        learner_id=learner_id,
        student_learner_id=learner_id,
        actor_type="STUDENT",
        actor_ref="10",
        context=PedagogicalContext(learner_id=learner_id, learner_display_name="Alex"),
    )
    assert session.learner_id == learner_id


def test_cached_learner_id_revalidated_on_login() -> None:
    assert cached_learner_id_if_valid(
        session_cache_key=learner_cache_key(1, "student:a"),
        user_id=1,
        external_ref="student:b",
        cached_learner_id=99,
    ) is None
    assert cached_learner_id_if_valid(
        session_cache_key=learner_cache_key(1, "student:a"),
        user_id=1,
        external_ref="student:a",
        cached_learner_id=99,
    ) == 99


def test_runtime_uses_expected_unified_ui() -> None:
    import ui.streamlit_app as streamlit_app

    assert hasattr(streamlit_app, "run_app")
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")
    assert "unified_app" in source


def test_parent_ref_from_user_is_stable() -> None:
    assert parent_ref_from_user({"id": 42, "name": "Marie"}) == "42"


def test_family_diagnostic_reports_missing_vt_preferences(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, parent_ref = family_db
    _complete_profile(path, learner_id)
    diagnostic = FamilyDataDiagnosticService(
        DuckDBUnifiedExperienceRepository(path),
        virtual_teacher_repository=DuckDBVirtualTeacherRepository(path),
    )
    issues = diagnostic.scan_for_parent(parent_ref)
    assert any(item.learner_id == learner_id and item.code == "MISSING_VT_PREFERENCES" for item in issues)


def test_safe_repairs_are_idempotent(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, parent_ref = family_db
    _complete_profile(path, learner_id)
    vt_repo = DuckDBVirtualTeacherRepository(path)
    diagnostic = FamilyDataDiagnosticService(
        DuckDBUnifiedExperienceRepository(path),
        virtual_teacher_repository=vt_repo,
    )
    issue = next(item for item in diagnostic.scan_for_parent(parent_ref) if item.code == "MISSING_VT_PREFERENCES")
    assert diagnostic.repair(parent_ref, issue) is True
    assert diagnostic.repair(parent_ref, issue) is False
    assert vt_repo.get_preferences(learner_id) is not None


def test_parent_experience_controller_lists_linked_learners_only(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, parent_ref = family_db
    _complete_profile(path, learner_id)
    repository = DuckDBUnifiedExperienceRepository(path)
    assert repository.list_linked_learners(parent_ref) == ((learner_id, "Alex"),)


def test_learner_last_activity_label(family_db: tuple[Path, int, str]) -> None:
    path, learner_id, _ = family_db
    repository = DuckDBUnifiedExperienceRepository(path)
    connection = connect_v2(path)
    try:
        connection.execute(
            "INSERT INTO learning_sessions(learner_id,kind,status,started_at) VALUES (?,'practice','completed',?)",
            [learner_id, datetime(2026, 7, 1, tzinfo=UTC)],
        )
    finally:
        connection.close()
    assert repository.learner_last_activity_label(learner_id) is not None
