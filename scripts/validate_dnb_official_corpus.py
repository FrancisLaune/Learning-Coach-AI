#!/usr/bin/env python3
"""LCAI-0036 — offline pedagogical validation of official DNB corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.brevet_referential.migrations import apply_brevet_content_migrations  # noqa: E402
from services.brevet_referential.pedagogical_validation import (  # noqa: E402
    run_pedagogical_validation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate official DNB pedagogical corpus (offline).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    apply_brevet_content_migrations()
    summary = run_pedagogical_validation(dry_run=args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    invariants = summary.get("invariants", {})
    if invariants.get("ARCHIVE_DERIVED_WITHOUT_PARENT", 1) != 0:
        return 2
    if invariants.get("VALIDATED_COMPATIBLE_WITHOUT_REASON", 1) != 0:
        return 3
    if invariants.get("PLAYABLE_WITH_MISSING_REQUIRED_ASSET", 1) != 0:
        return 4
    if summary.get("stats", {}).get("audited", 0) < 1098:
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
