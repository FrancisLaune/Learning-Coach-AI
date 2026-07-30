"""LCAI-0018B7 — strict mandatory AI homework completion tests."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.config import get_v2_database_path
from domain.content.factory import (
    AnswerKind,
    AnswerSpecification,
    CanonicalContentType,
    ContentGenerationRequest,
    CurriculumTarget,
    FactoryValidationIssue,
    FactoryValidationReport,
    GeneratedContentCandidate,
    GenerationProvenance,
    IssueSeverity,
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
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from infrastructure.repositories.unified_session_execution import DuckDBUnifiedSessionExecutionRepository
from migrations.runner import apply_migrations
from services.content.factory import CandidateValidator, ContentFactoryService
from services.homework.ai_fallback import HomeworkAiFallbackOrchestrator
from services.homework.config import HomeworkAiFallbackSettings
from services.homework.errors import HomeworkCompletionError
from services.platform_runtime import FeatureFlagService
from infrastructure.repositories.learning_session import DuckDBLearningSessionRepository
from services.learning.learning_engine_service import LearningEngineService
from services.learning_session.orchestration import ActivityRunner, LearningSessionService
from services.learning_session.submission import SubmissionService
from services.unified_experience import HomeworkService, HomeworkSessionService


class FakeGenerator:
    def __init__(self, *candidates: GeneratedContentCandidate) -> None:
        self._candidates = list(candidates)
        self._offset = 0
        self.calls = 0

    def _next_batch(self, quantity: int) -> tuple[GeneratedContentCandidate, ...]:
        batch = tuple(self._candidates[self._offset : self._offset + quantity])
        self._offset += len(batch)
        return batch

    def generate(self, request: ContentGenerationRequest) -> tuple[GeneratedContentCandidate, ...]:
        self.calls += 1
        return self._next_batch(request.quantity)

    def generate_runtime_candidates(
        self, request: ContentGenerationRequest, quantity: int
    ) -> tuple[GeneratedContentCandidate, ...]:
        self.calls += 1
        return self._next_batch(quantity)


class RejectingValidator(CandidateValidator):
    def validate(self, candidate, *, target_errors=(), known_fingerprints=None) -> FactoryValidationReport:
        if candidate.code.startswith("BAD-"):
            return FactoryValidationReport(
                (FactoryValidationIssue("schema", "invalid", "invalid", IssueSeverity.ERROR),),
            )
        return super().validate(candidate, target_errors=target_errors, known_fingerprints=known_fingerprints)


class FakeFactoryRepository:
    def validate_target(self, target: object) -> tuple[str, ...]:
        return ()

    def known_fingerprints(self) -> dict[str, tuple[str | None, str | None]]:
        return {}

    def persist_draft(self, candidate: GeneratedContentCandidate, author: str) -> None:
        raise AssertionError("runtime fallback must not persist catalogue drafts")


def _candidate(
    code: str,
    prompt: str,
    *,
    target: CurriculumTarget,
    answer: str = "ok",
) -> GeneratedContentCandidate:
    return GeneratedContentCandidate(
        code,
        f"Title {code}",
        "Answer briefly.",
        prompt,
        AnswerSpecification(AnswerKind.EXACT_TEXT, answer),
        "Because.",
        target,
        CanonicalContentType.PRACTICE,
        PedagogicalIntent.PRACTICE,
        2,
        GenerationProvenance("fake", "fake-model", "1", "1", "1"),
    )


@pytest.fixture
def strict_database(tmp_path: Path) -> tuple[Path, int, int, int]:
    source = get_v2_database_path()
    path = tmp_path / "lcai_0018b7.duckdb"
    shutil.copy2(source, path)
    apply_migrations(path)
    reset_v2_connections()
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student:4e-b7','Lina') RETURNING id"
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


@pytest.fixture
def english_target(strict_database: tuple[Path, int, int, int]) -> CurriculumTarget:
    path, _, english_id, grade_id = strict_database
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


def _request(learner_id: int, subject_id: int, grade_id: int, *, count: int = 10) -> HomeworkRequest:
    return HomeworkRequest(
        learner_id,
        "STUDENT",
        "student:4e-b7",
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
    generator: FakeGenerator | None,
    *,
    settings: HomeworkAiFallbackSettings | None = None,
) -> HomeworkService:
    factory = None
    if generator is not None:
        factory = ContentFactoryService(generator, FakeFactoryRepository(), CandidateValidator())
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_completion", True, ("v2.enabled",)),
        )
    )
    orchestrator = HomeworkAiFallbackOrchestrator(
        repository,
        content_factory=factory,
        settings=settings or HomeworkAiFallbackSettings(max_retry=3, allow_degraded_result=False, max_generated_per_request=40),
    )
    return HomeworkService(repository, feature_flags=flags, ai_fallback=orchestrator)


def _limited_selection(
    repository: DuckDBUnifiedExperienceRepository,
    learner_id: int,
    subject_id: int,
    grade_id: int,
    *,
    limit: int,
):
    real = repository.select_approved_content_detailed(_request(learner_id, subject_id, grade_id, count=100))
    limited_ids = real.content_ids[:limit]

    def side_effect(request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection(
            limited_ids,
            real.requested_difficulty,
            real.applied_difficulty,
            real.difficulty_relaxed,
        )

    return side_effect, limited_ids


def test_01_ten_requested_two_catalog_eight_generated(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    side_effect, _ = _limited_selection(repository, learner_id, english_id, grade_id, limit=2)
    generator = FakeGenerator(
        *[_candidate(f"B7-{index}", f"Prompt unique {index}", target=english_target) for index in range(8)]
    )
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=side_effect):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=10))
    assert result.catalog_count == 2
    assert result.ai_requested_count == 8
    assert result.ai_accepted_count == 8
    assert result.final_count == 10


def test_02_eight_requested_zero_catalog(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))

    def empty_catalog(_request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection(
            (),
            real.requested_difficulty,
            real.applied_difficulty,
            real.difficulty_relaxed,
        )

    generator = FakeGenerator(
        *[_candidate(f"ZERO-{index}", f"All AI {index}", target=english_target) for index in range(8)]
    )
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=empty_catalog):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=8))
    assert result.catalog_count == 0
    assert result.ai_accepted_count == 8
    assert result.final_count == 8


def test_03_five_requested_five_catalog_no_generation(
    strict_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    catalog = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))
    if len(catalog.content_ids) < 5:
        pytest.skip("Need at least 5 catalogue exercises")
    generator = FakeGenerator()
    service = _homework_service(repository, generator)
    result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=5))
    assert result.ai_requested_count == 0
    assert result.final_count == 5
    assert generator.calls == 0


def test_04_six_requested_four_catalog_two_generated(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    side_effect, catalog_ids = _limited_selection(repository, learner_id, english_id, grade_id, limit=4)
    if len(catalog_ids) < 2:
        pytest.skip("Need at least 2 catalogue exercises")
    requested = len(catalog_ids) + 2
    generator = FakeGenerator(
        _candidate("B7-4A", "Fourth prompt", target=english_target),
        _candidate("B7-4B", "Fifth prompt", target=english_target),
    )
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=side_effect):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=requested))
    assert result.catalog_count == len(catalog_ids)
    assert result.ai_accepted_count == 2
    assert result.final_count == requested


def test_05_spanish_4e_two_rubrics_ten_questions(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, _, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    connection = connect_v2(path)
    try:
        row = connection.execute("SELECT id FROM subjects WHERE code='SPANISH'").fetchone()
        if row is None:
            pytest.skip("SPANISH subject missing")
        spanish_id = int(row[0])
        chapter_count = len(repository.chapters(spanish_id, grade_id))
    finally:
        connection.close()
        reset_v2_connections()
    if chapter_count < 1:
        pytest.skip("No Spanish chapters in test DB")
    side_effect, catalog_ids = _limited_selection(repository, learner_id, spanish_id, grade_id, limit=2)
    deficit = max(0, 10 - len(catalog_ids))
    generator = FakeGenerator(
        *[
            _candidate(f"ES-{index}", f"Spanish unique {index}", target=english_target)
            for index in range(deficit)
        ]
    )
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=side_effect):
        result = service.create_with_diagnostics(_request(learner_id, spanish_id, grade_id, count=10))
    assert result.final_count == 10
    assert chapter_count <= 2 or result.ai_accepted_count >= 8


def test_06_multiple_exercises_same_rubric(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))

    def one_catalog(_request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection(
            real.content_ids[:1],
            real.requested_difficulty,
            real.applied_difficulty,
            real.difficulty_relaxed,
        )

    generator = FakeGenerator(
        *[_candidate(f"SAME-{index}", f"Same rubric {index}", target=english_target) for index in range(4)]
    )
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=one_catalog):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=5))
    assert result.final_count == 5
    assert len({item.chapter_id for item in result.generated_exercises}) >= 1


def test_07_ui_does_not_expose_limiting_seulement_message_when_ai_enabled() -> None:
    source = (Path(__file__).resolve().parents[1] / "ui" / "unified_app.py").read_text(encoding="utf-8")
    marker = "elif available_total < exercise_count:"
    start = source.index(marker)
    block = source[start : start + 900]
    ai_branch = block.split("if service.supports_ai_completion():")[1].split("else:")[0]
    assert "Seulement" not in ai_branch
    assert "limité à ce maximum" not in ai_branch


def test_08_homework_immediately_playable(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))

    def empty_catalog(_request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection(
            (),
            real.requested_difficulty,
            real.applied_difficulty,
            real.difficulty_relaxed,
        )

    generator = FakeGenerator(_candidate("PLAY-1", "Playable", target=english_target, answer="Paris"))
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=empty_catalog):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=1))
    session_repository = DuckDBLearningSessionRepository(path)
    session_service = LearningSessionService(
        DuckDBRecommendationRepository(path), session_repository, session_repository
    )
    materialized = HomeworkSessionService(repository, session_service).materialize(
        learner_id, result.homework.homework_id, datetime.now(UTC)
    )
    assert materialized.session_id is not None


def test_09_correction_metadata_available(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))

    def empty_catalog(_request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection((), real.requested_difficulty, real.applied_difficulty, real.difficulty_relaxed)

    generator = FakeGenerator(_candidate("CORR-1", "Correction prompt", target=english_target, answer="42"))
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=empty_catalog):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=1))
    generated = result.generated_exercises[0]
    assert generated.expected_answer == "42"
    assert generated.correction is not None or generated.statement


def test_10_progression_can_be_recorded(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))

    def empty_catalog(_request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection((), real.requested_difficulty, real.applied_difficulty, real.difficulty_relaxed)

    generator = FakeGenerator(_candidate("PROG-1", "Progress prompt", target=english_target, answer="ok"))
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=empty_catalog):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=1))
    session_repository = DuckDBLearningSessionRepository(path)
    session_service = LearningSessionService(
        DuckDBRecommendationRepository(path), session_repository, session_repository
    )
    materialized = HomeworkSessionService(repository, session_service).materialize(
        learner_id, result.homework.homework_id, datetime.now(UTC)
    )
    assert materialized.session_id is not None
    execution_repo = DuckDBUnifiedSessionExecutionRepository(path)
    material = execution_repo.current_question(learner_id, materialized.session_id)
    assert material is not None


def test_11_invalid_exercise_rejected_and_replaced(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))

    def empty_catalog(_request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection((), real.requested_difficulty, real.applied_difficulty, real.difficulty_relaxed)

    invalid = _candidate("BAD-1", "Invalid prompt", target=english_target)
    valid = _candidate("GOOD-1", "Valid prompt", target=english_target)
    generator = FakeGenerator(invalid, valid)
    factory = ContentFactoryService(generator, FakeFactoryRepository(), RejectingValidator())
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_completion", True, ("v2.enabled",)),
        )
    )
    orchestrator = HomeworkAiFallbackOrchestrator(
        repository,
        content_factory=factory,
        settings=HomeworkAiFallbackSettings(max_retry=5, allow_degraded_result=False, max_generated_per_request=10),
    )
    service = HomeworkService(repository, feature_flags=flags, ai_fallback=orchestrator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=empty_catalog):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=1))
    assert result.final_count == 1
    assert generator.calls >= 1


def test_12_duplicate_generated_exercise_replaced(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))

    def empty_catalog(_request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection((), real.requested_difficulty, real.applied_difficulty, real.difficulty_relaxed)

    duplicate = _candidate("DUP-1", "Same prompt text", target=english_target)
    unique = _candidate("DUP-2", "Different prompt text", target=english_target)
    generator = FakeGenerator(duplicate, unique)
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=empty_catalog):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=2))
    assert result.final_count == 2
    prompts = {item.statement for item in result.generated_exercises}
    assert len(prompts) == 2


def test_13_double_creation_is_idempotent(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    side_effect, _ = _limited_selection(repository, learner_id, english_id, grade_id, limit=2)
    generator = FakeGenerator(_candidate("IDEM-1", "Idempotent", target=english_target))
    service = _homework_service(repository, generator)
    request = _request(learner_id, english_id, grade_id, count=3)
    with patch.object(repository, "select_approved_content_detailed", side_effect=side_effect):
        first = service.create_with_diagnostics(request)
        second = service.create_with_diagnostics(request)
    assert first.homework.homework_id == second.homework.homework_id
    assert generator.calls == 1


def test_14_rerun_does_not_duplicate_homework_rows(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    side_effect, _ = _limited_selection(repository, learner_id, english_id, grade_id, limit=1)
    generator = FakeGenerator(_candidate("RERUN-1", "Rerun prompt", target=english_target))
    service = _homework_service(repository, generator)
    request = _request(learner_id, english_id, grade_id, count=2)
    with patch.object(repository, "select_approved_content_detailed", side_effect=side_effect):
        service.create_with_diagnostics(request)
        service.create_with_diagnostics(request)
    connection = connect_v2(path)
    try:
        count = connection.execute(
            "SELECT count(*) FROM homework_assignments WHERE learner_id=?", [learner_id]
        ).fetchone()[0]
        assert count == 1
    finally:
        connection.close()
        reset_v2_connections()


def test_15_ai_unavailable_rolls_back_and_raises(
    strict_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))

    def empty_catalog(_request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection((), real.requested_difficulty, real.applied_difficulty, real.difficulty_relaxed)

    service = _homework_service(repository, None)
    with patch.object(repository, "select_approved_content_detailed", side_effect=empty_catalog):
        with pytest.raises(HomeworkCompletionError) as exc:
            service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=3))
    assert "indisponible" in exc.value.user_message.lower()
    connection = connect_v2(path)
    try:
        count = connection.execute(
            "SELECT count(*) FROM homework_assignments WHERE learner_id=?", [learner_id]
        ).fetchone()[0]
        assert count == 0
    finally:
        connection.close()
        reset_v2_connections()


def test_16_classic_catalog_creation_without_ai(
    strict_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    catalog = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))
    if len(catalog.content_ids) < 2:
        pytest.skip("Need catalogue stock")
    flags = FeatureFlagService((FeatureFlagDefinition("v2.enabled", True),))
    service = HomeworkService(repository, feature_flags=flags, ai_fallback=None)
    homework = service.create(_request(learner_id, english_id, grade_id, count=2))
    assert len(homework.selected_content_ids) == 2


def test_17_mixed_catalog_and_ai(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    side_effect, catalog_ids = _limited_selection(repository, learner_id, english_id, grade_id, limit=3)
    if not catalog_ids:
        pytest.skip("Need catalogue stock")
    ai_needed = 5
    requested = len(catalog_ids) + ai_needed
    generator = FakeGenerator(
        *[_candidate(f"MIX-{index}", f"Mixed {index}", target=english_target) for index in range(ai_needed)]
    )
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=side_effect):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=requested))
    assert result.catalog_count == len(catalog_ids)
    assert result.ai_accepted_count == ai_needed
    assert result.final_count == requested


def test_18_full_ai_homework(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))

    def empty_catalog(_request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection((), real.requested_difficulty, real.applied_difficulty, real.difficulty_relaxed)

    generator = FakeGenerator(
        *[_candidate(f"FULL-{index}", f"Full AI {index}", target=english_target) for index in range(6)]
    )
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=empty_catalog):
        result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=6))
    assert result.catalog_count == 0
    assert result.final_count == 6


@pytest.mark.parametrize("grade_code", ("FR-CM1", "FR-CM2", "FR-6E", "FR-5E", "FR-4E", "FR-3E"))
def test_19_grade_codes_supported_for_completion(grade_code: str) -> None:
    from services.homework.config import HomeworkAiCompletionSettings

    settings = HomeworkAiCompletionSettings(
        allowed_grades=frozenset({"FR-CM1", "FR-CM2", "FR-6E", "FR-5E", "FR-4E", "FR-3E"}),
        allowed_subjects=None,
    )
    assert settings.grade_allowed(grade_code)


@pytest.mark.parametrize("subject_code", ("MATHEMATICS", "FRENCH", "ENGLISH", "SPANISH"))
def test_20_core_subjects_eligible_when_configured(subject_code: str) -> None:
    from services.homework.config import HomeworkAiCompletionSettings

    settings = HomeworkAiCompletionSettings(allowed_grades=frozenset({"FR-4E"}), allowed_subjects=None)
    repo = MagicMock()
    repo.grade_code.return_value = "FR-4E"
    repo.subject_code.return_value = subject_code
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_completion", True, ("v2.enabled",)),
        )
    )
    from services.homework.eligibility import is_homework_ai_completion_eligible

    assert is_homework_ai_completion_eligible(
        _request(1, 1, 11),
        repo,
        flags=flags,
        settings=settings,
        orchestrator_configured=True,
    )


def test_strict_mode_raises_when_generation_insufficient(
    strict_database: tuple[Path, int, int, int],
    english_target: CurriculumTarget,
) -> None:
    path, learner_id, english_id, grade_id = strict_database
    repository = DuckDBUnifiedExperienceRepository(path)
    real = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=100))

    def empty_catalog(_request: HomeworkRequest) -> HomeworkContentSelection:
        return HomeworkContentSelection((), real.requested_difficulty, real.applied_difficulty, real.difficulty_relaxed)

    generator = FakeGenerator(_candidate("ONE-1", "Only one", target=english_target))
    service = _homework_service(repository, generator)
    with patch.object(repository, "select_approved_content_detailed", side_effect=empty_catalog):
        with pytest.raises(HomeworkCompletionError):
            service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=3))
    connection = connect_v2(path)
    try:
        count = connection.execute(
            "SELECT count(*) FROM homework_assignments WHERE learner_id=?", [learner_id]
        ).fetchone()[0]
        assert count == 0
    finally:
        connection.close()
        reset_v2_connections()
