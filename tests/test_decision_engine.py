from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from domain.decision.engine import decide, detect_blockages, next_window, prioritize
from domain.decision.enums import ActivityKind, ObjectiveKind, PedagogicalStrategy, PriorityBand
from domain.decision.models import (
    CandidateActivity,
    DecisionContext,
    LearnerJourney,
    PedagogicalObjective,
    WeeklyAvailability,
)
from domain.learning.enums import LearningPhase, MasteryLevel
from domain.learning.models import AcademicYear, GradeLevel, MasteryState
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.decision import DuckDBDecisionRepository
from infrastructure.repositories.v2 import LearnerRepositoryV2
from migrations.runner import apply_migrations
from services.decision import DecisionEngineService, LearnerJourneyService

NOW = datetime(2027, 6, 1, 10, tzinfo=UTC)
FOURTH = GradeLevel("FR-4E", 4, "Quatrième")
THIRD = GradeLevel("FR-3E", 3, "Troisième")
SECOND = GradeLevel("FR-2NDE", 6, "Seconde")


def objective(kind: ObjectiveKind = ObjectiveKind.PREPARATION_NEXT_GRADE, code: str = "OBJ-1") -> PedagogicalObjective:
    return PedagogicalObjective(code, kind, kind.value, date(2027, 9, 1))


def journey(
    kind: ObjectiveKind = ObjectiveKind.PREPARATION_NEXT_GRADE,
    *,
    vacation: bool = False,
    preferred: tuple[int, ...] = (1,),
    weak: tuple[int, ...] = (),
) -> LearnerJourney:
    return LearnerJourney(
        1,
        FOURTH,
        THIRD,
        AcademicYear(2026, 2027),
        objective(kind),
        None,
        objective(ObjectiveKind.PREPARATION_BREVET, "BREVET") if kind is ObjectiveKind.PREPARATION_BREVET else None,
        LearningPhase.TRANSITION_PREPARATION,
        date(2027, 9, 1),
        preferred,
        weak,
        30,
        (WeeklyAvailability(1, time(10), 30), WeeklyAvailability(3, time(17), 30)),
        3,
        False,
        True,
        "balanced",
        (1, 3),
        vacation,
        True,
        True,
    )


def candidate(
    code: str, skill: int, subject: int, *, score: float | None = None, due: bool = False, difficulty: int = 3
) -> CandidateActivity:
    mastery = None if score is None else MasteryState(1, skill, score, MasteryLevel.DEVELOPING, 5, confidence=0.7)
    return CandidateActivity(code, skill, subject, ActivityKind.LEARNING, 20, difficulty, mastery, revision_due=due)


def context(
    kind: ObjectiveKind = ObjectiveKind.PREPARATION_NEXT_GRADE,
    *,
    vacation: bool = False,
    preferred: tuple[int, ...] = (1,),
    weak: tuple[int, ...] = (),
) -> DecisionContext:
    candidates = (
        candidate("blocking", 101, 1, score=0.8),
        candidate("fragile", 102, 2, score=0.5),
        candidate("revision", 103, 1, score=0.8, due=True),
        candidate("new", 104, 3),
    )
    states = {item.skill_id: item.mastery for item in candidates if item.mastery is not None}
    states[99] = MasteryState(1, 99, 0.2, MasteryLevel.EMERGING, 4, confidence=0.8, origin_grade_code="FR-4E")
    return DecisionContext(
        journey(kind, vacation=vacation, preferred=preferred, weak=weak),
        candidates,
        states,
        {101: (99,), 99: (98,)},
        NOW,
        recent_subject_ids=(2,),
    )


def test_entry_to_third_prioritizes_blocking_previous_grade_prerequisite() -> None:
    ctx = context()
    decision = decide(ctx)
    assert decision.strategy is PedagogicalStrategy.TRANSITION_PREPARATION
    assert decision.priorities[0].band is PriorityBand.BLOCKING_PREREQUISITE
    assert decision.selected and decision.selected.candidate_id == "blocking"
    assert "Impossible de poursuivre" in decision.explanation.reason
    assert decision.blockages[0].chain == (98, 99)


@pytest.mark.parametrize(
    ("kind", "strategy"),
    [
        (ObjectiveKind.PREPARATION_BREVET, PedagogicalStrategy.EXAM_PREPARATION),
        (ObjectiveKind.PREPARATION_BAC, PedagogicalStrategy.EXAM_PREPARATION),
        (ObjectiveKind.CATCH_UP, PedagogicalStrategy.CATCH_UP),
        (ObjectiveKind.REVISION, PedagogicalStrategy.SPACED_REVISION),
        (ObjectiveKind.LONG_TERM_MASTERY, PedagogicalStrategy.BALANCED_LEARNING),
    ],
)
def test_objectives_select_configured_strategy(kind: ObjectiveKind, strategy: PedagogicalStrategy) -> None:
    assert decide(context(kind)).strategy is strategy


def test_transition_to_second_remains_generic() -> None:
    ctx = context()
    updated_journey = replace(
        ctx.journey, current_grade=THIRD, target_grade=SECOND, learning_phase=LearningPhase.TRANSITION_PREPARATION
    )
    decision = decide(replace(ctx, journey=updated_journey))
    assert decision.strategy is PedagogicalStrategy.TRANSITION_PREPARATION
    assert decision.selected is not None


def test_vacation_mode_reduces_daily_plan_without_disabling_it() -> None:
    regular = decide(context()).plan
    vacation = decide(context(vacation=True)).plan
    assert sum(item.duration_minutes for item in vacation) < sum(item.duration_minutes for item in regular)
    assert sum(item.duration_minutes for item in vacation) >= 10


def test_preferred_and_weak_subjects_change_priority_deterministically() -> None:
    baseline = prioritize(context(preferred=(), weak=()))
    boosted = prioritize(context(preferred=(2,), weak=(2,)))
    base_fragile = next(item.score for item in baseline if item.candidate_id == "fragile")
    boosted_fragile = next(item.score for item in boosted if item.candidate_id == "fragile")
    assert boosted_fragile > base_fragile
    first = decide(context())
    second = decide(context())
    assert first.context_hash == second.context_hash and first.plan == second.plan


def test_blockage_detection_reports_chain_and_critical_gap() -> None:
    blockages = detect_blockages(context())
    assert blockages[0].blocking_skill_ids == (99,)
    assert blockages[0].severity == pytest.approx(0.8)
    assert blockages[0].reason == "blocking_prerequisite"


def test_weekly_schedule_uses_next_available_window() -> None:
    # 1 June 2027 is a Tuesday (weekday 1), so today's 10:00 slot is used.
    assert next_window(context()) == NOW
    later = replace(context(), now=NOW.replace(hour=11))
    assert next_window(later).weekday() == 3


@pytest.fixture
def decision_database(tmp_path: Path) -> Path:
    path = tmp_path / "decision.duckdb"
    apply_migrations(path)
    return path


def test_journey_objective_changes_and_decisions_are_persistent(decision_database: Path) -> None:
    learner_id = LearnerRepositoryV2(decision_database).create("Decision test")
    repository = DuckDBDecisionRepository(decision_database)
    service = LearnerJourneyService(repository)
    initial = replace(journey(), learner_id=learner_id)
    service.save(initial)
    loaded = service.load(learner_id)
    assert loaded.current_objective.kind is ObjectiveKind.PREPARATION_NEXT_GRADE
    changed = service.change_objective(loaded, objective(ObjectiveKind.PREPARATION_BREVET, "NEW-BREVET"))
    assert changed.current_objective.kind is ObjectiveKind.PREPARATION_BREVET
    assert service.load(learner_id).preferred_subjects == (1,)

    real_candidates = (
        candidate("fragile", 10001, 1, score=0.5),
        candidate("revision", 10002, 2, score=0.8, due=True),
    )
    real_mastery = {item.skill_id: item.mastery for item in real_candidates if item.mastery is not None}
    ctx = replace(
        context(ObjectiveKind.PREPARATION_BREVET),
        journey=changed,
        candidates=real_candidates,
        mastery=real_mastery,
        prerequisite_graph={},
    )
    decision = DecisionEngineService(repository).decide(ctx)
    payload = repository.get_decision_payload(decision.correlation_id)
    assert payload and payload["strategy"] == "exam_preparation"
    connection = connect_v2(decision_database, read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM learning_decisions").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM decision_plan_items").fetchone()[0] >= 1
        assert connection.execute("SELECT count(*) FROM pedagogical_objectives").fetchone() == (2,)
    finally:
        connection.close()
