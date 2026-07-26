from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.approval_acceleration import (
    RankedCandidate,
    ReviewReason,
    automatic_resolution_possible,
    classify_review,
    rank_candidates,
)

ROOT = Path(__file__).parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"


@pytest.fixture
def approval_database(tmp_path: Path) -> Path:
    target = tmp_path / "approval.duckdb"
    shutil.copy2(ROOT / "data" / "learning_coach_v2.duckdb", target)
    return target


def _result(**changes: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "decision": "REVIEW",
        "subject": "MATHEMATICS",
        "content_type": "practice",
        "difficulty": 2,
        "prompt": "Calcule 20 % de 80.",
        "explanation": "Le calcul détaillé donne correctement 16.",
        "hard_gates": {
            "structural_validity": True,
            "answer_correctness": True,
            "skill_alignment": True,
            "grade_appropriateness": False,
            "executability": True,
            "duplicate_safety": True,
        },
    }
    result.update(changes)
    return result


def _source(**answer_changes: Any) -> dict[str, Any]:
    answer = {
        "kind": "numeric",
        "expected": "16",
        "independently_computed": "16",
        "options": [],
    }
    answer.update(answer_changes)
    return {"answer": answer}


def test_review_reason_classification_supports_multiple_reasons() -> None:
    reasons = classify_review(
        _result(subject="ENGLISH", prompt="Réponds à l'oral après l'audio."),
        _source(kind="open_response", independently_computed=None),
    )
    assert ReviewReason.OPEN_RESPONSE in reasons
    assert ReviewReason.LANGUAGE_PRODUCTION in reasons
    assert ReviewReason.SOURCE_DOCUMENT_REQUIRED in reasons
    assert ReviewReason.ORAL_MODALITY in reasons


def test_specialized_verified_math_review_can_be_resolved() -> None:
    result = _result()
    reasons = classify_review(result, _source())
    assert automatic_resolution_possible(result, _source(), reasons)
    assert not automatic_resolution_possible(
        result,
        _source(independently_computed=None),
        classify_review(result, _source(independently_computed=None)),
    )


def test_candidate_ranking_prioritizes_pass_and_never_selects_failed_gate() -> None:
    ranked = rank_candidates(
        [
            RankedCandidate("review", "SK", "practice", "REVIEW", 90, True, ()),
            RankedCandidate("failed", "SK", "practice", "PASS", 100, False, ()),
            RankedCandidate("pass", "SK", "assessment", "PASS", 80, True, ()),
        ]
    )
    assert [item.code for item in ranked] == ["pass", "review", "failed"]


def test_approval_queue_prioritizes_missing_coverage_and_practice() -> None:
    queue = json.loads((QUALITY / "lcai_0012d2_approval_queue.json").read_text(encoding="utf-8"))
    assert queue[0]["missing_coverage"]
    first_skill = queue[0]["skill"]
    same_skill = [item for item in queue if item["skill"] == first_skill]
    positions = {kind: index for index, kind in enumerate(item["content_type"] for item in same_skill)}
    if "practice" in positions and "assessment" in positions:
        assert positions["practice"] < positions["assessment"]


def test_human_approval_is_idempotent_and_feature_gated(approval_database: Path) -> None:
    queue = json.loads((QUALITY / "lcai_0012d2_approval_queue.json").read_text(encoding="utf-8"))
    item = next(row for row in queue if row["recommended_decision"] == "APPROVE")
    repository = DuckDBContentQualityRepository(approval_database)
    content_id = repository.approve_for_production(
        item=item,
        reviewer="human-reviewer",
        approver="human-approver",
        reason="Approved in integration test.",
    )
    assert (
        repository.approve_for_production(
            item=item,
            reviewer="human-reviewer",
            approver="human-approver",
            reason="Approved in integration test.",
        )
        == content_id
    )
    connection = connect_v2(approval_database, read_only=True)
    try:
        assert connection.execute(
            "SELECT count(*) FROM production_learning_catalog WHERE content_id=?",
            [content_id],
        ).fetchone() == (1,)
    finally:
        connection.close()


def test_reject_and_review_never_enter_student_catalog(approval_database: Path) -> None:
    queue = json.loads((QUALITY / "lcai_0012d2_approval_queue.json").read_text(encoding="utf-8"))
    repository = DuckDBContentQualityRepository(approval_database)
    for decision, item in zip(
        ("REJECT", "KEEP_FOR_REVIEW"),
        (queue[-1], queue[-2]),
        strict=True,
    ):
        repository.record_human_decision(
            version_id=int(item["version_id"]),
            reviewer=f"reviewer-{decision}",
            decision=decision,
            notes="Integration test.",
        )
    connection = connect_v2(approval_database, read_only=True)
    try:
        version_ids = [queue[-1]["version_id"], queue[-2]["version_id"]]
        assert connection.execute(
            """
            SELECT count(*) FROM production_learning_catalog
            WHERE content_version_id IN (SELECT unnest(?))
            """,
            [version_ids],
        ).fetchone() == (0,)
    finally:
        connection.close()


def test_qcm_historical_and_deterministic_regressions_are_preserved() -> None:
    connection = connect_v2(read_only=True)
    try:
        assert connection.execute(
            """
            SELECT count(*) FROM content_questions
            WHERE response_type IN ('single_choice','multiple_choice')
            """
        ).fetchone() == (255,)
        assert connection.execute(
            """
            SELECT count(*) FROM content_questions q
            WHERE q.response_type IN ('single_choice','multiple_choice')
              AND (
                NOT EXISTS (
                    SELECT 1 FROM content_answer_options o
                    WHERE o.question_id=q.id AND o.is_correct
                )
                OR EXISTS (
                    SELECT stable_code FROM content_answer_options o
                    WHERE o.question_id=q.id GROUP BY stable_code HAVING count(*)>1
                )
              )
            """
        ).fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM approved_learning_catalog").fetchone() == (68,)
        assert connection.execute("SELECT count(*) FROM production_learning_catalog").fetchone() == (68,)
        assert connection.execute(
            """
            SELECT count(*) FROM questions
            WHERE expected_answer::VARCHAR LIKE '%2004%'
              AND code LIKE 'DRAFT-0012C-AI-ENR-MATHEMATICS-3E-ARITH-DIVISIBILITY%'
            """
        ).fetchone() == (1,)
    finally:
        connection.close()
