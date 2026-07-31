from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.config import get_v2_database_path
from domain.unified_experience.models import AssignmentType, DifficultyMode, HomeworkRequest
from infrastructure.database.v2 import connect_v2, reset_v2_connections
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from services.homework.exercise_selection import (
    HomeworkExerciseSelectionService,
    difficulty_fit_score,
    panachage_select,
    uses_mixed_difficulties,
)


def test_difficulty_fit_prefers_target_level() -> None:
    assert difficulty_fit_score(3, 3) > difficulty_fit_score(2, 3)
    assert difficulty_fit_score(3, 3) > difficulty_fit_score(4, 3)


def test_panachage_can_select_multiple_difficulty_levels() -> None:
    rows = [
        (1, 10, 100, 2),
        (2, 10, 100, 3),
        (3, 11, 101, 3),
        (4, 11, 101, 4),
        (5, 12, 102, 2),
        (6, 12, 102, 4),
        (7, 13, 103, 3),
        (8, 13, 103, 4),
    ]
    selected = panachage_select(rows, target=3, exercise_count=8)
    difficulties = {int(row[3]) for row in selected}
    assert len(selected) == 8
    assert len(difficulties) >= 2


def test_mixed_difficulties_detects_non_target_levels() -> None:
    rows = [(1, 1, 1, 2), (2, 1, 1, 3)]
    assert uses_mixed_difficulties(rows, 3) is True
    assert uses_mixed_difficulties([(1, 1, 1, 3)], 3) is False


@pytest.fixture
def homework_database(tmp_path: Path) -> tuple[Path, int, int]:
    source = get_v2_database_path()
    path = tmp_path / "lcai_0021.duckdb"
    shutil.copy2(source, path)
    reset_v2_connections()
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student:0021','Noa') RETURNING id"
            ).fetchone()[0]
        )
        grade_id = int(connection.execute("SELECT id FROM school_levels WHERE code='FR-4E'").fetchone()[0])
        english_id = int(connection.execute("SELECT id FROM subjects WHERE code='ENGLISH'").fetchone()[0])
    finally:
        connection.close()
        reset_v2_connections()
    return path, learner_id, english_id, grade_id


def _request(learner_id: int, subject_id: int, grade_id: int, *, count: int = 8) -> HomeworkRequest:
    return HomeworkRequest(
        learner_id,
        "STUDENT",
        "student:0021",
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


def test_catalog_selection_is_not_blocked_by_requested_difficulty(
    homework_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, english_id, grade_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    all_rows = repository._approved_content_rows(_request(learner_id, english_id, grade_id, count=100))
    medium_rows = [row for row in all_rows if int(row[3]) == 3]
    selection = repository.select_approved_content_detailed(_request(learner_id, english_id, grade_id, count=8))
    assert selection.content_ids
    if len(medium_rows) < 8 and len(all_rows) >= 8:
        selected_difficulties = {
            int(row[3])
            for row in all_rows
            if int(row[0]) in selection.content_ids
        }
        assert len(selected_difficulties) >= 2


def test_count_eligible_content_ignores_difficulty_filter(
    homework_database: tuple[Path, int, int, int],
) -> None:
    path, learner_id, english_id, grade_id = homework_database
    repository = DuckDBUnifiedExperienceRepository(path)
    request = _request(learner_id, english_id, grade_id)
    total = repository.count_eligible_content(request)
    medium_only = len(
        {
            int(row[0])
            for row in repository._approved_content_rows(request)
            if int(row[3]) == 3
        }
    )
    assert total >= medium_only


def test_selection_service_prepares_global_subject_rows() -> None:
    rows = [
        (1, 10, 100, 2),
        (2, 10, 100, 3),
        (3, 11, 101, 4),
        (4, 12, 102, 3),
    ]
    request = HomeworkRequest(
        1,
        "STUDENT",
        "x",
        AssignmentType.GLOBAL_SUBJECT,
        1,
        1,
        (),
        (),
        DifficultyMode.MEDIUM,
        3,
        30,
        datetime.now(tz=UTC),
    )
    prepared = HomeworkExerciseSelectionService().prepare_catalog_rows(rows, request=request, target_difficulty=3)
    assert len(prepared) >= 3
    assert len({int(row[0]) for row in prepared[:3]}) == 3
