"""LCAI-0038 curriculum tree audit tests."""

from __future__ import annotations

import pytest

from core.config import get_database_path
from services.brevet_referential.curriculum_audit import (
    format_tree_console,
    labels_overlap,
    normalize_label,
    run_curriculum_audit,
)


def test_normalize_and_overlap() -> None:
    assert normalize_label("Théorème de Thalès") == "theoreme de thales"
    assert labels_overlap("Thalès", "Théorème de Thalès")
    assert labels_overlap("Calcul littéral", "Calcul litteral")


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_extraction_layers() -> None:
    result = run_curriculum_audit(export=False, subject_filter=None)
    assert result.stats.subjects >= 8
    assert result.stats.domains >= 1
    assert result.stats.chapters >= 1
    assert result.stats.skills >= 1
    codes = {s["subject_code"] for s in result.subjects}
    for required in (
        "FRENCH",
        "MATHEMATICS",
        "HISTORY",
        "GEOGRAPHY",
        "EMC",
        "PHYSICS_CHEMISTRY",
        "SVT",
        "TECHNOLOGY",
    ):
        assert required in codes


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_orphan_and_duplicate_detection_run() -> None:
    result = run_curriculum_audit(export=False)
    assert isinstance(result.orphans, list)
    assert isinstance(result.duplicates, list)


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_content_and_official_coverage_fields() -> None:
    result = run_curriculum_audit(export=False, subject_filter="MATHEMATICS")
    assert result.chapters
    assert "content_count" in result.chapters[0]
    assert "official_question_count" in result.chapters[0]
    assert any(g.subject == "MATHEMATICS" for g in result.gaps)


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_tree_ordering_stable() -> None:
    a = run_curriculum_audit(export=False, subject_filter="MATHEMATICS")
    b = run_curriculum_audit(export=False, subject_filter="MATHEMATICS")
    assert [r.get("chapter_id") for r in a.tree_rows] == [r.get("chapter_id") for r in b.tree_rows]
    text = format_tree_console(a.tree_rows)
    assert "MATH" in text.upper() or "Math" in text


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_read_only_hash_unchanged() -> None:
    path = get_database_path()
    before = path.stat().st_mtime_ns
    run_curriculum_audit(export=False)
    after = path.stat().st_mtime_ns
    assert before == after


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_math_verdict_not_complete_with_known_gaps() -> None:
    result = run_curriculum_audit(export=False)
    assert result.subject_verdicts.get("MATHEMATICS") in {"PARTIAL", "INCOMPLETE"}
    assert any(g.subject == "MATHEMATICS" and "Trigonom" in g.expected_chapter_or_skill for g in result.gaps)
