"""Evidence-based analytics, explainability, authorization and rebuild use cases."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from domain.learning_intelligence.calculators import (
    calculate_metrics,
    detect_strength,
    detect_weakness,
    difficulty_guidance,
    recurring_errors,
)
from domain.learning_intelligence.models import (
    AnalyticsStatus,
    DecisionEvidenceBundle,
    EvidenceWindow,
    IndicatorResult,
    LearningEvidence,
)
from domain.learning_intelligence.policies import LearningIntelligenceConfiguration


class EvidenceRepository(Protocol):
    def for_learner_window(self, learner_id: int, window: EvidenceWindow) -> tuple[LearningEvidence, ...]: ...

    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool: ...


class SnapshotRepository(Protocol):
    def save(
        self,
        *,
        learner_id: int,
        calculation_type: str,
        scope_id: int,
        window: EvidenceWindow,
        calculation_version: str,
        configuration_version: str,
        source_cutoff: datetime,
        facts: dict[str, Any],
        indicators: dict[str, Any],
    ) -> int: ...

    def count(self, learner_id: int) -> int: ...


@dataclass(frozen=True, slots=True)
class LearningOverview:
    learner_id: int
    window: EvidenceWindow
    strengths: tuple[IndicatorResult, ...]
    weaknesses: tuple[IndicatorResult, ...]
    recurring_errors: tuple[IndicatorResult, ...]
    difficulty_guidance: tuple[IndicatorResult, ...]
    evidence_status: AnalyticsStatus
    evidence_count: int
    calculation_version: str


@dataclass(frozen=True, slots=True)
class RebuildReport:
    learner_id: int
    evidence_rows_read: int
    invalid_evidence_excluded: int
    indicators_to_create: int
    snapshots_to_create: int
    existing_results: int
    writes: int
    dry_run: bool


class LearningIntelligenceService:
    def __init__(
        self,
        evidence: EvidenceRepository,
        snapshots: SnapshotRepository | None = None,
        config: LearningIntelligenceConfiguration | None = None,
    ) -> None:
        self.evidence = evidence
        self.snapshots = snapshots
        self.config = config or LearningIntelligenceConfiguration()

    def overview(self, learner_id: int, window: EvidenceWindow, now: datetime) -> LearningOverview:
        rows = self.evidence.for_learner_window(learner_id, window)
        valid = tuple(item for item in rows if self._valid(item))
        grouped: dict[int, list[LearningEvidence]] = defaultdict(list)
        for item in valid:
            grouped[item.skill_id].append(item)
        strengths: list[IndicatorResult] = []
        weaknesses: list[IndicatorResult] = []
        errors: list[IndicatorResult] = []
        difficulties: list[IndicatorResult] = []
        for skill_id, values in sorted(grouped.items()):
            items = tuple(values)
            metrics = calculate_metrics(items)
            confidence = min(1.0, metrics.assessed_attempt_count / 6)
            repeated = recurring_errors(items, self.config)
            strength = detect_strength(metrics, confidence, self.config)
            weakness = detect_weakness(metrics, sum(count for _, count in repeated), False, self.config)
            difficulty = difficulty_guidance(metrics, confidence, False, self.config)
            refs = tuple(item.attempt_id for item in items)
            if strength.value != AnalyticsStatus.INSUFFICIENT_DATA.value:
                strengths.append(
                    self._indicator(
                        learner_id,
                        skill_id,
                        window,
                        now,
                        "STRENGTH",
                        strength.value,
                        metrics.accuracy_rate,
                        metrics.assessed_attempt_count,
                        refs,
                    )
                )
            if weakness.value != AnalyticsStatus.INSUFFICIENT_DATA.value:
                weaknesses.append(
                    self._indicator(
                        learner_id,
                        skill_id,
                        window,
                        now,
                        "WEAKNESS",
                        weakness.value,
                        metrics.accuracy_rate,
                        metrics.assessed_attempt_count,
                        refs,
                    )
                )
            for code, count in repeated:
                errors.append(
                    self._indicator(
                        learner_id,
                        skill_id,
                        window,
                        now,
                        "RECURRING_ERROR",
                        code,
                        float(count),
                        metrics.assessed_attempt_count,
                        refs,
                    )
                )
            difficulties.append(
                self._indicator(
                    learner_id,
                    skill_id,
                    window,
                    now,
                    "DIFFICULTY_GUIDANCE",
                    difficulty.value,
                    float(items[-1].difficulty),
                    metrics.assessed_attempt_count,
                    refs,
                )
            )
        status = AnalyticsStatus.AVAILABLE if valid else AnalyticsStatus.INSUFFICIENT_DATA
        return LearningOverview(
            learner_id,
            window,
            tuple(strengths),
            tuple(weaknesses),
            tuple(errors),
            tuple(difficulties),
            status,
            len(valid),
            self.config.version,
        )

    def parent_overview(
        self,
        parent_ref: str,
        learner_id: int,
        window: EvidenceWindow,
        now: datetime,
    ) -> LearningOverview:
        if not self.evidence.parent_authorized(parent_ref, learner_id):
            raise PermissionError("Parent analytics access denied")
        return self.overview(learner_id, window, now)

    def decision_evidence(self, learner_id: int, window: EvidenceWindow, now: datetime) -> DecisionEvidenceBundle:
        overview = self.overview(learner_id, window, now)
        return DecisionEvidenceBundle(
            learner_id,
            now,
            overview.weaknesses,
            overview.strengths,
            overview.difficulty_guidance,
            (),
            overview.recurring_errors,
            overview.evidence_status,
            self.config.version,
        )

    def rebuild(
        self,
        learner_id: int,
        window: EvidenceWindow,
        source_cutoff: datetime,
        *,
        dry_run: bool,
    ) -> RebuildReport:
        rows = self.evidence.for_learner_window(learner_id, window)
        invalid = sum(not self._valid(item) for item in rows)
        overview = self.overview(learner_id, window, source_cutoff)
        indicator_count = sum(
            len(items)
            for items in (
                overview.strengths,
                overview.weaknesses,
                overview.recurring_errors,
                overview.difficulty_guidance,
            )
        )
        existing = self.snapshots.count(learner_id) if self.snapshots else 0
        writes = 0
        if not dry_run and self.snapshots:
            self.snapshots.save(
                learner_id=learner_id,
                calculation_type="LEARNER_WINDOW",
                scope_id=learner_id,
                window=window,
                calculation_version=self.config.version,
                configuration_version=self.config.configuration_version,
                source_cutoff=source_cutoff,
                facts={"evidence_count": overview.evidence_count},
                indicators=asdict(overview),
            )
            writes = int(self.snapshots.count(learner_id) > existing)
        return RebuildReport(
            learner_id,
            len(rows),
            invalid,
            indicator_count,
            1,
            existing,
            writes,
            dry_run,
        )

    def weekly(self, learner_id: int, reference: datetime) -> LearningOverview:
        return self.overview(
            learner_id,
            EvidenceWindow("LAST_7_DAYS", reference - timedelta(days=7), reference),
            reference,
        )

    def monthly(self, learner_id: int, reference: datetime) -> LearningOverview:
        start = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.overview(learner_id, EvidenceWindow("CURRENT_MONTH", start, reference), reference)

    def _indicator(
        self,
        learner_id: int,
        skill_id: int,
        window: EvidenceWindow,
        now: datetime,
        code: str,
        classification: str,
        value: float,
        evidence_count: int,
        references: tuple[int, ...],
    ) -> IndicatorResult:
        status = AnalyticsStatus.AVAILABLE if evidence_count else AnalyticsStatus.INSUFFICIENT_DATA
        return IndicatorResult(
            code,
            learner_id,
            "skill",
            skill_id,
            window,
            value,
            "ratio" if code in {"STRENGTH", "WEAKNESS"} else "value",
            classification,
            self._confidence_level(evidence_count),
            evidence_count,
            status,
            self.config.version,
            now,
            f"{code}_{classification}",
            (
                ("configuration_version", self.config.configuration_version),
                ("evidence_count", str(evidence_count)),
            ),
            references,
        )

    @staticmethod
    def _confidence_level(count: int) -> str:
        if count < 3:
            return "VERY_LOW"
        if count < 5:
            return "LOW"
        if count < 8:
            return "MODERATE"
        return "HIGH"

    @staticmethod
    def _valid(item: LearningEvidence) -> bool:
        return (
            0 <= item.raw_score <= 100
            and 0 <= item.final_score <= 100
            and item.duration_seconds >= 0
            and item.expected_duration_seconds >= 0
            and 1 <= item.difficulty <= 5
        )


def default_window(now: datetime | None = None) -> EvidenceWindow:
    reference = now or datetime.now(UTC)
    return EvidenceWindow("LAST_14_DAYS", reference - timedelta(days=14), reference)
