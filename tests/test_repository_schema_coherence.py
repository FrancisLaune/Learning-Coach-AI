"""Smoke tests for V2 repository SQL coherence against the live schema."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import get_v2_database_path
from infrastructure.database.v2 import connect_v2, reset_v2_connections
from infrastructure.repositories.experience import DuckDBExperienceReadModel
from infrastructure.repositories.pedagogical_intelligence import DuckDBPedagogicalIntelligenceRepository
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from infrastructure.repositories.unified_session_execution import DuckDBUnifiedSessionExecutionRepository


@pytest.fixture(scope="module")
def v2_path() -> Path:
    return get_v2_database_path()


def test_experience_activities_joins_exercises_not_legacy_content_items(v2_path: Path) -> None:
    connection = connect_v2(v2_path, read_only=True)
    try:
        row = connection.execute(
            """
            SELECT d.session_id FROM learning_session_details d
            JOIN session_activities a ON a.session_id=d.session_id
            LIMIT 1
            """
        ).fetchone()
    finally:
        connection.close()
        reset_v2_connections()
    if row is None:
        pytest.skip("No session activities in database")
    activities = DuckDBExperienceReadModel(v2_path).activities(int(row[0]))
    assert isinstance(activities, tuple)


def test_pedagogical_intelligence_transition_readiness_query_is_valid(v2_path: Path) -> None:
    repo = DuckDBPedagogicalIntelligenceRepository(v2_path)
    connection = connect_v2(v2_path, read_only=True)
    try:
        learner_id = connection.execute("SELECT id FROM learners ORDER BY id LIMIT 1").fetchone()
    finally:
        connection.close()
        reset_v2_connections()
    if learner_id is None:
        pytest.skip("No learners in database")
    result = repo.transition_readiness(int(learner_id[0]), "FR-3E")
    assert result is None or "source_grade_code" in result


def test_pedagogical_intelligence_curriculum_skill_fallback_is_valid(v2_path: Path) -> None:
    repo = DuckDBPedagogicalIntelligenceRepository(v2_path)
    skills = repo.target_skills_for_grade("FR-4E", limit=3)
    assert isinstance(skills, tuple)


def test_unified_experience_last_activity_query_is_valid(v2_path: Path) -> None:
    repo = DuckDBUnifiedExperienceRepository(v2_path)
    connection = connect_v2(v2_path, read_only=True)
    try:
        learner_id = connection.execute("SELECT id FROM learners ORDER BY id LIMIT 1").fetchone()
    finally:
        connection.close()
        reset_v2_connections()
    if learner_id is None:
        pytest.skip("No learners in database")
    label = repo.learner_last_activity_label(int(learner_id[0]))
    assert label is None or isinstance(label, str)


def test_session_execution_current_question_query_is_valid(v2_path: Path) -> None:
    repo = DuckDBUnifiedSessionExecutionRepository(v2_path)
    connection = connect_v2(v2_path, read_only=True)
    try:
        row = connection.execute(
            """
            SELECT ls.learner_id, ls.id FROM learning_sessions ls
            JOIN session_activities a ON a.session_id=ls.id
            LIMIT 1
            """
        ).fetchone()
    finally:
        connection.close()
        reset_v2_connections()
    if row is None:
        pytest.skip("No runnable sessions in database")
    material = repo.current_question(int(row[0]), int(row[1]))
    assert material is None or material.question.statement
