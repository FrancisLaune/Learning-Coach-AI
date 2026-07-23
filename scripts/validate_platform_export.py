"""Validate an export request without querying or writing learner data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.platform_runtime import ImportExportRegistry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--filename", default="learning-summary.json")
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument("--dry-run", action="store_true", required=True)
    args = parser.parse_args()
    if not args.authorized:
        raise SystemExit("EXPORT_ACCESS_DENIED")
    target = ImportExportRegistry.safe_output(args.output_directory, args.filename)
    print(json.dumps({"authorized": True, "dry_run": True, "target": str(target), "writes": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
