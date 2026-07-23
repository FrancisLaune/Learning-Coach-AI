from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from core.config import PROJECT_ROOT
from domain.curriculum.validation import CatalogValidator, PrerequisiteCycleError, assert_acyclic
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.curriculum import DuckDBCurriculumRepository
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from migrations.runner import apply_migrations
from services.curriculum import (
    ContentApprovalService,
    ContentQualityService,
    CurriculumImportService,
    EditorialWorkflowService,
)

CATALOG = PROJECT_ROOT / "resources" / "catalog" / "lcai_0009_catalog.json"


@pytest.fixture
def document() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


@pytest.fixture
def catalog_database(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.duckdb"
    apply_migrations(path)
    report = CurriculumImportService(DuckDBCurriculumRepository(path)).import_file(CATALOG, dry_run=False)
    assert not report.errors
    return path


def test_catalog_manifest_meets_minimum_scope(document: dict[str, Any]) -> None:
    contents = document["contents"]
    chapters = document["chapters"]
    relations = document["relations"]
    assert isinstance(contents, list) and len(contents) == 68
    assert isinstance(chapters, list) and len(chapters) == 34
    assert isinstance(relations, list) and len(relations) >= 20
    assert sum(item["question"]["evaluative"] for item in contents) >= 40
    assert sum(item["content_type"] == "worked_example" for item in contents) >= 20
    assert sum("brevet" in item["tags"] for item in contents) >= 20
    assert sum("remediation" in item["tags"] for item in contents) >= 10
    assert sum("transition_ready" in item["tags"] for item in contents) >= 10


def test_curriculum_and_content_validation(document: dict[str, Any]) -> None:
    report = CatalogValidator().validate(document)
    assert report.valid and not report.issues


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda content: content.update(difficulty=9), "invalid_difficulty"),
        (lambda content: content.update(duration_minutes=0), "invalid_duration"),
        (lambda content: content["question"].update(statement=""), "missing_statement"),
        (lambda content: content["solution"].update(explanation=""), "missing_solution"),
        (lambda content: content.update(tags=["not_registered"]), "unknown_tag"),
        (lambda content: content.update(reviewer=content["author_source"]), "self_approval"),
    ],
)
def test_invalid_content_is_rejected(
    document: dict[str, Any], mutation: Callable[[dict[str, Any]], None], code: str
) -> None:
    broken = deepcopy(document)
    content = broken["contents"][0]
    mutation(content)
    assert code in {issue.code for issue in CatalogValidator().validate(broken).issues}


def test_prerequisite_graph_rejects_self_reference_and_cycle() -> None:
    with pytest.raises(PrerequisiteCycleError, match="Self prerequisite"):
        assert_acyclic([{"prerequisite": "A", "target": "A"}])
    with pytest.raises(PrerequisiteCycleError, match="cycle"):
        assert_acyclic(
            [
                {"prerequisite": "A", "target": "B"},
                {"prerequisite": "B", "target": "C"},
                {"prerequisite": "C", "target": "A"},
            ]
        )


def test_workflow_role_separation_and_validation() -> None:
    workflow = EditorialWorkflowService()
    assert workflow.transition("draft", "review", validated=True) == "review"
    with pytest.raises(ValueError, match="requires complete validation"):
        workflow.transition("review", "approved", validated=False)
    with pytest.raises(ValueError, match="self-approval"):
        ContentApprovalService.approve(author="same", reviewer="same", approver="other", validated=True)


def test_quality_score_is_explainable(document: dict[str, Any]) -> None:
    report = CatalogValidator().validate(document)
    content = document["contents"][0]
    quality = ContentQualityService().assess(content, report)
    assert quality.score == 100
    assert quality.level == "excellent"
    assert len(quality.passed) == 10
    assert not quality.blocking_errors


def test_dry_run_does_not_write_and_real_import_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "dry-run.duckdb"
    apply_migrations(path)
    service = CurriculumImportService(DuckDBCurriculumRepository(path))
    dry = service.import_file(CATALOG, dry_run=True)
    con = connect_v2(path, read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM curriculum_chapters").fetchone() == (0,)
        assert con.execute("SELECT count(*) FROM content_import_batches").fetchone() == (0,)
    finally:
        con.close()
    first = service.import_file(CATALOG, dry_run=False)
    second = service.import_file(CATALOG, dry_run=False)
    assert dry.dry_run and first.created == 211
    assert second.created == 0 and second.ignored == 211


def test_persisted_curriculum_graph_and_editorial_audit(catalog_database: Path) -> None:
    con = connect_v2(catalog_database, read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM curriculum_chapters").fetchone() == (34,)
        assert con.execute("SELECT count(*) FROM curriculum_skill_details").fetchone() == (34,)
        assert con.execute("SELECT count(*) FROM learning_objectives").fetchone() == (34,)
        assert con.execute("SELECT count(*) FROM curriculum_skill_relations").fetchone() == (38,)
        assert con.execute("SELECT count(*) FROM editorial_reviews").fetchone() == (68,)
        assert con.execute("SELECT count(*) FROM editorial_approvals WHERE active").fetchone() == (68,)
        assert con.execute("SELECT min(score) FROM content_quality_assessments").fetchone() == (100,)
    finally:
        con.close()


def test_approved_catalog_is_directly_consumable_by_lcai_0008(catalog_database: Path) -> None:
    contents = DuckDBRecommendationRepository(catalog_database).load_approved_contents()
    assert len(contents) == 68
    assert all(item.version_status == "approved" and item.active for item in contents)
    assert {item.grade_code for item in contents} == {"FR-4E", "FR-3E"}
    assert any("brevet" in item.tags for item in contents)
    assert any("remediation" in item.tags for item in contents)
    assert any(item.transition_markers for item in contents)
    assert all(1 <= item.difficulty <= 5 and item.estimated_minutes > 0 for item in contents)


def test_non_approved_statuses_never_enter_catalog(catalog_database: Path) -> None:
    con = connect_v2(catalog_database, read_only=True)
    try:
        statuses = con.execute(
            """SELECT DISTINCT cv.status FROM approved_learning_catalog c
            JOIN content_versions cv ON cv.id=c.content_version_id"""
        ).fetchall()
        assert statuses == [("approved",)]
        assert con.execute(
            """SELECT count(*) FROM approved_learning_catalog c JOIN content_versions cv
            ON cv.id=c.content_version_id WHERE cv.status IN ('draft','review','archived')"""
        ).fetchone() == (0,)
    finally:
        con.close()


def test_catalog_breakdown_by_subject_and_grade(catalog_database: Path) -> None:
    con = connect_v2(catalog_database, read_only=True)
    try:
        rows = con.execute(
            """SELECT sl.code,s.code,count(*) FROM approved_learning_catalog c
            JOIN school_levels sl ON sl.code=c.grade_code JOIN subjects s ON s.id=c.subject_id
            GROUP BY sl.code,s.code"""
        ).fetchall()
        breakdown = {(grade, subject): count for grade, subject, count in rows}
        assert breakdown[("FR-4E", "MATHEMATICS")] == 16
        assert breakdown[("FR-3E", "MATHEMATICS")] == 16
        assert breakdown[("FR-4E", "FRENCH")] == 12
        assert breakdown[("FR-3E", "FRENCH")] == 12
        for subject in ("HISTORY", "GEOGRAPHY", "PHYSICS_CHEMISTRY", "SVT", "ENGLISH", "SPANISH"):
            assert breakdown[("FR-3E", subject)] == 2
    finally:
        con.close()
