#!/usr/bin/env python3
"""LCAI-0035 — offline CLI for massive official DNB archive ingestion.

Never call this from Streamlit runtime. Admin/offline only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.brevet_referential.catalog import (  # noqa: E402
    sync_manifest_from_catalog,
    write_catalog,
)
from services.brevet_referential.massive_ingest import run_ingestion  # noqa: E402
from services.brevet_referential.migrations import apply_brevet_content_migrations  # noqa: E402


def _parse_years(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    if ":" in value:
        left, right = value.split(":", 1)
        return int(left), int(right)
    year = int(value)
    return year, year


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest official DNB EduScol archives (offline).")
    parser.add_argument("--year", type=int, help="Single year filter")
    parser.add_argument("--years", type=str, help="Inclusive range YEAR:YEAR (e.g. 2018:2026)")
    parser.add_argument("--subject", type=str, help="Subject filter (MATHEMATICS, FRENCH, ...)")
    parser.add_argument("--archive-id", type=str, help="exam_identity_key or eduscol document id")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--parse-only", action="store_true")
    parser.add_argument("--map-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", action="store_true", default=True)
    parser.add_argument("--no-report", action="store_true")
    parser.add_argument("--include-accessibility", action="store_true")
    parser.add_argument("--rebuild-catalog", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    apply_brevet_content_migrations()
    if args.rebuild_catalog:
        path = write_catalog(include_accessibility=True)
        sync_manifest_from_catalog()
        print(json.dumps({"catalog": str(path)}, ensure_ascii=False))
    years = _parse_years(args.years)
    if args.year is not None:
        years = (args.year, args.year)
    if years is None and not args.validate_only and not args.archive_id:
        years = (2018, 2026)
    summary = run_ingestion(
        years=years,
        subject=args.subject,
        archive_id=args.archive_id,
        download_only=args.download_only,
        parse_only=args.parse_only,
        map_only=args.map_only,
        validate_only=args.validate_only,
        resume=not args.no_resume,
        force=args.force,
        dry_run=args.dry_run,
        include_accessibility=args.include_accessibility,
        report=not args.no_report,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary.get("pass_official_gt_3", False) and not args.dry_run and not args.download_only:
        return 2
    if not summary.get("pass_orphan_invariant", True):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
