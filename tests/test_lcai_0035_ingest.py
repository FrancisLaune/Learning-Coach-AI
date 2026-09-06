"""LCAI-0035 massive official DNB archive ingestion tests."""

from __future__ import annotations

import duckdb
import pytest

from core.config import PROJECT_ROOT, get_database_path
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.catalog import exam_identity_key, write_catalog
from services.brevet_referential.eduscol_ingest import detect_document_variant
from services.brevet_referential.pdf_parser import is_dnb_document, parse_dnb_pdf
from services.brevet_referential.traceability import count_archive_derived_without_parent

PDF_DIR = PROJECT_ROOT / "artifacts" / "LCAI-0035" / "pdfs"


def test_exam_identity_collapses_french_parts() -> None:
    a = exam_identity_key(
        year=2024,
        session="normale",
        zone="centres_etrangers",
        series="generale",
        subject_group="FRENCH",
        exam_code="24GENFRDAA1",
    )
    b = exam_identity_key(
        year=2024,
        session="normale",
        zone="centres_etrangers",
        series="generale",
        subject_group="FRENCH",
        exam_code="24GENFRQGCAA1",
    )
    assert a == b


def test_accessibility_variant_detection() -> None:
    assert detect_document_variant("Sujet Arial 24") == "ARIAL_24"
    assert detect_document_variant("braille intégral") == "BRAILLE"


@pytest.mark.skipif(not any(PDF_DIR.glob("eduscol_68113.pdf")), reason="sample PDF missing")
def test_parse_math_pdf_segments_exercises() -> None:
    path = PDF_DIR / "eduscol_68113.pdf"
    parsed = parse_dnb_pdf(path)
    assert is_dnb_document(parsed.full_text)
    assert parsed.official_exam_code == "25GENMATAA1"
    assert parsed.year == 2025
    assert len(parsed.sections) >= 4
    assert sum(len(s.questions) for s in parsed.sections) >= 5


def test_catalog_rebuild_has_official_urls() -> None:
    path = write_catalog(include_accessibility=False)
    text = path.read_text(encoding="utf-8")
    assert "eduscol.education.fr/document/" in text or "education.gouv.fr" in text
    assert "EDUSCOL" in text


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_official_question_count_after_ingest_gt_3() -> None:
    con = duckdb.connect(str(get_database_path()), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM content_items WHERE source_type = 'OFFICIAL_ARCHIVE'").fetchone()[0]
        assert int(n) > 3
    finally:
        con.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_orphan_archive_derived_invariant() -> None:
    store = BrevetContentStore()
    try:
        assert count_archive_derived_without_parent(store) == 0
    finally:
        store.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_official_questions_have_nonempty_statement() -> None:
    con = duckdb.connect(str(get_database_path()), read_only=True)
    try:
        empty = con.execute(
            """
            SELECT COUNT(*) FROM content_items
            WHERE source_type = 'OFFICIAL_ARCHIVE'
              AND (statement IS NULL OR length(trim(statement)) < 10)
            """
        ).fetchone()[0]
        assert int(empty) == 0
    finally:
        con.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_ingestion_tables_exist() -> None:
    con = duckdb.connect(str(get_database_path()), read_only=True)
    try:
        tables = {
            r[0]
            for r in con.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_name IN (
                  'archive_ingestion_runs',
                  'archive_ingestion_events',
                  'exam_archive_documents_ref'
                )
                """
            ).fetchall()
        }
        assert "archive_ingestion_runs" in tables
        assert "archive_ingestion_events" in tables
        assert "exam_archive_documents_ref" in tables
    finally:
        con.close()
