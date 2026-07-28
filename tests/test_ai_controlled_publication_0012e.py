"""Tests for LCAI-0012E controlled publication preparation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from scripts.run_ai_controlled_publication_0012e import run_publication, run_rollback
from services.content.ai_controlled_publication import assess_publication_eligibility
from services.content.primary_ai_review import CAMPAIGN_ID as PRIMARY_REVIEW_CAMPAIGN
from services.content.primary_controlled_publication import (
    PUBLICATION_CAMPAIGN,
    load_primary_publication_bundles,
    plan_primary_controlled_publication,
    verify_import_state,
    verify_review_completion,
)

ROOT = Path(__file__).parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"


def _eligible_primary_item(**overrides: object) -> dict:
    base = {
        "version_id": 91001,
        "code": "DRAFT-TEST-0012E-PUBLICATION",
        "grade": "FR-CM1",
        "subject": "MATHEMATICS",
        "chapter": "CH-MATHEMATICS-CM1-NUMERATION",
        "skill": "SK-ENR-MATHEMATICS-CM1-NUMERATION-COMPARE",
        "skill_code": "SK-ENR-MATHEMATICS-CM1-NUMERATION-COMPARE",
        "content_type": "practice",
        "target_slot": "practice",
        "candidate_score": 60,
        "recommended_decision": "REVIEW",
        "hard_gates_passed": True,
        "review_campaign": PRIMARY_REVIEW_CAMPAIGN,
        "campaign_id": PRIMARY_REVIEW_CAMPAIGN,
        "publication_campaign": PUBLICATION_CAMPAIGN,
        "authoritative_ai_review": True,
        "ai_prevalidation_decision": "AI_PREVALIDATED_HIGH",
        "ai_prevalidation_confidence": "HIGH",
        "fact_check_required": False,
        "automated_checks": {
            "structural_validity": True,
            "answer_correctness": True,
            "skill_alignment": True,
            "grade_appropriateness": True,
            "executability": True,
            "duplicate_safety": True,
        },
        "grade_assessment": {
            "status": "GRADE_PEDAGOGICALLY_APPROPRIATE",
            "gate_pass": True,
            "curriculum_exact": True,
        },
        "ai_pedagogical_review": {
            "confidence": "HIGH",
            "expected_answer_match": "CORRECT",
            "answer_correctness": 95,
            "explanation_correctness": 85,
            "skill_alignment": 90,
            "executability": 90,
            "authoritative_ai_review": True,
            "ai_review_pipeline_version": "lcai-0012d4-ai-review-v2",
            "review_idempotency_key": "91001:lcai-0012d4-ai-review-v2:openai:gpt-5-mini",
        },
        "question": "Question",
        "expected_answer": "Réponse",
        "explanation": "Explication",
        "choices": [],
        "answer_kind": "open_response",
    }
    base.update(overrides)
    return base


@pytest.fixture
def publication_database(tmp_path: Path) -> Path:
    target = tmp_path / "0012e-publication.duckdb"
    shutil.copy2(ROOT / "data" / "learning_coach_v2.duckdb", target)
    return target


def test_review_completion_from_committed_summary() -> None:
    status = verify_review_completion()
    assert status["complete"] is True
    assert status["expected_candidates"] == 731
    assert status["remaining_candidates"] == 0
    assert status["high_cases"] == 271
    assert status["unresolved_curriculum_excluded"] == 18


def test_primary_ai_high_eligible_with_publication_campaign() -> None:
    assert assess_publication_eligibility(
        _eligible_primary_item(),
        campaign=PUBLICATION_CAMPAIGN,
        review_campaign=PRIMARY_REVIEW_CAMPAIGN,
    ).eligible is True


def test_teacher_cannot_publish_0012e() -> None:
    assert assess_publication_eligibility(
        _eligible_primary_item(
            ai_prevalidation_decision="TEACHER_REVIEW_REQUIRED",
            teacher_review_required=True,
            ai_pedagogical_review={
                "confidence": "HIGH",
                "expected_answer_match": "CORRECT",
                "answer_correctness": 95,
                "explanation_correctness": 85,
                "skill_alignment": 90,
                "executability": 90,
                "authoritative_ai_review": True,
                "decision": "TEACHER_REVIEW_REQUIRED",
            },
        ),
        campaign=PUBLICATION_CAMPAIGN,
        review_campaign=PRIMARY_REVIEW_CAMPAIGN,
    ).eligible is False


def test_warning_cannot_publish_0012e() -> None:
    assert assess_publication_eligibility(
        _eligible_primary_item(
            ai_prevalidation_decision="AI_PREVALIDATED_WITH_WARNING",
            ai_prevalidated_high=False,
            ai_prevalidated_with_warning=True,
            ai_pedagogical_review={
                "confidence": "HIGH",
                "expected_answer_match": "CORRECT",
                "answer_correctness": 95,
                "explanation_correctness": 80,
                "skill_alignment": 90,
                "executability": 90,
                "authoritative_ai_review": True,
                "decision": "AI_PREVALIDATED_WITH_WARNING",
            },
        ),
        campaign=PUBLICATION_CAMPAIGN,
        review_campaign=PRIMARY_REVIEW_CAMPAIGN,
    ).eligible is False


def test_rejected_cannot_publish_0012e() -> None:
    assert assess_publication_eligibility(
        _eligible_primary_item(
            ai_prevalidation_decision="AI_REJECTED",
            ai_prevalidated_high=False,
            ai_pedagogical_review={
                "confidence": "HIGH",
                "expected_answer_match": "CORRECT",
                "answer_correctness": 95,
                "explanation_correctness": 85,
                "skill_alignment": 90,
                "executability": 90,
                "authoritative_ai_review": True,
                "decision": "AI_REJECTED",
            },
        ),
        campaign=PUBLICATION_CAMPAIGN,
        review_campaign=PRIMARY_REVIEW_CAMPAIGN,
    ).eligible is False


def test_wrong_review_campaign_cannot_publish() -> None:
    assert assess_publication_eligibility(
        _eligible_primary_item(review_campaign="LCAI-0012D4-WAVE2", campaign_id="LCAI-0012D4-WAVE2"),
        campaign=PUBLICATION_CAMPAIGN,
        review_campaign=PRIMARY_REVIEW_CAMPAIGN,
    ).eligible is False


def test_dry_run_writes_no_production_records(publication_database: Path) -> None:
    before = publication_database.read_bytes()
    report = run_publication(execute=False, confirmed=False, database_path=publication_database)
    assert report["mode"] == "DRY_RUN"
    assert report["production_db_modified"] is False
    assert publication_database.read_bytes() == before
    manifest = json.loads((QUALITY / "lcai_0012e_ai_controlled_publication_manifest.json").read_text(encoding="utf-8"))
    assert isinstance(manifest, list)


def test_execute_without_confirmation_writes_nothing(publication_database: Path) -> None:
    before = publication_database.read_bytes()
    with pytest.raises(SystemExit):
        run_publication(execute=True, confirmed=False, database_path=publication_database)
    assert publication_database.read_bytes() == before


def test_production_execute_requires_confirmation(publication_database: Path) -> None:
    production = ROOT / "data" / "learning_coach_v2.duckdb"
    with pytest.raises(SystemExit, match="Real execution requires"):
        run_publication(execute=True, confirmed=False, database_path=production)


def test_post_import_dry_run_resolves_eligible_candidates(publication_database: Path) -> None:
    import_status = verify_import_state(publication_database)
    assert import_status["pass"] is True
    assert import_status["review_linkage"]["ai_high_unresolved"] == 0

    bundles, loader_meta = load_primary_publication_bundles()
    assert loader_meta["unmapped_ai_high_isolated_ids"] == []

    preparation = plan_primary_controlled_publication(bundles, database_path=publication_database)
    assert preparation["eligible_candidate_count"] > 0
    assert preparation["unresolved_production_draft_mappings"] == 0
    assert preparation["hash_mismatch_count"] == 0
    assert preparation["eligible_candidate_count"] == preparation["eligible_practice"] + preparation["eligible_assessment"]


def test_post_import_manifest_uses_production_version_ids(publication_database: Path) -> None:
    report = run_publication(execute=False, confirmed=False, database_path=publication_database)
    assert report["import_status"]["pass"] is True
    assert report["eligible_candidate_count"] > 0
    manifest = json.loads((QUALITY / "lcai_0012e_ai_controlled_publication_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == report["eligible_candidate_count"]
    for row in manifest:
        assert int(row["production_candidate_version_id"]) > 0
        assert int(row["isolated_candidate_version_id"]) > 0
        assert row["production_candidate_version_id"] != row["isolated_candidate_version_id"]
        assert row["publication_campaign"] == PUBLICATION_CAMPAIGN
        assert row["source_hash"]
        assert row["production_draft_hash"]


def test_controlled_publication_idempotence_and_rollback_on_isolated_item(publication_database: Path) -> None:
    source_version_id = 107742
    item = _eligible_primary_item(
        version_id=source_version_id,
        skill="SK-ENR-HISTORY-3E-AFTER1945-COLD_WAR",
        publication_campaign=PUBLICATION_CAMPAIGN,
    )
    repository = DuckDBContentQualityRepository(publication_database)
    first = repository.approve_for_ai_controlled_publication(
        item=item,
        review_model="gpt-5-mini",
        review_pipeline="lcai-0012d4-ai-review-v2",
        reason="Test 0012E controlled publication.",
    )
    second = repository.approve_for_ai_controlled_publication(
        item=item,
        review_model="gpt-5-mini",
        review_pipeline="lcai-0012d4-ai-review-v2",
        reason="Test 0012E controlled publication.",
    )
    assert first == second
    revoked = repository.revoke_ai_controlled_publication(
        source_version_id=source_version_id,
        reason="Rollback test.",
        revoked_by="test-operator",
    )
    assert revoked["status"] == "REVOKED"


def test_campaign_rollback_dry_run(publication_database: Path) -> None:
    result = run_rollback(
        execute=False,
        confirmed=False,
        database_path=publication_database,
        reason="Dry-run rollback.",
        revoked_by="test-operator",
    )
    assert result["mode"] == "DRY_RUN"
    assert result["campaign_id"] == PUBLICATION_CAMPAIGN
