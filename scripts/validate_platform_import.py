"""Dry-run content import validation through the existing editorial importers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.content.importers import ImporterRegistry
from services.platform_runtime import ImportExportRegistry


def _load(path: Path) -> object:
    registry = ImporterRegistry.defaults()
    return registry.for_source(path).load(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    args = parser.parse_args()
    registry = ImportExportRegistry()
    for suffix in ("json", "csv", "md", "markdown", "yaml", "yml", "xlsx"):
        registry.register_importer(suffix, _load)
    preview = registry.preview(args.source)
    print(
        json.dumps(
            preview.__dict__
            if hasattr(preview, "__dict__")
            else {
                "source_hash": preview.source_hash,
                "format_name": preview.format_name,
                "status": preview.status,
                "record_count": preview.record_count,
                "writes": preview.writes,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
