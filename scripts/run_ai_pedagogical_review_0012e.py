"""Run calibrated AI pedagogical review on LCAI-0012E CM1–5e handoff (731 candidates)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.pedagogical_review import (  # noqa: E402
    AI_REVIEW_PIPELINE_VERSION,
    ASSESSOR_TYPE_OPENAI,
    REVIEW_MODE_OPENAI,
    build_review_idempotency_key,
)
from infrastructure.assessors.openai_pedagogical_review import OpenAIPedagogicalReviewAssessor  # noqa: E402
from infrastructure.config.openai_settings import (  # noqa: E402
    OpenAIConfigurationError,
    is_permanent_openai_error,
    verify_openai_pedagogical_assessor,
)
from scripts.run_ai_pedagogical_review_wave2 import (  # noqa: E402
    _append_review,
    _normalize_audit_record,
    _record_from_audit,
)
from services.content.ai_pedagogical_review import (  # noqa: E402
    CandidateReviewContext,
    attach_ai_review,
    run_ai_pedagogical_review,
)
from services.content.ai_review_calibration import (  # noqa: E402
    CALIBRATION_VERSION,
    is_ai_prevalidated_decision,
    reclassify_audit_record,
)
from services.content.primary_ai_review import (  # noqa: E402
    ALTERNATE_QUEUE_PATH,
    AUTHORITATIVE_AUDIT_PATH,
    CALIBRATED_AUDIT_PATH,
    CAMPAIGN_ID,
    COMBINED_PATH,
    SUMMARY_PATH,
    TEACHER_QUEUE_PATH,
    build_alternate_review_queue,
    build_curriculum_decision_appendix,
    build_primary_skill_bundles,
    build_teacher_queue,
    compute_post_ai_generation_gap,
    handoff_to_review_item,
    load_handoff_candidates,
    skill_pair_metrics,
    validate_handoff_population,
    write_curriculum_decision_appendix,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/phase2"
MAX_RETRY_DELAY = 60.0
IMPORTABLE_DRAFTS = 1293


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


def _authoritative_key(version_id: int, *, assessor_type: str, model: str) -> str:
    return build_review_idempotency_key(
        candidate_version_id=version_id,
        pipeline_version=AI_REVIEW_PIPELINE_VERSION,
        assessor_type=assessor_type,
        model_identifier=model,
    )


def _merge_reviews(candidates: list[dict[str, Any]], reviews_by_version: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in candidates:
        review = reviews_by_version.get(int(item["version_id"]))
        if review is None:
            enriched.append(dict(item))
            continue
        calibrated = reclassify_audit_record(review, item)
        enriched.append(attach_ai_review(item, _record_from_audit(calibrated)))
    return enriched


def _merge_bundles(bundles: list[dict[str, Any]], enriched_by_version: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for bundle in bundles:
        updated = dict(bundle)
        for slot in ("practice", "assessment"):
            item = updated.get(slot)
            if item is None:
                continue
            enriched = enriched_by_version.get(int(item["version_id"]))
            if enriched is not None:
                updated[slot] = enriched
            elif int(item["version_id"]) in enriched_by_version:
                updated[slot] = enriched_by_version[int(item["version_id"])]
        merged.append(updated)
    return merged


def _apply_alternate_outcomes(
    enriched: list[dict[str, Any]],
    alternate_reviews: dict[int, dict[str, Any]],
) -> int:
    """Swap rejected slots with prevalidated alternates when available."""
    recovered = 0
    by_rejected: dict[int, dict[str, Any]] = {}
    for alt_item, audit in alternate_reviews.items():
        rejected_vid = int((audit.get("alternate_lineage") or {}).get("rejected_version_id") or 0)
        if rejected_vid:
            by_rejected[rejected_vid] = audit

    for item in enriched:
        rejected_vid = int(item["version_id"])
        alt_audit = by_rejected.get(rejected_vid)
        if alt_audit is None:
            continue
        if is_ai_prevalidated_decision(str(alt_audit.get("decision"))):
            item["alternate_recovered"] = True
            item["alternate_review_decision"] = alt_audit.get("decision")
            recovered += 1
    return recovered


def _build_summary(
    *,
    population: dict[str, Any],
    reviews_by_version: dict[int, dict[str, Any]],
    bundles: list[dict[str, Any]],
    alternates_queued: int,
    alternates_reviewed: int,
    alternates_recovered: int,
    replacement_required: int,
    generation_gap: dict[str, Any],
    errors: list[str],
    assessor: dict[str, Any],
    status: str,
    main_campaign_complete: bool,
) -> dict[str, Any]:
    decisions = Counter(str(r.get("decision", "")) for r in reviews_by_version.values())
    fact_check = sum(1 for r in reviews_by_version.values() if r.get("fact_check_required"))
    by_grade: dict[str, Counter[str]] = defaultdict(Counter)
    by_subject: dict[str, Counter[str]] = defaultdict(Counter)
    for record in reviews_by_version.values():
        by_grade[str(record["grade"])][str(record["decision"])] += 1
        by_subject[str(record["subject"])][str(record["decision"])] += 1
    reviewed = len(reviews_by_version)
    total = int(population["deduplicated_candidates"])
    teacher = int(decisions.get("TEACHER_REVIEW_REQUIRED", 0))
    human_reduction = round(100 * (1 - teacher / reviewed), 1) if reviewed else 0.0
    pairs = skill_pair_metrics(bundles)
    return {
        "status": status,
        "campaign_id": CAMPAIGN_ID,
        "ai_review_pipeline_version": AI_REVIEW_PIPELINE_VERSION,
        "calibration_version": CALIBRATION_VERSION,
        "assessor": assessor,
        "integration_baseline": {
            "importable_drafts": IMPORTABLE_DRAFTS,
            "best_candidates_for_ai_review": total,
            "review_architecture": "Agent 1 calibrated generic reviewer (Pass A blind + Pass B compare)",
            "idempotent_resume": True,
        },
        "population": {
            **population,
            "reviewed": reviewed,
            "remaining": max(0, total - reviewed),
            "main_campaign_complete": main_campaign_complete,
        },
        "decisions": {
            "AI_PREVALIDATED_HIGH": int(decisions.get("AI_PREVALIDATED_HIGH", 0)),
            "AI_PREVALIDATED_WITH_WARNING": int(decisions.get("AI_PREVALIDATED_WITH_WARNING", 0)),
            "TEACHER_REVIEW_REQUIRED": teacher,
            "FACT_CHECK_REQUIRED": fact_check,
            "AI_REJECTED": int(decisions.get("AI_REJECTED", 0)),
        },
        "skill_pairs": pairs,
        "workload": {
            "human_specialist_workload_reduction_pct": human_reduction,
            "teacher_specialist_reviews_required": teacher,
            "fact_check_reviews_required": fact_check,
            "alternates_queued": alternates_queued,
            "alternates_reviewed": alternates_reviewed,
            "alternates_recovered": alternates_recovered,
            "replacement_required": replacement_required,
        },
        "generation_after_ai": generation_gap,
        "by_subject": {subject: dict(counter) for subject, counter in sorted(by_subject.items())},
        "by_grade": {grade: dict(counter) for grade, counter in sorted(by_grade.items())},
        "curriculum_decisions": build_curriculum_decision_appendix(),
        "errors": errors,
        "production_db_modified": False,
        "unresolved_curriculum_excluded": 18,
        "controlled_publication_ready": (
            main_campaign_complete
            and population.get("remaining", 1) == 0
            and status == "AUTHORITATIVE_OPENAI"
            and not errors
        ),
    }


def _write_report(summary: dict[str, Any]) -> None:
    pop = summary["population"]
    dec = summary["decisions"]
    pairs = summary["skill_pairs"]["overall"]
    gen = summary["generation_after_ai"]
    workload = summary["workload"]
    baseline = summary.get("integration_baseline", {})
    by_grade = summary.get("by_grade", {})
    by_subject = summary.get("by_subject", {})
    complete = pop.get("remaining", 1) == 0 and summary.get("status") == "AUTHORITATIVE_OPENAI"

    lines = [
        "# LCAI-0012E AI PEDAGOGICAL REVIEW",
        "",
        "## Integration baseline",
        f"- Importable drafts (isolated): **{baseline.get('importable_drafts', IMPORTABLE_DRAFTS)}**",
        f"- Best candidates for AI review: **{pop.get('expected', 731)}**",
        f"- Review architecture: {baseline.get('review_architecture', 'Agent 1 calibrated reviewer')}",
        f"- Pipeline version: `{summary.get('ai_review_pipeline_version')}`",
        f"- Calibration version: `{summary.get('calibration_version')}`",
        f"- Model: `{summary.get('assessor', {}).get('model', 'gpt-5-mini')}`",
        f"- Idempotent resume: **yes**",
        "",
        f"- Candidates expected: **{pop.get('expected', 731)}**",
        f"- Candidates reviewed: **{pop.get('reviewed', 0)}**",
        f"- Remaining: **{pop.get('remaining', 0)}**",
        "",
        "## Decisions",
        f"- AI_PREVALIDATED_HIGH: **{dec.get('AI_PREVALIDATED_HIGH', 0)}**",
        f"- AI_PREVALIDATED_WITH_WARNING: **{dec.get('AI_PREVALIDATED_WITH_WARNING', 0)}**",
        f"- TEACHER_REVIEW_REQUIRED: **{dec.get('TEACHER_REVIEW_REQUIRED', 0)}**",
        f"- FACT_CHECK_REQUIRED (flag): **{dec.get('FACT_CHECK_REQUIRED', 0)}**",
        f"- AI_REJECTED: **{dec.get('AI_REJECTED', 0)}**",
        "",
        "## Decisions by grade",
    ]
    for grade, counts in sorted(by_grade.items()):
        lines.append(f"- {grade}: {json.dumps(counts, ensure_ascii=False)}")
    lines.extend(["", "## Decisions by subject"])
    for subject, counts in sorted(by_subject.items()):
        lines.append(f"- {subject}: {json.dumps(counts, ensure_ascii=False)}")

    lines.extend(
        [
            "",
            "## Skill pairs",
            f"- Both AI prevalidated: **{pairs.get('BOTH_AI_PREVALIDATED', 0)}**",
            f"- Mixed (one AI / one Teacher): **{pairs.get('ONE_AI_ONE_TEACHER', 0)}**",
            f"- Both Teacher: **{pairs.get('BOTH_TEACHER', 0)}**",
            f"- Blocked by rejection: **{pairs.get('BLOCKED_BY_REJECTION', 0)}**",
            f"- Only one slot available: **{pairs.get('ONLY_ONE_SLOT_AVAILABLE', 0)}**",
            "",
            "## Workload",
            f"- Human specialist workload reduction: **{workload.get('human_specialist_workload_reduction_pct', 0)}%**",
            f"- Teacher specialist reviews required: **{workload.get('teacher_specialist_reviews_required', 0)}**",
            f"- Fact Check reviews required: **{workload.get('fact_check_reviews_required', 0)}**",
            "",
            "## Rejection analysis",
            f"- Alternates queued: **{workload.get('alternates_queued', 0)}**",
            f"- Alternates reviewed: **{workload.get('alternates_reviewed', 0)}**",
            f"- Alternates recovered (AI-prevalidated): **{workload.get('alternates_recovered', 0)}**",
            f"- Replacement required: **{workload.get('replacement_required', 0)}**",
            "",
            "## Final generation requirement (after AI review)",
            f"- Missing Practice (genuinely absent): **{gen.get('missing_practice_after_ai', 0)}**",
            f"- Missing Assessment (genuinely absent): **{gen.get('missing_assessment_after_ai', 0)}**",
            f"- Rejected without alternate: **{gen.get('rejected_without_alternate', 0)}**",
            f"- Teacher-blocked slots: **{gen.get('teacher_blocked_slots', 0)}**",
            f"- Fact-check-blocked slots: **{gen.get('fact_check_blocked_slots', 0)}**",
            f"- Replacement required: **{gen.get('replacement_required', 0)}**",
            f"- **TOTAL NEW CONTENTS REQUIRED: {gen.get('total_generation_required', 0)}**",
            "",
            "### Categories",
            f"- A. Genuinely absent content: **{gen.get('categories', {}).get('A_genuinely_absent', 0)}**",
            f"- B. Rejected needing replacement: **{gen.get('categories', {}).get('B_rejected_needing_replacement', 0)}**",
            f"- C. Awaiting human/fact-check: **{gen.get('categories', {}).get('C_awaiting_human_or_fact_check', 0)}**",
            "",
            "## Unresolved curriculum records",
            "- Total excluded: **18** (15 curriculum-decision + 3 Spanish COMPARE)",
            f"- See appendix: `docs/phase2/LCAI-0012E_UNRESOLVED_CURRICULUM_APPENDIX.md`",
            "",
            "- Production DB modified: **NO**",
            "- Controlled publication: **NOT executed** (pre-validation only)",
            "",
            "## Recommendation",
            "",
            "**LCAI-0012E AI REVIEW: READY FOR CONTROLLED PUBLICATION**"
            if complete and summary.get("controlled_publication_ready")
            else "**LCAI-0012E AI REVIEW: REQUIRES CORRECTION**",
        ]
    )
    if summary.get("errors"):
        lines.extend(["", "## Errors", *[f"- {err}" for err in summary["errors"][:20]]])
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "LCAI-0012E_AI_PEDAGOGICAL_REVIEW_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _persist_outputs(summary: dict[str, Any], bundles: list[dict[str, Any]], teacher_queue: list[dict[str, Any]], alternate_queue: list[dict[str, Any]]) -> None:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    COMBINED_PATH.write_text(
        json.dumps({"campaign_id": CAMPAIGN_ID, "summary": summary, "skills": bundles}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    TEACHER_QUEUE_PATH.write_text(json.dumps({"queue": teacher_queue}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ALTERNATE_QUEUE_PATH.write_text(
        json.dumps({"queue": alternate_queue}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_curriculum_decision_appendix()
    _write_report(summary)


def _review_one(
    item: dict[str, Any],
    *,
    assessor: OpenAIPedagogicalReviewAssessor,
    existing: dict[str, dict[str, Any]],
    reviews_by_version: dict[int, dict[str, Any]],
    errors: list[str],
    retry_delay: float,
) -> bool:
    """Review one candidate. Returns False on permanent auth failure."""
    version_id = int(item["version_id"])
    if version_id <= 0:
        errors.append(f"malformed candidate missing version_id: code={item.get('code')}")
        return True
    key = _authoritative_key(version_id, assessor_type=assessor.assessor_type, model=assessor.model)
    if key in existing:
        return True
    delay = retry_delay
    for attempt in range(4):
        try:
            review = run_ai_pedagogical_review(
                CandidateReviewContext(item=item, campaign_id=CAMPAIGN_ID),
                blind_assessor=assessor,
                comparison_assessor=assessor,
                reviewer_model=assessor.model,
                second_opinion_assessor=assessor,
                assessor_type=assessor.assessor_type,
                review_mode=REVIEW_MODE_OPENAI,
                authoritative_ai_review=True,
            )
            audit = reclassify_audit_record(review.audit_dict(), item)
            audit["calibration_version"] = CALIBRATION_VERSION
            if item.get("alternate_lineage"):
                audit["alternate_lineage"] = item["alternate_lineage"]
            _append_review(AUTHORITATIVE_AUDIT_PATH, audit)
            _append_review(CALIBRATED_AUDIT_PATH, audit)
            existing[key] = audit
            reviews_by_version[version_id] = audit
            return True
        except Exception as exc:  # noqa: BLE001
            if is_permanent_openai_error(exc):
                errors.append(f"AI_REVIEW_UNAVAILABLE: {exc}")
                return False
            if attempt == 3:
                errors.append(f"v{version_id}: {exc}")
                return True
            time.sleep(min(delay, MAX_RETRY_DELAY))
            delay = min(delay * 2, MAX_RETRY_DELAY)
    return True


def _pending_count(
    items: list[dict[str, Any]],
    *,
    existing: dict[str, dict[str, Any]],
    assessor_type: str,
    model: str,
) -> int:
    pending = 0
    for item in items:
        version_id = int(item["version_id"])
        if version_id <= 0:
            continue
        key = _authoritative_key(version_id, assessor_type=assessor_type, model=model)
        if key not in existing:
            pending += 1
    return pending


def _process_batch(
    items: list[dict[str, Any]],
    *,
    batch_size: int,
    assessor: OpenAIPedagogicalReviewAssessor,
    existing: dict[str, dict[str, Any]],
    reviews_by_version: dict[int, dict[str, Any]],
    errors: list[str],
    retry_delay: float,
) -> tuple[int, bool]:
    attempts = 0
    for item in items:
        version_id = int(item["version_id"])
        key = _authoritative_key(version_id, assessor_type=assessor.assessor_type, model=assessor.model)
        if key in existing:
            continue
        if attempts >= batch_size:
            break
        attempts += 1
        ok = _review_one(
            item,
            assessor=assessor,
            existing=existing,
            reviews_by_version=reviews_by_version,
            errors=errors,
            retry_delay=retry_delay,
        )
        if not ok:
            return attempts, False
    return attempts, True


def _finalize(
    *,
    population: dict[str, Any],
    reviews_by_version: dict[int, dict[str, Any]],
    candidates: list[dict[str, Any]],
    assessor_meta: dict[str, Any],
    errors: list[str],
    status: str,
    main_campaign_complete: bool,
) -> dict[str, Any]:
    enriched = _merge_reviews(candidates, reviews_by_version)
    enriched_by_version = {int(item["version_id"]): item for item in enriched}
    bundles = build_primary_skill_bundles(candidates)
    merged_bundles = _merge_bundles(bundles, enriched_by_version)

    alternate_queue, alternates_queued, replacement_required = build_alternate_review_queue(
        enriched,
        reviewed_version_ids=set(reviews_by_version),
    )
    alternate_reviews = {
        vid: audit
        for vid, audit in reviews_by_version.items()
        if audit.get("alternate_lineage")
    }
    alternates_reviewed = len(alternate_reviews)
    alternates_recovered = _apply_alternate_outcomes(enriched, alternate_reviews)

    generation_gap = compute_post_ai_generation_gap(merged_bundles)
    teacher_queue = build_teacher_queue(enriched)
    summary = _build_summary(
        population=population,
        reviews_by_version=reviews_by_version,
        bundles=merged_bundles,
        alternates_queued=alternates_queued,
        alternates_reviewed=alternates_reviewed,
        alternates_recovered=alternates_recovered,
        replacement_required=replacement_required,
        generation_gap=generation_gap,
        errors=errors,
        assessor=assessor_meta,
        status=status,
        main_campaign_complete=main_campaign_complete,
    )
    _persist_outputs(summary, merged_bundles, teacher_queue, alternate_queue)
    return summary


def run(
    *,
    batch_size: int = 50,
    until_complete: bool = False,
    verify_only: bool = False,
    finalize_only: bool = False,
    alternates_only: bool = False,
    retry_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    population = validate_handoff_population()
    candidates = load_handoff_candidates()
    if not population["valid"]:
        return {"status": "INVALID_HANDOFF", "population": population}

    existing = _load_audit_file(AUTHORITATIVE_AUDIT_PATH)
    reviews_by_version: dict[int, dict[str, Any]] = {
        int(r["candidate_version_id"]): r for r in existing.values() if r.get("authoritative_ai_review")
    }

    if finalize_only:
        main_complete = len(reviews_by_version) >= len(candidates)
        return _finalize(
            population=population,
            reviews_by_version=reviews_by_version,
            candidates=candidates,
            assessor_meta={"type": ASSESSOR_TYPE_OPENAI, "model": "gpt-5-mini"},
            errors=[],
            status="AUTHORITATIVE_OPENAI" if main_complete else "IN_PROGRESS",
            main_campaign_complete=main_complete,
        )

    try:
        verification = verify_openai_pedagogical_assessor()
    except OpenAIConfigurationError as exc:
        summary = {"status": "AI_REVIEW_UNAVAILABLE", "reason": str(exc), "population": population}
        SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return summary

    if verify_only:
        return {"status": "AVAILABLE", **verification}

    assessor = OpenAIPedagogicalReviewAssessor(model=verification["model"])
    assessor_meta = {"type": ASSESSOR_TYPE_OPENAI, **verification, "model": assessor.model}
    errors: list[str] = []
    auth_failed = False

    if not alternates_only:
        def _run_main() -> None:
            nonlocal auth_failed
            if until_complete:
                while not auth_failed:
                    pending = _pending_count(
                        candidates,
                        existing=existing,
                        assessor_type=assessor.assessor_type,
                        model=assessor.model,
                    )
                    if pending == 0:
                        break
                    done, ok = _process_batch(
                        candidates,
                        batch_size=batch_size,
                        assessor=assessor,
                        existing=existing,
                        reviews_by_version=reviews_by_version,
                        errors=errors,
                        retry_delay=retry_delay_seconds,
                    )
                    if not ok:
                        auth_failed = True
                        break
                    if done == 0:
                        pending = _pending_count(
                            candidates,
                            existing=existing,
                            assessor_type=assessor.assessor_type,
                            model=assessor.model,
                        )
                        if pending == 0:
                            break
                        time.sleep(min(retry_delay_seconds * 2, MAX_RETRY_DELAY))
                        continue
                    reviewed = len({int(r["candidate_version_id"]) for r in reviews_by_version.values()})
                    print(
                        json.dumps(
                            {
                                "checkpoint": "IN_PROGRESS",
                                "reviewed": reviewed,
                                "remaining": pending,
                            },
                            ensure_ascii=True,
                        ),
                        flush=True,
                    )
            else:
                _, ok = _process_batch(
                    candidates,
                    batch_size=batch_size,
                    assessor=assessor,
                    existing=existing,
                    reviews_by_version=reviews_by_version,
                    errors=errors,
                    retry_delay=retry_delay_seconds,
                )
                if not ok:
                    auth_failed = True

        _run_main()

    main_complete = (
        _pending_count(
            candidates,
            existing=existing,
            assessor_type=assessor.assessor_type,
            model=assessor.model,
        )
        == 0
        and not auth_failed
    )

    if main_complete or alternates_only:
        enriched = _merge_reviews(candidates, reviews_by_version)
        alternate_queue, _, _ = build_alternate_review_queue(
            enriched,
            reviewed_version_ids=set(reviews_by_version),
        )
        pending_alternates = [
            alt for alt in alternate_queue
            if _authoritative_key(int(alt["version_id"]), assessor_type=assessor.assessor_type, model=assessor.model)
            not in existing
            and int(alt["version_id"]) > 0
        ]
        if pending_alternates and (until_complete or alternates_only):
            while pending_alternates and not auth_failed:
                done, ok = _process_batch(
                    pending_alternates,
                    batch_size=batch_size,
                    assessor=assessor,
                    existing=existing,
                    reviews_by_version=reviews_by_version,
                    errors=errors,
                    retry_delay=retry_delay_seconds,
                )
                if not ok:
                    auth_failed = True
                    break
                if done == 0:
                    break
                pending_alternates = [
                    alt for alt in alternate_queue
                    if _authoritative_key(int(alt["version_id"]), assessor_type=assessor.assessor_type, model=assessor.model)
                    not in existing
                    and int(alt["version_id"]) > 0
                ]

    status = "AI_REVIEW_UNAVAILABLE" if auth_failed else (
        "AUTHORITATIVE_OPENAI" if main_complete else "IN_PROGRESS"
    )
    return _finalize(
        population=population,
        reviews_by_version=reviews_by_version,
        candidates=candidates,
        assessor_meta=assessor_meta,
        errors=errors,
        status=status,
        main_campaign_complete=main_complete,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--until-complete", action="store_true", help="Run batches until all candidates reviewed.")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--finalize-only", action="store_true", help="Rebuild summary/report from existing audits.")
    parser.add_argument("--alternates-only", action="store_true", help="Review alternates for rejected candidates only.")
    args = parser.parse_args()
    summary = run(
        batch_size=args.batch_size,
        until_complete=args.until_complete,
        verify_only=args.verify_only,
        finalize_only=args.finalize_only,
        alternates_only=args.alternates_only,
    )
    print(json.dumps(summary, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
