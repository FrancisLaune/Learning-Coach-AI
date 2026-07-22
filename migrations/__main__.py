"""Command-line entry point for DuckDB V2 migrations."""

from __future__ import annotations

import argparse
from pathlib import Path

from migrations.runner import apply_migrations


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Learning Coach AI DuckDB V2 migrations")
    parser.add_argument("--database", type=Path, help="Target DuckDB file")
    args = parser.parse_args()
    applied = apply_migrations(args.database)
    for migration in applied:
        print(f"Applied {migration.version:03d}_{migration.name}")
    print(f"Migration complete: {len(applied)} newly applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
