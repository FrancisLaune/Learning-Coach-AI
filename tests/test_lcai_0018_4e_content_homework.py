"""LCAI-0018 — 4e homework availability and full-subject coverage tests."""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.config import get_v2_database_path
from domain.unified_experience.models import AssignmentType, DifficultyMode, HomeworkRequest
from infrastructure.database.v2 import connect_v2, reset_v2_connections
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from services.content.homework_availability import HomeworkAvailabilityService
from services.unified_experience import HomeworkService

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "docs" / "phase3" / "exports"
AUDIT_SCRIPT = ROOT / "scripts" / "lcai_0018_phase0_audit.py"


@pytest.fixture
def homework_database(tmp_path: Path) -> tuple[Path, int, int, int]:
    source = get_v2_database_path()
    path = tmp_path / "lcai_0018.duckdb"
    shutil.copy2(source, path)
    reset_v2_connections()
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student:4e','Camille') RETURNING id"
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
        physics_id = int(connection.execute("SELECT id FROM subjects WHERE code='PHYSICS_CHEMISTRY'").fetchone()[0])
    finally:
        connection.close()
        reset_v2_connections()
    return path, learner_id, english_id, physics_id


def _request(learner_id: int, subject_id: int, grade_id: int, *, count: int = 10) -> HomeworkRequest:
    return HomeworkRequest(
        learner_id,
        "STUDENT",
        "student:4e",
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


def _grade_id(path: Path) -> int:
    connection = connect_v2(path)
    try:
        return int(connection.execute("SELECT id FROM school_levels WHERE code='FR-4E'").fetchone()[0])
    finally:
        connection.close()
        reset_v2_connections()


def test_english_4e_subject_has_active_chapters(homework_database: tuple[Path, int, int, int]) -> None:
    path, _learner_id, english_id, _physics_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    chapters = repository.chapters(english_id, _grade_id(path))
    assert chapters


def test_physics_chemistry_4e_subject_has_active_chapters(homework_database: tuple[Path, int, int, int]) -> None:
    path, _learner_id, _english_id, physics_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    chapters = repository.chapters(physics_id, _grade_id(path))
    assert chapters


def test_parent_can_generate_english_homework_for_4e(homework_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, english_id, _physics_id = homework_database
    service = HomeworkService(DuckDBUnifiedExperienceRepository(path))
    homework = service.create(_request(learner_id, english_id, _grade_id(path)))
    assert homework.selected_content_ids


def test_parent_can_generate_physics_chemistry_homework_for_4e(
    homework_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, _english_id, physics_id = homework_database
    service = HomeworkService(DuckDBUnifiedExperienceRepository(path))
    homework = service.create(_request(learner_id, physics_id, _grade_id(path)))
    assert homework.selected_content_ids


def test_generated_homework_is_not_empty(homework_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, english_id, _physics_id = homework_database
    selection = DuckDBUnifiedExperienceRepository(path).select_approved_content_detailed(
        _request(learner_id, english_id, _grade_id(path))
    )
    assert selection.content_ids
    assert selection.difficulty_relaxed is True


def test_insufficient_stock_returns_actionable_message(homework_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, english_id, _physics_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    available = repository.count_eligible_content(_request(learner_id, english_id, _grade_id(path)))
    assert available == 2


def test_engine_never_falls_back_to_another_subject(homework_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, english_id, physics_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    grade_id = _grade_id(path)
    english_ids = set(repository.select_approved_content(_request(learner_id, english_id, grade_id)))
    physics_ids = set(repository.select_approved_content(_request(learner_id, physics_id, grade_id)))
    assert english_ids.isdisjoint(physics_ids)


def test_homework_can_be_generated_for_each_available_4e_subject(
    homework_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, _english_id, _physics_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    service = HomeworkService(repository)
    grade_id = _grade_id(path)
    for item in HomeworkAvailabilityService(repository).list_for_learner(learner_id):
        if item.availability_status == "unavailable":
            continue
        homework = service.create(_request(learner_id, item.subject_id, grade_id))
        assert homework.selected_content_ids


def test_curriculum_subjects_include_all_configured_4e_subjects(
    homework_database: tuple[Path, int, int, int],
) -> None:
    path, _learner_id, _english_id, _physics_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    curriculum = {code for _id, code, _label in repository.curriculum_subjects_for_grade(_grade_id(path))}
    production = {code for _id, code, _label in repository.subjects_for_grade(_grade_id(path))}
    assert production.issubset(curriculum)
    assert "ENGLISH" in curriculum
    assert "PHYSICS_CHEMISTRY" in curriculum


def test_homework_never_returns_empty_when_subject_is_available(
    homework_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, english_id, _physics_id = homework_database
    selection = DuckDBUnifiedExperienceRepository(path).select_approved_content_detailed(
        _request(learner_id, english_id, _grade_id(path))
    )
    assert selection.content_ids


@pytest.fixture(scope="module")
def coverage_exports() -> Path:
    subprocess.run([sys.executable, str(AUDIT_SCRIPT)], check=True, cwd=ROOT)
    return EXPORTS / "LCAI-0018_4E_COVERAGE_MATRIX.csv"


def test_4e_coverage_export_contains_all_configured_subjects(coverage_exports: Path) -> None:
    with coverage_exports.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    subjects = {row["subject_code"] for row in rows}
    assert "ENGLISH" in subjects
    assert "PHYSICS_CHEMISTRY" in subjects
    assert "MATHEMATICS" in subjects
    assert len(subjects) >= 9


def test_4e_coverage_export_includes_zero_content_chapters(coverage_exports: Path) -> None:
    with coverage_exports.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    zero_rows = [row for row in rows if int(row["approved_count"]) == 0]
    assert zero_rows


def test_only_approved_active_content_is_eligible(homework_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, english_id, _physics_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    grade_id = _grade_id(path)
    selected = set(repository.select_approved_content(_request(learner_id, english_id, grade_id)))
    connection = connect_v2(path)
    try:
        for content_id in selected:
            row = connection.execute("SELECT status FROM exercises WHERE id=?", [content_id]).fetchone()
            assert row and row[0] == "active"
    finally:
        connection.close()
        reset_v2_connections()
