"""Batch AI pedagogical review for D4 Wave-2 Lots 1+2."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.pedagogical_review import (  # noqa: E402
    AI_REVIEW_PIPELINE_VERSION,
    ASSESSOR_TYPE_LOCAL,
    ASSESSOR_TYPE_OPENAI,
    CAMPAIGN_ID,
    REVIEW_MODE_LOCAL,
    REVIEW_MODE_OPENAI,
    build_review_idempotency_key,
)
from infrastructure.assessors.local_pedagogical_review import LocalPedagogicalReviewAssessor  # noqa: E402
from infrastructure.assessors.openai_pedagogical_review import OpenAIPedagogicalReviewAssessor  # noqa: E402
from infrastructure.config.openai_settings import (  # noqa: E402
    OpenAIConfigurationError,
    is_permanent_openai_error,
    verify_openai_pedagogical_assessor,
)
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository  # noqa: E402
from scripts.run_content_approval_d4_wave1 import _coverage_rows  # noqa: E402
from scripts.run_content_d4_wave2_combined import _patch_lot1_queue_with_replacements  # noqa: E402
from services.content.ai_pedagogical_review import (  # noqa: E402
    CandidateReviewContext,
    attach_ai_review,
    deduplicate_candidates,
    run_ai_pedagogical_review,
)
from services.content.ai_review_calibration import is_ai_prevalidated_decision  # noqa: E402
from services.content.approval_coverage import tier  # noqa: E402
from services.content.d4_wave2 import (  # noqa: E402
    build_skill_review_bundles,
    load_lot_review_queues,
    prioritize_skill_bundles,
    summarize_wave2_review_bundles,
)

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"
LEGACY_HEURISTIC_AUDIT_PATH = QUALITY / "lcai_0012d4_ai_pedagogical_review.jsonl"
HEURISTIC_HISTORY_PATH = QUALITY / "lcai_0012d4_ai_pedagogical_review_heuristic_history.jsonl"
AUTHORITATIVE_AUDIT_PATH = QUALITY / "lcai_0012d4_ai_pedagogical_review_authoritative.jsonl"
SUMMARY_PATH = QUALITY / "lcai_0012d4_ai_pedagogical_review_summary.json"
COMBINED_PATH = QUALITY / "lcai_0012d4_wave2_combined_review.json"


def _normalize_audit_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    pipeline = str(normalized.get("ai_review_pipeline_version", "lcai-0012d4-ai-review-v1"))
    assessor_type = str(normalized.get("assessor_type", ""))
    reviewer_model = str(normalized.get("reviewer_model", ""))
    if not assessor_type:
        assessor_type = (
            ASSESSOR_TYPE_LOCAL if reviewer_model.startswith("local-heuristic") else ASSESSOR_TYPE_OPENAI
        )
    if "review_mode" not in normalized:
        normalized["review_mode"] = REVIEW_MODE_LOCAL if assessor_type == ASSESSOR_TYPE_LOCAL else REVIEW_MODE_OPENAI
    if "authoritative_ai_review" not in normalized:
        normalized["authoritative_ai_review"] = assessor_type == ASSESSOR_TYPE_OPENAI and pipeline.startswith(
            "lcai-0012d4-ai-review-v2"
        )
    normalized["assessor_type"] = assessor_type
    normalized["review_idempotency_key"] = build_review_idempotency_key(
        candidate_version_id=int(normalized["candidate_version_id"]),
        pipeline_version=pipeline,
        assessor_type=assessor_type,
        model_identifier=reviewer_model,
    )
    return normalized


def _migrate_legacy_heuristic_audit() -> None:
    if not LEGACY_HEURISTIC_AUDIT_PATH.exists():
        return
    if HEURISTIC_HISTORY_PATH.exists():
        return
    lines = [
        json.dumps(_normalize_audit_record({**record, "authoritative_ai_review": False, "review_mode": REVIEW_MODE_LOCAL}))
        for record in (
            json.loads(line)
            for line in LEGACY_HEURISTIC_AUDIT_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    ]
    HEURISTIC_HISTORY_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    shutil.copy2(LEGACY_HEURISTIC_AUDIT_PATH, LEGACY_HEURISTIC_AUDIT_PATH.with_suffix(".jsonl.bak"))


def _load_audit_file(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = _normalize_audit_record(json.loads(line))
        records[str(record["review_idempotency_key"])] = record
    return records


def _append_review(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_candidates() -> list[dict[str, Any]]:
    queue = load_lot_review_queues(QUALITY, lots=(1, 2))
    queue = _patch_lot1_queue_with_replacements(queue)
    return deduplicate_candidates(queue)


def _authoritative_key(version_id: int, *, assessor_type: str, model: str) -> str:
    return build_review_idempotency_key(
        candidate_version_id=version_id,
        pipeline_version=AI_REVIEW_PIPELINE_VERSION,
        assessor_type=assessor_type,
        model_identifier=model,
    )


def _merge_reviews_into_bundles(
    bundles: list[dict[str, Any]],
    reviews_by_version: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for bundle in bundles:
        updated = dict(bundle)
        for slot in ("practice", "assessment"):
            item = updated.get(slot)
            if item is None:
                continue
            review = reviews_by_version.get(int(item["version_id"]))
            if review is not None:
                updated[slot] = attach_ai_review(item, _record_from_audit(review))
        merged.append(updated)
    return merged


def _record_from_audit(audit: dict[str, Any]) -> Any:
    from domain.content.pedagogical_review import AIPedagogicalReviewRecord, PedagogicalScores

    scores = PedagogicalScores(
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
    return AIPedagogicalReviewRecord(
        candidate_version_id=int(audit["candidate_version_id"]),
        campaign_id=str(audit["campaign_id"]),
        grade=str(audit["grade"]),
        subject=str(audit["subject"]),
        skill_code=str(audit["skill_code"]),
        content_type=str(audit["content_type"]),
        reviewer_model=str(audit["reviewer_model"]),
        review_timestamp=str(audit["review_timestamp"]),
        ai_review_pipeline_version=str(audit["ai_review_pipeline_version"]),
        blind_answer=str(audit["blind_answer"]),
        expected_answer_match=audit["expected_answer_match"],  # type: ignore[arg-type]
        scores=scores,
        confidence=audit["confidence"],  # type: ignore[arg-type]
        decision=audit["decision"],  # type: ignore[arg-type]
        fact_check_required=bool(audit["fact_check_required"]),
        concise_reason=str(audit["concise_reason"]),
        second_opinion_used=bool(audit.get("second_opinion_used", False)),
        extra={
            key: audit[key]
            for key in audit
            if key.startswith("legacy_") or key in {"assessor_type", "review_mode", "authoritative_ai_review"}
        },
    )


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
        prevalidated = sum(is_ai_prevalidated_decision(str(decision)) for decision in (practice_decision, assessment_decision))
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


def _authoritative_reviews_by_version(records: dict[str, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    output: dict[int, dict[str, Any]] = {}
    for record in records.values():
        if not record.get("authoritative_ai_review"):
            continue
        output[int(record["candidate_version_id"])] = record
    return output


def _build_summary(
    *,
    candidates: list[dict[str, Any]],
    reviews_by_version: dict[int, dict[str, Any]],
    bundles: list[dict[str, Any]],
    errors: list[str],
    assessor: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    decisions = Counter(record["decision"] for record in reviews_by_version.values())
    fact_check = sum(1 for record in reviews_by_version.values() if record.get("fact_check_required"))
    by_subject: dict[str, Counter[str]] = defaultdict(Counter)
    by_grade: dict[str, Counter[str]] = defaultdict(Counter)
    for record in reviews_by_version.values():
        by_subject[str(record["subject"])][str(record["decision"])] += 1
        by_grade[str(record["grade"])][str(record["decision"])] += 1
    pair_metrics = _skill_pair_metrics(bundles)
    reviewed = len(reviews_by_version)
    total = len(candidates)
    prevalidated = int(decisions.get("AI_PREVALIDATED", 0))
    human_reduction = round(100 * prevalidated / reviewed, 1) if reviewed else 0.0
    replacement_required = sum(
        1
        for record in reviews_by_version.values()
        if record["decision"] == "AI_REJECTED" and int(record.get("legacy_alternate_count") or 0) == 0
    )
    coverage_rows = _coverage_rows()
    baseline = sum(
        tier(int(row["approved_practice"]) > 0, int(row["approved_assessment"]) > 0) == 1 for row in coverage_rows
    )
    return {
        "status": status,
        "campaign_id": CAMPAIGN_ID,
        "ai_review_pipeline_version": AI_REVIEW_PIPELINE_VERSION,
        "assessor": assessor,
        "population": {
            "unique_skills": len(bundles),
            "candidates": total,
            "reviewed": reviewed,
            "remaining": max(0, total - reviewed),
        },
        "decisions": {
            "AI_PREVALIDATED": int(decisions.get("AI_PREVALIDATED", 0)),
            "TEACHER_REVIEW_REQUIRED": int(decisions.get("TEACHER_REVIEW_REQUIRED", 0)),
            "FACT_CHECK_REQUIRED": fact_check,
            "AI_REJECTED": int(decisions.get("AI_REJECTED", 0)),
        },
        "skill_pairs": pair_metrics,
        "workload": {
            "human_general_review_reduction_pct": human_reduction,
            "teacher_specialist_reviews_required": int(decisions.get("TEACHER_REVIEW_REQUIRED", 0)),
            "replacement_required": replacement_required,
        },
        "by_subject": {subject: dict(counter) for subject, counter in sorted(by_subject.items())},
        "by_grade": {grade: dict(counter) for grade, counter in sorted(by_grade.items())},
        "errors": errors,
        "production_baseline": {"tier1": baseline, "tier2": 0, "tier3": 372 - baseline},
        "approvals_executed": 0,
    }


def _persist_outputs(summary: dict[str, Any], merged_bundles: list[dict[str, Any]]) -> None:
    combined_payload = {
        "lots": [1, 2],
        "baseline_tier1": summary["production_baseline"]["tier1"],
        "summary": summarize_wave2_review_bundles(merged_bundles),
        "ai_review_summary": summary,
        "skills": merged_bundles,
    }
    COMBINED_PATH.write_text(json.dumps(combined_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(
    *,
    limit: int | None = None,
    batch_size: int = 9999,
    assessor_mode: str = "openai",
    verify_only: bool = False,
    retry_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    _migrate_legacy_heuristic_audit()
    candidates = _load_candidates()
    if limit is not None:
        candidates = candidates[:limit]

    assessor_meta: dict[str, Any] = {"type": assessor_mode}
    if assessor_mode == "local":
        assessor = LocalPedagogicalReviewAssessor()
        assessor_meta["model"] = assessor.reviewer_model
        existing = _load_audit_file(HEURISTIC_HISTORY_PATH)
        audit_path = HEURISTIC_HISTORY_PATH
        authoritative = False
        review_mode = REVIEW_MODE_LOCAL
        status = "LOCAL_HEURISTIC_DIAGNOSTIC"
    else:
        try:
            verification = verify_openai_pedagogical_assessor()
        except OpenAIConfigurationError as exc:
            summary = {
                "status": "AI_REVIEW_UNAVAILABLE",
                "reason": str(exc),
                "population": {"candidates": len(candidates), "reviewed": 0, "remaining": len(candidates)},
            }
            SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return summary
        assessor_meta.update(verification)
        if verify_only:
            print("OPENAI PEDAGOGICAL ASSESSOR: AVAILABLE", flush=True)
            return {"status": "AVAILABLE", **verification}
        assessor = OpenAIPedagogicalReviewAssessor(model=verification["model"])
        assessor_meta["model"] = assessor.model
        existing = _load_audit_file(AUTHORITATIVE_AUDIT_PATH)
        audit_path = AUTHORITATIVE_AUDIT_PATH
        authoritative = True
        review_mode = REVIEW_MODE_OPENAI
        status = "AUTHORITATIVE_OPENAI"

    errors: list[str] = []
    reviews_by_version = _authoritative_reviews_by_version(existing)
    attempts_this_run = 0
    auth_failed = False

    for item in candidates:
        version_id = int(item["version_id"])
        key = _authoritative_key(
            version_id,
            assessor_type=assessor.assessor_type,
            model=assessor.model,
        )
        if key in existing:
            continue
        if attempts_this_run >= batch_size:
            break
        attempts_this_run += 1
        try:
            review = run_ai_pedagogical_review(
                CandidateReviewContext(item=item),
                blind_assessor=assessor,
                comparison_assessor=assessor,
                reviewer_model=assessor.model,
                second_opinion_assessor=assessor if assessor_mode == "openai" else None,
                assessor_type=assessor.assessor_type,
                review_mode=review_mode,
                authoritative_ai_review=authoritative,
            )
            audit = review.audit_dict()
            audit["legacy_alternate_count"] = int(item.get("alternate_count", 0))
            _append_review(audit_path, audit)
            existing[key] = audit
            if authoritative:
                reviews_by_version[version_id] = audit
        except Exception as exc:  # noqa: BLE001 - batch resilience
            if assessor_mode == "openai" and is_permanent_openai_error(exc):
                auth_failed = True
                errors.append(f"AI_REVIEW_UNAVAILABLE: {exc}")
                break
            errors.append(f"v{version_id}: {exc}")
            if assessor_mode == "openai":
                time.sleep(retry_delay_seconds)

    if auth_failed:
        status = "AI_REVIEW_UNAVAILABLE"

    review_statuses = DuckDBContentQualityRepository().approval_queue_review_statuses()
    bundles = prioritize_skill_bundles(
        build_skill_review_bundles(_load_candidates(), review_statuses),
        _coverage_rows(),
    )
    merged_bundles = _merge_reviews_into_bundles(bundles, reviews_by_version)
    summary = _build_summary(
        candidates=_load_candidates(),
        reviews_by_version=reviews_by_version,
        bundles=merged_bundles,
        errors=errors,
        assessor=assessor_meta,
        status=status,
    )
    _persist_outputs(summary, merged_bundles)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI pedagogical review on Wave-2 Lots 1+2.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of new reviews.")
    parser.add_argument("--batch-size", type=int, default=9999, help="Max new reviews this run.")
    parser.add_argument("--assessor", choices=("openai", "local"), default="openai")
    parser.add_argument("--verify-only", action="store_true", help="Only verify OpenAI assessor availability.")
    args = parser.parse_args()
    summary = run(
        limit=args.limit,
        batch_size=args.batch_size,
        assessor_mode=args.assessor,
        verify_only=args.verify_only,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
