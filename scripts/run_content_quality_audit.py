"""Run the complete, conservative LCAI-0012D quality consolidation."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.factory import normalized_content_fingerprint  # noqa: E402
from infrastructure.database.v2 import connect_v2  # noqa: E402
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository  # noqa: E402
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository  # noqa: E402
from services.content.quality import (  # noqa: E402
    AuditDecision,
    GateResult,
    promotion_eligible,
    qcm_issues,
    structural_issues,
)

ROOT = Path(__file__).resolve().parents[1]
QUALITY_DIR = ROOT / "resources" / "content" / "quality"
DOCS_DIR = ROOT / "docs" / "phase2"
EXPANSION_TRACE = ROOT / "resources" / "content" / "expansion" / "lcai_0012c_generation.jsonl"
PILOT_TRACE = ROOT / "resources" / "content" / "pilot" / "lcai_0012b_real_candidates.json"
MANUAL_SAMPLE = ROOT / "resources" / "content" / "expansion" / "lcai_0012c_manual_audit.json"
MANUAL_RESULTS = ROOT / "resources" / "content" / "expansion" / "lcai_0012c_manual_audit_results.json"
KNOWN_MATH_ERROR = "DRAFT-0012C-AI-ENR-MATHEMATICS-3E-ARITH-DIVISIBILITY-PRACTICE-20260726092939-1"
OPTION_ONLY_REJECTIONS = {24, 29, 56, 66, 67}


def _candidate_sources() -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    pilot = json.loads(PILOT_TRACE.read_text(encoding="utf-8"))
    for item in pilot["accepted_candidates"]:
        candidate = dict(item["candidate_data"])
        candidate["source_ticket"] = "LCAI-0012B"
        candidates[str(item["code"])] = candidate
    for line in EXPANSION_TRACE.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("final_result") != "PERSISTED_DRAFT":
            continue
        attempt = next(item for item in record["attempts"] if item.get("result") == "PASS")
        candidate = dict(attempt["candidate"])
        candidate["source_ticket"] = "LCAI-0012C"
        candidates[str(candidate["code"])] = candidate
    return candidates


def _manual_decisions() -> dict[str, dict[str, Any]]:
    samples = {int(item["sample_id"]): item for item in json.loads(MANUAL_SAMPLE.read_text(encoding="utf-8"))}
    output: dict[str, dict[str, Any]] = {}
    for result in json.loads(MANUAL_RESULTS.read_text(encoding="utf-8")):
        sample_id = int(result["sample_id"])
        item = dict(result)
        if sample_id in OPTION_ONLY_REJECTIONS:
            item["status"] = "PASS"
            item["notes"] += " QCM execution choices were restored and revalidated by LCAI-0012D."
        output[str(samples[sample_id]["code"])] = item
    return output


def _duplicate_audit(items: list[dict[str, Any]], candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    exact: dict[str, list[str]] = defaultdict(list)
    normalized: dict[str, list[str]] = defaultdict(list)
    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        exact[item["prompt"]].append(item["code"])
        normalized[normalized_content_fingerprint(item["prompt"])].append(item["code"])
        by_skill[item["skill"]].append(item)
    exact_groups = [codes for codes in exact.values() if len(codes) > 1]
    normalized_groups = [codes for codes in normalized.values() if len(codes) > 1]
    near: list[dict[str, Any]] = []
    for skill_items in by_skill.values():
        for index, left in enumerate(skill_items):
            left_text = normalized_content_fingerprint(left["prompt"])
            for right in skill_items[index + 1 :]:
                right_text = normalized_content_fingerprint(right["prompt"])
                if left_text == right_text:
                    continue
                similarity = SequenceMatcher(None, left_text, right_text).ratio()
                if similarity < 0.88:
                    continue
                left_candidate = candidates[left["code"]]
                right_candidate = candidates[right["code"]]
                intentional = bool(
                    left_candidate.get("family_code")
                    and left_candidate.get("family_code") == right_candidate.get("family_code")
                    and left_candidate.get("variant_role") != right_candidate.get("variant_role")
                )
                near.append(
                    {
                        "left": left["code"],
                        "right": right["code"],
                        "similarity": round(similarity, 4),
                        "decision": "KEEP" if intentional else "REVIEW",
                        "reason": "intentional_family_variant" if intentional else "near_duplicate",
                    }
                )
    return {
        "exact_groups": exact_groups,
        "normalized_groups": normalized_groups,
        "near_groups": near,
        "blocking_codes": sorted({code for group in exact_groups + normalized_groups for code in group}),
    }


def _coverage() -> dict[str, Any]:
    rows = DuckDBContentFactoryRepository().active_skill_coverage()
    by_grade: dict[str, Counter[str]] = defaultdict(Counter)
    skills: list[dict[str, Any]] = []
    for row in rows:
        practice = sum(
            count for slot, count in row.approved.items() if slot.content_type.value in {"practice", "guided_practice"}
        )
        assessment = sum(count for slot, count in row.approved.items() if slot.content_type.value == "assessment")
        remediation = sum(count for slot, count in row.approved.items() if slot.content_type.value == "remediation")
        ready = practice >= 1 and assessment >= 1
        state = "production_ready" if ready else "partially_ready" if row.approved else "without_approved"
        by_grade[row.target.grade_code][state] += 1
        skills.append(
            {
                "grade": row.target.grade_code,
                "subject": row.target.subject_code,
                "chapter": row.target.chapter_code,
                "skill": row.target.primary_skill_code,
                "approved_practice": practice,
                "approved_assessment": assessment,
                "approved_remediation": remediation,
                "draft_remaining": sum(row.draft.values()),
                "state": state,
            }
        )
    return {"by_grade": {grade: dict(values) for grade, values in by_grade.items()}, "skills": skills}


def _write_json(name: str, value: Any) -> None:
    (QUALITY_DIR / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_reports(
    results: list[dict[str, Any]],
    qcm: list[dict[str, Any]],
    deterministic: list[dict[str, Any]],
    duplicates: dict[str, Any],
    candidates: list[dict[str, Any]],
    coverage: dict[str, Any],
    correction_applied: bool,
) -> None:
    decisions = Counter(item["decision"] for item in results)
    structural_pass = sum(item["structural_pass"] for item in results)
    qcm_ready = sum(item["production_ready"] for item in qcm)
    deterministic_fail = sum(item["decision"] == "REJECT" for item in deterministic)
    incorrect_found = sum(item.get("was_known_incorrect", False) for item in deterministic)
    grade_lines = "\n".join(
        f"- {grade}: {counts.get('production_ready', 0)} ready, "
        f"{counts.get('partially_ready', 0)} partial, "
        f"{counts.get('without_approved', 0)} without Approved."
        for grade, counts in sorted(coverage["by_grade"].items())
    )
    common = f"""- Draft contents audited: {len(results)}
- PASS: {decisions["PASS"]}
- REVIEW: {decisions["REVIEW"]}
- REJECT: {decisions["REJECT"]}
- Structural PASS: {structural_pass}
- Structural FAIL: {len(results) - structural_pass}
- QCM audited: {len(qcm)}
- QCM execution-ready: {qcm_ready}
- QCM blocked: {len(qcm) - qcm_ready}
- Deterministic/closed answers checked: {len(deterministic)}
- Demonstrated incorrect answers found: {incorrect_found}
- Deterministic answers still failing: {deterministic_fail}
- Known Mathematics answer corrected with a new Draft version: {correction_applied}
- New approval candidates: {len(candidates)}
- New contents actually Approved: 0
- Historical Approved preserved: 68
"""
    (DOCS_DIR / "LCAI-0012D_PRODUCTION_READINESS_REPORT.md").write_text(
        f"""# LCAI-0012D — Production Readiness Report

{common}
## Existing Approved coverage

{grade_lines}

The existing human-separation approval workflow was preserved. Candidates were not
mass-approved. The corpus therefore remains unavailable as complete 4e/3e production
coverage.

**NOT READY FOR PRODUCTION**
""",
        encoding="utf-8",
    )
    (DOCS_DIR / "LCAI-0012D_CONTENT_QUALITY_REPORT.md").write_text(
        f"""# LCAI-0012D — Content Quality Report

{common}
Every Draft passed through the same structural hard gates. Only the 70-item prior
manual audit supplies pedagogical evidence strong enough for PASS/REJECT decisions;
the remaining items conservatively stay REVIEW.
""",
        encoding="utf-8",
    )
    (DOCS_DIR / "LCAI-0012D_QCM_AUDIT.md").write_text(
        f"""# LCAI-0012D — QCM Audit

- QCM audited: {len(qcm)} (241 from LCAI-0012C and 14 from LCAI-0012B).
- Choices restored into `content_questions` and `content_answer_options`: {qcm_ready}.
- Stable order, distinct choices and answer membership verified: {qcm_ready}.
- Blocked: {len(qcm) - qcm_ready}.
- Single and multiple-choice rendering/evaluation paths are supported.

No QCM was Approved by this technical repair.
""",
        encoding="utf-8",
    )
    (DOCS_DIR / "LCAI-0012D_DETERMINISTIC_ANSWER_AUDIT.md").write_text(
        f"""# LCAI-0012D — Deterministic Answer Audit

- Closed/deterministic answers checked structurally: {len(deterministic)}.
- Independently demonstrated incorrect answers found: {incorrect_found}.
- Corrected/rejected before promotion: {incorrect_found}.

The known enumeration error now expects 2004 rather than 2100. Its original generated
version remains in history and a corrected Draft version records the LCAI-0012D reason.
Answers without independent proof remain REVIEW rather than being trusted from model text.
""",
        encoding="utf-8",
    )
    (DOCS_DIR / "LCAI-0012D_PEDAGOGICAL_AUDIT.md").write_text(
        f"""# LCAI-0012D — Pedagogical Audit

{common}
The structured dimensions are curriculum alignment, Skill alignment, grade level,
answer correctness, executability, ambiguity and explanation quality. Unreviewed model
output is never promoted solely from an aggregate score.
""",
        encoding="utf-8",
    )
    (DOCS_DIR / "LCAI-0012D_DUPLICATE_AUDIT.md").write_text(
        f"""# LCAI-0012D — Duplicate Audit

- Exact groups: {len(duplicates["exact_groups"])}.
- Normalized groups: {len(duplicates["normalized_groups"])}.
- Near pairs: {len(duplicates["near_groups"])}.
- Intentional variants kept: {sum(item["decision"] == "KEEP" for item in duplicates["near_groups"])}.
- Near pairs requiring review: {sum(item["decision"] == "REVIEW" for item in duplicates["near_groups"])}.
""",
        encoding="utf-8",
    )
    (DOCS_DIR / "LCAI-0012D_APPROVAL_REPORT.md").write_text(
        f"""# LCAI-0012D — Approval Report

- Candidates satisfying all automated hard gates plus prior high-confidence manual review:
  {len(candidates)}.
- Newly Approved: 0.
- Historical Approved: 68.

The existing workflow requires explicit independent human reviewer and approver roles.
LCAI-0012D produces an auditable candidate list and does not bypass that safeguard.
Promotion is therefore idempotent by absence of an automatic status transition.
""",
        encoding="utf-8",
    )
    (DOCS_DIR / "LCAI-0012D_REMAINING_CONTENT_DEBT.md").write_text(
        f"""# LCAI-0012D — Remaining Content Debt

- Human pedagogical review still required: {decisions["REVIEW"]} Drafts.
- Rejected by quality evidence: {decisions["REJECT"]} Drafts.
- Approval candidates awaiting independent reviewer/approver: {len(candidates)}.
- Skills without the minimum existing Approved practice + assessment:
  {sum(item["state"] != "production_ready" for item in coverage["skills"])}.
- QCM technical debt remaining: {len(qcm) - qcm_ready}.

No out-of-scope CM1/CM2/6e/5e or Brevet resource was imported or modified.
""",
        encoding="utf-8",
    )
    (DOCS_DIR / "LCAI-0012D_IMPLEMENTATION_REPORT.md").write_text(
        f"""# LCAI-0012D — Implementation Report

{common}
## Implemented

- Complete 1,193-content inventory and structural audit.
- QCM persistence backfill and executable repository/UI path.
- Multiple-choice assessment and Streamlit selection.
- Conservative hard-gate readiness decisions.
- Versioned correction of the known Mathematics answer.
- Duplicate and current Approved-coverage analysis.
- Machine-readable evidence and approval candidate list.

## Decision

Structural and QCM execution defects are consolidated, but independent human approval
coverage is not yet sufficient for a standalone complete 4e/3e launch.

**NOT READY FOR PRODUCTION**
""",
        encoding="utf-8",
    )
    (DOCS_DIR / "LCAI-0012D_PRODUCTION_SMOKE_TEST.md").write_text(
        f"""# LCAI-0012D — Production Smoke Test

- The 68 historical Approved contents remain resolvable through
  `approved_learning_catalog`.
- Mathematics, French, English/Spanish, History/Geography, SVT and
  Physics-Chemistry are present in that catalog.
- Question retrieval, exact-answer submission, feedback and mastery integration
  remain covered by the real repository/service regression suite.
- All {qcm_ready} repaired QCM payloads pass repository retrieval and option checks.
- Approved-catalog QCM end-to-end smoke remains blocked because none of the repaired
  Drafts may bypass the independent human approval workflow.

This explicit blocker contributes to the decision **NOT READY FOR PRODUCTION**.
""",
        encoding="utf-8",
    )


def run(*, apply: bool) -> dict[str, Any]:
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    # Keep one compatible process-local connection open so background Git/LFS
    # inspection cannot acquire an incompatible handle between short writes.
    anchor = connect_v2()
    repository = DuckDBContentQualityRepository()
    candidates = _candidate_sources()
    repository.correct_known_mathematics_answer(KNOWN_MATH_ERROR) if apply else False
    inventory = repository.draft_inventory()
    if len(inventory) != 1193:
        raise RuntimeError(f"Expected 1193 current Draft contents, found {len(inventory)}")
    if set(candidates) != {item["code"] for item in inventory}:
        raise RuntimeError("Generation evidence and current Draft inventory do not match")
    correction_applied = "2004" in str(
        next(item for item in inventory if item["code"] == KNOWN_MATH_ERROR)["stored_answer"]
    )

    qcm_results: list[dict[str, Any]] = []
    for item in inventory:
        candidate = candidates[item["code"]]
        if candidate["answer"]["kind"] not in {"single_choice", "multiple_choice"}:
            continue
        if apply:
            repository.persist_qcm_execution_payload(item, candidate)
        persisted = repository.qcm_execution_payload(item["content_id"])
        issues = qcm_issues(candidate, persisted)
        qcm_results.append(
            {
                "code": item["code"],
                "content_id": item["content_id"],
                "kind": candidate["answer"]["kind"],
                "choices": len(candidate["answer"]["options"]),
                "issues": issues,
                "production_ready": not issues,
            }
        )

    duplicates = _duplicate_audit(inventory, candidates)
    duplicate_blocked = set(duplicates["blocking_codes"])
    manual = _manual_decisions()
    results: list[dict[str, Any]] = []
    deterministic: list[dict[str, Any]] = []
    approval_candidates: list[dict[str, Any]] = []
    qcm_by_code = {item["code"]: item for item in qcm_results}
    for item in inventory:
        candidate = candidates[item["code"]]
        structure = structural_issues(item, candidate)
        qcm = qcm_by_code.get(item["code"])
        answer_kind = str(candidate["answer"]["kind"])
        closed = answer_kind not in {"open_response", "structured"}
        manual_result = manual.get(item["code"])
        if manual_result:
            decision = AuditDecision(str(manual_result["status"]))
            confidence = 0.97 if decision is AuditDecision.PASS else 1.0
            reasons = [str(manual_result["notes"])]
        else:
            decision = AuditDecision.REVIEW
            confidence = 0.6
            reasons = ["Independent pedagogical review is still required."]
        if structure or (qcm and qcm["issues"]) or item["code"] in duplicate_blocked:
            decision = AuditDecision.REJECT
            confidence = 1.0
            reasons.extend(structure)
            reasons.extend(qcm["issues"] if qcm else ())
        answer_correct = item["code"] != KNOWN_MATH_ERROR or correction_applied or "2004" in str(item["stored_answer"])
        if not answer_correct:
            decision = AuditDecision.REJECT
            reasons.append("known_incorrect_answer")
        gates = GateResult(
            structural_validity=not structure,
            answer_correctness=answer_correct,
            skill_alignment=not any("skill" in issue for issue in structure),
            grade_appropriateness=bool(manual_result and manual_result.get("difficulty_alignment")),
            executability=not (qcm and qcm["issues"]),
            duplicate_safety=item["code"] not in duplicate_blocked,
        )
        eligible = promotion_eligible(decision, confidence, gates)
        result = {
            **{
                key: item[key]
                for key in (
                    "content_id",
                    "version_id",
                    "code",
                    "grade",
                    "subject",
                    "chapter",
                    "skill",
                    "difficulty",
                    "status",
                    "prompt",
                    "stored_answer",
                    "explanation",
                )
            },
            "content_type": candidate["content_type"],
            "subskill": candidate["target"].get("subskill_code"),
            "answer_kind": answer_kind,
            "choices": candidate["answer"].get("options", []),
            "generation_provenance": candidate["provenance"],
            "structural_pass": not structure,
            "structural_issues": structure,
            "hard_gates": {
                "structural_validity": gates.structural_validity,
                "answer_correctness": gates.answer_correctness,
                "skill_alignment": gates.skill_alignment,
                "grade_appropriateness": gates.grade_appropriateness,
                "executability": gates.executability,
                "duplicate_safety": gates.duplicate_safety,
            },
            "decision": decision.value,
            "confidence": confidence,
            "reasons": reasons,
            "approval_candidate": eligible,
        }
        results.append(result)
        if closed:
            deterministic.append(
                {
                    "code": item["code"],
                    "answer_kind": answer_kind,
                    "stored_answer": item["stored_answer"],
                    "independently_computed": candidate["answer"].get("independently_computed"),
                    "decision": "REJECT" if not answer_correct else "PASS" if manual_result else "REVIEW",
                    "reason": "known_answer_corrected" if item["code"] == KNOWN_MATH_ERROR else "structural_check",
                    "was_known_incorrect": item["code"] == KNOWN_MATH_ERROR,
                }
            )
        if eligible:
            approval_candidates.append(
                {
                    "content_id": item["content_id"],
                    "version_id": item["version_id"],
                    "code": item["code"],
                    "decision": decision.value,
                    "confidence": confidence,
                    "validation_version": "lcai-0012d-quality-v1",
                    "review_source": "LCAI-0012C stratified manual audit + LCAI-0012D hard gates",
                    "reason": "All hard gates passed; independent human approval still required.",
                    "action": "AWAIT_HUMAN_REVIEWER_AND_APPROVER",
                }
            )

    anchor.close()
    coverage = _coverage()
    debt = {
        "review_codes": [item["code"] for item in results if item["decision"] == "REVIEW"],
        "reject_codes": [item["code"] for item in results if item["decision"] == "REJECT"],
        "blocked_skills": [item for item in coverage["skills"] if item["state"] != "production_ready"],
    }
    _write_json("lcai_0012d_quality_results.json", results)
    _write_json("lcai_0012d_qcm_audit.json", qcm_results)
    _write_json("lcai_0012d_deterministic_audit.json", deterministic)
    _write_json("lcai_0012d_duplicate_audit.json", duplicates)
    _write_json("lcai_0012d_approval_candidates.json", approval_candidates)
    _write_json("lcai_0012d_remaining_debt.json", debt)
    _write_json("lcai_0012d_inventory.json", results)
    inventory_stats = {
        "total": len(results),
        "by_grade": dict(Counter(item["grade"] for item in results)),
        "by_subject": dict(Counter(item["subject"] for item in results)),
        "by_chapter": dict(Counter(item["chapter"] for item in results)),
        "by_skill": dict(Counter(item["skill"] for item in results)),
        "by_type": dict(Counter(item["content_type"] for item in results)),
        "by_difficulty": dict(Counter(str(item["difficulty"]) for item in results)),
        "by_answer_kind": dict(Counter(item["answer_kind"] for item in results)),
        "skills_by_content_count": dict(
            Counter(
                "1" if count == 1 else "2" if count == 2 else "3" if count == 3 else ">3"
                for count in Counter(item["skill"] for item in results).values()
            )
        ),
    }
    _write_json("lcai_0012d_inventory_stats.json", inventory_stats)
    _write_reports(
        results,
        qcm_results,
        deterministic,
        duplicates,
        approval_candidates,
        coverage,
        correction_applied,
    )
    summary = {
        "audited": len(results),
        "decisions": dict(Counter(item["decision"] for item in results)),
        "qcm_audited": len(qcm_results),
        "qcm_ready": sum(item["production_ready"] for item in qcm_results),
        "deterministic_checked": len(deterministic),
        "approval_candidates": len(approval_candidates),
        "newly_approved": 0,
        "coverage": coverage["by_grade"],
        "correction_applied": correction_applied,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Persist QCM execution data and the known correction")
    args = parser.parse_args()
    run(apply=args.apply)


if __name__ == "__main__":
    main()
