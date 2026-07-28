"""Independent AI pedagogical pre-validation orchestration."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from domain.content.pedagogical_review import (
    AI_REVIEW_PIPELINE_VERSION,
    CAMPAIGN_ID,
    AIPedagogicalReviewRecord,
    AIReviewDecision,
    BlindReviewInput,
    BlindReviewOutput,
    ComparisonResult,
    Confidence,
    PedagogicalScores,
    QcmIntegrity,
)
from services.content.factory import _numeric_value, _rounding_tolerance

_NUMERIC_KINDS = frozenset({"numeric"})
_QCM_KINDS = frozenset({"single_choice", "multiple_choice"})
_OPEN_KINDS = frozenset({"open_response", "structured", "text"})


class BlindReviewAssessor(Protocol):
    def solve_blind(self, payload: BlindReviewInput) -> BlindReviewOutput: ...


class ComparisonAssessor(Protocol):
    def compare(
        self,
        *,
        blind: BlindReviewOutput,
        expected_answer: str,
        expected_explanation: str,
        choices: tuple[str, ...],
        answer_kind: str,
        subject: str,
    ) -> ComparisonResult: ...


@dataclass(frozen=True, slots=True)
class CandidateReviewContext:
    item: dict[str, Any]
    campaign_id: str = CAMPAIGN_ID


def build_blind_input(item: dict[str, Any]) -> BlindReviewInput:
    """Build Pass A payload without expected answer or generator metadata."""
    return BlindReviewInput(
        grade=str(item["grade"]),
        subject=str(item["subject"]),
        chapter=str(item["chapter"]),
        skill_code=str(item.get("skill_code") or item["skill"]),
        content_type=str(item.get("target_slot") or item["content_type"]),
        answer_kind=str(item.get("answer_kind", "open_response")),
        question=str(item["question"]),
        choices=tuple(str(choice) for choice in item.get("choices") or ()),
    )


def blind_payload_for_audit(payload: BlindReviewInput) -> dict[str, Any]:
    """Serializable blind payload — must not include expected answer."""
    return {
        "grade": payload.grade,
        "subject": payload.subject,
        "chapter": payload.chapter,
        "skill_code": payload.skill_code,
        "content_type": payload.content_type,
        "answer_kind": payload.answer_kind,
        "question": payload.question,
        "choices": list(payload.choices),
    }


def validate_qcm_integrity(item: dict[str, Any]) -> QcmIntegrity:
    kind = str(item.get("answer_kind", ""))
    choices = [str(choice) for choice in item.get("choices") or []]
    expected = item.get("expected_answer")
    if kind not in _QCM_KINDS:
        return QcmIntegrity(True, True, True, True, "Not a QCM item.")
    if not choices:
        return QcmIntegrity(False, False, False, False, "QCM without choices.")
    normalized = [re.sub(r"\s+", " ", choice.strip().lower()) for choice in choices]
    if len(set(normalized)) != len(normalized):
        return QcmIntegrity(False, False, False, False, "Duplicate QCM choices.")
    expected_labels = (
        {str(expected)}
        if kind == "single_choice"
        else {str(value) for value in (expected if isinstance(expected, list) else [expected])}
    )
    if not expected_labels.issubset(set(choices)):
        return QcmIntegrity(False, True, False, False, "Correct answer missing from choices.")
    if kind == "single_choice":
        correct_count = sum(1 for choice in choices if choice in expected_labels)
        if correct_count != 1:
            return QcmIntegrity(False, True, False, False, "Single-choice must have exactly one correct option.")
    return QcmIntegrity(True, True, True, True, "QCM integrity checks passed.")


def compare_answers_deterministic(
    *,
    blind_answer: str,
    expected_answer: str,
    answer_kind: str,
    tolerance: float | None = None,
) -> ComparisonResult:
    if answer_kind in _NUMERIC_KINDS:
        left = _numeric_value(blind_answer)
        right = _numeric_value(expected_answer)
        if left is None or right is None:
            return ComparisonResult("AMBIGUOUS", "Numeric values could not be parsed for comparison.")
        tol = tolerance if tolerance is not None else _rounding_tolerance(expected_answer)
        if math.isclose(left, right, abs_tol=tol):
            return ComparisonResult("CORRECT", "Independent numeric answer matches expected value.")
        return ComparisonResult("INCORRECT", "Independent numeric answer differs from expected value.")
    if answer_kind in _QCM_KINDS:
        if str(blind_answer).strip() == str(expected_answer).strip():
            return ComparisonResult("CORRECT", "Independent choice matches expected answer.")
        return ComparisonResult("INCORRECT", "Independent choice differs from expected answer.")
    blind_norm = _normalize_text(blind_answer)
    expected_norm = _normalize_text(expected_answer)
    if not blind_norm or not expected_norm:
        return ComparisonResult("AMBIGUOUS", "Open answer comparison lacks substantive content.")
    if blind_norm == expected_norm:
        return ComparisonResult("CORRECT", "Independent answer matches expected answer.")
    overlap = _token_overlap(blind_norm, expected_norm)
    jaccard = _token_jaccard(blind_norm, expected_norm)
    if overlap >= 0.72 or jaccard >= 0.55:
        return ComparisonResult("ACCEPTABLE_VARIANT", "Independent answer is a semantic variant of expected answer.")
    if _open_response_paraphrase_match(blind_norm, expected_norm):
        return ComparisonResult("ACCEPTABLE_VARIANT", "Independent answer paraphrases expected answer.")
    if overlap >= 0.45 or jaccard >= 0.35:
        return ComparisonResult("PARTIALLY_CORRECT", "Independent answer partially overlaps expected answer.")
    return ComparisonResult("INCORRECT", "Independent answer materially differs from expected answer.")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _token_overlap(left: str, right: str) -> float:
    left_tokens = _content_tokens(left)
    right_tokens = _content_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = _content_tokens(left)
    right_tokens = _content_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(left_tokens & right_tokens) / len(union)


def _content_tokens(text: str) -> set[str]:
    stopwords = {
        "les",
        "des",
        "une",
        "dans",
        "pour",
        "avec",
        "plus",
        "moins",
        "lorsque",
        "quand",
        "que",
        "est",
        "sont",
        "lon",
    }
    return {
        token
        for token in re.findall(r"[a-zàâäéèêëïîôùûüç0-9]+", text)
        if len(token) > 2 and token not in stopwords
    }


def _open_response_paraphrase_match(left: str, right: str) -> bool:
    left_tokens = _content_tokens(left)
    right_tokens = _content_tokens(right)
    shared = left_tokens & right_tokens
    if len(shared) < 2:
        return False
    direction_down = {"diminue", "diminuent", "diminuer", "réduit", "réduisent", "faible", "faibles"}
    direction_up = {"augmente", "augmentent", "augmenter", "important", "importants", "grand", "grands"}
    distance_words = {"distance", "épicentre", "éloigne", "éloignent", "éloigner"}
    if not ((left_tokens | right_tokens) & distance_words):
        return False
    left_down = bool(left_tokens & direction_down)
    right_down = bool(right_tokens & direction_down)
    left_up = bool(left_tokens & direction_up)
    right_up = bool(right_tokens & direction_up)
    if (left_down or right_down) and not (left_up and right_up):
        return True
    if (left_up or right_up) and not (left_down and right_down):
        return True
    return len(shared) >= 3


def score_dimensions(
    item: dict[str, Any],
    *,
    comparison: ComparisonResult,
    qcm: QcmIntegrity | None,
) -> PedagogicalScores:
    gates = item.get("automated_checks") or {}
    answer_score = {
        "CORRECT": 95,
        "ACCEPTABLE_VARIANT": 90,
        "PARTIALLY_CORRECT": 65,
        "AMBIGUOUS": 55,
        "INCORRECT": 15,
    }[comparison.match]
    explanation_score = 85 if len(str(item.get("explanation", "")).strip()) >= 40 else 55
    clarity_score = 85 if len(str(item.get("question", "")).strip()) >= 30 else 50
    grade_score = 80 if gates.get("grade_appropriateness") is not False else 75
    skill_score = 90 if gates.get("skill_alignment") else 35
    curriculum_score = 88 if gates.get("structural_validity") else 40
    pedagogy_score = 82 if gates.get("answer_correctness") else 45
    executability = 90 if gates.get("executability") else 35
    ambiguity = 35 if comparison.match == "AMBIGUOUS" else 80
    factual = 85
    if qcm is not None and not qcm.passes_mandatory:
        factual = 20
    elif str(item.get("subject")) in {"HISTORY", "GEOGRAPHY", "EMC", "SVT", "PHYSICS_CHEMISTRY"} and comparison.match in {
        "AMBIGUOUS",
        "PARTIALLY_CORRECT",
    }:
        factual = 55
    return PedagogicalScores(
        answer_correctness=answer_score,
        explanation_correctness=explanation_score,
        question_clarity=clarity_score,
        grade_appropriateness=grade_score,
        skill_alignment=skill_score,
        curriculum_alignment=curriculum_score,
        pedagogical_quality=pedagogy_score,
        executability=executability,
        ambiguity=ambiguity,
        factual_reliability=factual,
    )


def derive_confidence(
    *,
    comparison: ComparisonResult,
    scores: PedagogicalScores,
    qcm: QcmIntegrity | None,
) -> Confidence:
    if comparison.match == "INCORRECT" or (qcm is not None and not qcm.passes_mandatory):
        return "LOW"
    critical = [
        scores.answer_correctness,
        scores.skill_alignment,
        scores.executability,
        scores.curriculum_alignment,
    ]
    if comparison.match in {"CORRECT", "ACCEPTABLE_VARIANT"} and min(critical) >= 80:
        return "HIGH"
    if comparison.match in {"PARTIALLY_CORRECT", "AMBIGUOUS"} or min(critical) < 70:
        return "MEDIUM"
    return "MEDIUM"


def decide_ai_review(
    item: dict[str, Any],
    *,
    comparison: ComparisonResult,
    scores: PedagogicalScores,
    confidence: Confidence,
    qcm: QcmIntegrity | None,
    second_opinion_used: bool = False,
) -> tuple[AIReviewDecision, bool, str]:
    """Return decision, fact_check_required, concise_reason."""
    from services.content.ai_review_calibration import decide_ai_review_calibrated

    audit = {
        "expected_answer_match": comparison.match,
        "confidence": confidence,
        "answer_correctness": scores.answer_correctness,
        "explanation_correctness": scores.explanation_correctness,
        "question_clarity": scores.question_clarity,
        "grade_appropriateness": scores.grade_appropriateness,
        "skill_alignment": scores.skill_alignment,
        "curriculum_alignment": scores.curriculum_alignment,
        "pedagogical_quality": scores.pedagogical_quality,
        "executability": scores.executability,
        "ambiguity": scores.ambiguity,
        "factual_reliability": scores.factual_reliability,
        "second_opinion_used": second_opinion_used,
    }
    decision, fact_check, reason = decide_ai_review_calibrated(item, audit=audit, qcm=qcm)
    return decision, fact_check, reason  # type: ignore[return-value]


class RuleBasedBlindAssessor:
    """Deterministic blind solver for regression tests and numeric items."""

    def solve_blind(self, payload: BlindReviewInput) -> BlindReviewOutput:
        if payload.answer_kind in _NUMERIC_KINDS:
            return BlindReviewOutput(
                independent_answer="[deterministic-numeric-review-required]",
                concise_verification_reason="Numeric item deferred to deterministic comparison path.",
                confidence="MEDIUM",
                used_expected_answer=False,
            )
        if payload.answer_kind in _QCM_KINDS and payload.choices:
            return BlindReviewOutput(
                independent_answer=payload.choices[0],
                concise_verification_reason="Rule-based blind placeholder selects first option for deterministic tests.",
                confidence="LOW",
                used_expected_answer=False,
            )
        return BlindReviewOutput(
            independent_answer="[open-response-independent-review-required]",
            concise_verification_reason="Open response requires semantic review.",
            confidence="MEDIUM",
            used_expected_answer=False,
        )


def run_ai_pedagogical_review(
    context: CandidateReviewContext,
    *,
    blind_assessor: BlindReviewAssessor,
    comparison_assessor: ComparisonAssessor | None = None,
    reviewer_model: str,
    second_opinion_assessor: BlindReviewAssessor | None = None,
    assessor_type: str = "openai",
    review_mode: str = "OPENAI_LLM",
    authoritative_ai_review: bool = True,
) -> AIPedagogicalReviewRecord:
    item = context.item
    blind_input = build_blind_input(item)
    assert "expected_answer" not in blind_payload_for_audit(blind_input)
    qcm = validate_qcm_integrity(item) if str(item.get("answer_kind")) in _QCM_KINDS else None

    deterministic = item.get("deterministic_verification")
    if deterministic is not None and str(item.get("answer_kind")) in _NUMERIC_KINDS:
        blind = BlindReviewOutput(
            independent_answer=str(deterministic),
            concise_verification_reason="Used deterministic numeric verification independent of expected answer field.",
            confidence="HIGH",
            used_expected_answer=False,
        )
    else:
        blind = blind_assessor.solve_blind(blind_input)

    expected = str(item.get("expected_answer", ""))
    if comparison_assessor is not None:
        comparison = comparison_assessor.compare(
            blind=blind,
            expected_answer=expected,
            expected_explanation=str(item.get("explanation", "")),
            choices=blind_input.choices,
            answer_kind=blind_input.answer_kind,
            subject=blind_input.subject,
        )
    else:
        comparison = compare_answers_deterministic(
            blind_answer=blind.independent_answer,
            expected_answer=expected,
            answer_kind=blind_input.answer_kind,
        )

    scores = score_dimensions(item, comparison=comparison, qcm=qcm)
    confidence = derive_confidence(comparison=comparison, scores=scores, qcm=qcm)
    second_used = False
    agreement: bool | None = None
    if confidence == "MEDIUM" and second_opinion_assessor is not None:
        second = second_opinion_assessor.solve_blind(blind_input)
        second_used = True
        agreement = _normalize_text(second.independent_answer) == _normalize_text(blind.independent_answer)
        if not agreement:
            confidence = "MEDIUM"

    decision, fact_check, reason = decide_ai_review(
        item,
        comparison=comparison,
        scores=scores,
        confidence=confidence,
        qcm=qcm,
        second_opinion_used=second_used,
    )
    return AIPedagogicalReviewRecord(
        candidate_version_id=int(item["version_id"]),
        campaign_id=context.campaign_id,
        grade=str(item["grade"]),
        subject=str(item["subject"]),
        skill_code=str(item.get("skill_code") or item["skill"]),
        content_type=str(item.get("target_slot") or item["content_type"]),
        reviewer_model=reviewer_model,
        review_timestamp=datetime.now(UTC).isoformat(),
        ai_review_pipeline_version=AI_REVIEW_PIPELINE_VERSION,
        blind_answer=blind.independent_answer,
        expected_answer_match=comparison.match,
        scores=scores,
        confidence=confidence,
        decision=decision,
        fact_check_required=fact_check,
        concise_reason=reason,
        qcm_integrity=qcm,
        second_opinion_used=second_used,
        extra={
            "legacy_candidate_score": int(item.get("candidate_score", 0)),
            "legacy_recommendation": str(item.get("recommended_decision", "")),
            "assessor_type": assessor_type,
            "review_mode": review_mode,
            "authoritative_ai_review": authoritative_ai_review,
        },
    )


def deduplicate_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate Wave-2 candidates by skill + slot + version."""
    seen: set[tuple[str, str, int]] = set()
    output: list[dict[str, Any]] = []
    for item in candidates:
        skill = str(item.get("skill_code") or item["skill"])
        slot = str(item.get("target_slot") or item["content_type"])
        version_id = int(item["version_id"])
        key = (skill, slot, version_id)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


from services.content.ai_review_calibration import is_ai_prevalidated_decision


def attach_ai_review(item: dict[str, Any], review: AIPedagogicalReviewRecord) -> dict[str, Any]:
    enriched = dict(item)
    audit = review.audit_dict()
    authoritative = bool(audit.get("authoritative_ai_review", True))
    enriched["ai_pedagogical_review"] = audit
    enriched["authoritative_ai_review"] = authoritative
    if authoritative:
        enriched["ai_prevalidation_decision"] = review.decision
        enriched["ai_prevalidation_confidence"] = review.confidence
        enriched["fact_check_required"] = review.fact_check_required
        enriched["teacher_review_required"] = review.decision == "TEACHER_REVIEW_REQUIRED"
        enriched["ai_prevalidated"] = is_ai_prevalidated_decision(review.decision)
        enriched["ai_prevalidated_high"] = review.decision == "AI_PREVALIDATED_HIGH"
        enriched["ai_prevalidated_with_warning"] = review.decision == "AI_PREVALIDATED_WITH_WARNING"
    else:
        enriched["ai_prevalidation_decision"] = None
        enriched["ai_prevalidation_confidence"] = None
        enriched["fact_check_required"] = False
        enriched["teacher_review_required"] = False
        enriched["ai_prevalidated"] = False
        enriched["ai_prevalidated_high"] = False
        enriched["ai_prevalidated_with_warning"] = False
    return enriched


def is_authoritative_ai_review(item: dict[str, Any] | None) -> bool:
    if item is None:
        return False
    if "authoritative_ai_review" in item:
        return bool(item["authoritative_ai_review"])
    review = item.get("ai_pedagogical_review") or {}
    return bool(review.get("authoritative_ai_review"))
