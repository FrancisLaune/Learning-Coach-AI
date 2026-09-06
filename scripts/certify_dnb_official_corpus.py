#!/usr/bin/env python3
"""LCAI-0037 — automatic full certification of official DNB corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.brevet_referential.automatic_certification import (  # noqa: E402
    AutomaticDnbCertificationService,
)
from services.brevet_referential.migrations import apply_brevet_content_migrations  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automatically certify official DNB corpus.")
    parser.parse_args(argv)
    apply_brevet_content_migrations()
    summary = AutomaticDnbCertificationService().certify_all_official_questions()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assertions = summary.get("assertions", {})
    if assertions.get("OFFICIAL_REVIEW_COUNT", 1) != 0:
        return 2
    if assertions.get("OFFICIAL_COMPATIBILITY_REVIEW_COUNT", 1) != 0:
        return 3
    if assertions.get("ARCHIVE_DERIVED_WITHOUT_PARENT", 1) != 0:
        return 4
    if not summary.get("ready_for_review"):
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
