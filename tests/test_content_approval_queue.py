from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.approval_queue import build_dynamic_queue, filter_queue
from ui.content_approval_app import (
    _persist_and_verify_decision,
    _resolve_candidate_index,
    _subject_options,
)

ROOT = Path(__file__).parents[1]
QUEUE_PATH = ROOT / "resources" / "content" / "quality" / "lcai_0012d3_approval_priority.json"
WAVE1_QUEUE_PATH = ROOT / "resources" / "content" / "quality" / "lcai_0012d4_wave1_review_queue.json"


@pytest.fixture
def approval_persistence_database(tmp_path: Path) -> Path:
    target = tmp_path / "approval-persistence.duckdb"
    shutil.copy2(ROOT / "data" / "learning_coach_v2.duckdb", target)
    return target


def _load_queue(path: Path = QUEUE_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pending_queue_item(
    repository: DuckDBContentQualityRepository,
    *,
    queue_path: Path = WAVE1_QUEUE_PATH,
    answer_kind: str | None = None,
    recommendation: str | None = None,
    min_score: int | None = None,
) -> dict[str, Any]:
    """Return a queue item with no persisted human decision (isolated test fixture)."""
    for item in _load_queue(queue_path):
        if answer_kind is not None and item.get("answer_kind") != answer_kind:
            continue
        if recommendation is not None and item.get("recommended_decision") != recommendation:
            continue
        if min_score is not None and int(item.get("candidate_score", 0)) < min_score:
            continue
        version_id = int(item["version_id"])
        if repository.read_human_decision(version_id) is None:
            return item
    pytest.skip("No pending queue candidate matches the requested filters")
    return {}


def _coverage(
    skill: str,
    *,
    grade: str = "FR-3E",
    subject: str = "MATHEMATICS",
    practice: int = 0,
    assessment: int = 0,
) -> dict[str, Any]:
    return {
        "grade": grade,
        "subject": subject,
        "chapter": f"CH-{skill}",
        "skill": skill,
        "approved_practice": practice,
        "approved_assessment": assessment,
    }


def _candidate(
    version_id: int,
    skill: str,
    content_type: str,
    *,
    grade: str = "FR-3E",
    subject: str = "MATHEMATICS",
    recommendation: str = "APPROVE",
) -> dict[str, Any]:
    return {
        "content_id": version_id,
        "version_id": version_id,
        "code": f"C-{version_id}",
        "grade": grade,
        "subject": subject,
        "chapter": f"CH-{skill}",
        "skill": skill,
        "content_type": content_type,
        "candidate_score": 90,
        "quality_result": "PASS",
        "recommended_decision": recommendation,
        "hard_gates_passed": True,
        "missing_coverage": True,
        "answer_kind": "numeric",
    }


def _dynamic_fixture() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    coverage = [
        _coverage("IMMEDIATE", practice=1),
        _coverage("PLAN", grade="FR-4E", subject="FRENCH"),
        _coverage("PROGRESS", subject="SVT"),
    ]
    candidates = [
        _candidate(1, "IMMEDIATE", "assessment"),
        _candidate(2, "PLAN", "practice", grade="FR-4E", subject="FRENCH"),
        _candidate(3, "PLAN", "assessment", grade="FR-4E", subject="FRENCH"),
        _candidate(4, "PROGRESS", "practice", subject="SVT"),
    ]
    return build_dynamic_queue(candidates, coverage, {})


def test_default_minimal_plan_filter_contains_only_p1_and_p2() -> None:
    queue, _ = _dynamic_fixture()
    filtered = filter_queue(queue)
    assert {row["approval_priority_status"] for row in filtered} == {
        "TIER1_IMMEDIATE",
        "TIER1_PLAN",
    }


def test_tier1_immediate_and_tier2_progress_filters() -> None:
    queue, _ = _dynamic_fixture()
    immediate = filter_queue(
        queue,
        priority_filter="Complète immédiatement un Tier 1",
        priority_levels=("P1",),
    )
    progress = filter_queue(
        queue,
        priority_filter="Tier 3 → Tier 2",
        priority_levels=("P3",),
    )
    assert [row["version_id"] for row in immediate] == [1]
    assert [row["version_id"] for row in progress] == [4]


def test_grade_and_subject_filters() -> None:
    queue, _ = _dynamic_fixture()
    filtered = filter_queue(
        queue,
        priority_filter="Tous les candidats recommandés",
        priority_levels=("P1", "P2", "P3"),
        grade="FR-4E",
        subjects=("FRENCH",),
    )
    assert {row["version_id"] for row in filtered} == {2, 3}


def test_priority_4e_and_balanced_subject_modes() -> None:
    queue, _ = _dynamic_fixture()
    priority_4e = filter_queue(
        queue,
        priority_filter="Tous les candidats recommandés",
        priority_levels=("P1", "P2", "P3"),
        priority_4e=True,
    )
    assert priority_4e[0]["grade"] == "FR-4E"
    balanced = filter_queue(
        queue,
        priority_filter="Tous les candidats recommandés",
        priority_levels=("P1", "P2", "P3"),
        balance_subjects=True,
    )
    assert len({row["subject"] for row in balanced[:3]}) == 3


def test_queue_recalculation_removes_approved_and_promotes_plan_to_immediate() -> None:
    coverage_before = [_coverage("PLAN")]
    candidates = [
        _candidate(10, "PLAN", "practice"),
        _candidate(11, "PLAN", "assessment"),
    ]
    before, summary_before = build_dynamic_queue(candidates, coverage_before, {})
    assert {row["approval_priority_status"] for row in before} == {"TIER1_PLAN"}
    assert summary_before["minimal_plan_remaining"] == 2

    coverage_after = [_coverage("PLAN", practice=1)]
    after, summary_after = build_dynamic_queue(
        candidates,
        coverage_after,
        {10: "APPROVED"},
    )
    assert [row["version_id"] for row in after] == [11]
    assert after[0]["approval_priority_status"] == "TIER1_IMMEDIATE"
    assert after[0]["review_status"] == "PENDING"
    assert summary_after["minimal_plan_remaining"] == 1


def test_navigation_subset_order_is_stable_and_decided_items_are_removed() -> None:
    queue, _ = _dynamic_fixture()
    filtered = filter_queue(queue)
    decided_version = int(filtered[0]["version_id"])
    rebuilt, _ = build_dynamic_queue(
        [_candidate(1, "IMMEDIATE", "assessment"), *_dynamic_fixture()[0][1:]],
        [
            _coverage("IMMEDIATE", practice=1),
            _coverage("PLAN", grade="FR-4E", subject="FRENCH"),
            _coverage("PROGRESS", subject="SVT"),
        ],
        {decided_version: "APPROVED"},
    )
    assert all(int(row["version_id"]) != decided_version for row in rebuilt)


def test_regression_removed_current_item_never_calls_list_index() -> None:
    items = [{"version_id": 1}, {"version_id": 3}]
    assert _resolve_candidate_index(items, current_version_id=2, previous_index=1) == 1


def test_navigation_after_first_middle_and_last_decisions() -> None:
    original = [{"version_id": value} for value in (1, 2, 3)]
    assert _resolve_candidate_index(original[1:], 1, 0) == 0
    assert _resolve_candidate_index([original[0], original[2]], 2, 1) == 1
    assert _resolve_candidate_index(original[:-1], 3, 2) == 1


def test_navigation_after_decision_that_changes_filter_or_empties_list() -> None:
    changed_filter = [{"version_id": 8}]
    assert _resolve_candidate_index(changed_filter, 7, 4) == 0
    assert _resolve_candidate_index([], 7, 0) is None


def test_reject_keep_review_and_tier_change_remove_stable_version() -> None:
    coverage = [_coverage("CHANGE", practice=1)]
    candidates = [_candidate(20, "CHANGE", "assessment"), _candidate(21, "CHANGE", "assessment")]
    for status in ("APPROVED", "REJECTED", "KEEP_REVIEW"):
        queue, _ = build_dynamic_queue(candidates, coverage, {20: status})
        assert [row["version_id"] for row in queue] == [21]
        assert queue[0]["approval_priority_status"] == "TIER1_IMMEDIATE"


def test_previous_next_resolution_uses_version_id_not_object_equality() -> None:
    items = [{"version_id": 30}, {"version_id": 31}, {"version_id": 32}]
    assert _resolve_candidate_index(items, 31, 0) == 1
    assert _resolve_candidate_index(items, 30, 2) == 0
    assert _resolve_candidate_index(items, 32, 0) == 2


def test_filter_options_remain_stable_when_last_subject_candidate_is_removed() -> None:
    base = [
        {"subject": "FRENCH", "version_id": 1},
        {"subject": "MATHEMATICS", "version_id": 2},
    ]
    assert _subject_options(base) == ("FRENCH", "MATHEMATICS")
    remaining = [base[1]]
    assert _subject_options(base) != _subject_options(remaining)


def test_regression_structured_p1_does_not_use_list_index_for_composite_answer(
    approval_persistence_database: Path,
) -> None:
    repository = DuckDBContentQualityRepository(approval_persistence_database)
    item = _pending_queue_item(
        repository,
        answer_kind="structured",
        recommendation="APPROVE",
        min_score=80,
    )
    assert item["answer_kind"] == "structured"
    if item.get("choices"):
        with pytest.raises(ValueError, match=r"not in list"):
            item["choices"].index(item["expected_answer"])

    persisted = _persist_and_verify_decision(
        repository,
        item=item,
        action="APPROVE",
        reviewer="isolated-reviewer",
        approver="isolated-approver",
        reason="Isolated regression test.",
    )
    assert persisted["review_status"] == "APPROVED"
    assert persisted["production_enabled"] is True
    assert persisted["source_status"] == "draft"

    skill = str(item["skill"])
    rebuilt, _ = build_dynamic_queue(
        [item],
        [
            _coverage(
                skill,
                grade=str(item["grade"]),
                subject=str(item["subject"]),
                practice=1,
                assessment=1,
            )
        ],
        {int(item["version_id"]): "APPROVED"},
    )
    assert rebuilt == []
    assert _resolve_candidate_index(rebuilt, int(item["version_id"]), 0) is None


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [("REJECT", "REJECTED"), ("KEEP_FOR_REVIEW", "KEEP_REVIEW")],
)
def test_single_candidate_non_approval_decision_is_persisted_before_empty_queue(
    approval_persistence_database: Path,
    action: str,
    expected_status: str,
) -> None:
    repository = DuckDBContentQualityRepository(approval_persistence_database)
    item = _pending_queue_item(repository, recommendation="KEEP_FOR_REVIEW")
    persisted = _persist_and_verify_decision(
        repository,
        item=item,
        action=action,
        reviewer="isolated-reviewer",
        approver="",
        reason="Isolated lifecycle test.",
    )
    assert persisted["review_status"] == expected_status
    skill = str(item["skill"])
    rebuilt, _ = build_dynamic_queue(
        [item],
        [
            _coverage(
                skill,
                grade=str(item["grade"]),
                subject=str(item["subject"]),
                assessment=1 if item["content_type"] == "assessment" else 0,
                practice=1 if item["content_type"] == "practice" else 0,
            )
        ],
        {int(item["version_id"]): expected_status},
    )
    assert rebuilt == []


def test_approval_double_rerun_is_idempotent(
    approval_persistence_database: Path,
) -> None:
    repository = DuckDBContentQualityRepository(approval_persistence_database)
    item = _pending_queue_item(repository, recommendation="APPROVE", min_score=80)
    first = _persist_and_verify_decision(
        repository,
        item=item,
        action="APPROVE",
        reviewer="isolated-reviewer",
        approver="isolated-approver",
        reason="Idempotence test.",
    )
    second = _persist_and_verify_decision(
        repository,
        item=item,
        action="APPROVE",
        reviewer="isolated-reviewer",
        approver="isolated-approver",
        reason="Idempotence test.",
    )
    assert second["content_id"] == first["content_id"]
    connection = connect_v2(approval_persistence_database, read_only=True)
    try:
        source_id = str(item["version_id"])
        assert connection.execute(
            """
            SELECT count(*) FROM content_versions
            WHERE status='approved'
              AND json_extract_string(payload,'$.publication_source_version_id')=?
            """,
            [source_id],
        ).fetchone() == (1,)
        assert connection.execute(
            """
            SELECT count(*) FROM content_production_gates
            WHERE content_version_id=?
            """,
            [first["published_version_id"]],
        ).fetchone() == (1,)
    finally:
        connection.close()


def test_failure_after_commit_cannot_remove_persisted_decision(
    approval_persistence_database: Path,
) -> None:
    repository = DuckDBContentQualityRepository(approval_persistence_database)
    item = _pending_queue_item(repository, recommendation="APPROVE", min_score=80)
    with pytest.raises(RuntimeError, match="simulated navigation failure"):
        _persist_and_verify_decision(
            repository,
            item=item,
            action="APPROVE",
            reviewer="isolated-reviewer",
            approver="isolated-approver",
            reason="Commit boundary test.",
        )
        raise RuntimeError("simulated navigation failure")
    assert repository.read_human_decision(int(item["version_id"]))["review_status"] == "APPROVED"


def test_failure_before_commit_leaves_no_partial_decision(
    approval_persistence_database: Path,
) -> None:
    repository = DuckDBContentQualityRepository(approval_persistence_database)
    item = _pending_queue_item(repository, recommendation="KEEP_FOR_REVIEW")
    with pytest.raises(ValueError, match="high-confidence"):
        _persist_and_verify_decision(
            repository,
            item=item,
            action="APPROVE",
            reviewer="isolated-reviewer",
            approver="isolated-approver",
            reason="Pre-commit failure test.",
        )
    assert repository.read_human_decision(int(item["version_id"])) is None
