"""LCAI-0018E — 6e industrialization pipeline (verify, publish, audit)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.pedagogical_review import AI_REVIEW_PIPELINE_VERSION
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from scripts.run_ai_controlled_publication_0012e import (
    CONFIRMATION_FLAG,
    _execute_publication,
    _find_item,
)
from services.content.ai_controlled_publication import assess_publication_eligibility
from services.content.d4_review import ai_prevalidation_decision
from services.content.primary_ai_review import CAMPAIGN_ID as PRIMARY_REVIEW_CAMPAIGN
from services.content.primary_controlled_publication import (
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
GRADE = "FR-6E"
REPORT_DIR = ROOT / "docs" / "phase3" / "exports"
SIXE_MANIFEST_PATH = REPORT_DIR / "lcai_0018e_6e_publication_manifest.json"
SIXE_REPORT_PATH = REPORT_DIR / "lcai_0018e_6e_publication_report.json"


def _validate_6e_execution_safety(
    repository: DuckDBContentQualityRepository,
    *,
    bundles: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
    grade: str,
) -> list[str]:
    errors: list[str] = []
    manifest_ids = {int(row["production_candidate_version_id"]) for row in manifest}
    for row in manifest:
        version_id = int(row["production_candidate_version_id"])
        item = _find_item(bundles, version_id)
        if item is None:
            errors.append(f"manifest version {version_id} missing from bundles")
            continue
        if item.get("grade") != grade:
            errors.append(f"manifest version {version_id} grade mismatch: {item.get('grade')}")
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
            if item is None or item.get("grade") != grade:
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
                    errors.append(f"eligible 6e version {version_id} missing from manifest")
    return errors


def run_6e_publication(
    *,
    execute: bool,
    confirmed: bool,
    database_path: Path,
) -> dict[str, Any]:
    review_status = verify_review_completion()
    if not review_status["complete"]:
        raise RuntimeError(
            "LCAI-0012E review incomplete: "
            f"expected={review_status['expected_candidates']} "
            f"reviewed={review_status['reviewed_candidates']}"
        )

    import_status = verify_import_state(database_path)
    bundles, loader_meta = load_primary_publication_bundles()
    coverage_rows = primary_coverage_rows(database_path)
    preparation = plan_primary_controlled_publication(
        bundles,
        database_path=database_path,
        coverage_rows=coverage_rows,
    )
    full_manifest = build_primary_execution_manifest(
        preparation["bundles"],
        preparation["eligible_candidates"],
    )
    manifest = [row for row in full_manifest if row.get("grade") == GRADE]

    report = build_primary_publication_report(
        review_status=review_status,
        import_status=import_status,
        preparation=preparation,
        execute=execute,
    )
    report["scope"] = GRADE
    report["loader_meta"] = loader_meta
    report["execution_manifest_count_full"] = len(full_manifest)
    report["execution_manifest_count_6e"] = len(manifest)
    report["execution_manifest_path"] = str(SIXE_MANIFEST_PATH)
    report["review_pipeline"] = AI_REVIEW_PIPELINE_VERSION

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SIXE_MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not execute:
        report["production_db_modified"] = False
        report["published"] = []
        SIXE_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return report

    if not confirmed:
        raise SystemExit(f"Real execution requires {CONFIRMATION_FLAG}")

    repository = DuckDBContentQualityRepository(database_path)
    safety_errors = _validate_6e_execution_safety(
        repository,
        bundles=preparation["bundles"],
        manifest=manifest,
        grade=GRADE,
    )
    if safety_errors:
        raise RuntimeError("6e execution blocked: " + "; ".join(safety_errors[:8]))

    published = _execute_publication(repository, manifest=manifest, bundles=preparation["bundles"])
    report["production_db_modified"] = bool(published)
    report["published"] = published
    report["published_count"] = len(published)
    SIXE_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="LCAI-0018E 6e controlled publication pipeline.")
    parser.add_argument("--execute", action="store_true", help="Perform real 6e publication writes.")
    parser.add_argument(
        CONFIRMATION_FLAG,
        action="store_true",
        dest="confirm_publication",
        help="Required confirmation for real execution.",
    )
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    args = parser.parse_args()
    run_6e_publication(
        execute=args.execute,
        confirmed=args.confirm_publication,
        database_path=Path(args.database),
    )


if __name__ == "__main__":
    main()
