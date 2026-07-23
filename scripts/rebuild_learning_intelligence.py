"""Deterministically rebuild derived Learning Intelligence snapshots."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from domain.learning_intelligence.models import EvidenceWindow
from infrastructure.repositories.learning_intelligence import (
    DuckDBAnalyticsSnapshotRepository,
    DuckDBLearningEvidenceRepository,
)
from services.learning_intelligence import LearningIntelligenceService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--learner-id", type=int, required=True)
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    now = datetime.now(UTC)
    start = (
        datetime.fromisoformat(arguments.from_date).astimezone(UTC) if arguments.from_date else now - timedelta(days=30)
    )
    end = datetime.fromisoformat(arguments.to_date).astimezone(UTC) if arguments.to_date else now
    window = EvidenceWindow("CUSTOM", start, end)
    service = LearningIntelligenceService(
        DuckDBLearningEvidenceRepository(),
        DuckDBAnalyticsSnapshotRepository(),
    )
    report = service.rebuild(arguments.learner_id, window, end, dry_run=arguments.dry_run)
    print(json.dumps(asdict(report), indent=2, default=str))


if __name__ == "__main__":
    main()
