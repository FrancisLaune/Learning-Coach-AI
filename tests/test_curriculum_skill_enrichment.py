from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from core.config import PROJECT_ROOT
from domain.curriculum.validation import CatalogValidator
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.curriculum import DuckDBCurriculumRepository
from migrations.runner import apply_migrations
from services.curriculum import CurriculumImportService, CurriculumService
from services.curriculum.services import _expand_curriculum_enrichment, _expand_curriculum_packages

CATALOG = PROJECT_ROOT / "resources" / "catalog" / "lcai_0009_catalog.json"
CURRICULUM = PROJECT_ROOT / "resources" / "curriculum" / "lcai_0011b_curriculum_2026_2027.json"
ENRICHMENT = PROJECT_ROOT / "resources" / "curriculum" / "lcai_0011c_curriculum_enriched_2026_2027.json"


@pytest.fixture(scope="module")
def enriched_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("curriculum-enrichment") / "curriculum.duckdb"
    apply_migrations(path)
    service = CurriculumImportService(DuckDBCurriculumRepository(path))
    assert not service.import_file(CATALOG, dry_run=False).errors
    assert not service.import_file(CURRICULUM, dry_run=False).errors
    assert not service.import_file(ENRICHMENT, dry_run=False).errors
    return path


def _expanded_enrichment() -> dict[str, Any]:
    document = json.loads(ENRICHMENT.read_text(encoding="utf-8"))
    return _expand_curriculum_packages(_expand_curriculum_enrichment(ENRICHMENT, document))


def test_enrichment_is_traceable_and_contains_no_content() -> None:
    source = json.loads(ENRICHMENT.read_text(encoding="utf-8"))
    metadata = source["metadata"]
    assert metadata["curriculum_enrichment"] is True
    assert metadata["status"] == "pedagogically_enriched"
    assert "interprétations pédagogiques" in metadata["transformation_method"]
    assert source.get("contents") in (None, [])
    assert len(metadata["sources"]) >= 4


def test_every_chapter_has_an_explicit_pedagogical_decomposition() -> None:
    source = json.loads(ENRICHMENT.read_text(encoding="utf-8"))
    matrix_path = ENRICHMENT.parent / source["curriculum_enrichment"]["chapter_competency_dataset"]
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))["chapter_competencies"]
    overrides = {item["chapter_code"] for item in source["curriculum_enrichment"]["chapter_overrides"]}
    chapters = {item["code"] for item in _expanded_enrichment()["chapters"]}
    assert len(matrix) == 152
    assert len(overrides) == 14
    assert set(matrix).isdisjoint(overrides)
    assert set(matrix) | overrides == chapters


def test_full_enriched_dataset_is_structurally_valid_and_acyclic() -> None:
    document = _expanded_enrichment()
    report = CatalogValidator().validate(document)
    assert report.valid, report.issues
    assert len(document["chapters"]) == 166
    assert len(document["skills"]) > len(document["chapters"])
    assert {item["grade_code"] for item in document["chapters"]} == {
        "FR-CM1",
        "FR-CM2",
        "FR-6E",
        "FR-5E",
        "FR-4E",
        "FR-3E",
    }


def test_every_chapter_has_multiple_measurable_skills(enriched_database: Path) -> None:
    con = connect_v2(enriched_database, read_only=True)
    try:
        distribution = con.execute(
            """SELECT count(*) AS skill_count, count(*) OVER ()
            FROM curriculum_skill_details
            GROUP BY chapter_id"""
        ).fetchall()
        assert len(distribution) == 166
        assert min(row[0] for row in distribution) >= 3
        assert max(row[0] for row in distribution) >= 5
    finally:
        con.close()


def test_quality_metrics_are_deterministic(enriched_database: Path) -> None:
    metrics = CurriculumService(DuckDBCurriculumRepository(enriched_database)).quality_metrics()
    overall = metrics["overall"]
    expanded = _expanded_enrichment()
    assert overall["chapters"] == 166
    assert overall["placed_skills"] == len(expanded["skills"])
    assert overall["subskills"] == len(expanded["subskills"]) + 6
    assert overall["chapters_with_one_skill"] == 0
    assert overall["chapters_with_multiple_skills"] == 166
    assert overall["minimum_skills_per_chapter"] == 3
    assert overall["maximum_skills_per_chapter"] >= 7
    assert len(metrics["by_grade_subject"]) == 51


def test_optional_subskills_increase_diagnostic_precision(enriched_database: Path) -> None:
    con = connect_v2(enriched_database, read_only=True)
    try:
        with_subskills = con.execute("SELECT count(DISTINCT skill_id) FROM subskills").fetchone()[0]
        total_skills = con.execute("SELECT count(*) FROM skills").fetchone()[0]
        assert 0 < with_subskills < total_skills
        assert con.execute(
            """SELECT count(*) FROM subskills child
            JOIN skills parent ON parent.id=child.skill_id
            WHERE lower(trim(child.default_label))=lower(trim(parent.default_label))"""
        ).fetchone() == (0,)
    finally:
        con.close()


def test_representative_fraction_decomposition_is_precise(enriched_database: Path) -> None:
    con = connect_v2(enriched_database, read_only=True)
    try:
        rows = con.execute(
            """SELECT s.code FROM skills s
            JOIN curriculum_skill_details d ON d.skill_id=s.id
            JOIN curriculum_chapters c ON c.id=d.chapter_id
            WHERE c.stable_code='CH-MATHEMATICS-5E-FRACTIONS'
            ORDER BY s.code"""
        ).fetchall()
        codes = {row[0] for row in rows}
        assert {
            "SK-ENR-MATHEMATICS-5E-FRACTIONS-QUOTIENT",
            "SK-ENR-MATHEMATICS-5E-FRACTIONS-EQUIVALENT",
            "SK-ENR-MATHEMATICS-5E-FRACTIONS-OPERATE",
            "SK-ENR-MATHEMATICS-5E-FRACTIONS-PROBLEM",
        } <= codes
    finally:
        con.close()


def test_enriched_import_is_idempotent(enriched_database: Path) -> None:
    service = CurriculumImportService(DuckDBCurriculumRepository(enriched_database))
    before = CurriculumService(DuckDBCurriculumRepository(enriched_database)).inventory()
    report = service.import_file(ENRICHMENT, dry_run=False)
    after = CurriculumService(DuckDBCurriculumRepository(enriched_database)).inventory()
    assert report.created == 0
    assert report.ignored == report.rows_read
    assert before == after


def test_compatibility_content_and_historical_state_are_preserved(enriched_database: Path) -> None:
    con = connect_v2(enriched_database, read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM approved_learning_catalog").fetchone() == (68,)
        assert con.execute(
            """SELECT count(*) FROM approved_learning_catalog a
            JOIN curriculum_chapters c ON c.id=a.chapter_id
            JOIN curriculum_skill_details d
              ON d.skill_id=a.skill_id AND d.chapter_id=a.chapter_id"""
        ).fetchone() == (68,)
        assert con.execute(
            """SELECT count(*) FROM curriculum_skill_details d
            JOIN curriculum_chapters c ON c.id=d.chapter_id
            LEFT JOIN program_skills p ON p.program_id=c.program_id AND p.skill_id=d.skill_id
            WHERE p.skill_id IS NULL"""
        ).fetchone() == (0,)
        assert con.execute(
            """SELECT count(*) FROM curriculum_skill_relations r
            LEFT JOIN skills source ON source.id=r.prerequisite_skill_id
            LEFT JOIN skills target ON target.id=r.target_skill_id
            WHERE source.id IS NULL OR target.id IS NULL
              OR r.prerequisite_skill_id=r.target_skill_id"""
        ).fetchone() == (0,)
        assert con.execute("SELECT count(*) FROM mastery_current").fetchone() == (0,)
        assert con.execute("SELECT count(*) FROM longitudinal_mastery_current").fetchone() == (0,)
    finally:
        con.close()


def test_zero_content_curriculum_remains_navigable(enriched_database: Path) -> None:
    coverage = CurriculumService(DuckDBCurriculumRepository(enriched_database)).coverage(
        grade_code="FR-5E", subject_code="MATHEMATICS"
    )
    assert coverage
    assert any(item["approved_content_count"] == 0 for item in coverage)


def test_unaccepted_generic_profiles_are_progressively_retired(tmp_path: Path) -> None:
    path = tmp_path / "profile-reconciliation.duckdb"
    apply_migrations(path)
    service = CurriculumImportService(DuckDBCurriculumRepository(path))
    assert not service.import_file(CATALOG, dry_run=False).errors
    assert not service.import_file(CURRICULUM, dry_run=False).errors

    old_source = json.loads(ENRICHMENT.read_text(encoding="utf-8"))
    old_source["metadata"]["reconcile_unaccepted_enrichment"] = False
    old_source["curriculum_enrichment"].pop("chapter_competency_dataset")
    old_source["curriculum_enrichment"]["base_datasets"] = [
        str(CATALOG.resolve()),
        str(CURRICULUM.resolve()),
    ]
    old_path = tmp_path / "unaccepted-profile.json"
    old_path.write_text(json.dumps(old_source, ensure_ascii=False), encoding="utf-8")
    assert not service.import_file(old_path, dry_run=False).errors

    assert not service.import_file(ENRICHMENT, dry_run=False).errors
    con = connect_v2(path, read_only=True)
    try:
        assert con.execute(
            """SELECT count(*) FROM curriculum_skill_details d
            JOIN skills s ON s.id=d.skill_id
            WHERE s.description LIKE
              'Compétence LCAI-0011C générique retirée du curriculum actif%'"""
        ).fetchone() == (0,)
        assert (
            con.execute(
                """SELECT count(*) FROM skills
            WHERE description LIKE
              'Compétence LCAI-0011C générique retirée du curriculum actif%'"""
            ).fetchone()[0]
            > 0
        )
        assert con.execute(
            """SELECT count(*) FROM curriculum_skill_details d
            JOIN skills s ON s.id=d.skill_id
            WHERE s.default_label LIKE 'Choisir et justifier une méthode pour %'
               OR s.default_label LIKE 'Mobiliser % dans une production'"""
        ).fetchone() == (0,)
    finally:
        con.close()
