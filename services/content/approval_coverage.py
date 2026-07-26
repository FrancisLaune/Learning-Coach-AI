"""Coverage-first planning for the human content approval workflow."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def normalized_type(value: str) -> str:
    """Collapse guided practice into the production practice slot."""
    return "practice" if value in {"practice", "guided_practice"} else value


def tier(practice: bool, assessment: bool) -> int:
    if practice and assessment:
        return 1
    if practice or assessment:
        return 2
    return 3


def coverage_impact(
    coverage: dict[str, Any],
    content_type: str,
) -> dict[str, Any]:
    """Describe the exact production-coverage effect of one approval."""
    slot = normalized_type(content_type)
    practice = int(coverage["approved_practice"]) > 0
    assessment = int(coverage["approved_assessment"]) > 0
    current_tier = tier(practice, assessment)
    adds_practice = slot == "practice" and not practice
    adds_assessment = slot == "assessment" and not assessment
    after_practice = practice or adds_practice
    after_assessment = assessment or adds_assessment
    potential_tier = tier(after_practice, after_assessment)
    return {
        "adds_practice": adds_practice,
        "adds_assessment": adds_assessment,
        "completes_tier_1": current_tier != 1 and potential_tier == 1,
        "improves_tier_2": current_tier == 3 and potential_tier == 2,
        "no_coverage_impact": current_tier == potential_tier,
        "current": {
            "practice_approved": practice,
            "assessment_approved": assessment,
            "tier": current_tier,
        },
        "potential": {
            "practice_approved": after_practice,
            "assessment_approved": after_assessment,
            "tier": potential_tier,
        },
    }


def priority_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    """Put immediate Tier-1 gains first, then useful Tier-2 gains."""
    impact = candidate["coverage_impact"]
    recommendation = str(candidate["recommended_decision"])
    group = (
        0
        if recommendation == "APPROVE" and impact["completes_tier_1"]
        else 1
        if recommendation == "APPROVE" and impact["improves_tier_2"]
        else 2
        if recommendation == "APPROVE" and not impact["no_coverage_impact"]
        else 3
        if recommendation == "APPROVE"
        else 4
        if recommendation == "KEEP_FOR_REVIEW"
        else 5
    )
    return (
        group,
        -int(candidate["candidate_score"]),
        str(candidate["grade"]),
        str(candidate["subject"]),
        str(candidate["skill"]),
        0 if normalized_type(str(candidate["content_type"])) == "practice" else 1,
        str(candidate["code"]),
    )


def build_pairing(
    coverage_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Select the best safe practice and assessment candidate for every Skill."""
    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_skill[str(candidate["skill"])].append(candidate)
    output: list[dict[str, Any]] = []
    for coverage in coverage_rows:
        rows = by_skill[str(coverage["skill"])]

        def best(
            slot: str,
            candidate_rows: list[dict[str, Any]] = rows,
        ) -> dict[str, Any] | None:
            eligible = [
                row
                for row in candidate_rows
                if normalized_type(str(row["content_type"])) == slot
                and row["recommended_decision"] == "APPROVE"
                and row["hard_gates_passed"]
            ]
            return min(eligible, key=priority_key, default=None)

        practice = best("practice")
        assessment = best("assessment")
        current_practice = int(coverage["approved_practice"]) > 0
        current_assessment = int(coverage["approved_assessment"]) > 0
        approvals_needed: list[dict[str, Any]] = []
        if not current_practice and practice:
            approvals_needed.append(practice)
        if not current_assessment and assessment:
            approvals_needed.append(assessment)
        potential_practice = current_practice or practice is not None
        potential_assessment = current_assessment or assessment is not None
        output.append(
            {
                "grade": coverage["grade"],
                "subject": coverage["subject"],
                "chapter": coverage["chapter"],
                "skill": coverage["skill"],
                "existing_approved_practice": current_practice,
                "existing_approved_assessment": current_assessment,
                "current_tier": tier(current_practice, current_assessment),
                "best_draft_practice_candidate": _candidate_summary(practice),
                "best_draft_assessment_candidate": _candidate_summary(assessment),
                "approvals_to_tier_1": (len(approvals_needed) if potential_practice and potential_assessment else None),
                "potential_tier": tier(potential_practice, potential_assessment),
                "missing_candidate_classification": _missing_classification(
                    rows,
                    current_practice,
                    current_assessment,
                    practice,
                    assessment,
                ),
            }
        )
    return output


def _candidate_summary(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "code": candidate["code"],
        "content_id": candidate["content_id"],
        "version_id": candidate["version_id"],
        "quality": candidate["quality_result"],
        "hard_gates_passed": candidate["hard_gates_passed"],
        "score": candidate["candidate_score"],
        "recommendation": candidate["recommended_decision"],
    }


def _missing_classification(
    rows: list[dict[str, Any]],
    has_practice: bool,
    has_assessment: bool,
    practice: dict[str, Any] | None,
    assessment: dict[str, Any] | None,
) -> list[str]:
    reasons: list[str] = []
    types = {normalized_type(str(row["content_type"])) for row in rows}
    if not has_practice and practice is None:
        reasons.append("NO_PRACTICE_CANDIDATE" if "practice" not in types else "NO_VALID_CANDIDATE")
    if not has_assessment and assessment is None:
        reasons.append("NO_ASSESSMENT_CANDIDATE" if "assessment" not in types else "NO_VALID_CANDIDATE")
    if rows and all(str(row["answer_kind"]) == "open_response" for row in rows):
        reasons.append("ONLY_OPEN_RESPONSE")
    if any("SOURCE_DOCUMENT_REQUIRED" in str(row.get("quality_reason", "")) for row in rows):
        reasons.append("RESOURCE_DEPENDENCY")
    if not reasons and tier(has_practice, has_assessment) != 1:
        reasons.append("PEDAGOGICAL_REVIEW_REQUIRED")
    return list(dict.fromkeys(reasons))


def minimal_approval_plan(pairing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the minimum candidate set that maximizes attainable Tier-1 Skills."""
    plan: list[dict[str, Any]] = []
    eligible = [row for row in pairing if row["current_tier"] != 1 and row["approvals_to_tier_1"] in {1, 2}]
    eligible.sort(
        key=lambda row: (
            int(row["approvals_to_tier_1"]),
            str(row["grade"]),
            str(row["subject"]),
            str(row["skill"]),
        )
    )
    sequence = 0
    for row in eligible:
        candidates = [
            candidate
            for slot, candidate in (
                ("practice", row["best_draft_practice_candidate"]),
                ("assessment", row["best_draft_assessment_candidate"]),
            )
            if candidate is not None and not bool(row[f"existing_approved_{slot}"])
        ]
        for candidate in candidates:
            sequence += 1
            plan.append(
                {
                    "sequence": sequence,
                    "grade": row["grade"],
                    "subject": row["subject"],
                    "chapter": row["chapter"],
                    "skill": row["skill"],
                    "content_type": ("practice" if candidate == row["best_draft_practice_candidate"] else "assessment"),
                    "candidate": candidate,
                    "approvals_required_for_skill": row["approvals_to_tier_1"],
                    "completes_tier_1": sequence == 0,
                }
            )
        if candidates:
            plan[-1]["completes_tier_1"] = True
    return plan


def potential_tier_1(
    pairing: list[dict[str, Any]],
    plan: list[dict[str, Any]],
    limits: tuple[int, ...] = (25, 50, 100),
) -> dict[str, int]:
    current = sum(row["current_tier"] == 1 for row in pairing)
    result: dict[str, int] = {"current": current}
    for limit in limits:
        result[f"after_{limit}"] = current + sum(bool(item["completes_tier_1"]) for item in plan[:limit])
    result["after_all_recommended"] = current + sum(
        row["current_tier"] != 1 and row["potential_tier"] == 1 for row in pairing
    )
    return result
