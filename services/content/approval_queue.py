"""Dynamic LCAI-0012D3A human-approval queue."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from collections.abc import Iterable
from typing import Any

from services.content.approval_coverage import (
    build_pairing,
    coverage_impact,
    minimal_approval_plan,
    potential_tier_1,
)

PRIORITY_LABELS = {
    "TIER1_IMMEDIATE": "🔴 P1 — Tier 1 immédiat",
    "TIER1_PLAN": "🟠 P2 — Plan Tier 1",
    "TIER2_PROGRESS": "🟡 P3 — Progression Tier 2",
    "COVERAGE_USEFUL": "🔵 P4 — Couverture utile",
    "NO_TIER_IMPACT": "⚪ P5 — Sans impact direct",
    "HUMAN_REVIEW": "🟣 Revue pédagogique",
}

PRIORITY_ORDER = {
    "TIER1_IMMEDIATE": 1,
    "TIER1_PLAN": 2,
    "TIER2_PROGRESS": 3,
    "COVERAGE_USEFUL": 4,
    "NO_TIER_IMPACT": 5,
    "HUMAN_REVIEW": 6,
}

REVIEW_STATUSES = (
    "PENDING",
    "IN_REVIEW",
    "APPROVED",
    "REJECTED",
    "KEEP_REVIEW",
    "SKIPPED",
)


def build_dynamic_queue(
    base_queue: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    review_statuses: dict[int, str],
    *,
    skipped: set[int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Recompute priority and rank from current Approved coverage."""
    skipped = skipped or set()
    coverage_by_skill = {str(row["skill"]): row for row in coverage_rows}
    pending: list[dict[str, Any]] = []
    for source in base_queue:
        version_id = int(source["version_id"])
        review_status = "SKIPPED" if version_id in skipped else review_statuses.get(version_id, "PENDING")
        if review_status in {"APPROVED", "REJECTED", "KEEP_REVIEW", "SKIPPED"}:
            continue
        item = dict(source)
        item["review_status"] = review_status
        item["coverage_impact"] = coverage_impact(
            coverage_by_skill[str(item["skill"])],
            str(item["content_type"]),
        )
        pending.append(item)

    recommended = [item for item in pending if item["recommended_decision"] == "APPROVE"]
    pairing = build_pairing(coverage_rows, recommended)
    plan = minimal_approval_plan(pairing)
    plan_versions = {int(item["candidate"]["version_id"]) for item in plan}

    for item in pending:
        impact = item["coverage_impact"]
        version_id = int(item["version_id"])
        if item["recommended_decision"] != "APPROVE":
            status = "HUMAN_REVIEW"
        elif impact["completes_tier_1"]:
            status = "TIER1_IMMEDIATE"
        elif version_id in plan_versions:
            status = "TIER1_PLAN"
        elif impact["improves_tier_2"]:
            status = "TIER2_PROGRESS"
        elif item.get("missing_coverage") and not impact["no_coverage_impact"]:
            status = "COVERAGE_USEFUL"
        else:
            status = "NO_TIER_IMPACT"
        item["approval_priority_status"] = status

    pending.sort(key=_priority_sort_key)
    for rank, item in enumerate(pending, 1):
        item["approval_priority_rank"] = rank

    potential = potential_tier_1(pairing, plan)
    summary = {
        "minimal_plan_remaining": len(plan),
        "current_tier_1": potential["current"],
        "additional_tier_1": sum(bool(item["completes_tier_1"]) for item in plan),
        "maximum_tier_1": potential["after_all_recommended"],
        "priority_counts": dict(Counter(str(item["approval_priority_status"]) for item in pending)),
    }
    return pending, summary


def filter_queue(
    queue: list[dict[str, Any]],
    *,
    priority_filter: str = "Plan minimal — prioritaire",
    priority_levels: Iterable[str] = ("P1", "P2"),
    grade: str = "Tous",
    subjects: Iterable[str] = (),
    tier1_only: bool = False,
    priority_4e: bool = False,
    balance_subjects: bool = False,
) -> list[dict[str, Any]]:
    """Apply the visible D3A filters and optional presentation modes."""
    selected_levels = set(priority_levels)
    level_by_status = {
        "TIER1_IMMEDIATE": "P1",
        "TIER1_PLAN": "P2",
        "TIER2_PROGRESS": "P3",
        "COVERAGE_USEFUL": "P4",
        "NO_TIER_IMPACT": "P5",
    }
    statuses_by_filter = {
        "Plan minimal — prioritaire": {"TIER1_IMMEDIATE", "TIER1_PLAN"},
        "Complète immédiatement un Tier 1": {"TIER1_IMMEDIATE"},
        "Tier 3 → Tier 2": {"TIER2_PROGRESS"},
        "Sans impact direct": {"NO_TIER_IMPACT"},
    }
    subject_set = set(subjects)
    result = []
    for item in queue:
        impact = item["coverage_impact"]
        if (
            priority_filter in statuses_by_filter
            and item["approval_priority_status"] not in statuses_by_filter[priority_filter]
        ):
            continue
        if priority_filter == "Évaluation manquante" and impact["current"]["assessment_approved"]:
            continue
        if priority_filter == "Entraînement manquant" and impact["current"]["practice_approved"]:
            continue
        if priority_filter == "Tous les candidats recommandés" and item["recommended_decision"] != "APPROVE":
            continue
        level = level_by_status.get(str(item["approval_priority_status"]))
        if level is not None and selected_levels and level not in selected_levels:
            continue
        if grade != "Tous" and item["grade"] != grade:
            continue
        if subject_set and item["subject"] not in subject_set:
            continue
        if tier1_only and not impact["completes_tier_1"]:
            continue
        result.append(item)

    result.sort(
        key=lambda item: (
            0 if priority_4e and item["grade"] == "FR-4E" else 1 if priority_4e else 0,
            int(item["approval_priority_rank"]),
        )
    )
    return _balance_by_subject(result) if balance_subjects else result


def _priority_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        PRIORITY_ORDER[str(item["approval_priority_status"])],
        -int(item["candidate_score"]),
        str(item["grade"]),
        str(item["subject"]),
        str(item["skill"]),
        str(item["code"]),
    )


def _balance_by_subject(queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for item in queue:
        groups[str(item["subject"])].append(item)
    output: list[dict[str, Any]] = []
    subjects = sorted(groups)
    while any(groups.values()):
        for subject in subjects:
            if groups[subject]:
                output.append(groups[subject].popleft())
    return output
