from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest

from core.config import PROJECT_ROOT
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.v2 import (
    AttemptRepositoryV2,
    ContentRepositoryV2,
    DecisionRepositoryV2,
    LearnerRepositoryV2,
    MasteryRepositoryV2,
    ObjectiveRepositoryV2,
    RecommendationRepositoryV2,
    ReferenceRepositoryV2,
    SessionRepositoryV2,
)
from migrations.runner import DEFAULT_MIGRATIONS_PATH, MigrationError, apply_migrations


@pytest.fixture
def v2_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "learning_coach_v2.duckdb"
    applied = apply_migrations(database_path)
    assert [migration.version for migration in applied] == [1, 2, 3, 4, 5, 6, 7, 8]
    return database_path


def test_migrations_rebuild_complete_empty_database(v2_database: Path) -> None:
    connection = connect_v2(v2_database, read_only=True)
    try:
        table_count = connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='main' AND table_type='BASE TABLE'"
        ).fetchone()
        view_count = connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='main' AND table_type='VIEW'"
        ).fetchone()
        assert table_count == (53,)
        assert view_count == (3,)
        assert connection.execute("SELECT COUNT(*) FROM duckdb_indexes()").fetchone() == (26,)
        assert connection.execute("SELECT COUNT(*) FROM learners").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM programs").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM subjects").fetchone() == (10,)
        assert connection.execute("SELECT COUNT(*) FROM domains").fetchone() == (21,)
        assert connection.execute("SELECT COUNT(*) FROM skills").fetchone() == (25,)
    finally:
        connection.close()


def test_migrations_are_idempotent(v2_database: Path) -> None:
    assert apply_migrations(v2_database) == []
    connection = connect_v2(v2_database, read_only=True)
    try:
        assert connection.execute("SELECT COUNT(*) FROM schema_versions").fetchone() == (8,)
    finally:
        connection.close()


def test_changed_applied_migration_is_rejected(v2_database: Path, tmp_path: Path) -> None:
    migrations_copy = tmp_path / "migrations"
    shutil.copytree(DEFAULT_MIGRATIONS_PATH, migrations_copy)
    seed = migrations_copy / "002_seed_reference.sql"
    seed.write_text(seed.read_text(encoding="utf-8") + "\n-- changed\n", encoding="utf-8")
    with pytest.raises(MigrationError, match="Checksum mismatch"):
        apply_migrations(v2_database, migrations_copy)


def test_failed_migration_is_rolled_back(tmp_path: Path) -> None:
    migrations_copy = tmp_path / "migrations"
    shutil.copytree(DEFAULT_MIGRATIONS_PATH, migrations_copy)
    (migrations_copy / "009_invalid.sql").write_text(
        "CREATE TABLE must_rollback(id INTEGER); INSERT INTO table_that_does_not_exist VALUES (1);",
        encoding="utf-8",
    )
    database_path = tmp_path / "rollback.duckdb"
    with pytest.raises(duckdb.Error):
        apply_migrations(database_path, migrations_copy)
    connection = connect_v2(database_path, read_only=True)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='must_rollback'"
        ).fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM schema_versions").fetchone() == (8,)
    finally:
        connection.close()


def test_foreign_keys_and_checks_are_enforced(v2_database: Path) -> None:
    connection = connect_v2(v2_database)
    try:
        with pytest.raises(duckdb.ConstraintException):
            connection.execute(
                "INSERT INTO domains(subject_id,code,default_label,display_order) VALUES (999999,'BAD','Bad',99)"
            )
        with pytest.raises(duckdb.ConstraintException):
            connection.execute(
                """
                INSERT INTO exercises(
                    subject_id,code,title,objective,estimated_seconds,difficulty,
                    instructions,evaluation_strategy,language_code
                ) VALUES (1,'BAD','Bad','Bad',60,9,'Bad','{}','fr-FR')
                """
            )
        with pytest.raises(duckdb.ConstraintException):
            connection.execute("INSERT INTO skill_prerequisites(skill_id,prerequisite_skill_id) VALUES (10001,10001)")
    finally:
        connection.close()


def test_reference_and_learning_repositories(v2_database: Path) -> None:
    references = ReferenceRepositoryV2(v2_database)
    learners = LearnerRepositoryV2(v2_database)
    content = ContentRepositoryV2(v2_database)
    objectives = ObjectiveRepositoryV2(v2_database)
    sessions = SessionRepositoryV2(v2_database)
    attempts = AttemptRepositoryV2(v2_database)
    mastery = MasteryRepositoryV2(v2_database)
    decisions = DecisionRepositoryV2(v2_database)
    recommendations = RecommendationRepositoryV2(v2_database)

    assert references.list_programs()[0]["code"] == "BREVET"
    assert len(references.skill_catalog(1)) == 25

    learner_id = learners.create("Élève test")
    assert learners.get(learner_id)["display_name"] == "Élève test"  # type: ignore[index]
    objective_id = objectives.create(learner_id, "Préparer le Brevet", program_id=1, kind="program")
    assert sessions.create(learner_id, objective_id=objective_id) >= 100000

    exercise_id = content.create_exercise(1, "TEST-EX-1", "Test", "Valider les repositories")
    question_id = content.create_question("TEST-Q-1", "Combien font 2 + 2 ?", 4, "2 + 2 = 4", answer_type="number")
    content.add_question(exercise_id, question_id, 1)
    content.link_skill(question_id, 10001)

    attempt_id = attempts.create(
        learner_id,
        question_id,
        4,
        score=1,
        difficulty=1,
        prompt_snapshot="Combien font 2 + 2 ?",
        expected_answer_snapshot=4,
        is_correct=True,
        elapsed_ms=1200,
    )
    assert attempt_id >= 100000

    mastery.upsert(learner_id, 10001, 0.65, 0.4, "test-only")
    mastery_state = mastery.get(learner_id, 10001)
    assert mastery_state is not None
    assert mastery_state["score"] == pytest.approx(0.65)

    decision_id = decisions.create(
        learner_id,
        "test_fixture",
        "context-hash",
        engine_version="not-implemented",
        ruleset_version="test",
        correlation_id="test-correlation",
        selected_entity_type="skill",
        selected_entity_id=10001,
    )
    recommendation_id = recommendations.create_for_skill(
        learner_id,
        decision_id,
        10001,
        kind="practice",
        priority_score=0.8,
        reason_code="TEST_ONLY",
    )
    assert recommendation_id >= 100000


def test_v2_default_location_is_separate_from_v1() -> None:
    from core.config import DEFAULT_DATABASE_PATH, DEFAULT_V2_DATABASE_PATH

    assert DEFAULT_V2_DATABASE_PATH == PROJECT_ROOT / "data" / "learning_coach_v2.duckdb"
    assert DEFAULT_V2_DATABASE_PATH != DEFAULT_DATABASE_PATH
