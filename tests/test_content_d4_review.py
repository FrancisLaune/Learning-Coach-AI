from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.d4_review import (
    can_dual_approve,
    can_individual_approve,
    confidence_band,
    eligible_for_explicit_pedagogical_confirmation,
    is_authorized_wave2_review_candidate,
    is_technically_blocked,
)
from services.content.d4_wave2 import (
    REVIEW_CAMPAIGN,
    WAVE_BAND_TIER3,
    build_skill_review_bundles,
    filter_skill_bundles,
    load_lot_review_queues,
    normalize_wave2_review_item,
    prioritize_skill_bundles,
)

ROOT = Path(__file__).parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"


def _wave2_item(**overrides: object) -> dict:
    base = {
        "version_id": 2001,
        "grade": "FR-3E",
        "subject": "HISTORY",
        "chapter": "CH-HISTORY-3E-AFTER1945",
        "skill": "SK-TEST",
        "skill_name": "SK-TEST",
        "content_type": "practice",
        "target_slot": "practice",
        "candidate_score": 53,
        "recommended_decision": "KEEP_FOR_REVIEW",
        "quality_result": "REVIEW",
        "hard_gates_passed": True,
        "automated_checks": {
            "structural_validity": True,
            "answer_correctness": True,
            "skill_alignment": True,
            "executability": True,
            "duplicate_safety": True,
        },
        "quality_reason": [],
        "question": "Question",
        "expected_answer": "Réponse",
        "explanation": "Explication",
        "choices": [],
        "answer_kind": "open_response",
        "review_campaign": REVIEW_CAMPAIGN,
        "review_queue_status": "ACTIVE",
        "wave_band": WAVE_BAND_TIER3,
        "candidate_source": "existing",
        "coverage_impact": {
            "completes_tier_1": True,
            "current": {"tier": 3, "practice_approved": False, "assessment_approved": False},
            "potential": {"tier": 1, "practice_approved": True, "assessment_approved": True},
        },
    }
    base.update(overrides)
    return base


def test_wave2_campaign_authorization() -> None:
    item = _wave2_item()
    assert is_authorized_wave2_review_candidate(item)
    assert eligible_for_explicit_pedagogical_confirmation(item, explicit_confirmation=True)


def test_unauthorized_wave2_candidate_rejected() -> None:
    item = _wave2_item(review_campaign="OTHER")
    assert not is_authorized_wave2_review_candidate(item)
    assert not eligible_for_explicit_pedagogical_confirmation(item, explicit_confirmation=True)


def test_reviewer_equals_approver_blocked() -> None:
    item = _wave2_item(recommended_decision="APPROVE", candidate_score=90)
    assert not can_individual_approve(
        item,
        reviewer="Same",
        approver="Same",
        explicit_pedagogical_confirmation=False,
    )


def test_low_score_requires_explicit_confirmation() -> None:
    item = _wave2_item()
    assert not can_individual_approve(
        item,
        reviewer="Rev",
        approver="App",
        explicit_pedagogical_confirmation=False,
    )
    assert can_individual_approve(
        item,
        reviewer="Rev",
        approver="App",
        explicit_pedagogical_confirmation=True,
    )


def test_reject_and_hard_gate_failures_block_approval() -> None:
    reject = _wave2_item(recommended_decision="REJECT")
    blocked = _wave2_item(
        answer_kind="single_choice",
        choices=[],
        recommended_decision="KEEP_FOR_REVIEW",
    )
    assert not can_individual_approve(
        reject,
        reviewer="Rev",
        approver="App",
        explicit_pedagogical_confirmation=True,
    )
    assert is_technically_blocked(blocked)
    assert not can_individual_approve(
        blocked,
        reviewer="Rev",
        approver="App",
        explicit_pedagogical_confirmation=True,
    )


def test_dual_approval_requires_both_slots_eligible() -> None:
    practice = _wave2_item(version_id=2001, target_slot="practice", content_type="practice")
    assessment = _wave2_item(
        version_id=2002,
        target_slot="assessment",
        content_type="assessment",
        recommended_decision="APPROVE",
        candidate_score=90,
    )
    assert can_dual_approve(
        practice,
        assessment,
        reviewer="Rev",
        approver="App",
        practice_pedagogical_confirmation=True,
        assessment_pedagogical_confirmation=False,
        practice_status=None,
        assessment_status=None,
    )
    assert confidence_band(practice) == "pedagogical"
    assert confidence_band(assessment) == "high"


def test_combined_wave2_bundles_group_practice_and_assessment() -> None:
    queue = load_lot_review_queues(QUALITY, lots=(1, 2))
    assert queue
    bundles = build_skill_review_bundles(queue, review_statuses={})
    assert bundles
    sample = bundles[0]
    assert sample.get("practice") is not None or sample.get("assessment") is not None


def test_filter_pending_excludes_completed_skill() -> None:
    practice = _wave2_item(version_id=3001, target_slot="practice", content_type="practice")
    assessment = _wave2_item(version_id=3002, target_slot="assessment", content_type="assessment")
    bundle = {
        "skill": "SK-TEST",
        "skill_name": "SK-TEST",
        "grade": "FR-3E",
        "subject": "HISTORY",
        "chapter": "CH",
        "lot_numbers": [1],
        "practice": practice,
        "assessment": assessment,
    }
    pending = filter_skill_bundles([bundle], status="pending", review_statuses={})
    assert pending
    completed = filter_skill_bundles(
        [bundle],
        status="pending",
        review_statuses={3001: "APPROVED", 3002: "APPROVED"},
    )
    assert not completed


@pytest.fixture
def approval_database(tmp_path: Path) -> Path:
    target = tmp_path / "wave2-approval.duckdb"
    shutil.copy2(ROOT / "data" / "learning_coach_v2.duckdb", target)
    return target


def test_wave2_approval_persistence_is_idempotent_on_isolated_db(approval_database: Path) -> None:
    generated = json.loads(
        (QUALITY / "lcai_0012d4_wave2_lot1_generated_candidates.json").read_text(encoding="utf-8")
    )
    record = next(item["queue_record"] for item in generated if item["queue_record"].get("review_campaign"))
    repository = DuckDBContentQualityRepository(approval_database)
    first = repository.approve_for_production(
        item=record,
        reviewer="Wave2-Reviewer",
        approver="Wave2-Approver",
        reason="Test idempotence.",
        human_pedagogical_confirmation=True,
    )
    second = repository.approve_for_production(
        item=record,
        reviewer="Wave2-Reviewer",
        approver="Wave2-Approver",
        reason="Test idempotence.",
        human_pedagogical_confirmation=True,
    )
    assert first == second


def test_normalize_wave2_review_item_sets_campaign_metadata() -> None:
    coverage_row = {
        "skill": "SK-TEST",
        "grade": "FR-3E",
        "subject": "HISTORY",
        "chapter": "CH",
        "approved_practice": 0,
        "approved_assessment": 0,
    }
    normalized = normalize_wave2_review_item(
        _wave2_item(),
        coverage_row,
        candidate_source="generated",
        lot_number=1,
    )
    assert normalized["review_campaign"] == REVIEW_CAMPAIGN
    assert normalized["target_slot"] == "practice"


def test_prioritize_skill_bundles_orders_high_confidence_first() -> None:
    coverage_rows = [
        {
            "subject": "HISTORY",
            "approved_practice": 0,
            "approved_assessment": 0,
            "grade": "FR-3E",
            "skill": "A",
        }
    ]
    high = {
        "skill": "SK-HIGH",
        "subject": "HISTORY",
        "grade": "FR-3E",
        "practice": _wave2_item(recommended_decision="APPROVE", candidate_score=90),
        "assessment": _wave2_item(
            version_id=4002,
            recommended_decision="APPROVE",
            candidate_score=90,
            target_slot="assessment",
            content_type="assessment",
        ),
    }
    low = {
        "skill": "SK-LOW",
        "subject": "HISTORY",
        "grade": "FR-3E",
        "practice": _wave2_item(version_id=5001),
        "assessment": _wave2_item(version_id=5002, target_slot="assessment", content_type="assessment"),
    }
    ordered = prioritize_skill_bundles([low, high], coverage_rows)
    assert ordered[0]["skill"] == "SK-HIGH"
