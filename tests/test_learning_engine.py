from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from domain.learning.calculators import (
    apply_forgetting,
    calculate_exam,
    calculate_progress,
    calculate_transition,
    evaluate_attempt,
    evaluate_prerequisites,
    recommend_difficulty,
    update_mastery,
)
from domain.learning.enums import LearningPhase, MasteryLevel, PrerequisiteCondition
from domain.learning.events import LearningEvent
from domain.learning.models import (
    AcademicYear,
    CurriculumContext,
    ExaminationObjective,
    GradeLevel,
    LearnerAttempt,
    LearnerJourneyContext,
    MasteryState,
)
from domain.learning.policies import LearningEngineConfiguration
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.learning import DuckDBLearningRepository
from infrastructure.repositories.v2 import LearnerRepositoryV2
from migrations.runner import apply_migrations
from services.learning import LearningEngineService

NOW = datetime(2026, 9, 15, 12, tzinfo=UTC)
FOURTH = GradeLevel("FR-4E", 4, "Quatrième")
THIRD = GradeLevel("FR-3E", 5, "Troisième")
SECOND = GradeLevel("FR-2NDE", 6, "Seconde")
CONFIG = LearningEngineConfiguration()


def journey(
    phase: LearningPhase = LearningPhase.CURRENT_LEARNING,
    current: GradeLevel = THIRD,
    target: GradeLevel | None = SECOND,
    exam: str | None = None,
) -> LearnerJourneyContext:
    objective = ExaminationObjective(exam, 1) if exam else None
    return LearnerJourneyContext(1, current, target, AcademicYear(2026, 2027), phase, 1, objective)


def attempt(**changes: Any) -> LearnerAttempt:
    base = LearnerAttempt(
        stable_id="attempt-1",
        learner_id=1,
        skill_id=101,
        occurred_at=NOW,
        correctness=1.0,
        difficulty=3,
        elapsed_seconds=60,
        expected_seconds=60,
    )
    return replace(base, **changes)


@pytest.mark.parametrize(
    ("changes", "phase"),
    [
        ({}, LearningPhase.PRACTICE),
        ({"hints_used": 1}, LearningPhase.PRACTICE),
        ({"attempt_number": 3}, LearningPhase.PRACTICE),
        ({"correctness": 0.0}, LearningPhase.PRACTICE),
        ({"correctness": 0.5}, LearningPhase.PRACTICE),
        ({"abandoned": True}, LearningPhase.PRACTICE),
        ({"solution_revealed": True}, LearningPhase.PRACTICE),
        ({"elapsed_seconds": 3}, LearningPhase.PRACTICE),
        ({"elapsed_seconds": 300}, LearningPhase.PRACTICE),
        ({"difficulty": 1}, LearningPhase.DIAGNOSTIC),
        ({"difficulty": 5}, LearningPhase.EXAM_PREPARATION),
        ({"is_revision": True}, LearningPhase.SPACED_REVISION),
    ],
)
def test_attempt_evaluation_is_bounded_and_explainable(changes: dict[str, Any], phase: LearningPhase) -> None:
    result = evaluate_attempt(attempt(**changes), journey(phase), CONFIG)
    assert 0 <= result.score <= 1
    assert result.reasons


def test_hints_retries_solution_and_difficulty_have_expected_effects() -> None:
    baseline = evaluate_attempt(attempt(), journey(), CONFIG).score
    assert evaluate_attempt(attempt(hints_used=2), journey(), CONFIG).score < baseline
    assert evaluate_attempt(attempt(attempt_number=3), journey(), CONFIG).score < baseline
    assert evaluate_attempt(attempt(solution_revealed=True), journey(), CONFIG).score <= CONFIG.solution_cap
    assert (
        evaluate_attempt(attempt(difficulty=5), journey(), CONFIG).score
        > evaluate_attempt(attempt(difficulty=1), journey(), CONFIG).score
    )


def test_mastery_updates_gradually_and_survives_grade_change() -> None:
    state = MasteryState(
        1,
        101,
        score=0.6,
        level=MasteryLevel.DEVELOPING,
        observations=8,
        confidence=0.7,
        last_activity_at=NOW - timedelta(days=1),
        origin_grade_code="FR-4E",
    )
    evaluation = evaluate_attempt(attempt(), journey(current=THIRD), CONFIG)
    forgetting = apply_forgetting(state, NOW, CONFIG)
    update = update_mastery(state, evaluation, attempt(), journey(current=THIRD), forgetting, CONFIG)
    assert 0 < update.current.score - state.score < 0.2
    assert update.current.origin_grade_code == "FR-4E"
    assert update.current.last_grade_code == "FR-3E"
    failure = update_mastery(
        update.current,
        evaluate_attempt(attempt(correctness=0), journey(), CONFIG),
        attempt(correctness=0),
        journey(),
        apply_forgetting(update.current, NOW, CONFIG),
        CONFIG,
    )
    assert failure.current.score > 0.4


def test_forgetting_same_day_progressive_stable_disabled_and_floor() -> None:
    state = MasteryState(1, 101, 0.9, MasteryLevel.MASTERED, 12, 10, 2, 3, 0, NOW, NOW, 5, "FR-3E", 0.9, stability=0.8)
    assert apply_forgetting(state, NOW, CONFIG).degradation == 0
    later = apply_forgetting(state, NOW + timedelta(days=120), CONFIG)
    assert 0 < later.degradation < state.score
    unstable = replace(state, observations=1, stability=0.05)
    assert apply_forgetting(unstable, NOW + timedelta(days=120), CONFIG).degradation > later.degradation
    disabled = replace(CONFIG, forgetting_enabled=False)
    assert apply_forgetting(state, NOW + timedelta(days=500), disabled).adjusted_score == state.score
    assert later.adjusted_score >= CONFIG.forgetting_floor


def test_prerequisites_include_previous_grade_and_all_conditions() -> None:
    states = {
        1: MasteryState(1, 1, 0.8, MasteryLevel.PROFICIENT, 5, confidence=0.8, origin_grade_code="FR-3E"),
        2: MasteryState(1, 2, 0.5, MasteryLevel.DEVELOPING, 4, confidence=0.7),
        3: MasteryState(1, 3, 0.2, MasteryLevel.EMERGING, 4, confidence=0.7),
    }
    statuses = evaluate_prerequisites(states, (1, 2, 3, 4), CONFIG)
    assert tuple(s.condition for s in statuses) == (
        PrerequisiteCondition.ACQUIRED,
        PrerequisiteCondition.FRAGILE,
        PrerequisiteCondition.NOT_ACQUIRED,
        PrerequisiteCondition.NOT_EVALUATED,
    )
    assert statuses[0].origin_grade_code == "FR-3E"


def test_difficulty_rises_falls_holds_and_respects_bounds() -> None:
    forgetting = apply_forgetting(MasteryState(1, 101), NOW, CONFIG)
    strong = MasteryState(1, 101, 0.85, MasteryLevel.PROFICIENT, 8, success_streak=4, last_difficulty=4, confidence=0.9)
    assert (
        recommend_difficulty(strong, replace(forgetting, adjusted_score=0.85), (), journey(), CONFIG).recommended == 5
    )
    weak = replace(strong, score=0.3, success_streak=0, failure_streak=3, last_difficulty=1)
    assert recommend_difficulty(weak, forgetting, (), journey(), CONFIG).recommended == 1
    uncertain = replace(strong, confidence=0.2, last_difficulty=3)
    assert (
        recommend_difficulty(uncertain, replace(forgetting, adjusted_score=0.85), (), journey(), CONFIG).recommended
        == 3
    )


def test_progress_transition_and_exam_are_generic_and_never_predict_marks() -> None:
    contexts = (
        CurriculumContext(1, 10, 1, THIRD, weight=2, required=True),
        CurriculumContext(2, 20, 1, THIRD, weight=1, required=True),
        CurriculumContext(3, 20, 1, THIRD, weight=1, required=False),
    )
    states = {
        1: MasteryState(1, 1, 0.9, MasteryLevel.MASTERED, 8, confidence=0.9),
        2: MasteryState(1, 2, 0.5, MasteryLevel.DEVELOPING, 4, confidence=0.6),
    }
    progress = calculate_progress("program", 1, contexts, states, CONFIG)
    assert 0 < progress.coverage < 1 and progress.not_evaluated == 1
    transition = calculate_transition(journey(), contexts, states, CONFIG)
    assert transition is not None and transition.fragile_skills == (2,)
    for code in ("BREVET", "BACCALAUREAT"):
        exam = calculate_exam(code, contexts, states, CONFIG)
        assert 0 <= exam.score <= 1 and set(exam.subject_scores) == {10, 20}
        assert not hasattr(exam, "predicted_mark")


class MemoryRepository:
    def __init__(self) -> None:
        self.states: dict[int, MasteryState] = {}
        self.saved = 0
        self.events: tuple[LearningEvent, ...] = ()

    def is_processed(self, stable_attempt_id: str) -> bool:
        return self.saved > 0

    def get_cached_result(self, stable_attempt_id: str) -> Any:
        raise AssertionError("service cache should win")

    def load_mastery(self, learner_id: int, skill_id: int) -> MasteryState | None:
        return self.states.get(skill_id)

    def load_all_mastery(self, learner_id: int) -> dict[int, MasteryState]:
        return dict(self.states)

    def load_journey(self, learner_id: int) -> LearnerJourneyContext:
        return journey(exam="BREVET")

    def load_curriculum(self, context: LearnerJourneyContext) -> tuple[CurriculumContext, ...]:
        return (CurriculumContext(101, 1, 1, THIRD, required=True),)

    def load_prerequisite_ids(self, skill_id: int) -> tuple[int, ...]:
        return ()

    def save_cycle(
        self,
        attempt: LearnerAttempt,
        mastery: MasteryState,
        events: tuple[LearningEvent, ...],
        progress: Any,
        transition: Any,
        exam: Any,
        result_payload: dict,
    ) -> None:
        self.states[mastery.skill_id] = mastery
        self.saved += 1
        self.events = events


def test_orchestration_is_deterministic_explainable_and_idempotent() -> None:
    repository = MemoryRepository()
    service = LearningEngineService(repository)
    first = service.process(attempt())
    second = service.process(attempt())
    assert first.mastery.current.observations == 1
    assert second.already_processed
    assert repository.saved == 1
    assert len(repository.events) == first.metrics.events_produced
    assert first.progress and first.transition and first.exam


@pytest.fixture
def learning_database(tmp_path: Path) -> Path:
    path = tmp_path / "learning.duckdb"
    apply_migrations(path)
    return path


def test_duckdb_repository_full_cycle_and_longitudinal_history(learning_database: Path) -> None:
    learner_id = LearnerRepositoryV2(learning_database).create("Longitudinal test")
    repository = DuckDBLearningRepository(learning_database)
    repository.set_journey(learner_id, 1, 12, 2026, LearningPhase.TRANSITION_PREPARATION, 1, "BREVET")
    service = LearningEngineService(repository)
    first = service.process(attempt(stable_id="db-attempt-1", learner_id=learner_id, skill_id=10001))
    repository.set_journey(learner_id, 12, 13, 2027, LearningPhase.CURRENT_LEARNING, 1)
    second = service.process(
        attempt(stable_id="db-attempt-2", learner_id=learner_id, skill_id=10001, occurred_at=NOW + timedelta(days=365))
    )
    assert second.mastery.current.observations == first.mastery.current.observations + 1
    assert second.mastery.current.origin_grade_code == first.mastery.current.origin_grade_code
    connection = connect_v2(learning_database, read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM learning_attempt_inputs").fetchone() == (2,)
        assert connection.execute("SELECT count(*) FROM longitudinal_mastery_events").fetchone() == (2,)
        assert connection.execute("SELECT count(*) FROM longitudinal_mastery_current").fetchone() == (1,)
        event_count = connection.execute("SELECT count(*) FROM learning_domain_events").fetchone()[0]
        assert event_count >= 4
    finally:
        connection.close()
