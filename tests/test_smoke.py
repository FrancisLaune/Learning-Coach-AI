from __future__ import annotations

import importlib
from pathlib import Path

import duckdb
import pytest

from core.config import DEFAULT_DATABASE_PATH, PROJECT_ROOT, get_database_path, get_log_level
from core.engine import is_correct, normalize_text
from core.logging_config import configure_logging
from core.registry import SUBJECTS


def test_main_modules_import_without_side_effects() -> None:
    modules = (
        "analytics.adaptive",
        "analytics.mastery",
        "core.config",
        "core.database",
        "core.engine",
        "core.logging_config",
        "core.registry",
    )
    for module_name in modules:
        assert importlib.import_module(module_name)


def test_configuration_defaults_do_not_require_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LCAI_DATABASE_PATH", raising=False)
    monkeypatch.delenv("LCAI_LOG_LEVEL", raising=False)

    assert get_database_path() == DEFAULT_DATABASE_PATH
    assert get_log_level() == "INFO"
    configure_logging()


def test_relative_database_path_is_resolved_from_project_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LCAI_DATABASE_PATH", "data/test.duckdb")
    assert get_database_path() == PROJECT_ROOT / "data" / "test.duckdb"


def test_reference_duckdb_exists_and_opens_read_only() -> None:
    database_path = get_database_path()
    assert database_path.is_file()

    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        table_names = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    finally:
        connection.close()

    assert {"users", "exams", "exam_questions", "practice_attempts"} <= table_names


def test_expected_legacy_databases_can_be_located() -> None:
    expected = (PROJECT_ROOT / "objectif_brevet_2027.db", PROJECT_ROOT / "revision_3e.db")
    assert all(path.is_file() for path in expected)


def test_subject_registry_exposes_generators() -> None:
    assert len(SUBJECTS) == 10
    assert all(hasattr(module, "generate_question") for module in SUBJECTS.values())


def test_text_normalization_and_answer_checking() -> None:
    assert normalize_text("  Théorème, d’Euclide! ") == "theoreme d'euclide"
    question = {"answer_type": "number", "expected_answer": "10"}
    assert is_correct(question, "10,0 cm")


def test_project_root_is_absolute() -> None:
    assert isinstance(PROJECT_ROOT, Path)
    assert PROJECT_ROOT.is_absolute()
