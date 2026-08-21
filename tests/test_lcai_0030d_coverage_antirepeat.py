"""LCAI-0030-D — anti-repetition, brevet preference, coverage classification."""

from __future__ import annotations

from services.homework.anti_repetition import exclude_recent_content_ids, prioritize_brevet_content
from services.homework.coverage import CERTIFICATION_GRADES, classify_coverage_status


def test_exclude_recent_content_ids_skips_seen_exercises() -> None:
    rows = [
        (11, 1, 1, 3, "exercise"),
        (12, 1, 1, 3, "exercise"),
        (13, 1, 2, 2, "exercise"),
    ]
    filtered = exclude_recent_content_ids(rows, {11, 13})
    assert [int(row[0]) for row in filtered] == [12]


def test_exclude_recent_falls_back_when_all_seen() -> None:
    rows = [(11, 1, 1, 3, "exercise"), (12, 1, 1, 3, "exercise")]
    filtered = exclude_recent_content_ids(rows, {11, 12})
    assert [int(row[0]) for row in filtered] == [11, 12]


def test_prioritize_brevet_content_for_3e() -> None:
    rows = [
        (1, 10, 100, 3, "exercise"),
        (2, 10, 101, 3, "exam_practice"),
        (3, 11, 102, 2, "quiz"),
        (4, 11, 100, 3, "mini_assessment"),
    ]
    ordered = prioritize_brevet_content(rows, grade_code="FR-3E", exam_skill_ids={100})
    assert int(ordered[0][0]) in {2, 4}
    assert str(ordered[0][4]) in {"exam_practice", "mini_assessment"}
    # exam-linked skill among non-brevet types still preferred after brevet types
    non_brevet = [row for row in ordered if str(row[4]) == "exercise"]
    assert non_brevet and int(non_brevet[0][2]) == 100


def test_prioritize_brevet_noop_outside_3e() -> None:
    rows = [(1, 1, 1, 3, "exercise"), (2, 1, 1, 3, "exam_practice")]
    ordered = prioritize_brevet_content(rows, grade_code="FR-4E")
    assert [int(row[0]) for row in ordered] == [1, 2]


def test_coverage_status_matrix_labels() -> None:
    assert classify_coverage_status(12, generable=False) == ("available", "Disponible")
    assert classify_coverage_status(3, generable=False) == ("limited", "Couverture limitée")
    assert classify_coverage_status(0, generable=True) == ("generable", "Générable (IA)")
    assert classify_coverage_status(0, generable=False) == ("gap", "Manquant")


def test_certification_grades_cover_cm1_to_3e() -> None:
    assert CERTIFICATION_GRADES[0] == "FR-CM1"
    assert CERTIFICATION_GRADES[-1] == "FR-3E"
    assert len(CERTIFICATION_GRADES) == 6
