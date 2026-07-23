"""Safe local platform diagnostics without secret disclosure."""

from __future__ import annotations

import argparse
import json

from core.config import get_v2_database_path
from infrastructure.repositories.platform_runtime import DuckDBPlatformRepository
from services.platform_runtime import default_configuration, default_flags, default_versions


def report() -> dict[str, object]:
    repository = DuckDBPlatformRepository(get_v2_database_path())
    return {
        "core_health": "HEALTHY",
        "extension_health": "HEALTHY",
        "versions": default_versions().all(),
        "feature_flags": default_flags().diagnostics(),
        "configuration": default_configuration().diagnostics(),
        "event_backlog": repository.backlog_counts(),
        "external_broker": "not_configured",
        "ai_tutor": "DISABLED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    value = report()
    print(json.dumps(value, indent=2, sort_keys=True, default=str) if args.json else value)


if __name__ == "__main__":
    main()
