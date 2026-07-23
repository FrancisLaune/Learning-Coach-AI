"""CLI for reproducible dry-run or real catalog import."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.repositories.curriculum import DuckDBCurriculumRepository  # noqa: E402
from services.curriculum import CurriculumImportService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = CurriculumImportService(DuckDBCurriculumRepository(args.database)).import_file(
        args.source, dry_run=args.dry_run
    )
    print(report)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
