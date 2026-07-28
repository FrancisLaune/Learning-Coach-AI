"""Regression tests for AI pedagogical pre-validation pipeline."""

from __future__ import annotations

import json
from typing import Any

from domain.content.pedagogical_review import BlindReviewInput, BlindReviewOutput
from services.content.ai_pedagogical_review import (
    CandidateReviewContext,
    ComparisonResult,
    attach_ai_review,
    blind_payload_for_audit,
    build_blind_input,
    compare_answers_deterministic,
    decide_ai_review,
    deduplicate_candidates,
    derive_confidence,
    run_ai_pedagogical_review,
    score_dimensions,
    validate_qcm_integrity,
)
from services.content.ai_review_calibration import is_ai_prevalidated_decision
from services.content.d4_review import can_individual_approve, is_ai_prevalidated, is_ai_rejected
from services.content.d4_wave2 import filter_skill_bundles, load_wave2_assigned_skills, select_wave2_lot_skills


def _assert_prevalidated(decision: str) -> None:
    assert is_ai_prevalidated_decision(decision), decision


def _wave2_item(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "version_id": 9001,
        "grade": "FR-4E",
        "subject": "MATHEMATICS",
        "chapter": "CH-MATH-4E-NUMBERS",
        "skill": "SK-MATH-TEST",
        "skill_code": "SK-MATH-TEST",
        "content_type": "practice",
        "target_slot": "practice",
        "question": "Calcule 12 + 8.",
        "choices": [],
        "expected_answer": "20",
        "answer_kind": "numeric",
        "explanation": "12 + 8 = 20 car on additionne les unités.",
        "automated_checks": {
            "structural_validity": True,
            "answer_correctness": True,
            "skill_alignment": True,
            "grade_appropriateness": True,
            "executability": True,
        },
        "hard_gates_passed": True,
        "recommended_decision": "KEEP_FOR_REVIEW",
        "candidate_score": 53,
        "review_campaign": "LCAI-0012D4-WAVE2",
        "review_queue_status": "ACTIVE",
        "wave_band": "TIER3_CORRECTIVE",
        "candidate_source": "existing",
        "deterministic_verification": "20",
        "alternate_count": 1,
    }
    base.update(overrides)
    return base


class ScriptedBlindAssessor:
    def __init__(self, answer: str, *, confidence: str = "HIGH") -> None:
        self.answer = answer
        self.confidence = confidence
        self.seen_payloads: list[BlindReviewInput] = []

    def solve_blind(self, payload: BlindReviewInput) -> BlindReviewOutput:
        self.seen_payloads.append(payload)
        return BlindReviewOutput(
            independent_answer=self.answer,
            concise_verification_reason="Scripted blind answer.",
            confidence=self.confidence,  # type: ignore[arg-type]
        )


class ScriptedComparisonAssessor:
    def compare(self, **kwargs: object) -> ComparisonResult:
        blind = kwargs["blind"]
        expected = kwargs["expected_answer"]
        if str(blind.independent_answer) == str(expected):
            return ComparisonResult("CORRECT", "Scripted agreement.")
        return ComparisonResult("INCORRECT", "Scripted disagreement.")


def test_blind_pass_cannot_access_expected_answer() -> None:
    item = _wave2_item(expected_answer="20", question="Calcule 12 + 8.", deterministic_verification=None)
    blind = build_blind_input(item)
    payload = blind_payload_for_audit(blind)
    assert "expected_answer" not in payload
    assert "explanation" not in payload
    assert "candidate_score" not in payload
    assessor = ScriptedBlindAssessor("20")
    run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=assessor,
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    assert assessor.seen_payloads
    assert all("expected" not in str(payload.question).lower() for payload in assessor.seen_payloads)


def test_correct_mathematics_question_prevalidated() -> None:
    item = _wave2_item()
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=ScriptedBlindAssessor("20"),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    _assert_prevalidated(review.decision)
    assert review.confidence == "HIGH"


def test_incorrect_expected_math_answer_rejected() -> None:
    item = _wave2_item(expected_answer="21", deterministic_verification="20")
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=ScriptedBlindAssessor("20"),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    assert review.decision == "AI_REJECTED"


def test_valid_qcm_prevalidated() -> None:
    item = _wave2_item(
        answer_kind="single_choice",
        choices=["20", "19", "21"],
        expected_answer="20",
        question="Quelle est la somme de 12 et 8 ?",
        deterministic_verification=None,
    )
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=ScriptedBlindAssessor("20"),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    assert validate_qcm_integrity(item).passes_mandatory
    _assert_prevalidated(review.decision)


def test_qcm_with_two_correct_answers_rejected() -> None:
    item = _wave2_item(
        answer_kind="single_choice",
        choices=["20", "20 bis", "21"],
        expected_answer="20",
        deterministic_verification=None,
    )
    qcm = validate_qcm_integrity(item)
    assert qcm.passes_mandatory
    item_bad = _wave2_item(
        answer_kind="single_choice",
        choices=["20", "20", "21"],
        expected_answer="20",
        deterministic_verification=None,
    )
    assert not validate_qcm_integrity(item_bad).passes_mandatory


def test_qcm_without_correct_answer_rejected() -> None:
    item = _wave2_item(
        answer_kind="single_choice",
        choices=["19", "18", "17"],
        expected_answer="20",
        deterministic_verification=None,
    )
    assert not validate_qcm_integrity(item).passes_mandatory


def test_ambiguous_open_response_teacher_required() -> None:
    item = _wave2_item(
        subject="HISTORY",
        answer_kind="open_response",
        expected_answer="La guerre froide résulte de rivalités idéologiques et de sécurité.",
        deterministic_verification=None,
    )
    comparison = ComparisonResult("AMBIGUOUS", "Several defensible answers.")
    scores = score_dimensions(item, comparison=comparison, qcm=None)
    decision, fact_check, _ = decide_ai_review(
        item,
        comparison=comparison,
        scores=scores,
        confidence="MEDIUM",
        qcm=None,
    )
    assert decision == "TEACHER_REVIEW_REQUIRED"
    assert fact_check is True


def test_legacy_unverified_grade_does_not_force_teacher() -> None:
    item = _wave2_item(
        automated_checks={
            "structural_validity": True,
            "answer_correctness": True,
            "skill_alignment": True,
            "grade_appropriateness": False,
            "executability": True,
        }
    )
    comparison = ComparisonResult("CORRECT", "Matches.")
    scores = score_dimensions(item, comparison=comparison, qcm=None)
    decision, _, _ = decide_ai_review(
        item,
        comparison=comparison,
        scores=scores,
        confidence="HIGH",
        qcm=None,
    )
    assert decision in {"AI_PREVALIDATED_HIGH", "AI_PREVALIDATED_WITH_WARNING"}


def test_wrong_skill_alignment_rejected() -> None:
    item = _wave2_item(
        automated_checks={
            "structural_validity": True,
            "answer_correctness": True,
            "skill_alignment": False,
            "grade_appropriateness": True,
            "executability": True,
        }
    )
    comparison = ComparisonResult("CORRECT", "Matches.")
    scores = score_dimensions(item, comparison=comparison, qcm=None)
    decision, _, _ = decide_ai_review(
        item,
        comparison=comparison,
        scores=scores,
        confidence="HIGH",
        qcm=None,
    )
    assert decision == "AI_REJECTED"


def test_correct_scientific_statement() -> None:
    item = _wave2_item(
        subject="SVT",
        answer_kind="open_response",
        expected_answer="La photosynthèse produit de l'oxygène.",
        deterministic_verification=None,
    )
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=ScriptedBlindAssessor("La photosynthèse produit de l'oxygène."),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    _assert_prevalidated(review.decision)


def test_false_scientific_statement_rejected() -> None:
    item = _wave2_item(
        subject="SVT",
        answer_kind="open_response",
        expected_answer="Les plantes respirent uniquement le dioxyde de carbone.",
        deterministic_verification=None,
    )
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=ScriptedBlindAssessor("Les plantes produisent surtout de l'oxygène."),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    assert review.decision == "AI_REJECTED"


def test_correct_historical_fact() -> None:
    item = _wave2_item(
        subject="HISTORY",
        answer_kind="open_response",
        expected_answer="La Seconde Guerre mondiale se termine en 1945.",
        deterministic_verification=None,
    )
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=ScriptedBlindAssessor("La Seconde Guerre mondiale se termine en 1945."),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    _assert_prevalidated(review.decision)


def test_ambiguous_historical_interpretation_teacher() -> None:
    item = _wave2_item(
        subject="HISTORY",
        answer_kind="open_response",
        expected_answer="La décolonisation peut être expliquée par plusieurs facteurs.",
        deterministic_verification=None,
    )
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=ScriptedBlindAssessor("La décolonisation est surtout économique."),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    assert review.decision in {"TEACHER_REVIEW_REQUIRED", "AI_REJECTED"}


def test_valid_french_grammar_exercise() -> None:
    item = _wave2_item(
        subject="FRENCH",
        answer_kind="open_response",
        expected_answer="Ils mangent.",
        deterministic_verification=None,
    )
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=ScriptedBlindAssessor("Ils mangent."),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    _assert_prevalidated(review.decision)


def test_valid_english_target_language_exercise() -> None:
    item = _wave2_item(
        subject="ENGLISH",
        answer_kind="open_response",
        expected_answer="She goes to school every day.",
        deterministic_verification=None,
    )
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=ScriptedBlindAssessor("She goes to school every day."),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    _assert_prevalidated(review.decision)


def test_semantically_acceptable_open_answers() -> None:
    result = compare_answers_deterministic(
        blind_answer="La capitale de la France est Paris.",
        expected_answer="Paris est la capitale de la France.",
        answer_kind="open_response",
    )
    assert result.match in {"CORRECT", "ACCEPTABLE_VARIANT"}


def test_ai_disagreement_requires_teacher() -> None:
    item = _wave2_item(deterministic_verification=None, answer_kind="open_response")
    primary = ScriptedBlindAssessor("Réponse A", confidence="MEDIUM")
    secondary = ScriptedBlindAssessor("Réponse B", confidence="MEDIUM")

    class DisagreeComparison:
        def compare(self, **kwargs: object) -> ComparisonResult:
            return ComparisonResult("AMBIGUOUS", "Borderline.")

    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=primary,
        comparison_assessor=DisagreeComparison(),
        reviewer_model="test-model",
        second_opinion_assessor=secondary,
    )
    assert review.decision == "TEACHER_REVIEW_REQUIRED"
    assert review.second_opinion_used is True


def test_ai_rejected_alternate_selection_not_approvable() -> None:
    rejected_item = _wave2_item(deterministic_verification=None, expected_answer="21")
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=rejected_item),
        blind_assessor=ScriptedBlindAssessor("20"),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
        authoritative_ai_review=True,
    )
    item = attach_ai_review(rejected_item, review)
    assert is_ai_rejected(item)
    assert not can_individual_approve(
        item,
        reviewer="rev",
        approver="app",
        explicit_pedagogical_confirmation=True,
    )


def test_no_alternate_replacement_required_flag() -> None:
    item = _wave2_item(alternate_count=0, expected_answer="21", deterministic_verification=None)
    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=item),
        blind_assessor=ScriptedBlindAssessor("20"),
        comparison_assessor=ScriptedComparisonAssessor(),
        reviewer_model="test-model",
    )
    assert review.decision == "AI_REJECTED"
    assert int(item["alternate_count"]) == 0


def test_prevalidated_pair_display_filter() -> None:
    practice = attach_ai_review(
        _wave2_item(target_slot="practice", version_id=1),
        run_ai_pedagogical_review(
            CandidateReviewContext(item=_wave2_item(target_slot="practice", version_id=1)),
            blind_assessor=ScriptedBlindAssessor("20"),
            comparison_assessor=ScriptedComparisonAssessor(),
            reviewer_model="test-model",
        ),
    )
    assessment = attach_ai_review(
        _wave2_item(target_slot="assessment", version_id=2),
        run_ai_pedagogical_review(
            CandidateReviewContext(item=_wave2_item(target_slot="assessment", version_id=2)),
            blind_assessor=ScriptedBlindAssessor("20"),
            comparison_assessor=ScriptedComparisonAssessor(),
            reviewer_model="test-model",
        ),
    )
    bundle = {
        "skill": "SK-MATH-TEST",
        "grade": "FR-4E",
        "subject": "MATHEMATICS",
        "chapter": "CH",
        "lot_numbers": [1],
        "practice": practice,
        "assessment": assessment,
    }
    filtered = filter_skill_bundles([bundle], ai_prevalidation="File prévalidée rapide")
    assert len(filtered) == 1
    assert is_ai_prevalidated(practice)
    assert is_ai_prevalidated(assessment)


def test_teacher_queue_filtering() -> None:
    history_item = _wave2_item(
        version_id=11,
        subject="HISTORY",
        deterministic_verification=None,
        answer_kind="open_response",
        expected_answer="La décolonisation peut être expliquée par plusieurs facteurs.",
    )

    class AmbiguousComparison:
        def compare(self, **kwargs: object) -> ComparisonResult:
            return ComparisonResult("AMBIGUOUS", "Interpretation nuance.")

    review = run_ai_pedagogical_review(
        CandidateReviewContext(item=history_item),
        blind_assessor=ScriptedBlindAssessor("Réponse partielle"),
        comparison_assessor=AmbiguousComparison(),
        reviewer_model="test-model",
    )
    practice = attach_ai_review(history_item, review)
    bundle = {
        "skill": "SK-HIST",
        "grade": "FR-3E",
        "subject": "HISTORY",
        "chapter": "CH",
        "lot_numbers": [1],
        "practice": practice,
        "assessment": practice,
    }
    filtered = filter_skill_bundles([bundle], ai_prevalidation="Revue enseignant requise")
    assert len(filtered) == 1


def test_deduplicate_candidates_by_skill_slot_version() -> None:
    items = [
        _wave2_item(version_id=1, target_slot="practice"),
        _wave2_item(version_id=1, target_slot="practice"),
        _wave2_item(version_id=2, target_slot="assessment"),
    ]
    assert len(deduplicate_candidates(items)) == 2


def test_lot_selector_excludes_previous_wave2_skills(tmp_path) -> None:
    quality_dir = tmp_path / "quality"
    quality_dir.mkdir()
    lot1_skills = [{"skill": "SK-A"}, {"skill": "SK-B"}]
    (quality_dir / "lcai_0012d4_wave2_lot1_skills.json").write_text(json.dumps(lot1_skills), encoding="utf-8")
    assigned = load_wave2_assigned_skills(quality_dir, before_lot=2)
    assert assigned == {"SK-A", "SK-B"}
    rows = [
        {"skill": "SK-A", "subject": "HISTORY", "grade": "FR-3E", "approved_practice": 0, "approved_assessment": 0},
        {"skill": "SK-C", "subject": "HISTORY", "grade": "FR-3E", "approved_practice": 0, "approved_assessment": 0},
    ]
    selected = select_wave2_lot_skills(rows, lot_number=1, lot_size=10, exclude_skills=assigned)
    assert all(str(row["skill"]) not in assigned for row in selected)


def test_confidence_not_only_from_legacy_score() -> None:
    item = _wave2_item(candidate_score=53)
    comparison = ComparisonResult("CORRECT", "Independent agreement.")
    scores = score_dimensions(item, comparison=comparison, qcm=None)
    confidence = derive_confidence(comparison=comparison, scores=scores, qcm=None)
    assert confidence == "HIGH"


def test_non_authoritative_heuristic_does_not_drive_decision() -> None:
    item = attach_ai_review(
        _wave2_item(),
        run_ai_pedagogical_review(
            CandidateReviewContext(item=_wave2_item()),
            blind_assessor=ScriptedBlindAssessor("20"),
            comparison_assessor=ScriptedComparisonAssessor(),
            reviewer_model="local-heuristic-v1",
            assessor_type="local",
            review_mode="LOCAL_HEURISTIC",
            authoritative_ai_review=False,
        ),
    )
    assert item["authoritative_ai_review"] is False
    assert item.get("ai_prevalidation_decision") is None
    assert not is_ai_rejected(item)
    assert not is_ai_prevalidated(item)


def test_review_idempotency_key_includes_assessor_and_model() -> None:
    from domain.content.pedagogical_review import build_review_idempotency_key

    key = build_review_idempotency_key(
        candidate_version_id=123,
        pipeline_version="lcai-0012d4-ai-review-v2",
        assessor_type="openai",
        model_identifier="gpt-5-mini",
    )
    assert key == "123:lcai-0012d4-ai-review-v2:openai:gpt-5-mini"

    item = _wave2_item(candidate_score=53)
    comparison = ComparisonResult("CORRECT", "Independent agreement.")
    scores = score_dimensions(item, comparison=comparison, qcm=None)
    confidence = derive_confidence(comparison=comparison, scores=scores, qcm=None)
    assert confidence == "HIGH"
