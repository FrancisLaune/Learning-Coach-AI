"""Thread-safe process-local operational counters without learner payloads."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from threading import Lock
from time import perf_counter


@dataclass(frozen=True, slots=True)
class OperationMeasurement:
    operation: str
    duration_ms: float
    outcome: str


class SessionOperationalMetrics:
    def __init__(self) -> None:
        self._counters: Counter[str] = Counter()
        self._durations: dict[str, list[float]] = {}
        self._lock = Lock()

    def increment(self, name: str) -> None:
        with self._lock:
            self._counters[name] += 1

    def measure(self, operation: str, started: float, outcome: str = "success") -> OperationMeasurement:
        measurement = OperationMeasurement(operation, (perf_counter() - started) * 1000, outcome)
        with self._lock:
            self._durations.setdefault(operation, []).append(measurement.duration_ms)
            self._counters[f"{operation}:{outcome}"] += 1
        return measurement

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            result = {name: float(value) for name, value in self._counters.items()}
            for operation, values in self._durations.items():
                result[f"{operation}:average_ms"] = sum(values) / len(values)
            return result
