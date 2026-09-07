#!/usr/bin/env python3
"""LCAI-0039 — rebuild 3e curriculum CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.brevet_referential.curriculum_rebuild.orchestrator import run_rebuild  # noqa: E402


def _safe_print(text: str) -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild 3e/DNB curriculum (LCAI-0039).")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--subject", type=str)
    parser.add_argument("--remap-only", action="store_true")
    parser.add_argument("--fill-gaps", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not any([args.dry_run, args.apply, args.remap_only, args.fill_gaps, args.report_only]):
        parser.error("Choose --dry-run, --apply, --remap-only, --fill-gaps or --report-only")

    subject = args.subject.upper() if args.subject else None
    mode = "dry-run" if args.dry_run else "apply"
    if args.remap_only:
        mode = "remap-only"
    if args.fill_gaps:
        mode = "fill-gaps"
    if args.report_only:
        mode = "report-only"

    result = run_rebuild(
        mode=mode,
        subject=subject,
        dry_run=bool(args.dry_run),
        remap_only=bool(args.remap_only),
        fill_gaps=bool(args.fill_gaps),
        report_only=bool(args.report_only),
    )
    for key, value in result.verdicts.items():
        _safe_print(f"{key}: {value}")
    impl = Path("artifacts/LCAI-0039/LCAI-0039_IMPLEMENTATION_REPORT.md").read_text(encoding="utf-8")
    last = [ln for ln in impl.splitlines() if ln.strip()][-1]
    _safe_print("")
    _safe_print(last)
    if args.json:
        _safe_print(
            json.dumps(
                {
                    "before": result.before_counts,
                    "after": result.after_counts,
                    "verdicts": result.verdicts,
                    "subject_verdicts": result.subject_verdicts,
                    "factory": {k: v for k, v in result.factory_stats.items() if k != "generation_rows"},
                    "remap": {k: v for k, v in result.remap_stats.items() if k != "rows"},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0 if last == "READY FOR REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
