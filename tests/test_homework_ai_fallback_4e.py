"""LCAI-0018B — homework AI fallback for 4e."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

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
from domain.unified_experience.models import AssignmentType, DifficultyMode, HomeworkRequest
from infrastructure.database.v2 import connect_v2, reset_v2_connections
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from migrations.runner import apply_migrations
from services.content.factory import CandidateValidator, ContentFactoryService
from services.homework.ai_fallback import HomeworkAiFallbackOrchestrator
from services.homework.curriculum_target import resolve_curriculum_target
from services.homework.factory import build_homework_service
from services.platform_runtime import FeatureFlagService
from services.unified_experience import HomeworkService

ROOT = Path(__file__).resolve().parents[1]


class FakeGenerator:
    def __init__(self, *candidates: GeneratedContentCandidate) -> None:
        self._candidates = candidates
        self.calls = 0

    def generate(self, request: ContentGenerationRequest) -> tuple[GeneratedContentCandidate, ...]:
        self.calls += 1
        return self._candidates[: request.quantity]


class FakeFactoryRepository:
    def validate_target(self, target: object) -> tuple[str, ...]:
        return ()

    def known_fingerprints(self) -> dict[str, tuple[str | None, str | None]]:
        return {}

    def persist_draft(self, candidate: GeneratedContentCandidate, author: str) -> None:
        raise AssertionError("runtime fallback must not persist catalogue drafts")


def _candidate(code: str, prompt: str) -> GeneratedContentCandidate:
    target = CurriculumTarget("FR-COLLEGE-2025", "4e", "ENGLISH", "CH1", "SK1")
    return GeneratedContentCandidate(
        code,
        f"Title {code}",
        "Answer briefly.",
        prompt,
        AnswerSpecification(AnswerKind.EXACT_TEXT, "ok"),
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
    path = tmp_path / "lcai_0018b.duckdb"
    shutil.copy2(source, path)
    apply_migrations(path)
    reset_v2_connections()
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student:4e-b4','Noa') RETURNING id"
            ).fetchone()[0]
        )
        grade_id = int(connection.execute("SELECT id FROM school_levels WHERE code='FR-4E'").fetchone()[0])
        program_id = int(connection.execute("SELECT id FROM programs LIMIT 1").fetchone()[0])
        connection.execute(
            """INSERT INTO learner_journeys(learner_id,current_school_level_id,academic_year_start,program_id,learning_phase)
            VALUES (?,?,2026,?,'current_learning')""",
            [learner_id, grade_id, program_id],
        )
        english_id = int(connection.execute("SELECT id FROM subjects WHERE code='ENGLISH'").fetchone()[0])
    finally:
        connection.close()
        reset_v2_connections()
    return path, learner_id, english_id, grade_id


def _request(learner_id: int, subject_id: int, grade_id: int, *, count: int = 10) -> HomeworkRequest:
    return HomeworkRequest(
        learner_id,
        "STUDENT",
        "student:4e-b4",
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


def test_flag_off_preserves_legacy_homework_creation(
    fallback_database: tuple[Path, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    monkeypatch.delenv("HOMEWORK_AI_FALLBACK_4E_ENABLED", raising=False)
    flags = FeatureFlagService((FeatureFlagDefinition("v2.enabled", True), FeatureFlagDefinition("homework_ai_fallback_4e", False, ("v2.enabled",))))
    service = HomeworkService(DuckDBUnifiedExperienceRepository(path), feature_flags=flags)
    homework = service.create(_request(learner_id, english_id, grade_id))
    assert homework.selected_content_ids


def test_flag_on_persists_runtime_exercises_with_stub_generator(
    fallback_database: tuple[Path, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    repository = DuckDBUnifiedExperienceRepository(path)
    factory = ContentFactoryService(
        FakeGenerator(*[_candidate(f"RT-{index}", f"Prompt unique {index}") for index in range(3)]),
        FakeFactoryRepository(),
        CandidateValidator(),
    )
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_fallback_4e", True, ("v2.enabled",)),
        )
    )
    orchestrator = HomeworkAiFallbackOrchestrator(repository, content_factory=factory)
    service = HomeworkService(repository, feature_flags=flags, ai_fallback=orchestrator)
    result = service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=10))
    assert result.runtime_exercise_ids
    connection = connect_v2(path)
    try:
        rows = connection.execute(
            "SELECT publication_status, source FROM homework_runtime_exercises WHERE homework_id=?",
            [result.homework.homework_id],
        ).fetchall()
    finally:
        connection.close()
        reset_v2_connections()
    assert rows
    assert all(str(row[0]) == "RUNTIME_ONLY" for row in rows)
    assert all(str(row[1]) == "ai_runtime_fallback" for row in rows)


def test_runtime_candidates_never_call_catalogue_persist(
    fallback_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    repository = DuckDBUnifiedExperienceRepository(path)
    factory_repo = FakeFactoryRepository()
    factory = ContentFactoryService(FakeGenerator(_candidate("X1", "Unique prompt")), factory_repo, CandidateValidator())
    orchestrator = HomeworkAiFallbackOrchestrator(repository, content_factory=factory)
    flags = FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", True),
            FeatureFlagDefinition("homework_ai_fallback_4e", True, ("v2.enabled",)),
        )
    )
    service = HomeworkService(repository, feature_flags=flags, ai_fallback=orchestrator)
    service.create_with_diagnostics(_request(learner_id, english_id, grade_id, count=10))


def test_resolve_curriculum_target_for_english_4e(
    fallback_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, english_id, grade_id = fallback_database
    repository = DuckDBUnifiedExperienceRepository(path)
    target = resolve_curriculum_target(repository, _request(learner_id, english_id, grade_id))
    assert target.subject_code == "ENGLISH"
    assert target.grade_code == "FR-4E"
    assert target.chapter_code
    assert target.primary_skill_code


def test_build_homework_service_without_flag_has_no_fallback(
    fallback_database: tuple[Path, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, _, _ = fallback_database
    monkeypatch.delenv("HOMEWORK_AI_FALLBACK_4E_ENABLED", raising=False)
    monkeypatch.delenv("LCAI_ENABLE_V2_UI", raising=False)
    service = build_homework_service(DuckDBUnifiedExperienceRepository(path))
    assert not service.supports_ai_fallback()


def test_build_homework_service_with_flag_uses_openai_config(
    fallback_database: tuple[Path, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _, _, _ = fallback_database
    monkeypatch.setenv("LCAI_ENABLE_V2_UI", "true")
    monkeypatch.setenv("HOMEWORK_AI_FALLBACK_4E_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    service = build_homework_service(DuckDBUnifiedExperienceRepository(path))
    assert service.supports_ai_fallback()
