"""LCAI-0018C — CM1 homework availability and coverage tests."""

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
AUDIT_SCRIPT = ROOT / "scripts" / "lcai_0018c_phase0_audit.py"
GRADE = "FR-CM1"


def _cm1_has_published_content() -> bool:
    connection = connect_v2(get_v2_database_path(), read_only=True)
    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM production_learning_catalog WHERE grade_code=?",
            [GRADE],
        ).fetchone()[0]
        return int(count) > 0
    finally:
        connection.close()
        reset_v2_connections()


@pytest.fixture
def homework_database(tmp_path: Path) -> tuple[Path, int, int, int]:
    source = get_v2_database_path()
    path = tmp_path / "lcai_0018c_cm1.duckdb"
    shutil.copy2(source, path)
    reset_v2_connections()
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student:cm1','Léa') RETURNING id"
            ).fetchone()[0]
        )
        grade_id = int(connection.execute("SELECT id FROM school_levels WHERE code=?", [GRADE]).fetchone()[0])
        program_id = int(connection.execute("SELECT id FROM programs LIMIT 1").fetchone()[0])
        connection.execute(
            """INSERT INTO learner_journeys(learner_id,current_school_level_id,academic_year_start,program_id,learning_phase)
            VALUES (?,?,2026,?,'current_learning')""",
            [learner_id, grade_id, program_id],
        )
        french_id = int(connection.execute("SELECT id FROM subjects WHERE code='FRENCH'").fetchone()[0])
        math_id = int(connection.execute("SELECT id FROM subjects WHERE code='MATHEMATICS'").fetchone()[0])
    finally:
        connection.close()
        reset_v2_connections()
    return path, learner_id, french_id, math_id


def _request(learner_id: int, subject_id: int, grade_id: int, *, count: int = 10) -> HomeworkRequest:
    return HomeworkRequest(
        learner_id,
        "STUDENT",
        "student:cm1",
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
        return int(connection.execute("SELECT id FROM school_levels WHERE code=?", [GRADE]).fetchone()[0])
    finally:
        connection.close()
        reset_v2_connections()


def test_cm1_curriculum_has_eight_subjects(homework_database: tuple[Path, int, int, int]) -> None:
    path, _learner_id, _french_id, _math_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    curriculum = {code for _id, code, _label in repository.curriculum_subjects_for_grade(_grade_id(path))}
    assert len(curriculum) >= 8
    assert "FRENCH" in curriculum
    assert "MATHEMATICS" in curriculum


def test_french_cm1_subject_has_active_chapters(homework_database: tuple[Path, int, int, int]) -> None:
    path, _learner_id, french_id, _math_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    chapters = repository.chapters(french_id, _grade_id(path))
    assert chapters


def test_mathematics_cm1_subject_has_active_chapters(homework_database: tuple[Path, int, int, int]) -> None:
    path, _learner_id, _french_id, math_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    chapters = repository.chapters(math_id, _grade_id(path))
    assert chapters


def test_homework_availability_lists_all_cm1_subjects(homework_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, _french_id, _math_id = homework_database
    items = HomeworkAvailabilityService(DuckDBUnifiedExperienceRepository(path)).list_for_learner(learner_id)
    assert len(items) >= 8


@pytest.mark.skipif(not _cm1_has_published_content(), reason="CM1 publication not yet executed")
def test_parent_can_generate_french_homework_for_cm1(homework_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, french_id, _math_id = homework_database
    service = HomeworkService(DuckDBUnifiedExperienceRepository(path))
    homework = service.create(_request(learner_id, french_id, _grade_id(path)))
    assert homework.selected_content_ids


@pytest.mark.skipif(not _cm1_has_published_content(), reason="CM1 publication not yet executed")
def test_parent_can_generate_mathematics_homework_for_cm1(homework_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, _french_id, math_id = homework_database
    service = HomeworkService(DuckDBUnifiedExperienceRepository(path))
    homework = service.create(_request(learner_id, math_id, _grade_id(path)))
    assert homework.selected_content_ids


@pytest.mark.skipif(not _cm1_has_published_content(), reason="CM1 publication not yet executed")
def test_homework_can_be_generated_for_each_available_cm1_subject(
    homework_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, _french_id, _math_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    service = HomeworkService(repository)
    grade_id = _grade_id(path)
    for item in HomeworkAvailabilityService(repository).list_for_learner(learner_id):
        if item.availability_status == "unavailable":
            continue
        homework = service.create(_request(learner_id, item.subject_id, grade_id))
        assert homework.selected_content_ids


@pytest.mark.skipif(not _cm1_has_published_content(), reason="CM1 publication not yet executed")
def test_engine_never_falls_back_to_another_subject(homework_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, french_id, math_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    grade_id = _grade_id(path)
    french_ids = set(repository.select_approved_content(_request(learner_id, french_id, grade_id)))
    math_ids = set(repository.select_approved_content(_request(learner_id, math_id, grade_id)))
    assert french_ids.isdisjoint(math_ids)


@pytest.fixture(scope="module")
def coverage_exports() -> Path:
    path = EXPORTS / "LCAI-0018C_CM1_COVERAGE_MATRIX.csv"
    if not path.exists():
        subprocess.run([sys.executable, str(AUDIT_SCRIPT)], check=True, cwd=ROOT)
    assert path.exists(), "CM1 coverage matrix export missing"
    return path


def test_cm1_coverage_export_contains_all_configured_subjects(coverage_exports: Path) -> None:
    with coverage_exports.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    subjects = {row["subject_code"] for row in rows}
    assert "FRENCH" in subjects
    assert "MATHEMATICS" in subjects
    assert len(subjects) >= 8


def test_cm1_coverage_export_includes_chapter_rows(coverage_exports: Path) -> None:
    with coverage_exports.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 100
