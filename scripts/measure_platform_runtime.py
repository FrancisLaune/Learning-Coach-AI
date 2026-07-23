"""Deterministic local micro-benchmarks for initialized platform registries."""

from __future__ import annotations

import json
import time

from services.platform_runtime import PluginRegistry, default_configuration, default_flags


def _average_ms(operation: object, iterations: int = 10_000) -> float:
    callable_operation = operation
    assert callable(callable_operation)
    started = time.perf_counter()
    for _ in range(iterations):
        callable_operation()
    return (time.perf_counter() - started) * 1000 / iterations


def main() -> None:
    configuration = default_configuration()
    flags = default_flags()
    plugins = PluginRegistry()
    values = {
        "configuration_lookup_average_ms": _average_ms(lambda: configuration.get("session.autosave_interval_seconds")),
        "feature_flag_lookup_average_ms": _average_ms(lambda: flags.enabled("v2.enabled")),
        "plugin_registry_lookup_average_ms": _average_ms(plugins.states),
    }
    print(json.dumps(values, sort_keys=True))


if __name__ == "__main__":
    main()
