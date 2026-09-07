#!/usr/bin/env python3
"""LCAI-0038 — read-only curriculum tree audit CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.brevet_referential.curriculum_audit import (  # noqa: E402
    format_tree_console,
    run_curriculum_audit,
)


def _safe_print(text: str) -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit 3e/DNB curriculum tree (read-only).")
    parser.add_argument("--subject", type=str, help="Filter one subject code (e.g. MATHEMATICS)")
    parser.add_argument("--all-subjects", action="store_true", help="Audit all subjects (default)")
    parser.add_argument("--include-content-counts", action="store_true", default=True)
    parser.add_argument("--include-official-coverage", action="store_true", default=True)
    parser.add_argument("--export", action="store_true", default=True)
    parser.add_argument("--no-export", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args(argv)

    subject = args.subject.upper() if args.subject else None
    result = run_curriculum_audit(
        subject_filter=subject,
        include_content_counts=args.include_content_counts,
        include_official_coverage=args.include_official_coverage,
        export=not args.no_export,
    )
    _safe_print(format_tree_console(result.tree_rows, verbose=args.verbose))
    _safe_print("")
    for key, value in result.verdicts.items():
        _safe_print(f"{key}: {value}")
    _safe_print("")
    ready = result.verdicts.get("CURRICULUM EXTRACTION") == "PASS"
    _safe_print("READY FOR REVIEW" if ready else "NOT READY")
    if args.json:
        _safe_print(
            json.dumps(
                {
                    "db_sha256": result.db_sha256,
                    "stats": result.stats.__dict__,
                    "subject_verdicts": result.subject_verdicts,
                    "verdicts": result.verdicts,
                    "gaps": len(result.gaps),
                    "orphans": len(result.orphans),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
