"""Tests for CM2 relaxed full publication planning."""

from __future__ import annotations

from pathlib import Path

from services.content.cm2_full_publication import (
    assess_cm2_relaxed_eligibility,
    plan_cm2_subject_chapters,
)
from services.content.d4_review import ai_prevalidation_decision
from services.content.primary_controlled_publication import load_primary_publication_bundles

ROOT = Path(__file__).resolve().parents[1]


def test_assess_cm2_relaxed_accepts_warning_and_teacher() -> None:
    item = {
        "hard_gates_passed": False,
        "automated_checks": {
            "structural_validity": True,
            "skill_alignment": True,
            "executability": True,
            "duplicate_safety": True,
            "answer_correctness": False,
        },
        "review_campaign": "LCAI-0012E-PRIMARY",
        "ai_prevalidation_decision": "TEACHER_REVIEW_REQUIRED",
        "ai_pedagogical_review": {
            "decision": "TEACHER_REVIEW_REQUIRED",
            "authoritative_ai_review": True,
            "confidence": "HIGH",
            "expected_answer_match": "CORRECT",
            "answer_correctness": 92,
            "explanation_correctness": 88,
            "skill_alignment": 90,
            "executability": 95,
        },
    }
    eligible, _ = assess_cm2_relaxed_eligibility(item)
    assert eligible


def test_cm2_french_chapter_plan_selects_unpublished_chapters(tmp_path: Path) -> None:
    database = tmp_path / "cm2-full.duckdb"
    database.write_bytes((ROOT / "data" / "learning_coach_v2.duckdb").read_bytes())
    bundles, _ = load_primary_publication_bundles()
    manifest, report = plan_cm2_subject_chapters(
        bundles,
        subject_code="FRENCH",
        database_path=database,
    )
    assert report["curriculum_chapters"] == 5
    assert report["manifest_count"] == len(report["missing_chapters_before"])
    assert report["manifest_count"] <= report["curriculum_chapters"]
    if report["manifest_count"] == 0:
        assert report["published_chapters_before"] == report["curriculum_chapters"]
        return
    assert manifest[0]["grade"] == "FR-CM2"
    assert manifest[0]["subject"] == "FRENCH"
    assert ai_prevalidation_decision(
        next(
            item
            for bundle in bundles
            for slot in ("practice", "assessment")
            if (item := bundle.get(slot)) is not None
            and int(item["version_id"]) == int(manifest[0]["production_candidate_version_id"])
        )
    ) in {"AI_REJECTED", "AI_PREVALIDATED_HIGH", "AI_PREVALIDATED_WITH_WARNING", "TEACHER_REVIEW_REQUIRED"}
