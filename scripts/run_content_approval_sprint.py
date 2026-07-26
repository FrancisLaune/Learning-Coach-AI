"""Build coverage-first LCAI-0012D3 approval-planning artifacts."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.content.approval_coverage import (  # noqa: E402
    build_pairing,
    coverage_impact,
    minimal_approval_plan,
    potential_tier_1,
    priority_key,
)

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"
DOCS = ROOT / "docs" / "phase2"


def _load(name: str) -> Any:
    return json.loads((QUALITY / name).read_text(encoding="utf-8"))


def _dump(name: str, value: Any) -> None:
    (QUALITY / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write(name: str, value: str) -> None:
    (DOCS / name).write_text(value.rstrip() + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    coverage: list[dict[str, Any]] = _load("lcai_0012d2_skill_coverage.json")
    queue: list[dict[str, Any]] = _load("lcai_0012d2_approval_queue.json")
    coverage_by_skill = {str(row["skill"]): row for row in coverage}
    priority: list[dict[str, Any]] = []
    for candidate in queue:
        item = dict(candidate)
        item["coverage_impact"] = coverage_impact(
            coverage_by_skill[str(candidate["skill"])],
            str(candidate["content_type"]),
        )
        item["approval_group"] = _approval_group(item)
        priority.append(item)
    priority.sort(key=priority_key)
    pairing = build_pairing(coverage, priority)
    plan = minimal_approval_plan(pairing)
    potential = potential_tier_1(pairing, plan)
    subjects = _subject_coverage(pairing, priority)

    _dump("lcai_0012d3_skill_pairing.json", pairing)
    _dump("lcai_0012d3_approval_priority.json", priority)
    _dump("lcai_0012d3_minimal_approval_plan.json", plan)
    _dump("lcai_0012d3_subject_coverage.json", subjects)

    decisions = Counter(str(item["quality_result"]) for item in queue)
    recommended = [item for item in priority if item["recommended_decision"] == "APPROVE"]
    summary = {
        "baseline": "3d1a70a",
        "drafts": len(queue),
        "pass": decisions["PASS"],
        "review": decisions["REVIEW"],
        "reject": decisions["REJECT"],
        "approval_candidates": len(recommended),
        "practice_candidates": sum(item["content_type"] == "practice" for item in recommended),
        "assessment_candidates": sum(item["content_type"] == "assessment" for item in recommended),
        "current_tier_1": sum(row["current_tier"] == 1 for row in pairing),
        "current_tier_2": sum(row["current_tier"] == 2 for row in pairing),
        "current_tier_3": sum(row["current_tier"] == 3 for row in pairing),
        "potential": potential,
        "actual_human_approvals": 0,
        "missing_practice": sum(not row["existing_approved_practice"] for row in pairing),
        "missing_assessment": sum(not row["existing_approved_assessment"] for row in pairing),
        "missing_both": sum(
            not row["existing_approved_practice"] and not row["existing_approved_assessment"] for row in pairing
        ),
        "skills_requiring_generation": sum(row["potential_tier"] != 1 and row["current_tier"] == 3 for row in pairing),
        "minimal_plan_approvals": len(plan),
        "minimal_plan_skills": sum(item["completes_tier_1"] for item in plan),
    }
    _reports(summary, pairing, plan, subjects)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def _approval_group(item: dict[str, Any]) -> str:
    impact = item["coverage_impact"]
    if impact["completes_tier_1"]:
        return "TIER1_COMPLETION_CANDIDATES"
    if item["subject"] == "MATHEMATICS" and item["deterministic_verification"] is not None:
        return "MATH_DETERMINISTIC_CANDIDATES"
    if item["answer_kind"] in {"single_choice", "multiple_choice"}:
        return "QCM_CANDIDATES"
    if item["subject"] == "FRENCH" and item["answer_kind"] != "open_response":
        return "FRENCH_CLOSED_ANSWER_CANDIDATES"
    if item["subject"] in {"SVT", "PHYSICS_CHEMISTRY"}:
        return "SCIENCE_CANDIDATES"
    return "OPEN_ANSWER_CANDIDATES" if item["answer_kind"] == "open_response" else "OTHER_CANDIDATES"


def _subject_coverage(
    pairing: list[dict[str, Any]],
    priority: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: Counter[tuple[str, str]] = Counter(
        (str(row["grade"]), str(row["subject"])) for row in priority if row["recommended_decision"] == "APPROVE"
    )
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in pairing:
        grouped[(str(row["grade"]), str(row["subject"]))].append(row)
    output: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        output.append(
            {
                "grade": key[0],
                "subject": key[1],
                "total_skills": len(rows),
                "tier_1": sum(row["current_tier"] == 1 for row in rows),
                "tier_2": sum(row["current_tier"] == 2 for row in rows),
                "tier_3": sum(row["current_tier"] == 3 for row in rows),
                "missing_practice": sum(not row["existing_approved_practice"] for row in rows),
                "missing_assessment": sum(not row["existing_approved_assessment"] for row in rows),
                "missing_both": sum(
                    not row["existing_approved_practice"] and not row["existing_approved_assessment"] for row in rows
                ),
                "approval_candidates_available": candidates[key],
            }
        )
    return output


def _reports(
    summary: dict[str, Any],
    pairing: list[dict[str, Any]],
    plan: list[dict[str, Any]],
    subjects: list[dict[str, Any]],
) -> None:
    potential = summary["potential"]
    _write(
        "LCAI-0012D3_APPROVAL_SPRINT_PLAN.md",
        f"""# LCAI-0012D3 — Approval Sprint Plan

- Baseline: `{summary["baseline"]}`
- Candidates: {summary["approval_candidates"]}
- Priority: immediate Tier 1 completion, then useful Tier 2 improvement.
- Every approval remains an explicit human action.
- Reviewer and approver separation is preserved.
- Actual human approvals performed by this build: 0.

Batch labels are review filters only and never trigger batch approval.
""",
    )
    _write(
        "LCAI-0012D3_MINIMAL_APPROVAL_PLAN.md",
        f"""# LCAI-0012D3 — Minimal Approval Plan

- Minimum approvals in the attainable plan: {len(plan)}
- Skills brought to Tier 1: {summary["minimal_plan_skills"]}
- Current Tier 1: {potential["current"]}
- Potential after 25 approvals: {potential["after_25"]}
- Potential after 50 approvals: {potential["after_50"]}
- Potential after 100 approvals: {potential["after_100"]}
- Potential after all recommended approvals: {potential["after_all_recommended"]}

One-approval completions precede two-approval completions. Skills without a safe
practice/assessment pair are excluded and classified in the pairing artifact.
""",
    )
    one = sum(row["approvals_to_tier_1"] == 1 for row in pairing)
    two = sum(row["approvals_to_tier_1"] == 2 for row in pairing)
    _write(
        "LCAI-0012D3_SKILL_PAIRING_REPORT.md",
        f"""# LCAI-0012D3 — Skill Pairing Report

- Skills analyzed: {len(pairing)}
- Tier 1 attainable with one approval: {one}
- Tier 1 attainable with two approvals: {two}
- Skills requiring generation: {summary["skills_requiring_generation"]}

The machine-readable report identifies existing Approved slots, the best Draft
for each missing slot, hard-gate status, score, recommendation and resulting tier.
""",
    )
    lines = [
        "# LCAI-0012D3 — Subject Coverage Report",
        "",
        "| Grade | Subject | Skills | T1 | T2 | T3 | Missing practice | Missing assessment | Missing both | Candidates |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        f"| {row['grade']} | {row['subject']} | {row['total_skills']} | {row['tier_1']} | "
        f"{row['tier_2']} | {row['tier_3']} | {row['missing_practice']} | "
        f"{row['missing_assessment']} | {row['missing_both']} | "
        f"{row['approval_candidates_available']} |"
        for row in subjects
    )
    _write("LCAI-0012D3_SUBJECT_COVERAGE_REPORT.md", "\n".join(lines))
    _write(
        "LCAI-0012D3_PRODUCTION_READINESS_REPORT.md",
        f"""# LCAI-0012D3 — Production Readiness

- Current Tier 1 / Tier 2 / Tier 3: {summary["current_tier_1"]} / {summary["current_tier_2"]} / {summary["current_tier_3"]}
- Missing practice / assessment / both: {summary["missing_practice"]} / {summary["missing_assessment"]} / {summary["missing_both"]}
- Actual human approvals: 0
- Actual tiers therefore remain unchanged.

Only Approved and production-enabled content is exposed. Draft and disabled content
remain excluded. Production remains limited pending explicit human decisions.

**4E/3E PRODUCTION STATUS: LIMITED**
""",
    )
    _write(
        "LCAI-0012D3_IMPLEMENTATION_REPORT.md",
        f"""# LCAI-0012D3 — Implementation Report

- Baseline: `{summary["baseline"]}`
- Coverage-first queue generated from {summary["drafts"]} existing Drafts.
- PASS / REVIEW / REJECT: {summary["pass"]} / {summary["review"]} / {summary["reject"]}.
- Practice / assessment candidates: {summary["practice_candidates"]} / {summary["assessment_candidates"]}.
- Pairing, minimal-plan and per-subject artifacts generated.
- Fast-review UI enriched with current and potential Skill status.
- Existing individual approval workflow and feature gating preserved.
- Automatic or simulated approvals: 0.
- Corrective generation: 0.

**READY FOR HUMAN APPROVAL SPRINT**
""",
    )


if __name__ == "__main__":
    run()
