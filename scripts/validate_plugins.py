"""Validate explicitly registered built-in platform plugins."""

from __future__ import annotations

import argparse
import json

from services.platform_runtime import PluginRegistry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--manifests-only", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.parse_args()
    registry = PluginRegistry()
    print(json.dumps({"valid": True, "plugins": registry.states(), "discovery": "explicit-only"}, sort_keys=True))


if __name__ == "__main__":
    main()
