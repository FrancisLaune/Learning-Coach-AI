"""LCAI-0012E controlled primary Draft import CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.content.primary_draft_import import (
    IMPORT_CAMPAIGN,
    create_database_backup,
    import_primary_drafts,
    reconcile_corpus,
    rollback_primary_draft_import,
    load_authoritative_corpus,
    load_excluded_unresolved_codes,
    REPORT_PATH,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "data" / "learning_coach_v2.duckdb"
CONFIRMATION_FLAG = "--confirm-primary-draft-import"
ROLLBACK_CONFIRMATION_FLAG = "--confirm-primary-draft-import-rollback"


def _write_report(payload: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    linkage = payload.get("review_linkage", {})
    counts = payload.get("count_reconciliation", {})
    tier_before = payload.get("tier_coverage_before", {})
    tier_after = payload.get("tier_coverage_after", {})
    reconciliation = payload.get("reconciliation_status_counts", {})
    body = f"""# LCAI-0012E PRIMARY DRAFT IMPORT

Authoritative source:
{payload.get("authoritative_source")}

Import campaign:
{payload.get("campaign")}

Drafts expected:
1293

New Drafts imported:
{payload.get("new_drafts_imported")}

Already present identical:
{reconciliation.get("ALREADY_PRESENT_IDENTICAL", 0)}

Already present different:
{reconciliation.get("ALREADY_PRESENT_DIFFERENT", 0)}

Excluded unresolved curriculum:
{payload.get("excluded_unresolved_curriculum")}

Invalid references:
{payload.get("invalid_references")}

Failed imports:
{payload.get("failed_imports")}

Isolated-to-production ID mappings:
{linkage.get("mapping_records", 0)}

AI_HIGH total:
{linkage.get("ai_high_total")}

AI_HIGH resolved to production Draft:
{linkage.get("ai_high_resolved_to_production_draft")}

AI_HIGH unresolved:
{linkage.get("ai_high_unresolved")}

Review-count reconciliation:
{"PASS" if counts.get("pass") else "FAIL"}

Lifecycle Draft only:
{"PASS" if payload.get("lifecycle_draft_only") else "FAIL"}

Production gates created:
0

Approved versions created:
0

Tier coverage before:
CM1: {tier_before.get("CM1")}
CM2: {tier_before.get("CM2")}
6e: {tier_before.get("6e")}
5e: {tier_before.get("5e")}

Tier coverage after:
CM1: {tier_after.get("CM1")}
CM2: {tier_after.get("CM2")}
6e: {tier_after.get("6e")}
5e: {tier_after.get("5e")}

Tier coverage unchanged:
{"PASS" if payload.get("tier_coverage_unchanged") else "FAIL"}

Dry-run:
{"PASS" if payload.get("dry_run_pass") else "FAIL"}

Execution:
{"PASS" if payload.get("execution_pass") else "NOT RUN" if payload.get("dry_run_pass") else "FAIL"}

Idempotence:
{"PASS" if payload.get("idempotence_pass") else "NOT RUN" if payload.get("dry_run_pass") else "FAIL"}

Rollback:
{"PASS" if payload.get("rollback_pass") else "NOT RUN" if payload.get("dry_run_pass") else "FAIL"}

Production DB modified:
{payload.get("production_db_modified")}

Backup:
{payload.get("backup", {}).get("path", "N/A")}
checksum:
{payload.get("backup", {}).get("checksum_sha256", "N/A")}

Import command:
{payload.get("import_command")}

Rollback command:
{payload.get("rollback_command")}

Code commit:
{payload.get("code_commit", "NOT COMMITTED")}

Database commit:
{payload.get("database_commit", "NOT COMMITTED")}

Push:
{payload.get("push_status", "NOT PERFORMED")}

Verdict:
{payload.get("verdict")}
"""
    REPORT_PATH.write_text(body, encoding="utf-8")


def run_import(
    *,
    execute: bool,
    confirmed: bool,
    database_path: Path,
    campaign: str,
    skip_backup: bool = False,
) -> dict[str, Any]:
    if execute and not confirmed:
        raise SystemExit(f"Real execution requires {CONFIRMATION_FLAG}")

    import_command = (
        f"python scripts/run_primary_draft_import_0012e.py --execute "
        f"--database {database_path.as_posix()} --campaign {campaign} {CONFIRMATION_FLAG}"
    )
    rollback_command = (
        f"python scripts/run_primary_draft_import_0012e.py --rollback --execute "
        f"--database {database_path.as_posix()} --campaign {campaign} {ROLLBACK_CONFIRMATION_FLAG}"
    )

    backup: dict[str, Any] = {}
    if execute and not skip_backup:
        backup = create_database_backup(database_path)

    report = import_primary_drafts(database_path, execute=execute, campaign=campaign)
    report["backup"] = backup
    report["import_command"] = import_command
    report["rollback_command"] = rollback_command
    report["dry_run_pass"] = not execute
    report["execution_pass"] = execute and report["failed_imports"] == 0
    report["production_db_modified"] = "YES — DRAFT IMPORT ONLY" if execute and report["new_drafts_imported"] > 0 else "NO"
    report["idempotence_pass"] = None
    report["rollback_pass"] = None
    report["verdict"] = (
        "REQUIRES CORRECTION"
        if execute and (report["failed_imports"] > 0 or not report["tier_coverage_unchanged"])
        else "LCAI-0012E PRIMARY DRAFT IMPORT: READY FOR PUBLICATION DRY-RUN"
        if execute
        else "DRY-RUN COMPLETE — AWAITING EXECUTION"
    )
    _write_report(report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return report


def run_idempotence_check(database_path: Path, *, campaign: str) -> dict[str, Any]:
    first = import_primary_drafts(database_path, execute=True, campaign=campaign)
    second = import_primary_drafts(database_path, execute=True, campaign=campaign)
    return {
        "first_imported": first["new_drafts_imported"],
        "second_imported": second["new_drafts_imported"],
        "second_already_identical": second["reconciliation_status_counts"].get("ALREADY_PRESENT_IDENTICAL", 0),
        "pass": second["new_drafts_imported"] == 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="LCAI-0012E controlled primary Draft import.")
    parser.add_argument("--execute", action="store_true", help="Perform real import writes. Default is dry-run.")
    parser.add_argument(
        CONFIRMATION_FLAG,
        action="store_true",
        dest="confirm_import",
        help="Required confirmation flag for real import execution.",
    )
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--campaign", default=IMPORT_CAMPAIGN)
    parser.add_argument("--rollback", action="store_true", help="Rollback imported campaign drafts (dry-run default).")
    parser.add_argument(
        ROLLBACK_CONFIRMATION_FLAG,
        action="store_true",
        dest="confirm_rollback",
        help="Required confirmation flag for real rollback execution.",
    )
    parser.add_argument("--reconcile-only", action="store_true", help="Only print reconciliation summary.")
    parser.add_argument("--skip-backup", action="store_true", help="Skip pre-import backup (not recommended).")
    args = parser.parse_args()
    database_path = Path(args.database)

    if args.rollback:
        result = rollback_primary_draft_import(
            database_path,
            execute=args.execute,
            campaign=args.campaign,
        )
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return

    if args.reconcile_only:
        importable, corrected, meta = load_authoritative_corpus(database_path=database_path)
        excluded = load_excluded_unresolved_codes(corrected, importable)
        reconciliation = reconcile_corpus(importable, database_path=database_path, excluded_codes=excluded)
        print(json.dumps({"meta": meta, "reconciliation": reconciliation["status_counts"]}, ensure_ascii=True, indent=2))
        return

    run_import(
        execute=args.execute,
        confirmed=args.confirm_import,
        database_path=database_path,
        campaign=args.campaign,
        skip_backup=args.skip_backup,
    )


if __name__ == "__main__":
    main()
