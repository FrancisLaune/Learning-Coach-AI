"""Shared D4 human-review authorization across Wave 1 and Wave 2 campaigns."""

from __future__ import annotations

from typing import Any

from services.content.ai_review_calibration import is_ai_prevalidated_decision
from services.content.ai_pedagogical_review import is_authoritative_ai_review
from services.content.d4_wave1 import (
    PEDAGOGICAL_ATTENTION_THRESHOLD,
    PEDAGOGICAL_WARNING_FR,
    is_authorized_wave1_review_candidate,
    pedagogical_attention_reason,
    requires_pedagogical_attention,
)
from services.content.d4_wave1 import (
    classify_wave1_human_review as classify_human_review,
)

WAVE2_REVIEW_CAMPAIGN = "LCAI-0012D4-WAVE2"
WAVE_BAND_TIER3 = "TIER3_CORRECTIVE"
AUTHORIZED_WAVE2_SOURCES = frozenset({"existing", "generated"})


def is_authorized_wave2_review_candidate(item: dict[str, Any]) -> bool:
    """True when the item belongs to the active D4 Wave-2 human-review campaign."""
    if str(item.get("review_campaign")) != WAVE2_REVIEW_CAMPAIGN:
        return False
    if str(item.get("review_queue_status")) != "ACTIVE":
        return False
    if not item.get("version_id"):
        return False
    if str(item.get("wave_band", "")) != WAVE_BAND_TIER3:
        return False
    return str(item.get("candidate_source", "")) in AUTHORIZED_WAVE2_SOURCES


def is_authorized_d4_review_candidate(item: dict[str, Any]) -> bool:
    """True when the item belongs to an authorized D4 human-review campaign."""
    return is_authorized_wave1_review_candidate(item) or is_authorized_wave2_review_candidate(item)


def is_technically_blocked(item: dict[str, Any]) -> bool:
    return classify_human_review(item)["classification"] == "TECHNICALLY_BLOCKED"


def ai_prevalidation_decision(item: dict[str, Any]) -> str | None:
    if not is_authoritative_ai_review(item):
        return None
    decision = item.get("ai_prevalidation_decision") or (item.get("ai_pedagogical_review") or {}).get("decision")
    return str(decision) if decision else None


def is_ai_rejected(item: dict[str, Any]) -> bool:
    return ai_prevalidation_decision(item) == "AI_REJECTED"


def is_ai_prevalidated(item: dict[str, Any]) -> bool:
    return is_ai_prevalidated_decision(ai_prevalidation_decision(item))


def requires_teacher_review(item: dict[str, Any]) -> bool:
    decision = ai_prevalidation_decision(item)
    if decision == "TEACHER_REVIEW_REQUIRED":
        return True
    return bool(item.get("fact_check_required"))


def eligible_for_explicit_pedagogical_confirmation(
    item: dict[str, Any],
    *,
    explicit_confirmation: bool,
) -> bool:
    """True when low-score approval is allowed via an authorized review campaign."""
    if not explicit_confirmation:
        return False
    if not is_authorized_d4_review_candidate(item):
        return False
    if is_technically_blocked(item):
        return False
    if str(item.get("recommended_decision")) == "REJECT":
        return False
    return bool(item.get("hard_gates_passed"))


def can_individual_approve(
    item: dict[str, Any],
    *,
    reviewer: str,
    approver: str,
    explicit_pedagogical_confirmation: bool,
    review_status: str | None = None,
) -> bool:
    """True when one candidate may be approved through the normal D4 path."""
    if review_status == "APPROVED":
        return False
    if not reviewer.strip() or not approver.strip() or reviewer.strip() == approver.strip():
        return False
    if is_technically_blocked(item):
        return False
    if is_ai_rejected(item):
        return False
    if str(item.get("recommended_decision")) == "REJECT":
        return False
    if not item.get("hard_gates_passed"):
        return False
    if not is_authorized_d4_review_candidate(item):
        return False
    if is_ai_prevalidated(item) and str(item.get("ai_prevalidation_confidence")) == "HIGH":
        return True
    if requires_teacher_review(item):
        return eligible_for_explicit_pedagogical_confirmation(
            item,
            explicit_confirmation=explicit_pedagogical_confirmation,
        )
    high_confidence = item["recommended_decision"] == "APPROVE" and int(item["candidate_score"]) >= 80
    if high_confidence:
        return True
    return eligible_for_explicit_pedagogical_confirmation(
        item,
        explicit_confirmation=explicit_pedagogical_confirmation and requires_pedagogical_attention(item),
    )


def can_dual_approve(
    practice: dict[str, Any] | None,
    assessment: dict[str, Any] | None,
    *,
    reviewer: str,
    approver: str,
    practice_pedagogical_confirmation: bool,
    assessment_pedagogical_confirmation: bool,
    practice_status: str | None,
    assessment_status: str | None,
) -> bool:
    """Dual approval is allowed only when both slots would pass individually."""
    if practice is None or assessment is None:
        return False
    return can_individual_approve(
        practice,
        reviewer=reviewer,
        approver=approver,
        explicit_pedagogical_confirmation=practice_pedagogical_confirmation,
        review_status=practice_status,
    ) and can_individual_approve(
        assessment,
        reviewer=reviewer,
        approver=approver,
        explicit_pedagogical_confirmation=assessment_pedagogical_confirmation,
        review_status=assessment_status,
    )


def confidence_band(item: dict[str, Any] | None) -> str:
    if item is None:
        return "missing"
    if is_technically_blocked(item):
        return "blocked"
    if requires_pedagogical_attention(item):
        return "pedagogical"
    return "high"


__all__ = [
    "PEDAGOGICAL_ATTENTION_THRESHOLD",
    "PEDAGOGICAL_WARNING_FR",
    "ai_prevalidation_decision",
    "can_dual_approve",
    "can_individual_approve",
    "classify_human_review",
    "confidence_band",
    "eligible_for_explicit_pedagogical_confirmation",
    "is_ai_prevalidated",
    "is_ai_rejected",
    "is_authorized_d4_review_candidate",
    "is_authorized_wave2_review_candidate",
    "is_technically_blocked",
    "pedagogical_attention_reason",
    "requires_pedagogical_attention",
    "requires_teacher_review",
]
