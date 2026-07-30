"""LCAI-0018G — 3e homework availability and coverage tests."""

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
AUDIT_SCRIPT = ROOT / "scripts" / "lcai_0018g_phase0_audit.py"
GRADE = "FR-3E"


@pytest.fixture
def homework_database(tmp_path: Path) -> tuple[Path, int, int, int]:
    source = get_v2_database_path()
    path = tmp_path / "lcai_0018g_3e.duckdb"
    shutil.copy2(source, path)
    reset_v2_connections()
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student:3e','Noah') RETURNING id"
            ).fetchone()[0]
        )
        grade_id = int(connection.execute("SELECT id FROM school_levels WHERE code=?", [GRADE]).fetchone()[0])
        program_id = int(connection.execute("SELECT id FROM programs LIMIT 1").fetchone()[0])
        connection.execute(
            """INSERT INTO learner_journeys(learner_id,current_school_level_id,academic_year_start,program_id,learning_phase)
            VALUES (?,?,2026,?,'current_learning')""",
            [learner_id, grade_id, program_id],
        )
        math_id = int(connection.execute("SELECT id FROM subjects WHERE code='MATHEMATICS'").fetchone()[0])
        french_id = int(connection.execute("SELECT id FROM subjects WHERE code='FRENCH'").fetchone()[0])
    finally:
        connection.close()
        reset_v2_connections()
    return path, learner_id, math_id, french_id


def _request(learner_id: int, subject_id: int, grade_id: int, *, count: int = 10) -> HomeworkRequest:
    return HomeworkRequest(
        learner_id,
        "STUDENT",
        "student:3e",
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


def test_3e_curriculum_has_nine_subjects(homework_database: tuple[Path, int, int, int]) -> None:
    path, _learner_id, _math_id, _french_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    curriculum = {code for _id, code, _label in repository.curriculum_subjects_for_grade(_grade_id(path))}
    assert len(curriculum) >= 9
    assert "MATHEMATICS" in curriculum
    assert "FRENCH" in curriculum


def test_mathematics_3e_subject_has_active_chapters(homework_database: tuple[Path, int, int, int]) -> None:
    path, _learner_id, math_id, _french_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    assert repository.chapters(math_id, _grade_id(path))


def test_parent_can_generate_mathematics_homework_for_3e(homework_database: tuple[Path, int, int, int]) -> None:
    path, learner_id, math_id, _french_id = homework_database
    service = HomeworkService(DuckDBUnifiedExperienceRepository(path))
    homework = service.create(_request(learner_id, math_id, _grade_id(path)))
    assert homework.selected_content_ids


def test_homework_can_be_generated_for_each_available_3e_subject(
    homework_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, _math_id, _french_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    service = HomeworkService(repository)
    grade_id = _grade_id(path)
    generated = 0
    for item in HomeworkAvailabilityService(repository).list_for_learner(learner_id):
        if item.availability_status == "unavailable":
            continue
        homework = service.create(_request(learner_id, item.subject_id, grade_id))
        assert homework.selected_content_ids
        generated += 1
    assert generated >= 1


@pytest.fixture(scope="module")
def coverage_exports() -> Path:
    subprocess.run([sys.executable, str(AUDIT_SCRIPT)], check=True, cwd=ROOT)
    return EXPORTS / "LCAI-0018G_3E_COVERAGE_MATRIX.csv"


def test_3e_coverage_export_contains_all_configured_subjects(coverage_exports: Path) -> None:
    with coverage_exports.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    subjects = {row["subject_code"] for row in rows}
    assert "MATHEMATICS" in subjects
    assert "FRENCH" in subjects
    assert len(subjects) >= 9


def test_3e_phase0_audit_script_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr[-1500:]
