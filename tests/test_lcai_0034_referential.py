"""LCAI-0034 referential correction tests."""

from __future__ import annotations

import duckdb
import pytest

from core.config import get_database_path
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.eduscol_ingest import detect_document_variant, exam_identity_from_entry
from services.brevet_referential.families import classify_near_duplicate_group
from services.brevet_referential.repository import PedagogicalContentRepository
from services.brevet_referential.traceability import count_archive_derived_without_parent
from services.homework.exercise_selection import panachage_select


def test_detect_accessibility_variant() -> None:
    assert detect_document_variant("Sujet Arial 16") == "ARIAL_16"
    assert detect_document_variant("Sujet standard") == "STANDARD"


def test_exam_identity_stable() -> None:
    entry = {
        "year": 2023,
        "session": "normale",
        "zone": "metropole",
        "series": "generale",
        "subject": "mathematics",
        "base_exam_identifier": "2023-normale-metropole-generale-mathematics",
    }
    assert exam_identity_from_entry(entry) == "2023-normale-metropole-generale-mathematics"


def test_near_duplicate_classification() -> None:
    assert classify_near_duplicate_group(["abc", "abc"]) == "TRUE_DUPLICATE"
    assert classify_near_duplicate_group(["Calcule 2+2", "Calcule 3+3"]) in {
        "PARAMETRIC_FAMILY",
        "SAME_SKILL_DIFFERENT_REASONING",
        "LEGITIMATE_SIMILARITY",
    }


def test_max_per_family_selection() -> None:
    rows = [
        (1, 1, 1, 3, "EXERCISE", 2, 10),
        (2, 1, 1, 3, "EXERCISE", 2, 10),
        (3, 1, 1, 3, "EXERCISE", 2, 11),
        (4, 1, 1, 2, "EXERCISE", 2, 12),
    ]
    selected = panachage_select(rows, target=3, exercise_count=3, max_per_family=1)
    families = [r[6] for r in selected]
    assert families.count(10) <= 1


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_no_orphan_archive_derived_after_pipeline() -> None:
    # Pipeline may already have been run; assert invariant.
    store = BrevetContentStore()
    try:
        assert count_archive_derived_without_parent(store) == 0
    finally:
        store.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_derived_chain_dod() -> None:
    store = BrevetContentStore()
    try:
        repo = PedagogicalContentRepository(store)
        sample = repo.find_derived_of_archive(subject_code="MATHEMATICS")
        if sample is None:
            pytest.skip("no derived chain yet — run scripts/lcai_0034_run_corrections.py")
        assert sample["source_type"] == "ARCHIVE_DERIVED"
        assert sample["parent_question_id"] is not None
        assert sample["parent_archive_id"] is not None
        assert sample["source_provider"] == "EDUSCOL"
    finally:
        store.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_coverage_view_has_family_columns() -> None:
    con = duckdb.connect(str(get_database_path()), read_only=True)
    try:
        cols = [
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='v_content_coverage'"
            ).fetchall()
        ]
        assert "unique_family_count" in cols
        assert "brevet_style_count" in cols
        assert "archive_grounding_rate" in cols
    finally:
        con.close()
