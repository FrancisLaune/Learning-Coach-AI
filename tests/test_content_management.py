from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from domain.content.models import ValidationStatus
from domain.content.validation import ContentValidator, Severity
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.content import (
    ContentSearchRepository,
    ContentUnitOfWork,
    MediaRepository,
    SubjectRepository,
    ValidationRepository,
    VersionRepository,
)
from migrations.runner import apply_migrations
from services.content import (
    ContentImportService,
    ContentSearchService,
    ContentValidationService,
    ContentVersionService,
    CSVContentImporter,
    ExcelContentImporter,
    ImporterRegistry,
    JSONContentImporter,
    MarkdownContentImporter,
    YAMLContentImporter,
)


@pytest.fixture
def content_database(tmp_path: Path) -> Path:
    path = tmp_path / "content.duckdb"
    apply_migrations(path)
    return path


def manifest() -> dict[str, object]:
    return {
        "subjects": [{"code": "TEST-SUBJECT", "label": "Test subject"}],
        "domains": [{"code": "TEST-DOMAIN", "label": "Test domain", "subject_code": "TEST-SUBJECT"}],
        "skills": [{"code": "TEST-SKILL", "label": "Test skill", "domain_code": "TEST-DOMAIN"}],
        "exercises": [
            {
                "code": "TEST-EXERCISE",
                "title": "Test exercise",
                "objective": "Test objective",
                "subject_code": "TEST-SUBJECT",
                "difficulty": 3,
                "tags": ["algebra"],
                "questions": [
                    {
                        "code": "TEST-QUESTION",
                        "statement": "What is 2 + 2?",
                        "answer": 4,
                        "answer_type": "number",
                        "explanation": "Two plus two equals four.",
                        "skills": [{"skill_code": "TEST-SKILL", "primary": True}],
                    }
                ],
            }
        ],
        "metadata": {"tags": ["algebra", "unused"]},
    }


def test_json_markdown_csv_and_registry_imports(tmp_path: Path) -> None:
    payload = json.dumps(manifest())
    assert JSONContentImporter().load(payload).exercises[0].questions[0].answer.value == 4
    assert MarkdownContentImporter().load(f"# Content\n```json\n{payload}\n```").subjects[0].code == "TEST-SUBJECT"
    csv_document = CSVContentImporter().load("entity_type,code,label\nsubjects,CSV-SUBJECT,CSV subject\n")
    assert csv_document.subjects[0].label == "CSV subject"
    path = tmp_path / "content.json"
    path.write_text(payload, encoding="utf-8")
    assert isinstance(ImporterRegistry.defaults().for_source(path), JSONContentImporter)


def test_yaml_and_excel_importers(tmp_path: Path) -> None:
    yaml = pytest.importorskip("yaml")
    yaml_path = tmp_path / "content.yaml"
    yaml_path.write_text(yaml.safe_dump({"subjects": [{"code": "YAML", "label": "YAML"}]}), encoding="utf-8")
    assert YAMLContentImporter().load(yaml_path).subjects[0].code == "YAML"
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "subjects"
    sheet.append(["code", "label"])
    sheet.append(["XLSX", "Excel"])
    excel_path = tmp_path / "content.xlsx"
    workbook.save(excel_path)
    assert ExcelContentImporter().load(excel_path).subjects[0].label == "Excel"


def test_validation_pipeline_produces_detailed_quality_report() -> None:
    document = JSONContentImporter().load(json.dumps(manifest()))
    report = ContentValidator().validate(document)
    assert report.valid
    assert report.count(Severity.WARNING) == 1
    assert report.issues[0].code == "unused_tag"

    broken = manifest()
    exercise = cast(list[dict[str, Any]], broken["exercises"])[0]
    exercise["questions"][0]["answer"] = ""
    exercise["questions"][0]["skills"] = [{"skill_code": "UNKNOWN"}]
    invalid = ContentValidator().validate(JSONContentImporter().load(json.dumps(broken)))
    assert not invalid.valid
    assert {issue.code for issue in invalid.issues} >= {"question_without_answer", "broken_skill"}


def test_specialized_repositories_and_version_history(content_database: Path) -> None:
    subjects = SubjectRepository(content_database)
    subject_id = subjects.upsert({"code": "REPO-SUBJECT", "label": "Repository subject"})
    assert subjects.get("REPO-SUBJECT")["id"] == subject_id  # type: ignore[index]
    media = MediaRepository(content_database)
    assert media.upsert({"code": "MEDIA-1", "kind": "image", "uri": "assets/test.png"}) >= 100000

    versions = VersionRepository(content_database)
    version_id = versions.create(
        "subject", subject_id, {"label": "Repository subject"}, "author", ValidationStatus.DRAFT
    )
    service = ContentVersionService(versions)
    service.transition(version_id, ValidationStatus.DRAFT, ValidationStatus.REVIEW, "reviewer")
    service.transition(version_id, ValidationStatus.REVIEW, ValidationStatus.APPROVED, "reviewer")
    assert versions.history("subject", subject_id)[0]["status"] == "approved"
    with pytest.raises(ValueError, match="Invalid content transition"):
        service.transition(version_id, ValidationStatus.APPROVED, ValidationStatus.DRAFT, "author")
    connection = connect_v2(content_database, read_only=True)
    try:
        assert connection.execute(
            "SELECT count(*) FROM content_status_events WHERE content_version_id=?", [version_id]
        ).fetchone() == (3,)
    finally:
        connection.close()


def test_transactional_import_validation_persistence_and_search(content_database: Path) -> None:
    payload = manifest()
    exercises = cast(list[dict[str, Any]], payload["exercises"])
    exercises[0]["media"] = [{"code": "DIAGRAM-1", "kind": "image", "uri": "assets/diagram.png"}]
    document = JSONContentImporter().load(json.dumps(payload))
    source = content_database.parent / "manifest.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    counts = ContentImportService(ContentUnitOfWork(content_database)).import_file(source, "content-author")
    assert counts == {"subjects": 1, "domains": 1, "skills": 1, "exercises": 1, "questions": 1}

    validation = ContentValidationService(ValidationRepository(content_database))
    report = validation.validate(document, "test-manifest.json")
    assert report.valid
    search = ContentSearchService(ContentSearchRepository(content_database))
    assert (
        search.search(subject="TEST-SUBJECT", skill="TEST-SKILL", keyword="exercise", tags=("algebra",), difficulty=3)[
            0
        ]["code"]
        == "TEST-EXERCISE"
    )

    connection = connect_v2(content_database, read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM validation_runs").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM content_versions").fetchone() == (2,)
        assert connection.execute("SELECT count(*) FROM content_media").fetchone() == (1,)
    finally:
        connection.close()
