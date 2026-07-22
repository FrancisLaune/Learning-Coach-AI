from __future__ import annotations

import importlib
from pathlib import Path

from core import database as legacy_database
from infrastructure.database.repositories import ProgressRepository, UserRepository
from ui.session import _session_defaults


def test_target_packages_are_importable() -> None:
    packages = (
        "application",
        "domain",
        "infrastructure",
        "infrastructure.config",
        "infrastructure.database",
        "infrastructure.logging",
        "infrastructure.repositories",
        "services",
        "ui",
    )
    for package_name in packages:
        assert importlib.import_module(package_name)


def test_user_repository_preserves_read_behavior() -> None:
    repository = UserRepository()
    assert repository.student_list() == legacy_database.student_list()


def test_progress_repository_preserves_dashboard_behavior() -> None:
    students = legacy_database.student_list()
    if not students:
        return
    user_id = int(students[0]["id"])
    repository = ProgressRepository()
    assert repository.dashboard_metrics(user_id) == legacy_database.dashboard_metrics(user_id)


def test_streamlit_entrypoint_is_thin_and_uses_ui_boundary() -> None:
    entrypoint = Path(__file__).resolve().parents[1] / "app.py"
    source = entrypoint.read_text(encoding="utf-8")
    assert len(source.splitlines()) < 30
    assert "from ui.streamlit_app import run_app" in source
    assert "core.database" not in source


def test_session_mutable_defaults_are_not_shared() -> None:
    first = _session_defaults()
    second = _session_defaults()
    assert first["training_questions"] is not second["training_questions"]
    assert first["exam_opened_at"] is not second["exam_opened_at"]
