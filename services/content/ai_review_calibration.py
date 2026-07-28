"""Calibrated decision engine and escalation analysis for AI pedagogical review."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from domain.content.pedagogical_review import PedagogicalScores, QcmIntegrity

CalibratedDecision = Literal[
    "AI_PREVALIDATED_HIGH",
    "AI_PREVALIDATED_WITH_WARNING",
    "TEACHER_REVIEW_REQUIRED",
    "AI_REJECTED",
]

EscalationCategory = Literal[
    "answer_uncertainty",
    "expected_answer_disagreement",
    "explanation_uncertainty",
    "grade_appropriateness",
    "curriculum_alignment",
    "skill_alignment",
    "factual_uncertainty",
    "open_response_ambiguity",
    "low_confidence",
    "policy_threshold_rule",
    "missing_structured_field",
    "parser_schema_issue",
    "automatic_subject_escalation",
    "legacy_quality_influence",
    "second_opinion_disagreement",
    "other",
]

CALIBRATION_VERSION = "lcai-0012d4-ai-review-calibration-v2-grade-repair"

AGREEMENT_MATCHES = frozenset({"CORRECT", "ACCEPTABLE_VARIANT"})


@dataclass(frozen=True, slots=True)
class EscalationAnalysis:
    primary_reason: EscalationCategory
    all_reasons: tuple[EscalationCategory, ...]
    concise_reason: str


def is_ai_prevalidated_decision(decision: str | None) -> bool:
    if not decision:
        return False
    return decision in {
        "AI_PREVALIDATED",
        "AI_PREVALIDATED_HIGH",
        "AI_PREVALIDATED_WITH_WARNING",
    }


def analyze_escalation_reasons(
    *,
    item: dict[str, Any],
    audit: dict[str, Any],
    original_decision: str,
) -> EscalationAnalysis:
    """Classify why an authoritative review reached its original decision."""
    reasons: list[EscalationCategory] = []
    comparison = str(audit.get("expected_answer_match", ""))
    confidence = str(audit.get("confidence", ""))
    concise = str(audit.get("concise_reason", ""))
    gates = item.get("automated_checks") or {}

    if comparison == "INCORRECT":
        reasons.append("expected_answer_disagreement")
    if comparison in {"AMBIGUOUS", "PARTIALLY_CORRECT"}:
        reasons.append("open_response_ambiguity")
    if confidence in {"MEDIUM", "LOW"}:
        reasons.append("low_confidence")
    if not gates.get("grade_appropriateness", True):
        reasons.append("grade_appropriateness")
    if int(audit.get("skill_alignment", 0)) < 70:
        reasons.append("skill_alignment")
    if int(audit.get("curriculum_alignment", 0)) < 70:
        reasons.append("curriculum_alignment")
    if int(audit.get("factual_reliability", 0)) < 70:
        reasons.append("factual_uncertainty")
    if int(audit.get("explanation_correctness", 0)) < 70:
        reasons.append("explanation_uncertainty")
    if audit.get("fact_check_required"):
        reasons.append("factual_uncertainty")
    if audit.get("second_opinion_used") and original_decision == "TEACHER_REVIEW_REQUIRED":
        reasons.append("second_opinion_disagreement")
    if str(item.get("recommended_decision")) == "REJECT" and original_decision == "AI_REJECTED":
        reasons.append("legacy_quality_influence")
    if "Grade appropriateness requires specialist judgement." in concise:
        reasons.append("policy_threshold_rule")
    if "Genuine pedagogical or factual judgement still required." in concise:
        if comparison in AGREEMENT_MATCHES and confidence == "HIGH":
            reasons.append("policy_threshold_rule")
        else:
            reasons.append("answer_uncertainty")
    if "EMC civic nuance" in concise or "Interpretation or language nuance" in concise:
        reasons.append("automatic_subject_escalation")

    if not reasons:
        reasons.append("other")

    primary = reasons[0]
    if "policy_threshold_rule" in reasons and comparison in AGREEMENT_MATCHES and confidence == "HIGH":
        primary = "policy_threshold_rule"
    elif "expected_answer_disagreement" in reasons:
        primary = "expected_answer_disagreement"
    elif "open_response_ambiguity" in reasons and comparison != "CORRECT":
        primary = "open_response_ambiguity"

    return EscalationAnalysis(primary_reason=primary, all_reasons=tuple(dict.fromkeys(reasons)), concise_reason=concise)


def escalation_frequency_table(
    audits: list[dict[str, Any]],
    items_by_version: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    primary = Counter()
    all_reasons = Counter()
    for audit in audits:
        version_id = int(audit["candidate_version_id"])
        item = items_by_version.get(version_id, {})
        analysis = analyze_escalation_reasons(
            item=item,
            audit=audit,
            original_decision=str(audit.get("decision", "")),
        )
        primary[analysis.primary_reason] += 1
        for reason in analysis.all_reasons:
            all_reasons[reason] += 1
    return {
        "primary_reasons": dict(primary.most_common()),
        "all_reasons": dict(all_reasons.most_common()),
        "total": len(audits),
    }


def _legacy_grade_unverified(item: dict[str, Any]) -> bool:
    assessment = item.get("grade_assessment") or {}
    if assessment:
        return not bool(assessment.get("gate_pass"))
    gates = item.get("automated_checks") or {}
    return gates.get("grade_appropriateness") is False


def _grade_gate_pass(item: dict[str, Any]) -> bool:
    assessment = item.get("grade_assessment") or {}
    if assessment:
        return bool(assessment.get("gate_pass"))
    gates = item.get("automated_checks") or {}
    return gates.get("grade_appropriateness") is not False


def _effective_grade_score(
    item: dict[str, Any],
    scores: PedagogicalScores,
    *,
    comparison: str,
    confidence: str,
) -> int:
    """Legacy grade gate false means unverified, not wrong grade — do not block AI resolution."""
    if scores.grade_appropriateness >= 80:
        return scores.grade_appropriateness
    assessment = item.get("grade_assessment") or {}
    status = str(assessment.get("status", ""))
    if status in {"GRADE_MATCH_CONFIRMED", "GRADE_PEDAGOGICALLY_APPROPRIATE"}:
        return max(scores.grade_appropriateness, 85)
    if _legacy_grade_unverified(item) and comparison in AGREEMENT_MATCHES and confidence == "HIGH":
        return 80
    return scores.grade_appropriateness


def _effective_scores(
    item: dict[str, Any],
    audit: dict[str, Any],
) -> PedagogicalScores:
    scores = _scores_from_audit(audit)
    comparison = str(audit.get("expected_answer_match", ""))
    confidence = str(audit.get("confidence", ""))
    grade = _effective_grade_score(item, scores, comparison=comparison, confidence=confidence)
    explanation = scores.explanation_correctness
    if (
        explanation == 80
        and comparison in AGREEMENT_MATCHES
        and confidence == "HIGH"
        and len(str(item.get("explanation", "")).strip()) >= 40
    ):
        explanation = 85
    if grade == scores.grade_appropriateness and explanation == scores.explanation_correctness:
        return scores
    return PedagogicalScores(
        answer_correctness=scores.answer_correctness,
        explanation_correctness=explanation,
        question_clarity=scores.question_clarity,
        grade_appropriateness=grade,
        skill_alignment=scores.skill_alignment,
        curriculum_alignment=scores.curriculum_alignment,
        pedagogical_quality=scores.pedagogical_quality,
        executability=scores.executability,
        ambiguity=scores.ambiguity,
        factual_reliability=scores.factual_reliability,
    )


def _scores_from_audit(audit: dict[str, Any]) -> PedagogicalScores:
    return PedagogicalScores(
        answer_correctness=int(audit["answer_correctness"]),
        explanation_correctness=int(audit["explanation_correctness"]),
        question_clarity=int(audit["question_clarity"]),
        grade_appropriateness=int(audit["grade_appropriateness"]),
        skill_alignment=int(audit["skill_alignment"]),
        curriculum_alignment=int(audit["curriculum_alignment"]),
        pedagogical_quality=int(audit["pedagogical_quality"]),
        executability=int(audit["executability"]),
        ambiguity=int(audit["ambiguity"]),
        factual_reliability=int(audit["factual_reliability"]),
    )


def decide_ai_review_calibrated(
    item: dict[str, Any],
    *,
    audit: dict[str, Any],
    qcm: QcmIntegrity | None = None,
) -> tuple[CalibratedDecision, bool, str]:
    """Recompute decision from existing authoritative evidence only."""
    comparison = str(audit.get("expected_answer_match", ""))
    confidence = str(audit.get("confidence", ""))
    scores = _effective_scores(item, audit)
    subject = str(item.get("subject", ""))
    fact_check = False
    grade_gate_pass = _grade_gate_pass(item)

    if not item.get("hard_gates_passed"):
        return "AI_REJECTED", False, "Mandatory technical hard gates failed."
    if qcm is not None and not qcm.passes_mandatory:
        return "AI_REJECTED", False, "QCM integrity checks failed."
    if comparison == "INCORRECT":
        return "AI_REJECTED", False, "Independent answer contradicts expected answer."
    if scores.skill_alignment < 50 or scores.executability < 50:
        return "AI_REJECTED", False, "Skill alignment or executability materially failed."
    if confidence == "LOW" and comparison not in AGREEMENT_MATCHES:
        return "AI_REJECTED", False, "Low-confidence independent review detected material issues."

    if audit.get("second_opinion_used") and comparison in {"AMBIGUOUS", "PARTIALLY_CORRECT"}:
        fact_check = subject in {"HISTORY", "GEOGRAPHY", "EMC", "SVT", "PHYSICS_CHEMISTRY"}
        return "TEACHER_REVIEW_REQUIRED", fact_check, "Independent AI reviewers disagreed on an ambiguous case."

    if comparison == "AMBIGUOUS":
        if subject in {"FRENCH", "ENGLISH", "SPANISH"}:
            return "TEACHER_REVIEW_REQUIRED", False, "Language interpretation requires specialist review."
        fact_check = subject in {"HISTORY", "GEOGRAPHY", "EMC", "SVT", "PHYSICS_CHEMISTRY"}
        return "TEACHER_REVIEW_REQUIRED", fact_check, "Independent answer remains genuinely ambiguous."

    if comparison == "PARTIALLY_CORRECT":
        if confidence == "HIGH" and min(scores.answer_correctness, scores.skill_alignment, scores.executability) >= 80:
            return (
                "AI_PREVALIDATED_WITH_WARNING",
                False,
                "Independent answer partially overlaps expected answer; minor wording difference only.",
            )
        fact_check = subject in {"HISTORY", "GEOGRAPHY", "EMC", "SVT", "PHYSICS_CHEMISTRY"}
        return "TEACHER_REVIEW_REQUIRED", fact_check, "Partial semantic agreement requires specialist confirmation."

    if subject == "EMC" and comparison not in AGREEMENT_MATCHES:
        return "TEACHER_REVIEW_REQUIRED", True, "EMC civic nuance requires Teacher review."

    if comparison in AGREEMENT_MATCHES and confidence == "HIGH":
        high_ready = (
            scores.answer_correctness >= 90
            and scores.explanation_correctness >= 85
            and scores.skill_alignment >= 85
            and scores.grade_appropriateness >= 80
            and scores.executability >= 90
            and scores.ambiguity >= 70
        )
        if high_ready:
            if not grade_gate_pass:
                return (
                    "AI_PREVALIDATED_WITH_WARNING",
                    False,
                    "Independent blind review agrees; grade check still requires attention.",
                )
            return "AI_PREVALIDATED_HIGH", False, "Independent blind review agrees; all core checks pass."

        warning_ready = (
            scores.answer_correctness >= 85
            and scores.explanation_correctness >= 75
            and scores.skill_alignment >= 80
            and scores.executability >= 80
            and scores.curriculum_alignment >= 75
        )
        if warning_ready:
            warnings: list[str] = []
            if scores.grade_appropriateness < 80 or not grade_gate_pass:
                warnings.append("grade appropriateness not yet explicitly verified")
            if scores.explanation_correctness < 85:
                warnings.append("explanation could be strengthened")
            if scores.ambiguity < 70:
                warnings.append("minor ambiguity remains")
            suffix = f" ({'; '.join(warnings)})" if warnings else ""
            return (
                "AI_PREVALIDATED_WITH_WARNING",
                False,
                f"Independent answer verified; acceptable with minor warning{suffix}.",
            )

    if confidence == "MEDIUM":
        fact_check = subject in {"HISTORY", "GEOGRAPHY", "SVT", "PHYSICS_CHEMISTRY"}
        return "TEACHER_REVIEW_REQUIRED", fact_check, "Medium-confidence review still requires specialist judgement."

    return "TEACHER_REVIEW_REQUIRED", fact_check, "Remaining pedagogical uncertainty requires Teacher review."


def reclassify_audit_record(
    audit: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    """Apply calibrated decision to an existing authoritative audit record."""
    from services.content.ai_pedagogical_review import validate_qcm_integrity

    qcm = None
    if str(item.get("answer_kind")) in {"single_choice", "multiple_choice"}:
        qcm_data = audit.get("qcm_integrity")
        if qcm_data:
            qcm = QcmIntegrity(
                correct_option_present=bool(qcm_data.get("QCM_CORRECT_OPTION_PRESENT", True)),
                uniqueness=bool(qcm_data.get("QCM_UNIQUENESS", True)),
                distractor_validity=bool(qcm_data.get("QCM_DISTRACTOR_VALIDITY", True)),
                structure_valid=bool(qcm_data.get("QCM_STRUCTURE_VALID", True)),
                concise_reason=str(qcm_data.get("concise_reason", "")),
            )
        else:
            qcm = validate_qcm_integrity(item)

    original = analyze_escalation_reasons(
        item=item,
        audit=audit,
        original_decision=str(audit.get("decision", "")),
    )
    decision, fact_check, reason = decide_ai_review_calibrated(item, audit=audit, qcm=qcm)
    effective = _effective_scores(item, audit)
    updated = dict(audit)
    updated["decision"] = decision
    updated["fact_check_required"] = fact_check
    updated["concise_reason"] = reason
    updated["grade_appropriateness"] = effective.grade_appropriateness
    updated["explanation_correctness"] = effective.explanation_correctness
    updated["calibration_version"] = CALIBRATION_VERSION
    updated["original_decision"] = audit.get("decision")
    updated["original_concise_reason"] = audit.get("concise_reason")
    updated["original_primary_escalation_reason"] = original.primary_reason
    updated["calibrated_primary_reason"] = (
        original.primary_reason
        if decision == "TEACHER_REVIEW_REQUIRED"
        else ("none" if is_ai_prevalidated_decision(decision) else "expected_answer_disagreement")
    )
    updated["ai_prevalidated"] = is_ai_prevalidated_decision(decision)
    updated["ai_prevalidated_high"] = decision == "AI_PREVALIDATED_HIGH"
    updated["ai_prevalidated_with_warning"] = decision == "AI_PREVALIDATED_WITH_WARNING"
    return updated
