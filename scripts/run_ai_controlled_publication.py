"""Controlled AI publication dry-run, manifest generation, execution, and rollback."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from scripts.run_content_approval_d4_wave1 import _coverage_rows
from scripts.run_ai_pedagogical_review_recalibrate import _dedupe_audits, _repair_grade_assessment
from scripts.run_ai_pedagogical_review_wave2 import (
    AUTHORITATIVE_AUDIT_PATH,
    _load_audit_file,
    _record_from_audit,
)
from services.content.ai_controlled_publication import (
    DEFAULT_CAMPAIGN,
    DEFAULT_REVIEW_MODEL,
    DEFAULT_REVIEW_PIPELINE,
    assess_publication_eligibility,
    build_execution_manifest,
    plan_controlled_publication,
    projected_tier1_after_publication,
    summarize_decisions,
)
from services.content.ai_pedagogical_review import attach_ai_review
from services.content.ai_review_calibration import reclassify_audit_record
from services.content.d4_review import ai_prevalidation_decision, is_ai_rejected, requires_teacher_review
from services.content.wave2_campaign_repair import repair_wave2_campaign_metadata

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"
COMBINED_PATH = QUALITY / "lcai_0012d4_wave2_combined_review.json"
DRY_RUN_REPORT_PATH = QUALITY / "lcai_0012d4_ai_controlled_publication_dry_run.json"
EXECUTION_MANIFEST_PATH = QUALITY / "lcai_0012d4_ai_controlled_publication_manifest.json"
CONFIRMATION_FLAG = "--confirm-ai-controlled-publication"
ROLLBACK_CONFIRMATION_FLAG = "--confirm-ai-controlled-rollback"
LOCK_RETRY_ATTEMPTS = 30
LOCK_RETRY_DELAY_SECONDS = 2.0


def _load_recalibrated_bundles() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(COMBINED_PATH.read_text(encoding="utf-8"))
    bundles = payload.get("skills", [])
    audits = {
        int(audit["candidate_version_id"]): audit
        for audit in _dedupe_audits(_load_audit_file(AUTHORITATIVE_AUDIT_PATH))
    }
    repaired_campaign_count = 0
    recalibrated: list[dict[str, Any]] = []
    for bundle in bundles:
        updated = dict(bundle)
        for slot in ("practice", "assessment"):
            item = updated.get(slot)
            if item is None:
                continue
            version_id = int(item["version_id"])
            audit = audits.get(version_id)
            if audit is None:
                continue
            repaired = repair_wave2_campaign_metadata(item, audit, quality_dir=QUALITY)
            if repaired.get("campaign_metadata_repair"):
                repaired_campaign_count += 1
            repaired = _repair_grade_assessment(repaired, audit)
            calibrated = reclassify_audit_record(audit, repaired)
            updated[slot] = attach_ai_review(repaired, _record_from_audit(calibrated))
        recalibrated.append(updated)
    return recalibrated, {
        "campaign_metadata_repairs": repaired_campaign_count,
        "authoritative_audits": len(audits),
    }


def _find_item(bundles: list[dict[str, Any]], version_id: int) -> dict[str, Any] | None:
    for bundle in bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is not None and int(item["version_id"]) == version_id:
                return item
    return None


def _build_report(
    *,
    campaign: str,
    required_decision: str,
    execute: bool,
    bundles: list[dict[str, Any]],
    repair_meta: dict[str, Any],
) -> dict[str, Any]:
    decisions = summarize_decisions(bundles)
    plan = plan_controlled_publication(
        bundles,
        required_decision=required_decision,
        campaign=campaign,
    )
    tier_projection = projected_tier1_after_publication(_coverage_rows(), plan["eligible_candidates"])
    manifest = build_execution_manifest(
        bundles,
        plan["eligible_candidates"],
        campaign=campaign,
        review_model=DEFAULT_REVIEW_MODEL,
        review_pipeline=DEFAULT_REVIEW_PIPELINE,
    )
    blocked_high = [
        item
        for item in plan["blocked"]
        if str(item.get("decision")) == required_decision
    ]
    return {
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "campaign": campaign,
        "required_decision": required_decision,
        "repair_meta": repair_meta,
        "decisions": decisions,
        "eligible_candidate_count": plan["eligible_candidate_count"],
        "complete_skill_pairs": plan["complete_skill_pairs"],
        "tier_projection": tier_projection,
        "teacher_remaining": len(plan["teacher"]),
        "teacher_excluded": len(plan["teacher"]),
        "fact_check_excluded": decisions.get("FACT_CHECK_REQUIRED", 0),
        "rejected_excluded": len(plan["rejected"]),
        "rejected": plan["rejected"],
        "replacement_required": [item for item in plan["rejected"] if item.get("replacement_required")],
        "blocked": plan["blocked"],
        "blocked_high_candidates": blocked_high,
        "warnings": plan["warnings"],
        "execution_manifest_count": len(manifest),
        "production_baseline": {
            "tier1": tier_projection["baseline_tier1"],
            "tier2": 0,
            "tier3": 272,
        },
        "production_db_modified": False,
        "published": [],
    }, manifest, plan


def _validate_execution_safety(
    repository: DuckDBContentQualityRepository,
    *,
    bundles: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
    campaign: str,
    required_decision: str,
) -> list[str]:
    errors: list[str] = []
    manifest_ids = {int(row["candidate_version_id"]) for row in manifest}
    for row in manifest:
        version_id = int(row["candidate_version_id"])
        item = _find_item(bundles, version_id)
        if item is None:
            errors.append(f"manifest version {version_id} missing from recalibrated bundles")
            continue
        eligibility = assess_publication_eligibility(item, required_decision=required_decision, campaign=campaign)
        if not eligibility.eligible:
            errors.append(f"version {version_id} no longer eligible: {eligibility.reasons[0]}")
        if requires_teacher_review(item):
            errors.append(f"version {version_id} requires teacher review")
        if is_ai_rejected(item):
            errors.append(f"version {version_id} is AI rejected")
        if item.get("fact_check_required"):
            errors.append(f"version {version_id} requires fact-check")
        if not repository.verify_draft_source_available(version_id):
            existing = repository.read_human_decision(version_id)
            if existing is None or existing.get("review_status") != "APPROVED":
                errors.append(f"version {version_id} draft source unavailable in database")
    for bundle in bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None:
                continue
            version_id = int(item["version_id"])
            if version_id in manifest_ids:
                continue
            if ai_prevalidation_decision(item) == required_decision and str(item.get("review_campaign", "")) == campaign:
                if not requires_teacher_review(item) and not is_ai_rejected(item):
                    errors.append(f"eligible-looking version {version_id} missing from manifest")
    return errors


def _execute_publication(
    repository: DuckDBContentQualityRepository,
    *,
    manifest: list[dict[str, Any]],
    bundles: list[dict[str, Any]],
    required_decision: str,
) -> list[dict[str, Any]]:
    published: list[dict[str, Any]] = []
    for row in manifest:
        version_id = int(row["candidate_version_id"])
        item = _find_item(bundles, version_id)
        if item is None:
            raise RuntimeError(f"Execution item missing for version {version_id}")
        if ai_prevalidation_decision(item) != required_decision:
            raise RuntimeError(f"Decision changed for version {version_id} during execution")
        exercise_id: int | None = None
        for attempt in range(LOCK_RETRY_ATTEMPTS):
            try:
                exercise_id = repository.approve_for_ai_controlled_publication(
                    item=item,
                    review_model=DEFAULT_REVIEW_MODEL,
                    review_pipeline=DEFAULT_REVIEW_PIPELINE,
                    reason="Publication contrôlée par validation IA.",
                )
                break
            except duckdb.IOException:
                if attempt >= LOCK_RETRY_ATTEMPTS - 1:
                    raise
                time.sleep(LOCK_RETRY_DELAY_SECONDS)
        if exercise_id is None:
            raise RuntimeError(f"Publication failed for version {version_id}")
        persisted = repository.read_human_decision(version_id)
        if persisted is None or persisted.get("review_status") != "APPROVED":
            raise RuntimeError(f"Publication verification failed for version {version_id}")
        if not persisted.get("production_enabled"):
            raise RuntimeError(f"Production gate not enabled for version {version_id}")
        published.append(
            {
                "version_id": version_id,
                "exercise_id": exercise_id,
                "skill_code": row.get("skill_code"),
                "published_version_id": persisted.get("published_version_id"),
                "production_enabled": persisted.get("production_enabled"),
            }
        )
    return published


def run_publication(
    *,
    campaign: str,
    required_decision: str,
    execute: bool,
    confirmed: bool,
    database_path: Path,
    allow_non_blocking_warning: bool = False,
) -> dict[str, Any]:
    bundles, repair_meta = _load_recalibrated_bundles()
    report, manifest, _plan = _build_report(
        campaign=campaign,
        required_decision=required_decision,
        execute=execute,
        bundles=bundles,
        repair_meta=repair_meta,
    )
    EXECUTION_MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        manifest_ref = str(EXECUTION_MANIFEST_PATH.relative_to(ROOT))
    except ValueError:
        manifest_ref = str(EXECUTION_MANIFEST_PATH)
    report["execution_manifest_path"] = manifest_ref

    if not execute:
        DRY_RUN_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return report

    if not confirmed:
        raise SystemExit("Real execution requires --confirm-ai-controlled-publication")
    if campaign != DEFAULT_CAMPAIGN:
        raise SystemExit(f"Campaign must be {DEFAULT_CAMPAIGN} for Wave-2 execution")

    repository = DuckDBContentQualityRepository(database_path)
    safety_errors = _validate_execution_safety(
        repository,
        bundles=bundles,
        manifest=manifest,
        campaign=campaign,
        required_decision=required_decision,
    )
    if safety_errors:
        raise RuntimeError("Execution blocked by safety checks: " + "; ".join(safety_errors[:8]))

    published = _execute_publication(
        repository,
        manifest=manifest,
        bundles=bundles,
        required_decision=required_decision,
    )
    report["production_db_modified"] = bool(published)
    report["published"] = published
    DRY_RUN_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return report


def run_rollback(
    *,
    campaign: str,
    execute: bool,
    confirmed: bool,
    database_path: Path,
    reason: str,
    revoked_by: str,
) -> dict[str, Any]:
    repository = DuckDBContentQualityRepository(database_path)
    if execute and not confirmed:
        raise SystemExit(f"Rollback execution requires {ROLLBACK_CONFIRMATION_FLAG}")
    result = repository.revoke_ai_controlled_campaign(
        campaign_id=campaign,
        reason=reason,
        revoked_by=revoked_by,
        dry_run=not execute,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled AI publication for D4 Wave-2.")
    parser.add_argument("--campaign", default=DEFAULT_CAMPAIGN)
    parser.add_argument("--decision", default="AI_PREVALIDATED_HIGH")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform real publication writes. Default is dry-run only.",
    )
    parser.add_argument(
        CONFIRMATION_FLAG,
        action="store_true",
        dest="confirm_publication",
        help="Required confirmation flag for real publication execution.",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback AI-controlled publications for the campaign (dry-run by default).",
    )
    parser.add_argument(
        ROLLBACK_CONFIRMATION_FLAG,
        action="store_true",
        dest="confirm_rollback",
        help="Required confirmation flag for real rollback execution.",
    )
    parser.add_argument("--rollback-reason", default="Rollback campagne LCAI-0012D4-WAVE2.")
    parser.add_argument("--revoked-by", default="AI_CONTROLLED_ROLLBACK")
    parser.add_argument(
        "--allow-non-blocking-warning",
        action="store_true",
        help="Allow AI_PREVALIDATED_WITH_WARNING when severity is NON_BLOCKING_WARNING.",
    )
    parser.add_argument("--database", default=str(ROOT / "data" / "learning_coach_v2.duckdb"))
    args = parser.parse_args()
    database_path = Path(args.database)

    if args.rollback:
        run_rollback(
            campaign=args.campaign,
            execute=args.execute,
            confirmed=args.confirm_rollback,
            database_path=database_path,
            reason=args.rollback_reason,
            revoked_by=args.revoked_by,
        )
        return

    run_publication(
        campaign=args.campaign,
        required_decision=args.decision,
        execute=args.execute,
        confirmed=args.confirm_publication,
        database_path=database_path,
        allow_non_blocking_warning=args.allow_non_blocking_warning,
    )


if __name__ == "__main__":
    main()
