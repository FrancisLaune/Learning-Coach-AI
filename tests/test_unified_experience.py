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
from domain.unified_experience.models import AssignmentStatus, AssignmentType, DifficultyMode, HomeworkRequest
from domain.learning_session.models import SessionStatus
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.curriculum import DuckDBCurriculumRepository
from infrastructure.repositories.learning import DuckDBLearningRepository
from infrastructure.repositories.learning_session import DuckDBLearningSessionRepository
from infrastructure.repositories.onboarding import DuckDBOnboardingRepository
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from infrastructure.repositories.unified_session_execution import DuckDBUnifiedSessionExecutionRepository
from migrations.runner import apply_migrations
from services.curriculum import CurriculumImportService
from services.learning.learning_engine_service import LearningEngineService
from services.learning_session.experience import MasteryView
from services.learning_session.orchestration import ActivityRunner, LearningSessionService
from services.learning_session.submission import SubmissionService
from services.onboarding import OnboardingService
from services.unified_experience import (
    DeterministicCoachService,
    HomeworkService,
    HomeworkSessionService,
    LearnerProfileManagementService,
    OnboardingProfileInput,
    ProgrammeChangeService,
    UnifiedOnboardingProfileService,
)
from services.unified_session_execution import DecisionRefreshNotifier, UnifiedSessionExecutionService


@pytest.fixture
def unified_database(tmp_path: Path) -> tuple[Path, int, int, int]:
    path = tmp_path / "unified.duckdb"
    apply_migrations(path)
    source = Path(__file__).parents[1] / "resources" / "catalog" / "lcai_0009_catalog.json"
    CurriculumImportService(DuckDBCurriculumRepository(path)).import_file(source, dry_run=False)
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student:test','Alexandre') RETURNING id"
            ).fetchone()[0]
        )
        subject_id, grade_id = connection.execute(
            """SELECT subject_id,grade_level_id FROM curriculum_chapters
            WHERE status='approved' ORDER BY id LIMIT 1"""
        ).fetchone()
        program_id = int(connection.execute("SELECT id FROM programs ORDER BY id LIMIT 1").fetchone()[0])
        connection.execute(
            """INSERT INTO learner_journeys
            (learner_id,current_school_level_id,academic_year_start,program_id,learning_phase)
            VALUES (?,?,2026,?,'current_learning')""",
            [learner_id, grade_id, program_id],
        )
        connection.execute(
            """INSERT INTO learner_journey_versions
            (learner_id,version_number,journey_snapshot,effective_from,changed_by_role,
             context_hash,correlation_id)
            VALUES (?,1,'{}',now(),'student','test-context','test-correlation')""",
            [learner_id],
        )
        connection.execute(
            """INSERT INTO learner_guardian_links(guardian_external_ref,learner_id,active)
            VALUES ('parent:test',?,TRUE)""",
            [learner_id],
        )
    finally:
        connection.close()
    return path, learner_id, int(subject_id), int(grade_id)


def request(
    learner_id: int,
    subject_id: int,
    grade_id: int,
    *,
    actor_type: str = "STUDENT",
    actor_ref: str = "student:test",
    mode: AssignmentType = AssignmentType.GLOBAL_SUBJECT,
) -> HomeworkRequest:
    return HomeworkRequest(
        learner_id,
        actor_type,
        actor_ref,
        mode,
        subject_id,
        grade_id,
        (),
        (),
        DifficultyMode.ADAPTIVE,
        2,
        30,
        datetime(2026, 7, 30, tzinfo=UTC),
    )


def test_profile_age_and_completion(unified_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, _, _ = unified_database
    repository = DuckDBUnifiedExperienceRepository(path)
    profile = OnboardingProfileInput(
        learner_id,
        "Alexandre",
        "Test",
        date(2013, 4, 12),
        "2026-2027",
        "FR-NATIONAL",
        ("Exercices progressifs",),
        "HINT_FIRST",
        True,
    )
    assert profile.age is not None
    UnifiedOnboardingProfileService(repository).save(profile)
    assert repository.onboarding_complete(learner_id)


@pytest.mark.parametrize(
    ("years_ago", "accepted"),
    ((5, True), (30, True), (31, False)),
)
def test_birth_date_boundaries(
    unified_database: tuple[Path, int, int, int],
    years_ago: int,
    accepted: bool,
) -> None:
    path, learner_id, _, _ = unified_database
    today = date.today()
    birth_date = date(today.year - years_ago, today.month, today.day)
    profile = OnboardingProfileInput(
        learner_id,
        "Alexandre",
        None,
        birth_date,
        "2026-2027",
        "FR-NATIONAL",
        (),
        "HINT_FIRST",
        False,
    )
    service = UnifiedOnboardingProfileService(DuckDBUnifiedExperienceRepository(path))
    if accepted:
        service.save(profile)
        assert profile.age == years_ago
    else:
        with pytest.raises(ValueError, match="date de naissance"):
            service.save(profile)


def test_birth_date_2012_is_accepted_and_age_is_derived(
    unified_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, _, _ = unified_database
    profile = OnboardingProfileInput(
        learner_id,
        "Alexandre",
        None,
        date(2012, 6, 15),
        "2026-2027",
        "FR-NATIONAL",
        (),
        "HINT_FIRST",
        False,
    )
    UnifiedOnboardingProfileService(DuckDBUnifiedExperienceRepository(path)).save(profile)
    assert profile.age in {13, 14}


def test_blank_email_is_treated_as_optional(unified_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, _, _ = unified_database
    UnifiedOnboardingProfileService(DuckDBUnifiedExperienceRepository(path)).save(
        OnboardingProfileInput(
            learner_id,
            "Alexandre",
            None,
            date(2012, 6, 15),
            "2026-2027",
            "FR-NATIONAL",
            (),
            "HINT_FIRST",
            False,
            "",
        )
    )


def _complete_management_profile(path: Path, learner_id: int, subject_id: int, grade_id: int) -> None:
    connection = connect_v2(path)
    try:
        grade = connection.execute(
            "SELECT code,rank,label FROM school_levels WHERE id=?",
            [grade_id],
        ).fetchone()
        connection.execute(
            """INSERT INTO learner_functional_profiles
            VALUES (?,'student:test','2012-06-15','parent',1,now())"""
            " ON CONFLICT(learner_id) DO NOTHING",
            [learner_id],
        )
    finally:
        connection.close()
    request = OnboardingRequest(
        f"management:{learner_id}",
        LearnerProfile(
            "student:test",
            "Alexandre",
            CreatorRole.PARENT,
            birth_date=date(2012, 6, 15),
            learner_id=learner_id,
        ),
        AcademicYear(2026, 2027),
        GradeLevel(str(grade[0]), int(grade[1]), str(grade[2])),
        LearnerGoalConfiguration(ObjectiveKind.LONG_TERM_MASTERY),
        (SubjectPreference(subject_id, priority=True),),
        StudyPreferences(
            30,
            (AvailabilitySlot(1, 30),),
            difficulty=DifficultyPreference.STANDARD,
        ),
        CreatorRole.PARENT,
    )
    OnboardingService(DuckDBOnboardingRepository(path)).complete(request)
    UnifiedOnboardingProfileService(DuckDBUnifiedExperienceRepository(path)).save(
        OnboardingProfileInput(
            learner_id,
            "Alexandre",
            "Test",
            date(2012, 6, 15),
            "2026-2027",
            "FR-NATIONAL",
            ("Exercices progressifs",),
            "HINT_FIRST",
            True,
        )
    )


def test_parent_can_edit_complete_learner_profile_and_authorization_is_required(
    unified_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, subject_id, grade_id = unified_database
    _complete_management_profile(path, learner_id, subject_id, grade_id)
    connection = connect_v2(path, read_only=True)
    try:
        grade = connection.execute(
            "SELECT code,rank,label FROM school_levels WHERE id=?",
            [grade_id],
        ).fetchone()
    finally:
        connection.close()
    request_update = OnboardingRequest(
        f"management-update:{learner_id}",
        LearnerProfile(
            "student:test",
            "Alex",
            CreatorRole.PARENT,
            birth_date=date(2012, 5, 10),
            learner_id=learner_id,
        ),
        AcademicYear(2027, 2028),
        GradeLevel(str(grade[0]), int(grade[1]), str(grade[2])),
        LearnerGoalConfiguration(ObjectiveKind.CONSOLIDATION),
        (SubjectPreference(subject_id, priority=True),),
        StudyPreferences(
            45,
            (AvailabilitySlot(2, 45), AvailabilitySlot(5, 45)),
            difficulty=DifficultyPreference.STANDARD,
        ),
        CreatorRole.PARENT,
        "parent_profile_edit",
    )
    profile_update = OnboardingProfileInput(
        learner_id,
        "Alex",
        "Martin",
        date(2012, 5, 10),
        "2027-2028",
        "FR-NATIONAL",
        ("Explications détaillées",),
        "EXPLAIN_METHOD",
        False,
    )
    repository = DuckDBUnifiedExperienceRepository(path)
    manager = LearnerProfileManagementService(repository)
    with pytest.raises(PermissionError):
        manager.update(
            "unknown",
            request_update,
            profile_update,
            OnboardingService(DuckDBOnboardingRepository(path)),
            UnifiedOnboardingProfileService(repository),
        )
    result = manager.update(
        "parent:test",
        request_update,
        profile_update,
        OnboardingService(DuckDBOnboardingRepository(path)),
        UnifiedOnboardingProfileService(repository),
    )
    updated = manager.get("parent:test", learner_id)
    assert result.journey_version == 3
    assert updated.first_name == "Alex"
    assert updated.last_name == "Martin"
    assert updated.birth_date == date(2012, 5, 10)
    assert updated.school_year == "2027-2028"
    assert updated.objective == ObjectiveKind.CONSOLIDATION.value
    assert updated.subject_ids == (subject_id,)
    assert updated.daily_duration_minutes == 45
    assert {item[0] for item in updated.availability} == {2, 5}
    assert updated.preferred_formats == ("Explications détaillées",)
    assert updated.error_help_preference == "EXPLAIN_METHOD"


def test_parent_can_create_and_link_learner(
    unified_database: tuple[Path, int, int, int],
) -> None:
    path, _, subject_id, grade_id = unified_database
    connection = connect_v2(path, read_only=True)
    try:
        grade = connection.execute(
            "SELECT code,rank,label FROM school_levels WHERE id=?",
            [grade_id],
        ).fetchone()
    finally:
        connection.close()
    onboarding_request = OnboardingRequest(
        "parent-create:new-child",
        LearnerProfile(
            "parent-child:new",
            "Camille",
            CreatorRole.PARENT,
            birth_date=date(2012, 9, 4),
        ),
        AcademicYear(2026, 2027),
        GradeLevel(str(grade[0]), int(grade[1]), str(grade[2])),
        LearnerGoalConfiguration(ObjectiveKind.LONG_TERM_MASTERY),
        (SubjectPreference(subject_id, priority=True),),
        StudyPreferences(30, (AvailabilitySlot(1, 30),)),
        CreatorRole.PARENT,
        "parent_created_learner",
    )
    repository = DuckDBUnifiedExperienceRepository(path)
    manager = LearnerProfileManagementService(repository)
    result = manager.create(
        "parent:test",
        onboarding_request,
        OnboardingProfileInput(
            0,
            "Camille",
            "Martin",
            date(2012, 9, 4),
            "2026-2027",
            "FR-NATIONAL",
            ("Exercices progressifs",),
            "HINT_FIRST",
            True,
            "camille@example.test",
        ),
        OnboardingService(DuckDBOnboardingRepository(path)),
        UnifiedOnboardingProfileService(repository),
    )
    assert repository.parent_authorized("parent:test", result.learner_id)
    created_profile = manager.get("parent:test", result.learner_id)
    assert created_profile.first_name == "Camille"
    assert created_profile.email == "camille@example.test"
    manager.delete("parent:test", result.learner_id, "Camille", True)


def test_parent_can_create_learner_without_email(
    unified_database: tuple[Path, int, int, int],
) -> None:
    path, _, subject_id, grade_id = unified_database
    connection = connect_v2(path, read_only=True)
    try:
        grade = connection.execute(
            "SELECT code,rank,label FROM school_levels WHERE id=?",
            [grade_id],
        ).fetchone()
    finally:
        connection.close()
    onboarding_request = OnboardingRequest(
        "parent-create:no-email",
        LearnerProfile(
            "parent-child:no-email",
            "Noah",
            CreatorRole.PARENT,
            birth_date=date(2012, 9, 4),
        ),
        AcademicYear(2026, 2027),
        GradeLevel(str(grade[0]), int(grade[1]), str(grade[2])),
        LearnerGoalConfiguration(ObjectiveKind.LONG_TERM_MASTERY),
        (SubjectPreference(subject_id, priority=True),),
        StudyPreferences(30, (AvailabilitySlot(1, 30),)),
        CreatorRole.PARENT,
        "parent_created_learner",
    )
    repository = DuckDBUnifiedExperienceRepository(path)
    manager = LearnerProfileManagementService(repository)
    result = manager.create(
        "parent:test",
        onboarding_request,
        OnboardingProfileInput(
            0,
            "Noah",
            "Martin",
            date(2012, 9, 4),
            "2026-2027",
            "FR-NATIONAL",
            ("Exercices progressifs",),
            "HINT_FIRST",
            True,
            None,
        ),
        OnboardingService(DuckDBOnboardingRepository(path)),
        UnifiedOnboardingProfileService(repository),
    )
    created_profile = manager.get("parent:test", result.learner_id)
    assert created_profile.email is None
    manager.delete("parent:test", result.learner_id, "Noah", True)


def test_parent_can_view_and_hard_delete_learner_without_touching_curriculum(
    unified_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, subject_id, grade_id = unified_database
    _complete_management_profile(path, learner_id, subject_id, grade_id)
    repository = DuckDBUnifiedExperienceRepository(path)
    manager = LearnerProfileManagementService(repository)
    profile = manager.get("parent:test", learner_id)
    assert profile.first_name == "Alexandre"
    assert profile.birth_date == date(2012, 6, 15)
    HomeworkService(repository).create(request(learner_id, subject_id, grade_id))

    connection = connect_v2(path, read_only=True)
    try:
        curriculum_before = connection.execute("SELECT count(*) FROM approved_learning_catalog").fetchone()[0]
    finally:
        connection.close()
    with pytest.raises(PermissionError):
        manager.delete("unknown", learner_id, "Alexandre", True)
    with pytest.raises(ValueError, match="définitive"):
        manager.delete("parent:test", learner_id, "Alexandre", False)
    with pytest.raises(ValueError, match="prénom"):
        manager.delete("parent:test", learner_id, "incorrect", True)

    manager.delete("parent:test", learner_id, "Alexandre", True)

    connection = connect_v2(path, read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM learners WHERE id=?", [learner_id]).fetchone() == (0,)
        learner_tables = [
            str(row[0])
            for row in connection.execute(
                """SELECT DISTINCT table_name FROM information_schema.columns
                WHERE table_schema='main' AND column_name='learner_id'
                AND table_name NOT LIKE 'v_%'"""
            ).fetchall()
        ]
        assert all(
            connection.execute(f"SELECT count(*) FROM {table} WHERE learner_id=?", [learner_id]).fetchone()[0] == 0
            for table in learner_tables
        )
        assert connection.execute("SELECT count(*) FROM approved_learning_catalog").fetchone()[0] == curriculum_before
    finally:
        connection.close()


def test_global_homework_uses_only_approved_content_and_is_idempotent(
    unified_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, subject_id, grade_id = unified_database
    repository = DuckDBUnifiedExperienceRepository(path)
    service = HomeworkService(repository)
    created = service.create(request(learner_id, subject_id, grade_id))
    repeated = service.create(request(learner_id, subject_id, grade_id))
    assert created.homework_id == repeated.homework_id
    assert created.status is AssignmentStatus.READY
    assert created.selected_content_ids
    connection = connect_v2(path, read_only=True)
    try:
        approved = {
            int(row[0])
            for row in connection.execute("SELECT DISTINCT content_id FROM approved_learning_catalog").fetchall()
        }
    finally:
        connection.close()
    assert set(created.selected_content_ids) <= approved


def test_homework_pause_resume_and_invalid_transition(unified_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, subject_id, grade_id = unified_database
    service = HomeworkService(DuckDBUnifiedExperienceRepository(path))
    created = service.create(request(learner_id, subject_id, grade_id))
    started = service.start(learner_id, created.homework_id)
    assert started.status is AssignmentStatus.IN_PROGRESS
    paused = service.pause(learner_id, created.homework_id)
    assert paused.status is AssignmentStatus.PAUSED
    resumed = service.resume(learner_id, created.homework_id)
    assert resumed.status is AssignmentStatus.IN_PROGRESS
    with pytest.raises(ValueError, match="Invalid homework transition"):
        service.start(learner_id, created.homework_id)


def test_homework_session_pause_syncs_learning_session(unified_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, subject_id, grade_id = unified_database
    unified = DuckDBUnifiedExperienceRepository(path)
    homework = HomeworkService(unified).create(request(learner_id, subject_id, grade_id))
    session_repository = DuckDBLearningSessionRepository(path)
    session_service = LearningSessionService(
        DuckDBRecommendationRepository(path), session_repository, session_repository
    )
    homework_sessions = HomeworkSessionService(unified, session_service)
    opened = homework_sessions.open_for_learner(learner_id, homework.homework_id, datetime.now(UTC))
    assert opened.session_id is not None
    session_id = int(opened.session_id)
    homework_sessions.pause_for_learner_session(learner_id, session_id, datetime.now(UTC))
    session = session_repository.get(session_id)
    assert session is not None
    assert session.status is SessionStatus.PAUSED
    paused_homework = unified.get_homework(homework.homework_id)
    assert paused_homework.status is AssignmentStatus.PAUSED
    homework_sessions.resume_for_learner_session(learner_id, session_id, datetime.now(UTC))
    session = session_repository.get(session_id)
    assert session is not None
    assert session.status is SessionStatus.RUNNING
    resumed_homework = unified.get_homework(homework.homework_id)
    assert resumed_homework.status is AssignmentStatus.IN_PROGRESS


def test_homework_materializes_and_executes_deterministic_session(
    unified_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, subject_id, grade_id = unified_database
    unified = DuckDBUnifiedExperienceRepository(path)
    homework = HomeworkService(unified).create(request(learner_id, subject_id, grade_id))
    session_repository = DuckDBLearningSessionRepository(path)
    session_service = LearningSessionService(
        DuckDBRecommendationRepository(path), session_repository, session_repository
    )
    materialized = HomeworkSessionService(unified, session_service).materialize(
        learner_id, homework.homework_id, datetime.now(UTC)
    )
    assert materialized.session_id is not None
    opened = HomeworkSessionService(unified, session_service).open_for_learner(
        learner_id, homework.homework_id, datetime.now(UTC)
    )
    assert opened.session_id == materialized.session_id
    started = session_repository.get(materialized.session_id)
    assert started is not None
    assert started.status is SessionStatus.RUNNING

    execution_repository = DuckDBUnifiedSessionExecutionRepository(path)
    submission = SubmissionService(
        session_repository,
        LearningEngineService(DuckDBLearningRepository(path)),
        DecisionRefreshNotifier(execution_repository.enqueue_refresh),
    )
    execution = UnifiedSessionExecutionService(
        execution_repository,
        submission,
        session_service,
        ActivityRunner(session_repository),
    )
    material = execution_repository.current_question(learner_id, materialized.session_id)
    assert material is not None
    result = execution.submit(
        learner_id,
        materialized.session_id,
        material.expected_answer,
        datetime.now(UTC),
        1000,
    )
    assert result.correct
    assert result.mastery_after >= result.mastery_before
    next_material = execution_repository.current_question(learner_id, materialized.session_id)
    if next_material is not None:
        execution.submit(
            learner_id,
            materialized.session_id,
            next_material.expected_answer,
            datetime.now(UTC),
            1000,
        )
    connection = connect_v2(path, read_only=True)
    try:
        assert connection.execute(
            "SELECT count(*) FROM decision_refresh_queue WHERE session_id=?", [materialized.session_id]
        ).fetchone() == (1,)
        if result.session_completed:
            assert connection.execute(
                "SELECT status FROM homework_assignments WHERE id=?", [homework.homework_id]
            ).fetchone() == ("COMPLETED",)
            assert connection.execute(
                "SELECT count(*) FROM homework_result_summaries WHERE homework_id=?", [homework.homework_id]
            ).fetchone() == (1,)
    finally:
        connection.close()


def test_parent_assignment_requires_relationship(unified_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, subject_id, grade_id = unified_database
    service = HomeworkService(DuckDBUnifiedExperienceRepository(path))
    parent_request = request(
        learner_id,
        subject_id,
        grade_id,
        actor_type="PARENT",
        actor_ref="parent:test",
    )
    assert service.assign_as_parent("parent:test", parent_request).assigned_by_type == "PARENT"
    with pytest.raises(PermissionError, match="ACCESS_DENIED"):
        service.assign_as_parent(
            "unknown",
            request(learner_id, subject_id, grade_id, actor_type="PARENT", actor_ref="unknown"),
        )


def test_major_programme_change_requires_authorized_parent(
    unified_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, _, _ = unified_database
    connection = connect_v2(path)
    try:
        proposal_id = int(
            connection.execute(
                """INSERT INTO programme_change_proposals
                (stable_key,learner_id,level,change_type,status,current_state,proposed_state,
                 reason_codes,evidence_references,expected_benefit_code,correlation_id)
                VALUES ('change:test',?,3,'PREREQUISITE_CONSOLIDATION','PENDING_PARENT','{}','{}',
                '["PERSISTENT_WEAKNESS"]','["skill:1"]','RESTORE_FOUNDATIONS','corr:test') RETURNING id""",
                [learner_id],
            ).fetchone()[0]
        )
    finally:
        connection.close()
    service = ProgrammeChangeService(DuckDBUnifiedExperienceRepository(path))
    with pytest.raises(PermissionError):
        service.list_for_parent("unknown", learner_id)
    service.decide("parent:test", proposal_id, "accept")
    assert service.list_for_parent("parent:test", learner_id)[0].status == "ACCEPTED"


def test_coach_advice_is_grounded_and_requires_trend() -> None:
    mastery = (
        MasteryView(1, "Équations", 43, "FRAGILE", "DECLINING"),
        MasteryView(2, "Fractions", 91, "MASTERED", "IMPROVING"),
        MasteryView(3, "Calcul", 65, "DEVELOPING", "STABLE"),
    )
    advice = DeterministicCoachService().advice(mastery)
    assert [item.title for item in advice] == [
        "Priorité : Équations",
        "Progression solide : Fractions",
    ]
    assert all(item.evidence_references for item in advice)


def test_unified_navigation_is_complete_and_legacy_is_opt_in() -> None:
    source = (Path(__file__).parents[1] / "ui" / "unified_app.py").read_text(encoding="utf-8")
    for label in (
        "Tableau de bord",
        "Ma séance IA",
        "Devoirs",
        "Révision",
        "Mes progrès",
        "Mes résultats",
        "Mon planning",
        "Profil",
        "Programme",
    ):
        assert label in source
    shell = (Path(__file__).parents[1] / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "is_legacy_ui_enabled" in shell
