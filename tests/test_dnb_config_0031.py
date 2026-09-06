"""LCAI-0031 — DNB product config unit tests (Phase 1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.dnb import (
    CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS,
    DNB_TERMINAL_SUBJECTS,
    PRIMARY_USER_GRADE_CODE,
    capabilities_for,
    load_dnb_exam_calendar,
    load_dnb_product_config,
)
from domain.dnb.subject_capabilities import terminal_brevet_subject_codes


def test_primary_user_grade_is_only_3e() -> None:
    config = load_dnb_product_config()
    assert config.primary_grade_code == "FR-3E"
    assert PRIMARY_USER_GRADE_CODE == "FR-3E"
    assert config.is_user_facing_grade("FR-3E")
    assert not config.is_user_facing_grade("FR-CM1")
    assert not config.is_user_facing_grade("FR-4E")
    assert "FR-CM1" in config.remediation_grade_codes


def test_terminal_subjects_match_dnb_written_scope() -> None:
    assert "FRENCH" in DNB_TERMINAL_SUBJECTS
    assert "MATHEMATICS" in DNB_TERMINAL_SUBJECTS
    assert "EMC" in DNB_TERMINAL_SUBJECTS
    assert "TECHNOLOGY" in DNB_TERMINAL_SUBJECTS
    assert "ENGLISH" not in DNB_TERMINAL_SUBJECTS
    assert "SPANISH" not in DNB_TERMINAL_SUBJECTS


def test_english_spanish_excluded_from_terminal_brevet_path() -> None:
    config = load_dnb_product_config()
    for code in CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS:
        caps = capabilities_for(code)
        assert caps.supports_brevet_exam is False
        assert caps.terminal_exam is False
        assert caps.continuous_assessment is True
        assert config.belongs_in_brevet_prep_path(code) is False
    assert "ENGLISH" not in terminal_brevet_subject_codes()
    assert "SPANISH" not in terminal_brevet_subject_codes()


def test_terminal_capabilities_enable_brevet_exam() -> None:
    for code in ("FRENCH", "MATHEMATICS", "PHYSICS_CHEMISTRY", "SVT", "TECHNOLOGY"):
        caps = capabilities_for(code)
        assert caps.supports_brevet_exam is True
        assert caps.terminal_exam is True
        assert caps.supports_revision is True


def test_science_pool_contains_three_disciplines() -> None:
    config = load_dnb_product_config()
    assert config.science_pool == frozenset({"PHYSICS_CHEMISTRY", "SVT", "TECHNOLOGY"})
    assert capabilities_for("SVT").in_science_pool is True
    assert capabilities_for("FRENCH").in_science_pool is False


def test_exam_calendar_is_versioned_metropole_2027() -> None:
    calendar = load_dnb_exam_calendar()
    assert calendar.version.startswith("DNB-2027")
    assert calendar.timezone == "Europe/Paris"
    assert calendar.source_reference
    dates = {item.exam_code: item.exam_date for item in calendar.written_exams}
    assert dates["FRENCH_WRITTEN"] == date(2027, 6, 24)
    assert dates["HISTORY_GEOGRAPHY_EMC_WRITTEN"] == date(2027, 6, 25)
    assert dates["MATHEMATICS_WRITTEN"] == date(2027, 6, 28)
    assert dates["SCIENCES_WRITTEN"] == date(2027, 6, 28)
    remaining = calendar.countdown_days(today=date(2027, 6, 1))
    assert remaining == 23


def test_oral_is_terminal_brevet_capability() -> None:
    caps = capabilities_for("ORAL")
    assert caps.supports_oral is True
    assert caps.supports_brevet_exam is True
    assert load_dnb_product_config().belongs_in_brevet_prep_path("ORAL")


def test_filter_product_facing_grades_keeps_only_3e() -> None:
    from services.dnb import filter_product_facing_grades

    grades = (
        (1, "FR-CM1", "CM1"),
        (2, "FR-4E", "4e"),
        (3, "FR-3E", "3e"),
    )
    assert filter_product_facing_grades(grades) == ((3, "FR-3E", "3e"),)
    assert len(filter_product_facing_grades(grades, include_remediation=True)) == 3


def test_filter_brevet_prep_subjects_drops_languages() -> None:
    from services.dnb import filter_brevet_prep_subjects

    subjects = (
        (1, "FRENCH", "Français"),
        (2, "ENGLISH", "Anglais"),
        (3, "MATHEMATICS", "Mathématiques"),
        (4, "SPANISH", "Espagnol"),
    )
    filtered = filter_brevet_prep_subjects(subjects)
    codes = {row[1] for row in filtered}
    assert codes == {"FRENCH", "MATHEMATICS"}


def test_homework_ai_default_grades_are_3e_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOMEWORK_AI_COMPLETION_GRADES", raising=False)
    from services.homework.config import HomeworkAiCompletionSettings

    settings = HomeworkAiCompletionSettings.from_environment()
    assert settings.allowed_grades == frozenset({"FR-3E"})


def test_migration_026_dnb_calendar_applies(tmp_path: Path) -> None:
    from infrastructure.database.v2 import connect_v2
    from migrations.runner import apply_migrations

    path = tmp_path / "dnb_cal.duckdb"
    applied = apply_migrations(path)
    assert any(item.version == 26 for item in applied)
    assert apply_migrations(path) == []
    connection = connect_v2(path, read_only=True)
    try:
        row = connection.execute("SELECT version, session_code FROM exam_calendar WHERE id=1").fetchone()
        assert row is not None
        assert str(row[0]) == "DNB-2027-METROPOLE-V1"
        count = connection.execute("SELECT COUNT(*) FROM exam_date").fetchone()[0]
        assert int(count) == 4
    finally:
        connection.close()
