"""Inspect the local event backlog; processing requires an explicit future handler set."""

from __future__ import annotations

import argparse
import json

from core.config import get_v2_database_path
from infrastructure.repositories.platform_runtime import DuckDBPlatformRepository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run:
        raise SystemExit("Refusing dispatch without --dry-run; no arbitrary handlers are loaded")
    counts = DuckDBPlatformRepository(get_v2_database_path()).backlog_counts()
    print(json.dumps({"dry_run": True, "limit": args.limit, "backlog": counts}, sort_keys=True))


if __name__ == "__main__":
    main()
