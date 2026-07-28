from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from scripts.run_content_approval_d4_wave1 import _coverage_rows
from scripts.run_content_approval_d4_wave1 import run as build_wave1
from services.content.d4_wave1 import (
    REVIEW_CAMPAIGN,
    WAVE_BAND_FINAL,
    WAVE_BAND_TIER2,
    active_candidate,
    append_final_generated_candidates,
    assert_wave1_review_item_ready,
    build_wave1_final_human_queue,
    eligible_for_explicit_pedagogical_confirmation,
    is_authorized_wave1_review_candidate,
    normalize_wave1_review_item,
    order_wave1_queue,
    prepare_ranked_records,
    projected_tier1_totals,
    requires_pedagogical_attention,
)

ROOT = Path(__file__).parents[1]


def test_wave1_builder_reflects_post_review_state() -> None:
    payload = build_wave1()
    summary = payload["summary"]
    assert summary["tier2_selected"] >= 0
    assert payload["projection"]["baseline_tier1"] >= 100


def test_wave1_queue_prefers_non_mathematics_when_scores_equal() -> None:
    queue = [
        {
            "wave_band": "TIER2_COMPLETION",
            "subject": "MATHEMATICS",
            "grade": "FR-4E",
            "candidate_score": 50,
            "skill": "SK-A",
            "coverage_impact": {"completes_tier_1": True},
        },
        {
            "wave_band": "TIER2_COMPLETION",
            "subject": "FRENCH",
            "grade": "FR-4E",
            "candidate_score": 50,
            "skill": "SK-B",
            "coverage_impact": {"completes_tier_1": True},
        },
    ]
    ordered = order_wave1_queue(queue)
    assert ordered[0]["subject"] == "FRENCH"


def test_active_candidate_skips_rejected_and_returns_next() -> None:
    target = {
        "candidates": [
            {"version_id": 1, "code": "A"},
            {"version_id": 2, "code": "B"},
        ]
    }
    review_statuses = {1: "REJECTED"}
    candidate = active_candidate(target, review_statuses)
    assert candidate is not None
    assert candidate["version_id"] == 2


def test_projected_tier1_totals_from_targets() -> None:
    coverage_rows = [
        {
            "grade": "FR-3E",
            "subject": "HISTORY",
            "chapter": "CH-HISTORY-3E-FRANCE",
            "skill": f"SK-TEST-{index}",
            "skill_name": "Test",
            "approved_practice": 1 if index < 50 else 0,
            "approved_assessment": 1 if index < 50 else 0,
        }
        for index in range(100)
    ]
    projection = projected_tier1_totals(coverage_rows, [])
    assert projection["baseline_tier1"] == 50
    assert projection["target_cap"] == 100


def test_wave1_artifacts_exist_after_build() -> None:
    build_wave1()
    quality = ROOT / "resources" / "content" / "quality"
    for name in (
        "lcai_0012d4_wave1_review_queue.json",
        "lcai_0012d4_wave1_targets.json",
        "lcai_0012d4_wave1_summary.json",
        "lcai_0012d4_wave1_g2_complements.json",
    ):
        assert (quality / name).exists()


@pytest.fixture
def approval_persistence_database(tmp_path: Path) -> Path:
    target = tmp_path / "approval-persistence.duckdb"
    shutil.copy2(ROOT / "data" / "learning_coach_v2.duckdb", target)
    return target


def test_final_svt_quality_artifact_is_human_reviewable() -> None:
    payload = json.loads(
        (ROOT / "resources/content/quality/lcai_0012d4_wave1_final_svt_assessment.json").read_text(encoding="utf-8")
    )
    audit = payload["audit"]
    record = payload["queue_record"]
    assert audit["classification"] != "TECHNICALLY_BLOCKED"
    assert audit["usable_for_slot"] is True
    assert record["hard_gates_passed"] is True
    assert record["recommended_decision"] == "KEEP_FOR_REVIEW"


def test_requires_pedagogical_attention_for_low_score() -> None:
    assert requires_pedagogical_attention({"candidate_score": 63, "recommended_decision": "KEEP_FOR_REVIEW"})
    assert not requires_pedagogical_attention({"candidate_score": 88, "recommended_decision": "APPROVE"})


def _normalized_generated_svt_final_item() -> dict[str, Any]:
    record = json.loads(
        (ROOT / "resources/content/quality/lcai_0012d4_wave1_final_svt_assessment.json").read_text(encoding="utf-8")
    )["queue_record"]
    coverage_rows = _coverage_rows()
    svt_row = next(row for row in coverage_rows if row["skill"] == record["skill"])
    return normalize_wave1_review_item(
        record,
        svt_row,
        candidate_source="generated",
        wave_band=WAVE_BAND_FINAL,
        alternate_count=0,
    )


def test_generated_svt_preserves_legacy_selection_flag_but_uses_campaign_metadata() -> None:
    item = _normalized_generated_svt_final_item()
    assert item["d4_wave1_selected"] is False
    assert item["review_campaign"] == REVIEW_CAMPAIGN
    assert is_authorized_wave1_review_candidate(item)
    assert eligible_for_explicit_pedagogical_confirmation(item, explicit_confirmation=True)


def test_historical_wave1_candidate_is_eligible_for_pedagogical_confirmation() -> None:
    coverage_rows = _coverage_rows()
    svt_row = next(row for row in coverage_rows if row["skill"] == "SK-ENR-SVT-4E-EARTH-EARTHQUAKE")
    historical = {
        "version_id": 107770,
        "content_id": 107768,
        "code": "DRAFT-HISTORICAL-WAVE1",
        "grade": svt_row["grade"],
        "subject": "GEOGRAPHY",
        "chapter": "CH-GEO-EXAMPLE",
        "skill": svt_row["skill"],
        "content_type": "assessment",
        "candidate_score": 72,
        "recommended_decision": "KEEP_FOR_REVIEW",
        "quality_result": "REVIEW",
        "hard_gates_passed": True,
        "automated_checks": {"structural_validity": True},
        "quality_reason": [],
        "question": "Question",
        "expected_answer": "Réponse",
        "explanation": "Explication",
        "choices": [],
        "d4_wave1_selected": True,
    }
    item = normalize_wave1_review_item(
        historical,
        svt_row,
        candidate_source="existing",
        wave_band=WAVE_BAND_TIER2,
        alternate_count=1,
    )
    assert eligible_for_explicit_pedagogical_confirmation(item, explicit_confirmation=True)


def test_unauthorized_low_score_draft_cannot_use_pedagogical_confirmation(
    approval_persistence_database: Path,
) -> None:
    record = json.loads(
        (ROOT / "resources/content/quality/lcai_0012d4_wave1_final_svt_assessment.json").read_text(encoding="utf-8")
    )["queue_record"]
    unauthorized = dict(record)
    repository = DuckDBContentQualityRepository(approval_persistence_database)
    with pytest.raises(ValueError, match="authorized review-campaign candidate"):
        repository.approve_for_production(
            item=unauthorized,
            reviewer="Rev",
            approver="App",
            reason="test",
            human_pedagogical_confirmation=True,
        )


def test_campaign_candidate_with_failed_hard_gates_is_not_eligible() -> None:
    item = _normalized_generated_svt_final_item()
    item["hard_gates_passed"] = False
    assert not eligible_for_explicit_pedagogical_confirmation(item, explicit_confirmation=True)


def test_campaign_candidate_reject_is_denied(approval_persistence_database: Path) -> None:
    item = _normalized_generated_svt_final_item()
    item["recommended_decision"] = "REJECT"
    repository = DuckDBContentQualityRepository(approval_persistence_database)
    with pytest.raises(ValueError, match="Rejected candidates cannot be approved"):
        repository.approve_for_production(
            item=item,
            reviewer="Rev",
            approver="App",
            reason="test",
            human_pedagogical_confirmation=True,
        )


def test_reviewer_equals_approver_is_denied(approval_persistence_database: Path) -> None:
    item = _normalized_generated_svt_final_item()
    repository = DuckDBContentQualityRepository(approval_persistence_database)
    with pytest.raises(ValueError, match="Reviewer and approver must be distinct"):
        repository.approve_for_production(
            item=item,
            reviewer="Same Person",
            approver="Same Person",
            reason="test",
            human_pedagogical_confirmation=True,
        )


def test_generated_final_pedagogical_approval_is_allowed_on_isolated_db(
    approval_persistence_database: Path,
) -> None:
    item = _normalized_generated_svt_final_item()
    repository = DuckDBContentQualityRepository(approval_persistence_database)
    content_id = repository.approve_for_production(
        item=item,
        reviewer="Wave1-Reviewer",
        approver="Wave1-Approver",
        reason="Explicit pedagogical confirmation on isolated DB.",
        human_pedagogical_confirmation=True,
    )
    assert content_id > 0


def test_pedagogical_approval_is_idempotent_on_isolated_db(approval_persistence_database: Path) -> None:
    item = _normalized_generated_svt_final_item()
    repository = DuckDBContentQualityRepository(approval_persistence_database)
    first = repository.approve_for_production(
        item=item,
        reviewer="Wave1-Reviewer",
        approver="Wave1-Approver",
        reason="First approval.",
        human_pedagogical_confirmation=True,
    )
    second = repository.approve_for_production(
        item=item,
        reviewer="Wave1-Reviewer",
        approver="Wave1-Approver",
        reason="Second approval.",
        human_pedagogical_confirmation=True,
    )
    assert first == second


def _load_quality_inputs_for_tests() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], set[str], set[str]]:
    from scripts.run_content_approval_acceleration import _review_taxonomy
    from scripts.run_content_quality_audit import _candidate_sources

    results = json.loads(
        (ROOT / "resources/content/quality/lcai_0012d_quality_results.json").read_text(encoding="utf-8")
    )
    duplicates = json.loads(
        (ROOT / "resources/content/quality/lcai_0012d_duplicate_audit.json").read_text(encoding="utf-8")
    )
    sources = _candidate_sources()
    near_codes = {
        str(item[key])
        for item in duplicates["near_groups"]
        for key in ("left", "right")
        if item["decision"] == "REVIEW"
    }
    _, resolved = _review_taxonomy(results, sources, near_codes)
    return results, sources, near_codes, resolved


def test_normalize_generated_svt_candidate_computes_coverage_impact() -> None:
    record = json.loads(
        (ROOT / "resources/content/quality/lcai_0012d4_wave1_final_svt_assessment.json").read_text(encoding="utf-8")
    )["queue_record"]
    assert "coverage_impact" not in record
    coverage_rows = _coverage_rows()
    svt_row = next(row for row in coverage_rows if row["skill"] == record["skill"])
    normalized = normalize_wave1_review_item(
        record,
        svt_row,
        candidate_source="generated",
        wave_band=WAVE_BAND_FINAL,
        alternate_count=0,
    )
    impact = normalized["coverage_impact"]
    assert impact["current"]["practice_approved"] is True
    assert impact["current"]["assessment_approved"] is True
    assert impact["current"]["tier"] == 1
    assert impact["potential"]["practice_approved"] is True
    assert impact["potential"]["assessment_approved"] is True
    assert impact["potential"]["tier"] == 1
    assert impact["completes_tier_1"] is False
    assert normalized["candidate_source"] == "generated"
    assert normalized["target_slot"] == "assessment"
    assert_wave1_review_item_ready(normalized)


def test_existing_wave1_final_candidate_normalizes_for_display() -> None:
    coverage_rows = _coverage_rows()
    tier3_row = next(
        row
        for row in coverage_rows
        if int(row["approved_practice"]) == 0 and int(row["approved_assessment"]) == 0
    )
    existing = {
        "version_id": 107770,
        "content_id": 107768,
        "code": "DRAFT-GEO-EXAMPLE",
        "grade": tier3_row["grade"],
        "subject": "GEOGRAPHY",
        "chapter": "CH-GEO-EXAMPLE",
        "skill": tier3_row["skill"],
        "skill_name": tier3_row.get("skill_name", tier3_row["skill"]),
        "content_type": "assessment",
        "candidate_score": 72,
        "recommended_decision": "KEEP_FOR_REVIEW",
        "quality_result": "REVIEW",
        "hard_gates_passed": True,
        "automated_checks": {"structural_validity": True},
        "quality_reason": ["Independent pedagogical review is still required."],
        "question": "Question",
        "expected_answer": "Réponse",
        "explanation": "Explication",
        "choices": [],
    }
    normalized = normalize_wave1_review_item(
        existing,
        tier3_row,
        candidate_source="existing",
        wave_band=WAVE_BAND_FINAL,
        alternate_count=2,
    )
    assert normalized["candidate_source"] == "existing"
    assert normalized["coverage_impact"]["completes_tier_1"] is False
    assert normalized["coverage_impact"]["improves_tier_2"] is True
    assert_wave1_review_item_ready(normalized)


def test_append_final_generated_candidate_normalizes_for_display() -> None:
    results, sources, near_codes, resolved = _load_quality_inputs_for_tests()
    coverage_rows = _coverage_rows()
    coverage = {str(row["skill"]): row for row in coverage_rows}
    ranked = prepare_ranked_records(results, sources, coverage, near_codes=near_codes, resolved=resolved)
    queue, summary = build_wave1_final_human_queue(coverage_rows, ranked, review_statuses={})
    queue = append_final_generated_candidates(
        queue,
        artifact_path=ROOT / "resources/content/quality/lcai_0012d4_wave1_final_svt_assessment.json",
        review_statuses={},
        baseline_tier1=summary["baseline_tier1"],
        coverage_by_skill=coverage,
    )
    generated = next(item for item in queue if item["candidate_source"] == "generated")
    assert generated["version_id"] == 114809
    assert_wave1_review_item_ready(generated)
