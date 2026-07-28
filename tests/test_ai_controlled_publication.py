"""Tests for controlled AI publication eligibility, execution safety, and rollback."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from scripts.run_ai_controlled_publication import run_publication, run_rollback
from services.content.ai_controlled_publication import assess_publication_eligibility, classify_warning_severity
from services.content.wave2_campaign_repair import repair_wave2_campaign_metadata

ROOT = Path(__file__).parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"


def _eligible_item(**overrides: object) -> dict:
    base = {
        "version_id": 91001,
        "code": "DRAFT-TEST-AI-PUBLICATION",
        "grade": "FR-3E",
        "subject": "GEOGRAPHY",
        "chapter": "CH-GEOGRAPHY-3E-EU",
        "skill": "SK-ENR-GEOGRAPHY-3E-EU-WORLD",
        "skill_code": "SK-ENR-GEOGRAPHY-3E-EU-WORLD",
        "content_type": "practice",
        "target_slot": "practice",
        "candidate_score": 53,
        "recommended_decision": "KEEP_FOR_REVIEW",
        "hard_gates_passed": True,
        "review_campaign": "LCAI-0012D4-WAVE2",
        "review_queue_status": "ACTIVE",
        "wave_band": "TIER3_CORRECTIVE",
        "candidate_source": "existing",
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
            "review_pipeline": "lcai-0012d4-ai-review-v2",
        },
        "question": "Question",
        "expected_answer": "Réponse",
        "explanation": "Explication",
        "choices": [],
        "answer_kind": "open_response",
    }
    base.update(overrides)
    return base


def test_ai_high_eligible() -> None:
    assert assess_publication_eligibility(_eligible_item()).eligible is True


def test_teacher_never_eligible() -> None:
    assert assess_publication_eligibility(
        _eligible_item(
            ai_prevalidation_decision="TEACHER_REVIEW_REQUIRED",
            ai_pedagogical_review={
                "confidence": "MEDIUM",
                "expected_answer_match": "PARTIALLY_CORRECT",
                "answer_correctness": 65,
                "explanation_correctness": 80,
                "skill_alignment": 90,
                "executability": 90,
                "authoritative_ai_review": True,
            },
        )
    ).eligible is False


def test_reject_never_eligible() -> None:
    assert assess_publication_eligibility(
        _eligible_item(
            ai_prevalidation_decision="AI_REJECTED",
            ai_pedagogical_review={
                "confidence": "LOW",
                "expected_answer_match": "INCORRECT",
                "answer_correctness": 15,
                "explanation_correctness": 80,
                "skill_alignment": 90,
                "executability": 90,
                "authoritative_ai_review": True,
            },
        )
    ).eligible is False


def test_fact_check_never_eligible() -> None:
    assert assess_publication_eligibility(
        _eligible_item(
            fact_check_required=True,
            ai_pedagogical_review={
                "confidence": "HIGH",
                "expected_answer_match": "CORRECT",
                "answer_correctness": 95,
                "explanation_correctness": 85,
                "skill_alignment": 90,
                "executability": 90,
                "fact_check_required": True,
                "authoritative_ai_review": True,
            },
        )
    ).eligible is False


def test_wrong_campaign_not_eligible() -> None:
    assert assess_publication_eligibility(
        _eligible_item(review_campaign="OTHER"),
        campaign="LCAI-0012D4-WAVE2",
    ).eligible is False


def test_warning_severity_blocks_default_publication() -> None:
    item = _eligible_item(
        ai_prevalidation_decision="AI_PREVALIDATED_WITH_WARNING",
        ai_pedagogical_review={
            "confidence": "HIGH",
            "expected_answer_match": "CORRECT",
            "answer_correctness": 95,
            "explanation_correctness": 80,
            "skill_alignment": 90,
            "executability": 90,
            "authoritative_ai_review": True,
            "concise_reason": "Minor wording warning only.",
        },
    )
    assert classify_warning_severity(item) == "PEDAGOGICAL_WARNING"
    assert assess_publication_eligibility(item).eligible is False


def test_blocked_high_candidate_campaign_repair() -> None:
    audit = {
        "campaign_id": "LCAI-0012D4-WAVE2",
        "authoritative_ai_review": True,
        "review_idempotency_key": "114842:lcai-0012d4-ai-review-v2:openai:gpt-5-mini",
        "skill_code": "SK-ENR-HISTORY-3E-AFTER1945-COLD_WAR",
    }
    item = {
        "version_id": 114842,
        "grade": "FR-3E",
        "subject": "HISTORY",
        "skill": "SK-ENR-HISTORY-3E-AFTER1945-COLD_WAR",
        "content_type": "assessment",
    }
    repaired = repair_wave2_campaign_metadata(item, audit, quality_dir=QUALITY)
    assert repaired.get("review_campaign") == "LCAI-0012D4-WAVE2"
    assert repaired.get("campaign_metadata_repair") is not None


def test_dry_run_performs_zero_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    combined = json.loads((QUALITY / "lcai_0012d4_wave2_combined_review.json").read_text(encoding="utf-8"))
    target = tmp_path / "combined.json"
    target.write_text(json.dumps(combined), encoding="utf-8")
    report_path = tmp_path / "dry_run.json"
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setattr("scripts.run_ai_controlled_publication.COMBINED_PATH", target)
    monkeypatch.setattr("scripts.run_ai_controlled_publication.DRY_RUN_REPORT_PATH", report_path)
    monkeypatch.setattr("scripts.run_ai_controlled_publication.EXECUTION_MANIFEST_PATH", manifest_path)
    report = run_publication(
        campaign="LCAI-0012D4-WAVE2",
        required_decision="AI_PREVALIDATED_HIGH",
        execute=False,
        confirmed=False,
        database_path=tmp_path / "unused.duckdb",
    )
    assert report["production_db_modified"] is False
    assert report_path.exists()
    assert manifest_path.exists()


@pytest.fixture
def publication_database(tmp_path: Path) -> Path:
    target = tmp_path / "ai-publication.duckdb"
    shutil.copy2(ROOT / "data" / "learning_coach_v2.duckdb", target)
    return target


def test_execute_without_confirmation_writes_nothing(publication_database: Path) -> None:
    before = publication_database.read_bytes()
    with pytest.raises(SystemExit):
        run_publication(
            campaign="LCAI-0012D4-WAVE2",
            required_decision="AI_PREVALIDATED_HIGH",
            execute=True,
            confirmed=False,
            database_path=publication_database,
        )
    assert publication_database.read_bytes() == before


def test_controlled_publication_idempotence_and_revocation(publication_database: Path) -> None:
    generated = json.loads(
        (QUALITY / "lcai_0012d4_wave2_lot1_generated_candidates.json").read_text(encoding="utf-8")
    )
    record = next(item["queue_record"] for item in generated if item["queue_record"].get("review_campaign") is None)
    enriched = _eligible_item(
        version_id=record["version_id"],
        code=record["code"],
        question=record["question"],
        expected_answer=record["expected_answer"],
        explanation=record["explanation"],
        choices=record.get("choices", []),
        answer_kind=record.get("answer_kind", "open_response"),
        content_type=record["content_type"],
        target_slot=record.get("target_slot", record["content_type"]),
        review_campaign="LCAI-0012D4-WAVE2",
    )
    repository = DuckDBContentQualityRepository(publication_database)
    first = repository.approve_for_ai_controlled_publication(
        item=enriched,
        review_model="gpt-5-mini",
        review_pipeline="lcai-0012d4-ai-review-v2",
        reason="Test controlled publication.",
    )
    second = repository.approve_for_ai_controlled_publication(
        item=enriched,
        review_model="gpt-5-mini",
        review_pipeline="lcai-0012d4-ai-review-v2",
        reason="Test controlled publication.",
    )
    assert first == second
    revoked = repository.revoke_ai_controlled_publication(
        source_version_id=int(record["version_id"]),
        reason="Rollback test.",
        revoked_by="test-operator",
    )
    assert revoked["status"] == "REVOKED"
    decision = repository.read_human_decision(int(record["version_id"]))
    assert decision is not None
    assert decision.get("production_enabled") is False


def test_campaign_rollback_dry_run(publication_database: Path) -> None:
    result = run_rollback(
        campaign="LCAI-0012D4-WAVE2",
        execute=False,
        confirmed=False,
        database_path=publication_database,
        reason="Dry-run rollback.",
        revoked_by="test-operator",
    )
    assert result["mode"] == "DRY_RUN"
