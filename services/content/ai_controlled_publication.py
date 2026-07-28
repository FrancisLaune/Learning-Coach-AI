"""Controlled AI publication eligibility, dry-run planning, and provenance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from domain.content.pedagogical_review import AI_REVIEW_PIPELINE_VERSION, CAMPAIGN_ID
from services.content.ai_review_calibration import is_ai_prevalidated_decision
from services.content.approval_coverage import tier
from services.content.d4_review import (
    ai_prevalidation_decision,
    is_ai_rejected,
    is_authoritative_ai_review,
    requires_teacher_review,
)
from services.content.grade_appropriateness import GradeAssessmentStatus

APPROVAL_TYPE_AI_CONTROLLED = "AI_CONTROLLED_APPROVAL"
APPROVAL_TYPE_HUMAN = "HUMAN_APPROVAL"
APPROVAL_TYPE_TEACHER = "TEACHER_APPROVAL"
REVIEW_SOURCE_AI = "AI_PEDAGOGICAL_REVIEW"
DEFAULT_REVIEW_MODEL = "gpt-5-mini"
DEFAULT_REVIEW_PIPELINE = AI_REVIEW_PIPELINE_VERSION
DEFAULT_CAMPAIGN = CAMPAIGN_ID

WarningSeverity = Literal[
    "NON_BLOCKING_WARNING",
    "PEDAGOGICAL_WARNING",
    "FACTUAL_WARNING",
    "CURRICULUM_WARNING",
    "TECHNICAL_WARNING",
]

AGREEMENT_MATCHES = frozenset({"CORRECT", "ACCEPTABLE_VARIANT"})


@dataclass(frozen=True, slots=True)
class PublicationEligibility:
    eligible: bool
    reasons: tuple[str, ...]
    warning_severity: WarningSeverity | None = None


def classify_warning_severity(item: dict[str, Any]) -> WarningSeverity | None:
    decision = ai_prevalidation_decision(item)
    if decision != "AI_PREVALIDATED_WITH_WARNING":
        return None
    grade_status = str((item.get("grade_assessment") or {}).get("status", ""))
    review = item.get("ai_pedagogical_review") or {}
    if grade_status == "GRADE_WARNING":
        return "CURRICULUM_WARNING"
    if review.get("fact_check_required"):
        return "FACTUAL_WARNING"
    if not item.get("hard_gates_passed"):
        return "TECHNICAL_WARNING"
    if int(review.get("explanation_correctness", 0)) < 85:
        return "PEDAGOGICAL_WARNING"
    concise = str(review.get("concise_reason", ""))
    if "legacy" in concise.lower() or "wording" in concise.lower() or "minor" in concise.lower():
        return "NON_BLOCKING_WARNING"
    return "PEDAGOGICAL_WARNING"


def _grade_status(item: dict[str, Any]) -> GradeAssessmentStatus | str:
    return str((item.get("grade_assessment") or {}).get("status", ""))


def assess_publication_eligibility(
    item: dict[str, Any],
    *,
    required_decision: str = "AI_PREVALIDATED_HIGH",
    allow_non_blocking_warning: bool = False,
    campaign: str = DEFAULT_CAMPAIGN,
) -> PublicationEligibility:
    reasons: list[str] = []
    decision = ai_prevalidation_decision(item)
    review = item.get("ai_pedagogical_review") or {}

    if not is_authoritative_ai_review(item):
        reasons.append("Authoritative AI review evidence is missing.")
    if str(item.get("review_campaign", "")) != campaign:
        reasons.append("Candidate is outside the authorized AI publication campaign.")
    if not item.get("hard_gates_passed"):
        reasons.append("Hard gates failed.")
    if is_ai_rejected(item):
        reasons.append("AI rejected this candidate.")
    if requires_teacher_review(item):
        reasons.append("Teacher review is required.")
    if review.get("fact_check_required"):
        reasons.append("Fact-check is required.")
    if str(review.get("confidence", "")) != "HIGH":
        reasons.append("AI confidence is not HIGH.")
    if str(review.get("expected_answer_match", "")) not in AGREEMENT_MATCHES:
        reasons.append("Independent answer is not verified against expected answer.")
    if int(review.get("answer_correctness", 0)) < 90:
        reasons.append("Answer correctness score is below publication threshold.")
    if int(review.get("explanation_correctness", 0)) < 85:
        reasons.append("Explanation correctness score is below publication threshold.")
    if int(review.get("skill_alignment", 0)) < 85:
        reasons.append("Skill alignment score is below publication threshold.")
    if int(review.get("executability", 0)) < 90:
        reasons.append("Executability score is below publication threshold.")
    grade_status = _grade_status(item)
    if grade_status not in {"GRADE_MATCH_CONFIRMED", "GRADE_PEDAGOGICALLY_APPROPRIATE"}:
        reasons.append(f"Grade check is not passing ({grade_status or 'missing'}).")
    if not (item.get("automated_checks") or {}).get("skill_alignment", False):
        reasons.append("Curriculum mapping is not exact.")

    warning_severity = classify_warning_severity(item)
    if decision == "AI_PREVALIDATED_WITH_WARNING":
        if not allow_non_blocking_warning or warning_severity != "NON_BLOCKING_WARNING":
            reasons.append(f"Warning severity blocks publication ({warning_severity or 'unknown'}).")
        elif required_decision == "AI_PREVALIDATED_HIGH":
            reasons.append("Only AI_PREVALIDATED_HIGH is eligible by default.")

    if decision != required_decision and not (
        allow_non_blocking_warning
        and decision == "AI_PREVALIDATED_WITH_WARNING"
        and warning_severity == "NON_BLOCKING_WARNING"
    ):
        if decision != required_decision:
            reasons.append(f"Decision is {decision}, required {required_decision}.")

    return PublicationEligibility(
        eligible=not reasons,
        reasons=tuple(reasons),
        warning_severity=warning_severity,
    )


def build_publication_provenance(
    item: dict[str, Any],
    *,
    review_model: str = DEFAULT_REVIEW_MODEL,
    review_pipeline: str = DEFAULT_REVIEW_PIPELINE,
) -> dict[str, Any]:
    review = item.get("ai_pedagogical_review") or {}
    return {
        "approval_type": APPROVAL_TYPE_AI_CONTROLLED,
        "review_source": REVIEW_SOURCE_AI,
        "review_model": review_model,
        "review_pipeline": review_pipeline,
        "review_idempotency_key": review.get("review_idempotency_key"),
        "ai_prevalidation_decision": ai_prevalidation_decision(item),
        "ai_prevalidation_confidence": review.get("confidence"),
        "grade_assessment_status": _grade_status(item),
        "campaign_id": item.get("review_campaign"),
    }


def build_execution_manifest(
    bundles: list[dict[str, Any]],
    eligible_candidates: list[dict[str, Any]],
    *,
    campaign: str,
    review_model: str = DEFAULT_REVIEW_MODEL,
    review_pipeline: str = DEFAULT_REVIEW_PIPELINE,
) -> list[dict[str, Any]]:
    eligible_ids = {int(candidate["version_id"]) for candidate in eligible_candidates}
    manifest: list[dict[str, Any]] = []
    for bundle in bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None:
                continue
            version_id = int(item["version_id"])
            if version_id not in eligible_ids:
                continue
            review = item.get("ai_pedagogical_review") or {}
            impact = item.get("coverage_impact") or {}
            current = impact.get("current") or {}
            potential = impact.get("potential") or {}
            manifest.append(
                {
                    "candidate_version_id": version_id,
                    "grade": item.get("grade"),
                    "subject": item.get("subject"),
                    "skill_code": item.get("skill_code") or item.get("skill"),
                    "content_type": item.get("target_slot") or item.get("content_type"),
                    "ai_decision": ai_prevalidation_decision(item),
                    "ai_confidence": review.get("confidence") or item.get("ai_prevalidation_confidence"),
                    "campaign": campaign,
                    "review_model": review_model,
                    "review_pipeline": review_pipeline,
                    "current_tier": current.get("tier"),
                    "projected_tier": potential.get("tier"),
                    "review_idempotency_key": review.get("review_idempotency_key"),
                    "grade_assessment_status": _grade_status(item),
                }
            )
    manifest.sort(key=lambda row: (str(row["skill_code"]), str(row["content_type"]), int(row["candidate_version_id"])))
    return manifest


def _bundle_slots(bundle: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    return bundle.get("practice"), bundle.get("assessment")


def plan_controlled_publication(
    bundles: list[dict[str, Any]],
    *,
    required_decision: str = "AI_PREVALIDATED_HIGH",
    allow_non_blocking_warning: bool = False,
    campaign: str = DEFAULT_CAMPAIGN,
) -> dict[str, Any]:
    eligible_candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    teacher: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    complete_skill_pairs = 0

    for bundle in bundles:
        practice, assessment = _bundle_slots(bundle)
        slots = [item for item in (practice, assessment) if item is not None]
        slot_eligibility: dict[str, PublicationEligibility] = {}
        for item in slots:
            decision = ai_prevalidation_decision(item)
            if is_ai_rejected(item):
                rejected.append(
                    {
                        "version_id": item.get("version_id"),
                        "skill": bundle.get("skill"),
                        "subject": item.get("subject"),
                        "alternate_count": item.get("alternate_count", 0),
                        "replacement_required": int(item.get("alternate_count") or 0) == 0,
                    }
                )
                continue
            if requires_teacher_review(item):
                teacher.append(
                    {
                        "version_id": item.get("version_id"),
                        "skill": bundle.get("skill"),
                        "subject": item.get("subject"),
                        "reason": (item.get("ai_pedagogical_review") or {}).get("concise_reason"),
                        "fact_check_required": bool(item.get("fact_check_required")),
                    }
                )
                continue
            eligibility = assess_publication_eligibility(
                item,
                required_decision=required_decision,
                allow_non_blocking_warning=allow_non_blocking_warning,
                campaign=campaign,
            )
            slot_eligibility[str(item.get("target_slot") or item.get("content_type"))] = eligibility
            if eligibility.eligible:
                eligible_candidates.append(
                    {
                        "version_id": item.get("version_id"),
                        "skill": bundle.get("skill"),
                        "slot": item.get("target_slot") or item.get("content_type"),
                        "decision": decision,
                        "provenance": build_publication_provenance(item),
                    }
                )
            else:
                blocked.append(
                    {
                        "version_id": item.get("version_id"),
                        "skill": bundle.get("skill"),
                        "slot": item.get("target_slot") or item.get("content_type"),
                        "decision": decision,
                        "reasons": list(eligibility.reasons),
                        "warning_severity": eligibility.warning_severity,
                    }
                )
                if eligibility.warning_severity:
                    warnings.append(
                        {
                            "version_id": item.get("version_id"),
                            "skill": bundle.get("skill"),
                            "severity": eligibility.warning_severity,
                        }
                    )

        practice_key = "practice"
        assessment_key = "assessment"
        if (
            practice is not None
            and assessment is not None
            and practice_key in slot_eligibility
            and assessment_key in slot_eligibility
            and slot_eligibility[practice_key].eligible
            and slot_eligibility[assessment_key].eligible
        ):
            complete_skill_pairs += 1

    return {
        "eligible_candidates": eligible_candidates,
        "eligible_candidate_count": len(eligible_candidates),
        "complete_skill_pairs": complete_skill_pairs,
        "blocked": blocked,
        "teacher": teacher,
        "rejected": rejected,
        "warnings": warnings,
    }


def projected_tier1_after_publication(
    coverage_rows: list[dict[str, Any]],
    eligible_candidates: list[dict[str, Any]],
) -> dict[str, int]:
    baseline = sum(
        tier(int(row["approved_practice"]) > 0, int(row["approved_assessment"]) > 0) == 1 for row in coverage_rows
    )
    by_skill: dict[str, set[str]] = {}
    for candidate in eligible_candidates:
        skill = str(candidate["skill"])
        slot = str(candidate["slot"])
        by_skill.setdefault(skill, set()).add(slot)
    newly_complete = sum(1 for slots in by_skill.values() if slots >= {"practice", "assessment"})
    return {
        "baseline_tier1": baseline,
        "projected_tier1": baseline + newly_complete,
        "newly_complete_skills": newly_complete,
    }


def summarize_decisions(bundles: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "AI_PREVALIDATED_HIGH": 0,
        "AI_PREVALIDATED_WITH_WARNING": 0,
        "TEACHER_REVIEW_REQUIRED": 0,
        "AI_REJECTED": 0,
        "FACT_CHECK_REQUIRED": 0,
    }
    for bundle in bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None:
                continue
            decision = ai_prevalidation_decision(item) or "UNKNOWN"
            if decision in counts:
                counts[decision] += 1
            if item.get("fact_check_required"):
                counts["FACT_CHECK_REQUIRED"] += 1
    return counts
