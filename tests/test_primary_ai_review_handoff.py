from __future__ import annotations

from pathlib import Path

import pytest

from services.content.primary_ai_review import (
    build_primary_skill_bundles,
    handoff_to_review_item,
    load_handoff_candidates,
    validate_handoff_population,
)
from domain.content.pedagogical_review import build_review_idempotency_key, AI_REVIEW_PIPELINE_VERSION


ROOT = Path(__file__).parents[1]


def test_handoff_population_is_731_unique() -> None:
    payload = validate_handoff_population(ROOT / "resources/content/integration/lcai_0012e_ai_review_handoff.jsonl")
    assert payload["valid"] is True
    assert payload["handoff_rows"] == 731
    assert payload["deduplicated_candidates"] == 731


def test_handoff_to_review_item_maps_gates() -> None:
    row = {
        "candidate_version_id": 1,
        "campaign_id": "LCAI-0012E-PRIMARY",
        "grade": "FR-CM1",
        "subject": "MATHEMATICS",
        "chapter": "CH-MATHEMATICS-CM1-NUMBERS",
        "skill_code": "SK-TEST",
        "content_type": "practice",
        "question": "2+2?",
        "choices": [],
        "expected_answer": "4",
        "explanation": "Basic addition.",
        "answer_kind": "numeric",
        "quality_metadata": {
            "decision": "REVIEW",
            "confidence": 0.6,
            "hard_gates": {
                "structural_validity": True,
                "answer_correctness": True,
                "skill_alignment": True,
                "grade_appropriateness": True,
                "executability": True,
                "duplicate_safety": True,
            },
        },
    }
    item = handoff_to_review_item(row)
    assert item["version_id"] == 1
    assert item["hard_gates_passed"] is True
    assert item["target_slot"] == "practice"


def test_skill_bundles_one_per_slot() -> None:
    candidates = load_handoff_candidates(ROOT / "resources/content/integration/lcai_0012e_ai_review_handoff.jsonl")
    bundles = build_primary_skill_bundles(candidates)
    assert len(bundles) > 0
    for bundle in bundles:
        assert bundle.get("practice") is not None or bundle.get("assessment") is not None


def test_idempotency_key_stable() -> None:
    key = build_review_idempotency_key(
        candidate_version_id=42,
        pipeline_version=AI_REVIEW_PIPELINE_VERSION,
        assessor_type="openai",
        model_identifier="gpt-5-mini",
    )
    assert key.startswith("42:lcai-0012d4-ai-review-v2:openai:")
