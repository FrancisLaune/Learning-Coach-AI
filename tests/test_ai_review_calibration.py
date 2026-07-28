"""Calibration tests for AI pedagogical decision engine."""

from __future__ import annotations

from typing import Any

from services.content.ai_pedagogical_review import ComparisonResult, compare_answers_deterministic, decide_ai_review, score_dimensions
from services.content.ai_review_calibration import decide_ai_review_calibrated, is_ai_prevalidated_decision


def _item(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "version_id": 1,
        "grade": "FR-3E",
        "subject": "SVT",
        "question": "Pourquoi les dégâts diminuent-ils quand on s'éloigne de l'épicentre ?",
        "expected_answer": "Les dégâts diminuent lorsque l'on s'éloigne de l'épicentre.",
        "explanation": "Plus la distance augmente, moins l'énergie sismique reçue est importante.",
        "answer_kind": "open_response",
        "automated_checks": {
            "structural_validity": True,
            "answer_correctness": True,
            "skill_alignment": True,
            "grade_appropriateness": False,
            "executability": True,
        },
        "hard_gates_passed": True,
    }
    base.update(overrides)
    return base


def _audit(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "expected_answer_match": "CORRECT",
        "confidence": "HIGH",
        "answer_correctness": 95,
        "explanation_correctness": 80,
        "question_clarity": 85,
        "grade_appropriateness": 45,
        "skill_alignment": 90,
        "curriculum_alignment": 88,
        "pedagogical_quality": 82,
        "executability": 90,
        "ambiguity": 80,
        "factual_reliability": 85,
        "second_opinion_used": False,
    }
    base.update(overrides)
    return base


def test_semantic_equivalent_open_response_passes() -> None:
    result = compare_answers_deterministic(
        blind_answer="Plus la distance à l'épicentre augmente, moins les dégâts sont importants.",
        expected_answer="Les dégâts diminuent lorsque l'on s'éloigne de l'épicentre.",
        answer_kind="open_response",
    )
    assert result.match in {"CORRECT", "ACCEPTABLE_VARIANT"}


def test_subject_alone_does_not_force_teacher() -> None:
    for subject in ("HISTORY", "GEOGRAPHY", "SVT"):
        decision, _, _ = decide_ai_review_calibrated(_item(subject=subject), audit=_audit())
        assert is_ai_prevalidated_decision(decision), subject


def test_legacy_grade_flag_does_not_force_teacher() -> None:
    decision, _, reason = decide_ai_review_calibrated(_item(), audit=_audit())
    assert is_ai_prevalidated_decision(decision)
    assert "Grade appropriateness requires specialist judgement." not in reason


def test_genuine_ambiguity_routes_teacher() -> None:
    decision, fact_check, _ = decide_ai_review_calibrated(
        _item(subject="HISTORY"),
        audit=_audit(expected_answer_match="AMBIGUOUS", confidence="MEDIUM", second_opinion_used=True),
    )
    assert decision == "TEACHER_REVIEW_REQUIRED"
    assert fact_check is True


def test_factual_uncertainty_routes_teacher_or_fact_check() -> None:
    decision, fact_check, _ = decide_ai_review_calibrated(
        _item(subject="HISTORY"),
        audit=_audit(expected_answer_match="PARTIALLY_CORRECT", confidence="MEDIUM", second_opinion_used=True),
    )
    assert decision == "TEACHER_REVIEW_REQUIRED"
    assert fact_check is True


def test_wrong_answer_routes_reject() -> None:
    decision, _, _ = decide_ai_review_calibrated(
        _item(),
        audit=_audit(expected_answer_match="INCORRECT", confidence="LOW", answer_correctness=15),
    )
    assert decision == "AI_REJECTED"


def test_minor_warning_does_not_force_teacher() -> None:
    item = _item()
    comparison = ComparisonResult("CORRECT", "Independent agreement.")
    scores = score_dimensions(item, comparison=comparison, qcm=None)
    decision, _, _ = decide_ai_review(
        item,
        comparison=comparison,
        scores=scores,
        confidence="HIGH",
        qcm=None,
    )
    assert decision == "AI_PREVALIDATED_WITH_WARNING"


def test_legacy_quality_score_does_not_override_authoritative_verification() -> None:
    item = _item(recommended_decision="KEEP_FOR_REVIEW", candidate_score=53)
    decision, _, _ = decide_ai_review_calibrated(item, audit=_audit())
    assert is_ai_prevalidated_decision(decision)
