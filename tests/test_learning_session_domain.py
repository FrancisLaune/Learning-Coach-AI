from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from core.config import PROJECT_ROOT
from domain.decision.enums import ObjectiveKind
from domain.learning.models import AcademicYear, GradeLevel
from domain.learning_session.models import (
    AnswerType,
    Assessment,
    AssessmentMethod,
    Attempt,
    LearningSession,
    SessionActivity,
    SessionCheckpoint,
    SessionEvent,
    SessionStatus,
    SessionSummary,
    StudentAnswer,
)
from domain.onboarding.enums import CreatorRole, DifficultyPreference
from domain.onboarding.models import (
    AvailabilitySlot,
    LearnerGoalConfiguration,
    LearnerProfile,
    OnboardingRequest,
    StudyPreferences,
    SubjectPreference,
)
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.curriculum import DuckDBCurriculumRepository
from infrastructure.repositories.learning_session import DuckDBLearningSessionRepository
from infrastructure.repositories.onboarding import DuckDBOnboardingRepository
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from migrations.runner import apply_migrations
from services.curriculum import CurriculumImportService
from services.onboarding import OnboardingService
from services.recommendation import PersonalizedSessionService

NOW = datetime(2027, 1, 10, 10, tzinfo=UTC)
CATALOG = PROJECT_ROOT / "resources" / "catalog" / "lcai_0009_catalog.json"


@pytest.fixture
def execution_database(tmp_path: Path) -> tuple[Path, int, int, int, int, int, int]:
    path = tmp_path / "session.duckdb"
    apply_migrations(path)
    CurriculumImportService(DuckDBCurriculumRepository(path)).import_file(CATALOG, dry_run=False)
    request = OnboardingRequest(
        "session-test-onboarding",
        LearnerProfile("session-test-profile", "Session Test", CreatorRole.STUDENT),
        AcademicYear(2026, 2027),
        GradeLevel("FR-4E", 4, "Quatrième"),
        LearnerGoalConfiguration(ObjectiveKind.REVISION, None, None, date(2027, 6, 1)),
        (SubjectPreference(1, priority=True),),
        StudyPreferences(
            30,
            (AvailabilitySlot(0, 30, time(17)),),
            difficulty=DifficultyPreference.STANDARD,
        ),
        CreatorRole.STUDENT,
    )
    onboarding = OnboardingService(DuckDBOnboardingRepository(path)).complete(request, NOW)
    recommendation = DuckDBRecommendationRepository(path)
    proposal = PersonalizedSessionService(session_repository=recommendation).generate(
        onboarding, recommendation.load_approved_contents(), NOW
    )
    con = connect_v2(path, read_only=True)
    try:
        proposal_id = int(
            con.execute(
                "SELECT id FROM personalized_session_proposals WHERE stable_id=?", [proposal.stable_id]
            ).fetchone()[0]
        )
        journey_version_id = int(
            con.execute(
                "SELECT id FROM learner_journey_versions WHERE learner_id=?", [onboarding.learner_id]
            ).fetchone()[0]
        )
        content_id, version_id, question_id = con.execute(
            """SELECT c.content_id,c.content_version_id,q.id FROM approved_learning_catalog c
            JOIN content_questions q ON q.exercise_id=c.content_id ORDER BY c.content_id LIMIT 1"""
        ).fetchone()
    finally:
        con.close()
    return (
        path,
        onboarding.learner_id,
        journey_version_id,
        proposal_id,
        int(content_id),
        int(version_id),
        int(question_id),
    )


def session(learner_id: int, journey_id: int, proposal_id: int) -> LearningSession:
    return LearningSession(
        0,
        learner_id,
        journey_id,
        proposal_id,
        SessionStatus.CREATED,
        NOW,
        1800,
        "app-v2",
        "curriculum-v1",
        "catalog-v1",
        "decision-v1",
        "assessment-v1",
    )


def test_domain_constraints_and_transitions() -> None:
    base = session(1, 2, 3)
    ready = base.transition(SessionStatus.READY, NOW)
    running = ready.transition(SessionStatus.RUNNING, NOW)
    paused = running.transition(SessionStatus.PAUSED, NOW)
    assert paused.transition(SessionStatus.RUNNING, NOW).status is SessionStatus.RUNNING
    with pytest.raises(ValueError, match="Invalid session transition"):
        base.transition(SessionStatus.COMPLETED, NOW)
    with pytest.raises(ValueError, match="between 0 and 100"):
        replace(base, completion_rate=101)


def test_session_activity_and_answer_validation() -> None:
    with pytest.raises(ValueError, match="difficulty"):
        SessionActivity(0, 1, 1, 1, 1, "exercise", 8, 60)
    with pytest.raises(ValueError, match="time non-negative"):
        StudentAnswer(0, 1, 1, 1, AnswerType.TEXT, "x", "x", NOW, -1, True, False, "key")


def test_create_load_and_transition_session(
    execution_database: tuple[Path, int, int, int, int, int, int],
) -> None:
    path, learner_id, journey_id, proposal_id, *_ = execution_database
    repository = DuckDBLearningSessionRepository(path)
    created = repository.create(session(learner_id, journey_id, proposal_id))
    assert created.session_id > 0 and repository.get(created.session_id) == created
    repository.transition(created.session_id, SessionStatus.CREATED, SessionStatus.READY, NOW)
    repository.transition(created.session_id, SessionStatus.READY, SessionStatus.RUNNING, NOW)
    assert repository.get(created.session_id).status is SessionStatus.RUNNING  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="Expected CREATED"):
        repository.transition(created.session_id, SessionStatus.CREATED, SessionStatus.READY, NOW)


def _persisted_context(
    data: tuple[Path, int, int, int, int, int, int],
) -> tuple[DuckDBLearningSessionRepository, LearningSession, SessionActivity, int]:
    path, learner_id, journey_id, proposal_id, content_id, version_id, question_id = data
    repository = DuckDBLearningSessionRepository(path)
    created = repository.create(session(learner_id, journey_id, proposal_id))
    activity = repository.add_activity(
        SessionActivity(0, created.session_id, content_id, version_id, 1, "exercise", 2, 600)
    )
    return repository, created, activity, question_id


def test_activity_order_and_foreign_keys(
    execution_database: tuple[Path, int, int, int, int, int, int],
) -> None:
    repository, created, activity, _ = _persisted_context(execution_database)
    assert activity.activity_id > 0
    with pytest.raises(Exception, match="Duplicate key"):
        repository.add_activity(replace(activity, activity_id=0))
    with pytest.raises(Exception, match="foreign key"):
        repository.add_activity(replace(activity, activity_id=0, activity_order=2, content_id=999999))
    assert created.session_id == activity.session_id


def test_answer_idempotence(
    execution_database: tuple[Path, int, int, int, int, int, int],
) -> None:
    repository, _, activity, question_id = _persisted_context(execution_database)
    answer = StudentAnswer(
        0, activity.activity_id, question_id, 1, AnswerType.TEXT, " 4 ", "4", NOW, 1200, True, False, "answer-1"
    )
    first = repository.save(answer)
    second = repository.save(answer)
    assert first.answer_id == second.answer_id


def test_assessment_attempt_mastery_transaction_and_idempotence(
    execution_database: tuple[Path, int, int, int, int, int, int],
) -> None:
    repository, _, activity, question_id = _persisted_context(execution_database)
    answer = StudentAnswer(
        0, activity.activity_id, question_id, 1, AnswerType.TEXT, "0", "0", NOW, 1200, False, True, "cycle-1"
    )
    assessment = Assessment(
        0, 0, True, 100, 0, 0, 0, AssessmentMethod.EXACT_MATCH, {"reason": "exact"}, "assessment-v1"
    )
    attempt = Attempt(0, execution_database[1], activity.activity_id, 0, 0, True, 0.2, 0.3, 1200, 0)
    saved = repository.save_cycle(answer, assessment, attempt, {"learning_engine_version": "learning-v1", "delta": 0.1})
    again = repository.save_cycle(answer, assessment, attempt, {"learning_engine_version": "learning-v1", "delta": 0.1})
    assert saved == again
    con = connect_v2(execution_database[0], read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM student_answers WHERE idempotency_key='cycle-1'").fetchone() == (1,)
        assert con.execute("SELECT count(*) FROM answer_assessments").fetchone() == (1,)
        assert con.execute("SELECT count(*) FROM session_attempt_records").fetchone() == (1,)
        assert con.execute("SELECT count(*) FROM session_mastery_updates").fetchone() == (1,)
        assert con.execute("SELECT count(*) FROM attempts").fetchone() == (1,)
    finally:
        con.close()


def test_assessment_cycle_rolls_back_completely(
    execution_database: tuple[Path, int, int, int, int, int, int],
) -> None:
    repository, _, activity, question_id = _persisted_context(execution_database)
    answer = StudentAnswer(
        0, activity.activity_id, question_id, 1, AnswerType.TEXT, "0", "0", NOW, 1200, False, True, "rollback"
    )
    assessment = Assessment(
        0, 0, True, 100, 0, 0, 0, AssessmentMethod.EXACT_MATCH, {"reason": "exact"}, "assessment-v1"
    )
    attempt = Attempt(0, execution_database[1], activity.activity_id, 0, 0, True, 0.2, 0.3, 1200, 0)
    with pytest.raises(TypeError):
        repository.save_cycle(answer, assessment, attempt, {"learning_engine_version": object()})
    con = connect_v2(execution_database[0], read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM student_answers WHERE idempotency_key='rollback'").fetchone() == (0,)
        assert con.execute("SELECT count(*) FROM answer_assessments").fetchone() == (0,)
        assert con.execute("SELECT count(*) FROM session_attempt_records").fetchone() == (0,)
        assert con.execute("SELECT count(*) FROM attempts").fetchone() == (0,)
    finally:
        con.close()


def test_events_checkpoints_and_summary_are_persisted(
    execution_database: tuple[Path, int, int, int, int, int, int],
) -> None:
    repository, created, activity, question_id = _persisted_context(execution_database)
    event = repository.save_event(SessionEvent(0, created.session_id, "SESSION_CREATED", NOW, {}, "corr-1"))
    assert event.event_id == repository.save_event(replace(event, event_id=0)).event_id
    checkpoint = repository.save_checkpoint(
        SessionCheckpoint(0, created.session_id, activity.activity_id, question_id, 1200, None, NOW)
    )
    summary = repository.save_summary(
        SessionSummary(0, created.session_id, 100, 1200, 80, 10, (10001,), (10002,), None)
    )
    assert checkpoint.checkpoint_id > 0 and summary.summary_id > 0


def test_database_constraints_are_enforced(
    execution_database: tuple[Path, int, int, int, int, int, int],
) -> None:
    repository, created, _, _ = _persisted_context(execution_database)
    with pytest.raises(ValueError, match="outside allowed ranges"):
        repository.save_summary(SessionSummary(0, created.session_id, 100, 1200, 80, 101, (), (), None))
