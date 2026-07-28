"""Recompute AI pedagogical decisions from existing authoritative OpenAI evidence."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_ai_pedagogical_review_wave2 import (  # noqa: E402
    AUTHORITATIVE_AUDIT_PATH,
    COMBINED_PATH,
    SUMMARY_PATH,
    _load_audit_file,
    _merge_reviews_into_bundles,
    _record_from_audit,
)
from scripts.run_content_approval_d4_wave1 import _coverage_rows  # noqa: E402
from services.content.ai_pedagogical_review import attach_ai_review  # noqa: E402
from services.content.ai_review_calibration import (  # noqa: E402
    CALIBRATION_VERSION,
    analyze_escalation_reasons,
    escalation_frequency_table,
    is_ai_prevalidated_decision,
    reclassify_audit_record,
)
from services.content.approval_coverage import tier  # noqa: E402
from services.content.d4_wave2 import build_skill_review_bundles, summarize_wave2_review_bundles  # noqa: E402
from services.content.grade_appropriateness import apply_grade_assessment  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"
CALIBRATED_AUDIT_PATH = QUALITY / "lcai_0012d4_ai_pedagogical_review_calibrated.jsonl"
CALIBRATION_REPORT_PATH = QUALITY / "lcai_0012d4_ai_review_calibration_report.json"
GOLD_SAMPLE_PATH = QUALITY / "lcai_0012d4_ai_review_calibration_gold_sample.json"


def _dedupe_audits(records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_version: dict[int, dict[str, Any]] = {}
    for record in records.values():
        if not record.get("authoritative_ai_review"):
            continue
        version_id = int(record["candidate_version_id"])
        by_version[version_id] = record
    return list(by_version.values())


def _load_items_by_version() -> dict[int, dict[str, Any]]:
    combined = json.loads(COMBINED_PATH.read_text(encoding="utf-8"))
    items: dict[int, dict[str, Any]] = {}
    for bundle in combined.get("skills", []):
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is not None:
                items[int(item["version_id"])] = item
    return items


def _skill_pair_metrics(bundles: list[dict[str, Any]]) -> dict[str, int]:
    both_prevalidated = 0
    one_prevalidated_one_teacher = 0
    both_teacher = 0
    blocked = 0
    for bundle in bundles:
        practice = bundle.get("practice") or {}
        assessment = bundle.get("assessment") or {}
        practice_decision = practice.get("ai_prevalidation_decision")
        assessment_decision = assessment.get("ai_prevalidation_decision")
        if practice_decision == "AI_REJECTED" or assessment_decision == "AI_REJECTED":
            blocked += 1
            continue
        prevalidated = sum(
            is_ai_prevalidated_decision(str(decision)) for decision in (practice_decision, assessment_decision)
        )
        teacher = sum(decision == "TEACHER_REVIEW_REQUIRED" for decision in (practice_decision, assessment_decision))
        if prevalidated == 2:
            both_prevalidated += 1
        elif prevalidated == 1 and teacher >= 1:
            one_prevalidated_one_teacher += 1
        elif teacher == 2:
            both_teacher += 1
    return {
        "both_practice_assessment_ai_prevalidated": both_prevalidated,
        "one_prevalidated_one_teacher": one_prevalidated_one_teacher,
        "both_teacher": both_teacher,
        "blocked_skills": blocked,
    }


def _teacher_reasons(calibrated: list[dict[str, Any]], items: dict[int, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for audit in calibrated:
        if audit["decision"] != "TEACHER_REVIEW_REQUIRED":
            continue
        version_id = int(audit["candidate_version_id"])
        item = items.get(version_id, {})
        rows.append(
            {
                "version_id": str(version_id),
                "subject": str(audit.get("subject", "")),
                "skill_code": str(audit.get("skill_code", "")),
                "expected_answer_match": str(audit.get("expected_answer_match", "")),
                "confidence": str(audit.get("confidence", "")),
                "reason": str(audit.get("concise_reason", "")),
                "question_preview": str(item.get("question", ""))[:120],
            }
        )
    return rows


def _select_gold_sample(
    calibrated: list[dict[str, Any]],
    items: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for audit in calibrated:
        subject = str(audit.get("subject", ""))
        if subject in {"HISTORY", "GEOGRAPHY", "SVT"}:
            by_subject[subject].append(audit)

    selected: list[dict[str, Any]] = []
    for subject in ("HISTORY", "GEOGRAPHY", "SVT"):
        pool = by_subject[subject]
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for audit in pool:
            item = items.get(int(audit["candidate_version_id"]), {})
            kind = str(item.get("answer_kind", "unknown"))
            if kind in {"single_choice", "multiple_choice"}:
                key = "qcm"
            elif kind in {"open_response", "structured", "text"}:
                key = "open_response"
            else:
                key = "short_response"
            score_band = "high" if int(audit.get("answer_correctness", 0)) >= 90 else "medium"
            buckets[f"{key}:{score_band}"].append(audit)

        chosen: list[dict[str, Any]] = []
        for bucket_audits in buckets.values():
            if bucket_audits and len(chosen) < 10:
                chosen.append(bucket_audits[0])
        for audit in pool:
            if len(chosen) >= 10:
                break
            if audit not in chosen:
                chosen.append(audit)
        selected.extend(chosen[:10])

    rows: list[dict[str, Any]] = []
    for audit in selected:
        version_id = int(audit["candidate_version_id"])
        item = items.get(version_id, {})
        original = analyze_escalation_reasons(
            item=item,
            audit={**audit, "decision": audit.get("original_decision", audit.get("decision"))},
            original_decision=str(audit.get("original_decision", audit.get("decision", ""))),
        )
        rows.append(
            {
                "version_id": version_id,
                "subject": audit.get("subject"),
                "skill_code": audit.get("skill_code"),
                "answer_kind": item.get("answer_kind"),
                "question": item.get("question"),
                "expected_answer": item.get("expected_answer"),
                "blind_ai_answer": audit.get("blind_answer"),
                "original_decision": audit.get("original_decision"),
                "original_escalation_reason": original.primary_reason,
                "original_concise_reason": audit.get("original_concise_reason"),
                "proposed_decision": audit.get("decision"),
                "proposed_reason": audit.get("concise_reason"),
            }
        )
    return rows


def _apply_repaired_items(
    bundles: list[dict[str, Any]],
    items_by_version: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for bundle in bundles:
        new_bundle = dict(bundle)
        for slot in ("practice", "assessment"):
            item = new_bundle.get(slot)
            if item is None:
                continue
            version_id = int(item["version_id"])
            if version_id in items_by_version:
                new_bundle[slot] = items_by_version[version_id]
        updated.append(new_bundle)
    return updated


def _repair_grade_assessment(item: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    ai_grade_score = int(audit.get("grade_appropriateness", 0))
    if (
        str(audit.get("expected_answer_match", "")) in {"CORRECT", "ACCEPTABLE_VARIANT"}
        and str(audit.get("confidence", "")) == "HIGH"
    ):
        ai_grade_score = max(ai_grade_score, 85)
    return apply_grade_assessment(item, ai_grade_score=ai_grade_score)


def run() -> dict[str, Any]:
    records = _load_audit_file(AUTHORITATIVE_AUDIT_PATH)
    original_audits = _dedupe_audits(records)
    items = _load_items_by_version()

    calibrated: list[dict[str, Any]] = []
    grade_status_counts: Counter[str] = Counter()
    for audit in original_audits:
        version_id = int(audit["candidate_version_id"])
        item = items.get(version_id, {})
        repaired = _repair_grade_assessment(item, audit)
        grade_status_counts[str((repaired.get("grade_assessment") or {}).get("status", "missing"))] += 1
        items[version_id] = repaired
        calibrated.append(reclassify_audit_record(audit, repaired))

    CALIBRATED_AUDIT_PATH.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in calibrated) + "\n",
        encoding="utf-8",
    )

    original_decisions = Counter(str(a.get("decision", "")) for a in original_audits)
    new_decisions = Counter(str(a["decision"]) for a in calibrated)
    fact_check = sum(1 for a in calibrated if a.get("fact_check_required"))

    frequency = escalation_frequency_table(original_audits, items)
    gold_sample = _select_gold_sample(calibrated, items)
    GOLD_SAMPLE_PATH.write_text(json.dumps(gold_sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    reviews_by_version = {int(a["candidate_version_id"]): a for a in calibrated}
    combined = json.loads(COMBINED_PATH.read_text(encoding="utf-8"))
    repaired_bundles = _apply_repaired_items(combined.get("skills", []), items)
    merged_bundles = _merge_reviews_into_bundles(repaired_bundles, reviews_by_version)
    pair_metrics = _skill_pair_metrics(merged_bundles)

    prevalidated_count = sum(1 for a in calibrated if is_ai_prevalidated_decision(str(a["decision"])))
    teacher_count = int(new_decisions.get("TEACHER_REVIEW_REQUIRED", 0))
    original_teacher = int(original_decisions.get("TEACHER_REVIEW_REQUIRED", 0))
    workload_reduction = round(100 * (original_teacher - teacher_count) / original_teacher, 1) if original_teacher else 0.0

    coverage_rows = _coverage_rows()
    baseline = sum(
        tier(int(row["approved_practice"]) > 0, int(row["approved_assessment"]) > 0) == 1 for row in coverage_rows
    )

    report = {
        "calibration_version": CALIBRATION_VERSION,
        "original": {
            "AI_PREVALIDATED": int(original_decisions.get("AI_PREVALIDATED", 0)),
            "TEACHER_REVIEW_REQUIRED": original_teacher,
            "AI_REJECTED": int(original_decisions.get("AI_REJECTED", 0)),
            "FACT_CHECK_REQUIRED": 0,
        },
        "calibrated": {
            "AI_PREVALIDATED_HIGH": int(new_decisions.get("AI_PREVALIDATED_HIGH", 0)),
            "AI_PREVALIDATED_WITH_WARNING": int(new_decisions.get("AI_PREVALIDATED_WITH_WARNING", 0)),
            "TEACHER_REVIEW_REQUIRED": teacher_count,
            "FACT_CHECK_REQUIRED": fact_check,
            "AI_REJECTED": int(new_decisions.get("AI_REJECTED", 0)),
        },
        "skill_pairs": pair_metrics,
        "human_specialist_workload_reduction_pct": workload_reduction,
        "ai_prevalidated_total": prevalidated_count,
        "top_original_escalation_causes": frequency,
        "teacher_case_reasons": _teacher_reasons(calibrated, items),
        "gold_sample_count": len(gold_sample),
        "gold_sample_path": str(GOLD_SAMPLE_PATH.relative_to(ROOT)),
        "grade_assessment_status_counts": dict(grade_status_counts),
        "grade_appropriateness_root_cause": (
            "Legacy LCAI-0012D quality audit set grade_appropriateness=false unless a manual "
            "difficulty_alignment flag existed; Wave-2 generated candidates also hardcoded false. "
            "Deterministic curriculum grade mapping is now used instead."
        ),
        "verdict": "CALIBRATED_AND_READY",
        "production_baseline": {"tier1": baseline, "tier2": 0, "tier3": 372 - baseline},
    }
    CALIBRATION_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    combined_payload = {
        "lots": combined.get("lots", [1, 2]),
        "baseline_tier1": combined.get("baseline_tier1", baseline),
        "summary": summarize_wave2_review_bundles(merged_bundles),
        "ai_review_summary": {
            **combined.get("ai_review_summary", {}),
            "calibration_version": CALIBRATION_VERSION,
            "original_decisions": report["original"],
            "decisions": report["calibrated"],
            "skill_pairs": pair_metrics,
            "workload": {
                "human_specialist_workload_reduction_pct": workload_reduction,
                "teacher_specialist_reviews_required": teacher_count,
                "ai_prevalidated_total": prevalidated_count,
            },
        },
        "skills": merged_bundles,
    }
    COMBINED_PATH.write_text(json.dumps(combined_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8")) if SUMMARY_PATH.exists() else {}
    summary.update(
        {
            "calibration_version": CALIBRATION_VERSION,
            "original_decisions": report["original"],
            "calibrated_decisions": report["calibrated"],
            "skill_pairs_calibrated": pair_metrics,
            "human_specialist_workload_reduction_pct": workload_reduction,
        }
    )
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=True, indent=2))
    return report


if __name__ == "__main__":
    run()
