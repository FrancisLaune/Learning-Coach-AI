"""LCAI-0018B5 — runtime generated homework playability."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from core.config import get_v2_database_path
from domain.content.factory import (
    AnswerKind,
    AnswerSpecification,
    CanonicalContentType,
    ContentGenerationRequest,
    CurriculumTarget,
    GeneratedContentCandidate,
    GenerationProvenance,
    PedagogicalIntent,
)
from domain.platform_runtime.models import FeatureFlagDefinition
from domain.unified_experience.models import (
    AssignmentType,
    DifficultyMode,
    HomeworkContentSelection,
    HomeworkRequest,
)
from infrastructure.database.v2 import connect_v2, reset_v2_connections
from infrastructure.repositories.learning import DuckDBLearningRepository
from infrastructure.repositories.learning_session import DuckDBLearningSessionRepository
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from infrastructure.repositories.unified_session_execution import DuckDBUnifiedSessionExecutionRepository
from migrations.runner import apply_migrations
from services.content.factory import CandidateValidator, ContentFactoryService
from services.homework.ai_fallback import HomeworkAiFallbackOrchestrator
from services.homework.runtime_persistence import is_playable_candidate
from services.learning.learning_engine_service import LearningEngineService
from services.learning_session.orchestration import ActivityRunner, LearningSessionService
from services.learning_session.submission import SubmissionService
from services.platform_runtime import FeatureFlagService
from services.unified_experience import HomeworkService, HomeworkSessionService
from services.unified_session_execution import DecisionRefreshNotifier, UnifiedSessionExecutionService


class FakeGenerator:
    def __init__(self, *candidates: GeneratedContentCandidate) -> None:
        self._candidates = candidates
        self.calls = 0

    def generate(self, request: ContentGenerationRequest) -> tuple[GeneratedContentCandidate, ...]:
        self.calls += 1
        return self._candidates[: request.quantity]

    def generate_runtime_candidates(
        self, request: ContentGenerationRequest, quantity: int
    ) -> tuple[GeneratedContentCandidate, ...]:
        self.calls += 1
        return self._candidates[:quantity]


class FakeFactoryRepository:
    def validate_target(self, target: object) -> tuple[str, ...]:
        return ()

    def known_fingerprints(self) -> dict[str, tuple[str | None, str | None]]:
        return {}

    def persist_draft(self, candidate: GeneratedContentCandidate, author: str) -> None:
        raise AssertionError("runtime fallback must not persist catalogue drafts")


@pytest.fixture
def english_target(fallback_database: tuple[Path, int, int, int]) -> CurriculumTarget:
    path, _, english_id, grade_id = fallback_database
    connection = connect_v2(path)
    try:
        row = connection.execute(
            """
            SELECT p.code, sl.code, su.code, cc.stable_code, s.code
            FROM curriculum_chapters cc
            JOIN programs p ON p.id=cc.program_id
            JOIN school_levels sl ON sl.id=cc.grade_level_id
            JOIN subjects su ON su.id=cc.subject_id
            JOIN curriculum_skill_details csd ON csd.chapter_id=cc.id AND csd.grade_level_id=cc.grade_level_id
            JOIN skills s ON s.id=csd.skill_id
            WHERE su.id=? AND sl.id=? AND cc.status='approved' AND csd.status='approved'
            ORDER BY cc.sequence_order, s.code LIMIT 1
            """,
            [english_id, grade_id],
        ).fetchone()
        assert row is not None
        return CurriculumTarget(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]))
    finally:
        connection.close()
        reset_v2_connections()


def _candidate(
    code: str,
    prompt: str,
    *,
    target: CurriculumTarget,
    answer: str = "ok",
    kind: AnswerKind = AnswerKind.EXACT_TEXT,
) -> GeneratedContentCandidate:
    return GeneratedContentCandidate(
        code,
        f"Title {code}",
        "Answer briefly.",
        prompt,
        AnswerSpecification(kind, answer),
        "Because.",
        target,
        CanonicalContentType.PRACTICE,
        PedagogicalIntent.PRACTICE,
        2,
        GenerationProvenance("fake", "fake-model", "1", "1", "1"),
    )


@pytest.fixture
def fallback_database(tmp_path: Path) -> tuple[Path, int, int, int]:
    source = get_v2_database_path()
    path = tmp_path / "lcai_0018b5.duckdb"
    shutil.copy2(source, path)
    apply_migrations(path)
    reset_v2_connections()
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student:4e-b5','Noa') RETURNING id"
            ).fetchone()[0]
        )
        grade_id = int(connection.execute("SELECT id FROM school_levels WHERE code='FR-4E'").fetchone()[0])
        program_id = int(connection.execute("SELECT id FROM programs LIMIT 1").fetchone()[0])
        connection.execute(
            """INSERT INTO learner_journeys(learner_id,current_school_level_id,academic_year_start,program_id,learning_phase)
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
        english_id = int(connection.execute("SELECT id FROM subjects WHERE code='ENGLISH'").fetchone()[0])
    finally:
        connection.close()
        reset_v2_connections()
    return path, learner_id, english_id, grade_id


def _request(learner_id: int, subject_id: int, grade_id: int, *, count: int = 8) -> HomeworkRequest:
    return HomeworkRequest(
        learner_id,
        "STUDENT",
        "student:4e-b5",
        AssignmentType.GLOBAL_SUBJECT,
        subject_id,
        grade_id,
        (),
        (),
        DifficultyMode.MEDIUM,
        count,
        30,
        datetime.now(tz=UTC),
    )


def _homework_service(
    repository: DuckDBUnifiedExperienceRepository,
    generator: FakeGenerator,
) -> HomeworkService:
    factory = ContentFactoryService(generator, FakeFactoryRepository(), CandidateValidator())
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_fallback_4e", True, ("v2.enabled",)),
        )
    )
    orchestrator = HomeworkAiFallbackOrchestrator(repository, content_factory=factory)
    return HomeworkService(repository, feature_flags=flags, ai_fallback=orchestrator)


def test_catalog_sufficient_skips_openai(
    fallback_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    repository = DuckDBUnifiedExperienceRepository(path)
    selection = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=1))
    if len(selection.content_ids) < 1:
        pytest.skip("Insufficient catalogue stock in test database")
    generator = FakeGenerator(_candidate("SKIP", "unused", target=english_target))
    service = _homework_service(repository, generator)
    result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=1))
    assert generator.calls == 0
    assert result.ai_requested_count == 0
    assert result.final_count == 1


def test_deficit_triggers_generation_only_for_missing_count(
    fallback_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    repository = DuckDBUnifiedExperienceRepository(path)
    catalog = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))
    catalog_count = len(catalog.content_ids)
    if catalog_count == 0:
        pytest.skip("No catalogue content for ENGLISH 4e")
    requested = catalog_count + 3
    generator = FakeGenerator(
        *[_candidate(f"RT-{index}", f"Unique prompt {index}", target=english_target) for index in range(5)]
    )
    service = _homework_service(repository, generator)
    result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=requested))
    assert result.catalog_count == catalog_count
    assert result.ai_requested_count == 3
    assert result.ai_accepted_count == 3
    assert result.final_count == requested
    assert len(result.generated_exercises) == 3


def test_generated_exercise_included_in_proposal_items(
    fallback_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))
    if len(real.content_ids) < 2:
        pytest.skip("Need at least 2 catalogue exercises for mixed proposal test")
    limited_ids = real.content_ids[:2]

    def limited_selection(request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection(
            limited_ids,
            real.requested_difficulty,
            real.applied_difficulty,
            real.difficulty_relaxed,
        )

    generator = FakeGenerator(
        *[_candidate(f"PLAY-{index}", f"Playable prompt {index}", target=english_target) for index in range(6)]
    )
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=limited_selection):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=8))
    assert result.final_count == 8
    assert result.ai_accepted_count == 6

    proposal_id = repository.create_homework_proposal(result.homework.homework_id)
    connection = connect_v2(path)
    try:
        items = connection.execute(
            "SELECT content_id, position FROM personalized_session_items WHERE proposal_id=? ORDER BY position",
            [proposal_id],
        ).fetchall()
        runtime_ids = {int(item.exercise_id) for item in result.generated_exercises}
        proposal_ids = {int(row[0]) for row in items}
        assert runtime_ids <= proposal_ids
        assert len(items) == 8
        assert len({row[0] for row in items}) == 8
    finally:
        connection.close()
        reset_v2_connections()


def test_runtime_exercise_is_playable_in_student_session(
    fallback_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real_selection = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=1))

    def limited_selection(request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection(
            (),
            real_selection.requested_difficulty,
            real_selection.applied_difficulty,
            real_selection.difficulty_relaxed,
        )

    generator = FakeGenerator(_candidate("SOLO-1", "Single runtime exercise", target=english_target, answer="Paris"))
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=limited_selection):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=1))
    assert result.ai_accepted_count == 1

    session_repository = DuckDBLearningSessionRepository(path)
    session_service = LearningSessionService(
        DuckDBRecommendationRepository(path), session_repository, session_repository
    )
    materialized = HomeworkSessionService(repository, session_service).materialize(
        learner_id, result.homework.homework_id, datetime.now(UTC)
    )
    assert materialized.session_id is not None
    session_service.start_session(materialized.session_id, datetime.now(UTC))

    execution_repository = DuckDBUnifiedSessionExecutionRepository(path)
    material = execution_repository.current_question(learner_id, materialized.session_id)
    assert material is not None
    assert material.expected_answer == "Paris"

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
    answer = execution.submit(
        learner_id,
        materialized.session_id,
        "Paris",
        datetime.now(UTC),
        1000,
    )
    assert answer.correct

    connection = connect_v2(path)
    try:
        runtime_id = int(result.generated_exercises[0].exercise_id)
        attempt = connection.execute(
            """SELECT count(*) FROM student_answers ans
            JOIN session_activities a ON a.id=ans.activity_id
            WHERE a.session_id=? AND a.content_id=? AND ans.validated""",
            [materialized.session_id, runtime_id],
        ).fetchone()
        assert attempt == (1,)
    finally:
        connection.close()
        reset_v2_connections()


def test_non_playable_candidate_rejected(
    english_target: CurriculumTarget,
) -> None:
    unsupported = _candidate("BAD", "prompt", target=english_target)
    unsupported = GeneratedContentCandidate(
        unsupported.code,
        unsupported.title,
        unsupported.instructions,
        unsupported.prompt,
        AnswerSpecification(AnswerKind.EXACT_TEXT, ""),
        unsupported.explanation,
        unsupported.target,
        unsupported.content_type,
        unsupported.pedagogical_intent,
        unsupported.difficulty,
        unsupported.provenance,
    )
    assert not is_playable_candidate(unsupported)


def test_fallback_disabled_preserves_catalog_only_behavior(
    fallback_database: tuple[Path, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    monkeypatch.delenv("HOMEWORK_AI_FALLBACK_4E_ENABLED", raising=False)
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_fallback_4e", False, ("v2.enabled",)),
        )
    )
    service = HomeworkService(DuckDBUnifiedExperienceRepository(path), feature_flags=flags)
    homework = service.create(_request(learner_id, english_id, grade_id, count=3))
    assert homework.selected_content_ids


def test_idempotent_homework_creation_does_not_duplicate_runtime_rows(
    fallback_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real_selection = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))
    limited_ids = real_selection.content_ids[:2]

    def limited_selection(request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection(
            limited_ids,
            real_selection.requested_difficulty,
            real_selection.applied_difficulty,
            real_selection.difficulty_relaxed,
        )

    generator = FakeGenerator(_candidate("IDEM-1", "Idempotent prompt", target=english_target))
    service = _homework_service(repository, generator)
    request = _request(learner_id, english_id, grade_id, count=3)
    with patch.object(repository, "select_approved_content_detailed", side_effect=limited_selection):
        first = service.create_with_diagnostics(request)
        second = service.create_with_diagnostics(request)
    assert first.homework.homework_id == second.homework.homework_id
    assert second.ai_requested_count == 0
    assert generator.calls == 1
    connection = connect_v2(path)
    try:
        count = connection.execute(
            "SELECT count(*) FROM homework_runtime_exercises WHERE homework_id=?",
            [first.homework.homework_id],
        ).fetchone()[0]
        assert count == 1
    finally:
        connection.close()
        reset_v2_connections()


def test_runtime_traceability_metadata_persisted(
    fallback_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real_selection = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=1))

    def empty_catalog(request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection(
            (),
            real_selection.requested_difficulty,
            real_selection.applied_difficulty,
            real_selection.difficulty_relaxed,
        )

    generator = FakeGenerator(_candidate("TRACE-1", "Trace prompt", target=english_target))
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=empty_catalog):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=1))
    generated = result.generated_exercises[0]
    assert generated.source == "ai_runtime_fallback"
    assert generated.provider == "fake"
    assert generated.model == "fake-model"
    connection = connect_v2(path)
    try:
        row = connection.execute(
            """SELECT source, generator_model, content_id, content_version_id
            FROM homework_runtime_exercises WHERE homework_id=?""",
            [result.homework.homework_id],
        ).fetchone()
        assert row is not None
        assert row[0] == "ai_runtime_fallback"
        assert row[1] == "fake-model"
        assert row[2] is not None
        assert row[3] is not None
        payload = connection.execute(
            "SELECT payload FROM content_versions WHERE id=?", [int(row[3])]
        ).fetchone()
        assert payload is not None
        data = json.loads(str(payload[0]))
        assert data["homework_runtime"]["source"] == "ai_runtime_fallback"
    finally:
        connection.close()
        reset_v2_connections()
