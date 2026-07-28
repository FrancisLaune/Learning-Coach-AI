"""Controlled AI publication dry-run, manifest, execution, and rollback for LCAI-0012E."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.pedagogical_review import AI_REVIEW_PIPELINE_VERSION
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from scripts.run_ai_controlled_publication import (
    CONFIRMATION_FLAG,
    LOCK_RETRY_ATTEMPTS,
    LOCK_RETRY_DELAY_SECONDS,
    ROLLBACK_CONFIRMATION_FLAG,
)
from services.content.ai_controlled_publication import (
    DEFAULT_REVIEW_MODEL,
    assess_publication_eligibility,
)
from services.content.d4_review import ai_prevalidation_decision
from services.content.primary_ai_review import CAMPAIGN_ID as PRIMARY_REVIEW_CAMPAIGN
from services.content.primary_controlled_publication import (
    DRY_RUN_PATH,
    MANIFEST_PATH,
    PUBLICATION_CAMPAIGN,
    build_primary_execution_manifest,
    build_primary_publication_report,
    load_primary_publication_bundles,
    plan_primary_controlled_publication,
    primary_coverage_rows,
    verify_import_state,
    verify_review_completion,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "data" / "learning_coach_v2.duckdb"


def _find_item(bundles: list[dict[str, Any]], version_id: int) -> dict[str, Any] | None:
    for bundle in bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None:
                continue
            if int(item["version_id"]) == version_id:
                return item
            if int(item.get("isolated_version_id") or -1) == version_id:
                return item
    return None


def _validate_execution_safety(
    repository: DuckDBContentQualityRepository,
    *,
    bundles: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    manifest_ids = {int(row["production_candidate_version_id"]) for row in manifest}
    for row in manifest:
        version_id = int(row["production_candidate_version_id"])
        item = _find_item(bundles, version_id)
        if item is None:
            errors.append(f"manifest version {version_id} missing from bundles")
            continue
        eligibility = assess_publication_eligibility(
            item,
            required_decision="AI_PREVALIDATED_HIGH",
            campaign=PUBLICATION_CAMPAIGN,
            review_campaign=PRIMARY_REVIEW_CAMPAIGN,
        )
        if not eligibility.eligible:
            errors.append(f"version {version_id} no longer eligible: {eligibility.reasons[0]}")
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
            if ai_prevalidation_decision(item) == "AI_PREVALIDATED_HIGH":
                eligibility = assess_publication_eligibility(
                    item,
                    campaign=PUBLICATION_CAMPAIGN,
                    review_campaign=PRIMARY_REVIEW_CAMPAIGN,
                )
                if eligibility.eligible:
                    errors.append(f"eligible-looking version {version_id} missing from manifest")
    return errors


def _execute_publication(
    repository: DuckDBContentQualityRepository,
    *,
    manifest: list[dict[str, Any]],
    bundles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    published: list[dict[str, Any]] = []
    for row in manifest:
        version_id = int(row["production_candidate_version_id"])
        item = _find_item(bundles, version_id)
        if item is None:
            raise RuntimeError(f"Execution item missing for version {version_id}")
        if ai_prevalidation_decision(item) != "AI_PREVALIDATED_HIGH":
            raise RuntimeError(f"Decision changed for version {version_id} during execution")
        exercise_id: int | None = None
        for attempt in range(LOCK_RETRY_ATTEMPTS):
            try:
                exercise_id = repository.approve_for_ai_controlled_publication(
                    item=item,
                    review_model=str(row.get("model", DEFAULT_REVIEW_MODEL)),
                    review_pipeline=str(row.get("pipeline_version", AI_REVIEW_PIPELINE_VERSION)),
                    reason="Publication contrôlée par validation IA (CM1–5e).",
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
    execute: bool,
    confirmed: bool,
    database_path: Path,
) -> dict[str, Any]:
    review_status = verify_review_completion()
    if not review_status["complete"]:
        raise RuntimeError(
            "LCAI-0012E review is incomplete: "
            f"expected={review_status['expected_candidates']} "
            f"reviewed={review_status['reviewed_candidates']} "
            f"remaining={review_status['remaining_candidates']}"
        )

    import_status = verify_import_state(database_path)
    bundles, loader_meta = load_primary_publication_bundles()
    coverage_rows = primary_coverage_rows(database_path)
    preparation = plan_primary_controlled_publication(
        bundles,
        database_path=database_path,
        coverage_rows=coverage_rows,
    )
    manifest = build_primary_execution_manifest(
        preparation["bundles"],
        preparation["eligible_candidates"],
    )
    report = build_primary_publication_report(
        review_status=review_status,
        import_status=import_status,
        preparation=preparation,
        execute=execute,
    )
    report["loader_meta"] = loader_meta
    report["execution_manifest_count"] = len(manifest)
    report["execution_manifest_path"] = str(MANIFEST_PATH)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not execute:
        DRY_RUN_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return report

    if not confirmed:
        raise SystemExit(f"Real execution requires {CONFIRMATION_FLAG}")

    repository = DuckDBContentQualityRepository(database_path)
    safety_errors = _validate_execution_safety(repository, bundles=preparation["bundles"], manifest=manifest)
    if safety_errors:
        raise RuntimeError("Execution blocked by safety checks: " + "; ".join(safety_errors[:8]))

    published = _execute_publication(repository, manifest=manifest, bundles=preparation["bundles"])
    report["production_db_modified"] = bool(published)
    report["published"] = published
    DRY_RUN_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return report


def run_rollback(
    *,
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
        campaign_id=PUBLICATION_CAMPAIGN,
        reason=reason,
        revoked_by=revoked_by,
        dry_run=not execute,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled AI publication for LCAI-0012E CM1–5e.")
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
    parser.add_argument("--rollback-reason", default="Rollback campagne LCAI-0012E-CM1-5E-PUBLICATION-V1.")
    parser.add_argument("--revoked-by", default="AI_CONTROLLED_ROLLBACK")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    args = parser.parse_args()
    database_path = Path(args.database)

    if args.rollback:
        run_rollback(
            execute=args.execute,
            confirmed=args.confirm_rollback,
            database_path=database_path,
            reason=args.rollback_reason,
            revoked_by=args.revoked_by,
        )
        return

    run_publication(
        execute=args.execute,
        confirmed=args.confirm_publication,
        database_path=database_path,
    )


if __name__ == "__main__":
    main()
