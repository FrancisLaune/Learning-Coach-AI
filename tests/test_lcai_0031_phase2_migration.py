"""LCAI-0031 Phase 2 — product classification migration tests."""

from __future__ import annotations

from pathlib import Path

from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from migrations.runner import apply_migrations
from scripts.lcai_0031_phase2_inventory import (
    _classify_grade,
    _classify_subject,
    inventory_database,
)


def test_classify_helpers() -> None:
    assert _classify_grade("FR-3E") == "KEEP_TERMINAL"
    assert _classify_grade("FR-CM1") == "ARCHIVE_PREREQUISITE"
    assert _classify_grade("FR-TERM") == "DEPRECATE_OUT_OF_SCOPE"
    assert _classify_subject("MATHEMATICS") == "MIGRATE_TERMINAL"
    assert _classify_subject("ENGLISH") == "KEEP_CONTINUOUS_ONLY"


def test_migration_027_classifies_grades_and_subjects(tmp_path: Path) -> None:
    path = tmp_path / "phase2.duckdb"
    applied = apply_migrations(path)
    assert any(item.version == 27 for item in applied)
    connection = connect_v2(path, read_only=True)
    try:
        roles = dict(
            connection.execute("SELECT code, product_role FROM school_levels WHERE code LIKE 'FR-%'").fetchall()
        )
        assert roles["FR-3E"] == "terminal"
        assert roles["FR-4E"] == "remediation"
        assert roles["FR-TERM"] == "out_of_scope"
        assessment = dict(connection.execute("SELECT code, assessment_role FROM subjects").fetchall())
        assert assessment["ENGLISH"] == "continuous"
        assert assessment["MATHEMATICS"] == "terminal"
        version = connection.execute(
            "SELECT code FROM curriculum_versions WHERE code='FR_3E_2027_V1'"
        ).fetchone()
        assert version is not None
        caps = connection.execute("SELECT COUNT(*) FROM subject_dnb_capabilities").fetchone()
        assert int(caps[0]) >= 10
    finally:
        connection.close()

    repo = DuckDBUnifiedExperienceRepository(path)
    facing = {code for _, code, _ in repo.grade_levels()}
    assert facing == {"FR-3E"}
    all_grades = {code for _, code, _ in repo.grade_levels(product_facing=False)}
    assert "FR-CM1" in all_grades
    assert "FR-3E" in all_grades


def test_inventory_runs_on_migrated_db(tmp_path: Path) -> None:
    path = tmp_path / "phase2_inv.duckdb"
    apply_migrations(path)
    payload = inventory_database(path)
    assert payload["curriculum_version"]["code"] == "FR_3E_2027_V1"
    assert payload["subject_capabilities_rows"] >= 10
