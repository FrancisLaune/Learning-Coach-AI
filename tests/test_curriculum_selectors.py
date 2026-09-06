from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from domain.unified_experience.models import AssignmentType, DifficultyMode, HomeworkRequest
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.curriculum import DuckDBCurriculumRepository
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from migrations.runner import apply_migrations
from services.curriculum import CurriculumImportService
from ui.curriculum_state import reconcile_skills, reconcile_subject_change


@pytest.fixture
def catalog_repository(tmp_path: Path) -> DuckDBUnifiedExperienceRepository:
    path = tmp_path / "catalog.duckdb"
    apply_migrations(path)
    source = Path(__file__).parents[1] / "resources" / "catalog" / "lcai_0009_catalog.json"
    CurriculumImportService(DuckDBCurriculumRepository(path)).import_file(source, dry_run=False)
    return DuckDBUnifiedExperienceRepository(path)


def test_subject_switch_clears_chapters_and_skills() -> None:
    state: dict[str, object] = {
        "homework_subject_marker": 1,
        "homework_chapters": [10],
        "homework_skills": [100],
    }
    for subject_id in (2, 3, 1):
        reconcile_subject_change(state, "homework", subject_id)
        assert state["homework_chapters"] == []
        assert state["homework_skills"] == []
        state["homework_chapters"] = [subject_id * 10]
        state["homework_skills"] = [subject_id * 100]


def test_removed_chapter_removes_incompatible_skills() -> None:
    state: dict[str, object] = {"revision_skills": [101, 102, 103]}
    reconcile_skills(state, "revision", {101, 103})
    assert state["revision_skills"] == [101, 103]
    reconcile_skills(state, "revision", set())
    assert state["revision_skills"] == []


def test_grade_filters_subjects_and_prevents_cross_subject_chapters(
    catalog_repository: DuckDBUnifiedExperienceRepository,
) -> None:
    grades = {code: grade_id for grade_id, code, _ in catalog_repository.grade_levels(product_facing=False)}
    subjects_4e = catalog_repository.subjects_for_grade(grades["FR-4E"])
    labels_4e = {label: subject_id for subject_id, _, label in subjects_4e}
    assert set(labels_4e) == {"Français", "Mathématiques"}

    subjects_3e = {label: subject_id for subject_id, _, label in catalog_repository.subjects_for_grade(grades["FR-3E"])}
    english_chapters = dict(catalog_repository.chapters(subjects_3e["Anglais"], grades["FR-3E"]))
    mathematics_chapters = dict(catalog_repository.chapters(subjects_3e["Mathématiques"], grades["FR-3E"]))
    french_chapters = dict(catalog_repository.chapters(subjects_3e["Français"], grades["FR-3E"]))
    assert "Past simple" in english_chapters.values()
    assert "Past simple" not in mathematics_chapters.values()
    assert "Past simple" not in french_chapters.values()


def test_skills_are_union_of_selected_chapters(
    catalog_repository: DuckDBUnifiedExperienceRepository,
) -> None:
    grades = {code: grade_id for grade_id, code, _ in catalog_repository.grade_levels(product_facing=False)}
    subjects = {label: subject_id for subject_id, _, label in catalog_repository.subjects_for_grade(grades["FR-4E"])}
    chapters = catalog_repository.chapters(subjects["Mathématiques"], grades["FR-4E"])
    first_two = tuple(chapter_id for chapter_id, _ in chapters[:2])
    first_skills = catalog_repository.skills(subjects["Mathématiques"], (first_two[0],), grades["FR-4E"])
    union_skills = catalog_repository.skills(subjects["Mathématiques"], first_two, grades["FR-4E"])
    assert set(first_skills) < set(union_skills)


def test_targeted_and_global_selection_are_filtered_balanced_and_unique(
    catalog_repository: DuckDBUnifiedExperienceRepository,
) -> None:
    grades = {code: grade_id for grade_id, code, _ in catalog_repository.grade_levels(product_facing=False)}
    subjects = {label: subject_id for subject_id, _, label in catalog_repository.subjects_for_grade(grades["FR-4E"])}
    subject_id = subjects["Mathématiques"]
    chapters = catalog_repository.chapters(subject_id, grades["FR-4E"])
    selected_chapter = chapters[0][0]
    selected_skill = catalog_repository.skills(subject_id, (selected_chapter,), grades["FR-4E"])[0][0]
    targeted = HomeworkRequest(
        999,
        "STUDENT",
        "learner:999",
        AssignmentType.TARGETED,
        subject_id,
        grades["FR-4E"],
        (selected_chapter,),
        (selected_skill,),
        DifficultyMode.MEDIUM,
        10,
        30,
        datetime(2026, 7, 30, tzinfo=UTC),
    )
    targeted_ids = catalog_repository.select_approved_content(targeted)
    assert targeted_ids
    connection = connect_v2(catalog_repository.database_path, read_only=True)
    try:
        assert connection.execute(
            """SELECT count(*) FROM approved_learning_catalog
            WHERE content_id IN (SELECT unnest(?::BIGINT[])) AND chapter_id<>?""",
            [list(targeted_ids), selected_chapter],
        ).fetchone() == (0,)
    finally:
        connection.close()

    global_request = HomeworkRequest(
        999,
        "STUDENT",
        "learner:999",
        AssignmentType.GLOBAL_SUBJECT,
        subject_id,
        grades["FR-4E"],
        (),
        (),
        DifficultyMode.ADAPTIVE,
        20,
        30,
        datetime(2026, 7, 30, tzinfo=UTC),
    )
    global_ids = catalog_repository.select_approved_content(global_request)
    assert len(global_ids) == len(set(global_ids))
    assert len(global_ids) < global_request.exercise_count
    connection = connect_v2(catalog_repository.database_path, read_only=True)
    try:
        covered_chapters = connection.execute(
            """SELECT count(DISTINCT chapter_id) FROM approved_learning_catalog
            WHERE content_id IN (SELECT unnest(?::BIGINT[]))""",
            [list(global_ids)],
        ).fetchone()[0]
    finally:
        connection.close()
    assert covered_chapters > 1
