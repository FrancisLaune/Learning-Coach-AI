from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from core.config import PROJECT_ROOT
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.curriculum import DuckDBCurriculumRepository
from migrations.runner import apply_migrations
from services.curriculum import CurriculumImportService, CurriculumService

CATALOG = PROJECT_ROOT / "resources" / "catalog" / "lcai_0009_catalog.json"
CURRICULUM = PROJECT_ROOT / "resources" / "curriculum" / "lcai_0011b_curriculum_2026_2027.json"


@pytest.fixture(scope="module")
def phase2_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("phase2-curriculum") / "curriculum.duckdb"
    apply_migrations(path)
    service = CurriculumImportService(DuckDBCurriculumRepository(path))
    assert not service.import_file(CATALOG, dry_run=False).errors
    report = service.import_file(CURRICULUM, dry_run=False)
    assert not report.errors
    return path


def test_phase2_manifest_is_curriculum_only_and_traceable() -> None:
    document = json.loads(CURRICULUM.read_text(encoding="utf-8"))
    assert document.get("contents") in (None, [])
    assert document["metadata"]["phase2_curriculum"] is True
    assert document["metadata"]["effective_school_year"] == "2026-2027"
    assert len(document["metadata"]["sources"]) >= 8
    assert {item["program"]["grade_code"] for item in document["curriculum_packages"]} == {
        "FR-CM1",
        "FR-CM2",
        "FR-6E",
        "FR-5E",
        "FR-4E",
        "FR-3E",
    }


def test_curriculum_only_import_is_idempotent(phase2_database: Path) -> None:
    service = CurriculumImportService(DuckDBCurriculumRepository(phase2_database))
    before = CurriculumService(DuckDBCurriculumRepository(phase2_database)).inventory()
    repeated = service.import_file(CURRICULUM, dry_run=False)
    after = CurriculumService(DuckDBCurriculumRepository(phase2_database)).inventory()
    assert repeated.created == 0
    assert repeated.ignored == repeated.rows_read
    assert before == after


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("grade_code", "FR-UNKNOWN", "unknown_grade:FR-UNKNOWN"),
        ("subject", "UNKNOWN_SUBJECT", "unknown_subject:UNKNOWN_SUBJECT"),
    ],
)
def test_unknown_references_are_rejected(
    tmp_path: Path,
    field: str,
    value: str,
    expected_error: str,
) -> None:
    path = tmp_path / "unknown-reference.duckdb"
    apply_migrations(path)
    document: dict[str, Any] = json.loads(CURRICULUM.read_text(encoding="utf-8"))
    if field == "grade_code":
        document["curriculum_packages"][0]["program"]["grade_code"] = value
    else:
        document["curriculum_packages"][0]["subjects"][0]["code"] = value
    source = tmp_path / f"{field}.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    report = CurriculumImportService(DuckDBCurriculumRepository(path)).import_file(source, dry_run=False)
    assert expected_error in report.errors
    con = connect_v2(path, read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM curriculum_chapters").fetchone() == (0,)
    finally:
        con.close()


def test_all_supported_grades_have_curriculum_without_approved_content(phase2_database: Path) -> None:
    service = CurriculumService(DuckDBCurriculumRepository(phase2_database))
    for grade_code in ("FR-CM1", "FR-CM2", "FR-6E", "FR-5E", "FR-4E", "FR-3E"):
        rows = service.coverage(grade_code=grade_code)
        assert rows, grade_code
    assert all(item["approved_content_count"] == 0 for item in service.coverage(grade_code="FR-5E"))


def test_program_skills_are_a_complete_compatibility_projection(phase2_database: Path) -> None:
    con = connect_v2(phase2_database, read_only=True)
    try:
        missing = con.execute(
            """SELECT count(*) FROM curriculum_skill_details csd
            JOIN curriculum_chapters cc ON cc.id=csd.chapter_id
            LEFT JOIN program_skills ps ON ps.program_id=cc.program_id AND ps.skill_id=csd.skill_id
            WHERE ps.skill_id IS NULL"""
        ).fetchone()
        assert missing == (0,)
    finally:
        con.close()


def test_enriched_prerequisites_are_projected_for_learning_engine(phase2_database: Path) -> None:
    con = connect_v2(phase2_database, read_only=True)
    try:
        missing = con.execute(
            """SELECT count(*) FROM curriculum_skill_relations r
            LEFT JOIN skill_prerequisites sp
              ON sp.skill_id=r.target_skill_id
             AND sp.prerequisite_skill_id=r.prerequisite_skill_id
            WHERE r.active AND r.relation_type='required' AND r.mandatory
              AND sp.skill_id IS NULL"""
        ).fetchone()
        assert missing == (0,)
        assert (
            con.execute(
                """SELECT count(*) FROM curriculum_skill_relations
            WHERE source='legacy-skill-prerequisites-compatibility'"""
            ).fetchone()[0]
            == 5
        )
    finally:
        con.close()


def test_existing_approved_content_remains_fully_resolvable(phase2_database: Path) -> None:
    con = connect_v2(phase2_database, read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM approved_learning_catalog").fetchone() == (68,)
        assert con.execute(
            """SELECT count(*) FROM approved_learning_catalog a
            JOIN curriculum_chapters c ON c.id=a.chapter_id
            JOIN curriculum_skill_details d
              ON d.skill_id=a.skill_id AND d.chapter_id=a.chapter_id"""
        ).fetchone() == (68,)
        assert con.execute(
            """SELECT count(*) FROM curriculum_chapters c
            LEFT JOIN programs p ON p.id=c.program_id
            LEFT JOIN school_levels l ON l.id=c.grade_level_id
            LEFT JOIN subjects s ON s.id=c.subject_id
            LEFT JOIN domains d ON d.id=c.domain_id
            WHERE p.id IS NULL OR l.id IS NULL OR s.id IS NULL OR d.id IS NULL"""
        ).fetchone() == (0,)
    finally:
        con.close()
