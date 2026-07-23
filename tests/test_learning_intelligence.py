from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from domain.learning_intelligence.calculators import (
    calculate_metrics,
    detect_strength,
    detect_weakness,
    difficulty_guidance,
    recurring_errors,
    revision_state,
)
from domain.learning_intelligence.models import (
    AnalyticsStatus,
    DifficultyAction,
    EvidenceWindow,
    LearningEvidence,
    RevisionState,
    StrengthClassification,
    WeaknessClassification,
)
from domain.learning_intelligence.policies import LearningIntelligenceConfiguration
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.learning_intelligence import DuckDBAnalyticsSnapshotRepository
from migrations.runner import apply_migrations
from services.learning_intelligence import LearningIntelligenceService

NOW = datetime(2026, 7, 23, 10, tzinfo=UTC)
WINDOW = EvidenceWindow("LAST_14_DAYS", NOW - timedelta(days=14), NOW)
CONFIG = LearningIntelligenceConfiguration()


def evidence(
    index: int,
    *,
    success: bool = True,
    score: float = 90,
    mastery_before: float = 0.75,
    mastery_after: float = 0.9,
    hints: int = 0,
    error_code: str | None = None,
    skill_id: int = 10001,
) -> LearningEvidence:
    return LearningEvidence(
        7,
        10 + index % 2,
        20,
        100 + index,
        200 + index,
        skill_id,
        30,
        40,
        3,
        1,
        score,
        score,
        success,
        60,
        75,
        hints,
        5 if hints else 0,
        NOW - timedelta(days=5 - index),
        mastery_before,
        mastery_after,
        error_code,
    )


def test_metrics_use_assessed_denominator_and_canonical_scale() -> None:
    rows = (evidence(0), evidence(1, success=False, score=40), evidence(2, hints=1))
    result = calculate_metrics(rows)
    assert result.assessed_attempt_count == 3
    assert result.success_count == 2
    assert result.accuracy_rate == pytest.approx(2 / 3)
    assert result.average_score == pytest.approx(220 / 3)
    assert result.hint_usage_rate == pytest.approx(1 / 3)
    assert calculate_metrics(()).assessed_attempt_count == 0


def test_strength_requires_minimum_and_cross_session_evidence() -> None:
    insufficient = calculate_metrics(tuple(evidence(index) for index in range(4)))
    assert detect_strength(insufficient, 1, CONFIG) is StrengthClassification.INSUFFICIENT_DATA
    sufficient = calculate_metrics(tuple(evidence(index) for index in range(5)))
    assert detect_strength(sufficient, 0.9, CONFIG) is StrengthClassification.STABLE


def test_one_failure_is_watch_not_fragile() -> None:
    metrics = calculate_metrics((evidence(0, success=False, score=20, mastery_after=0.3),))
    assert detect_weakness(metrics, 0, False, CONFIG) is WeaknessClassification.WATCH


def test_recurring_structured_error_triggers_remediation() -> None:
    rows = tuple(
        evidence(index, success=False, score=30, mastery_after=0.4, error_code="INVERSION") for index in range(4)
    )
    assert recurring_errors(rows, CONFIG) == (("INVERSION", 4),)
    metrics = calculate_metrics(rows)
    assert detect_weakness(metrics, 4, False, CONFIG) is WeaknessClassification.REMEDIATION_REQUIRED


@pytest.mark.parametrize(
    ("rows", "confidence", "blocked", "expected"),
    [
        (tuple(evidence(i) for i in range(4)), 0.9, False, DifficultyAction.INCREASE),
        (
            tuple(evidence(i, success=False, score=30, mastery_after=0.3) for i in range(4)),
            0.9,
            False,
            DifficultyAction.DECREASE,
        ),
        (tuple(evidence(i) for i in range(4)), 0.9, True, DifficultyAction.DECREASE),
        (tuple(evidence(i) for i in range(3)), 0.9, False, DifficultyAction.INSUFFICIENT_DATA),
    ],
)
def test_difficulty_policy_boundaries(
    rows: tuple[LearningEvidence, ...],
    confidence: float,
    blocked: bool,
    expected: DifficultyAction,
) -> None:
    assert difficulty_guidance(calculate_metrics(rows), confidence, blocked, CONFIG) is expected


def test_revision_states_are_deterministic() -> None:
    assert revision_state(None, NOW, 0.9, CONFIG) is RevisionState.NOT_APPLICABLE
    assert revision_state(NOW + timedelta(days=2), NOW, 0.9, CONFIG) is RevisionState.DUE_SOON
    assert revision_state(NOW, NOW, 0.9, CONFIG) is RevisionState.DUE
    assert revision_state(NOW - timedelta(days=10), NOW, 0.9, CONFIG) is RevisionState.HIGH_PRIORITY_OVERDUE


class MemoryEvidence:
    def __init__(self, rows: tuple[LearningEvidence, ...], authorized: bool = True) -> None:
        self.rows = rows
        self.authorized = authorized

    def for_learner_window(self, learner_id: int, window: EvidenceWindow) -> tuple[LearningEvidence, ...]:
        return self.rows

    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool:
        return self.authorized


class MemorySnapshots:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    def save(self, **values: object) -> int:
        self.keys.add(str(values))
        return 1

    def count(self, learner_id: int) -> int:
        return len(self.keys)


def test_overview_is_structured_explainable_and_deterministic() -> None:
    rows = tuple(evidence(index) for index in range(5))
    service = LearningIntelligenceService(MemoryEvidence(rows))
    first = service.overview(7, WINDOW, NOW)
    second = service.overview(7, WINDOW, NOW)
    assert first == second
    assert first.evidence_status is AnalyticsStatus.AVAILABLE
    assert first.strengths[0].source_references
    assert first.strengths[0].explanation_parameters


def test_parent_authorization_precedes_analytics() -> None:
    service = LearningIntelligenceService(MemoryEvidence((), authorized=False))
    with pytest.raises(PermissionError):
        service.parent_overview("forged-parent", 7, WINDOW, NOW)


def test_invalid_evidence_is_excluded_and_dry_run_writes_nothing() -> None:
    invalid = replace(evidence(0), final_score=101)
    snapshots = MemorySnapshots()
    service = LearningIntelligenceService(MemoryEvidence((invalid,)), snapshots)
    report = service.rebuild(7, WINDOW, NOW, dry_run=True)
    assert report.invalid_evidence_excluded == 1
    assert report.writes == 0
    assert snapshots.count(7) == 0


def test_rebuild_is_idempotent_at_active_snapshot_level() -> None:
    snapshots = MemorySnapshots()
    service = LearningIntelligenceService(MemoryEvidence((evidence(0),)), snapshots)
    first = service.rebuild(7, WINDOW, NOW, dry_run=False)
    second = service.rebuild(7, WINDOW, NOW, dry_run=False)
    assert first.writes == 1
    assert second.writes == 0


def test_duckdb_snapshot_stable_key_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "intelligence.duckdb"
    apply_migrations(path)
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute("INSERT INTO learners(display_name) VALUES ('Test') RETURNING id").fetchone()[0]
        )
    finally:
        connection.close()
    repository = DuckDBAnalyticsSnapshotRepository(path)

    def save() -> int:
        return repository.save(
            learner_id=learner_id,
            calculation_type="SKILL",
            scope_id=10001,
            window=WINDOW,
            calculation_version=CONFIG.version,
            configuration_version=CONFIG.configuration_version,
            source_cutoff=NOW,
            facts={"attempts": 5},
            indicators={"accuracy": 0.8},
        )

    first = save()
    second = save()
    assert first == second
    assert repository.count(learner_id) == 1
