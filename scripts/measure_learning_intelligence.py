"""Measure deterministic Part 06 policies with generated evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from time import perf_counter

from domain.learning_intelligence.models import EvidenceWindow, LearningEvidence
from services.learning_intelligence import LearningIntelligenceService


class GeneratedEvidence:
    def __init__(self, rows: tuple[LearningEvidence, ...]) -> None:
        self.rows = rows

    def for_learner_window(self, learner_id: int, window: EvidenceWindow) -> tuple[LearningEvidence, ...]:
        return tuple(item for item in self.rows if window.start <= item.submitted_at <= window.end)

    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool:
        return parent_ref == "benchmark-parent"


def main() -> None:
    now = datetime.now(UTC)
    rows = tuple(
        LearningEvidence(
            1,
            index // 20,
            index // 5,
            index,
            index,
            10001 + index % 25,
            20000 + index % 50,
            30000 + index % 50,
            1 + index % 5,
            1 + index % 2,
            90 if index % 5 else 30,
            90 if index % 5 else 30,
            index % 5 != 0,
            45 + index % 90,
            75,
            int(index % 7 == 0),
            5 if index % 7 == 0 else 0,
            now - timedelta(days=index % 30),
            0.5,
            0.7,
            "CALCULATION_ERROR" if index % 5 == 0 else None,
        )
        for index in range(10000)
    )
    service = LearningIntelligenceService(GeneratedEvidence(rows))
    window = EvidenceWindow("LAST_30_DAYS", now - timedelta(days=30), now)
    started = perf_counter()
    overview = service.overview(1, window, now)
    elapsed = (perf_counter() - started) * 1000
    started_parent = perf_counter()
    service.parent_overview("benchmark-parent", 1, window, now)
    parent_elapsed = (perf_counter() - started_parent) * 1000
    print(
        json.dumps(
            {
                "evidence_records": len(rows),
                "learner_overview_ms": elapsed,
                "parent_overview_ms": parent_elapsed,
                "indicators": sum(
                    len(items)
                    for items in (
                        overview.strengths,
                        overview.weaknesses,
                        overview.recurring_errors,
                        overview.difficulty_guidance,
                    )
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
