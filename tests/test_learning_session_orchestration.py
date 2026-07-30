from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

from domain.learning_session.models import (
    ActivityStatus,
    AnswerType,
    AssessmentMethod,
    LearningSession,
    SessionActivity,
    SessionCheckpoint,
    SessionEvent,
    SessionStatus,
    StudentAnswer,
)
from services.learning_session.assessment import (
    AnswerValidationError,
    DeterministicAssessmentEngine,
    format_decimal_fr,
)
from services.learning_session.models import (
    ActivityExecutionState,
    ActivityExecutionStatus,
    AssessmentRequest,
    ExecutableActivity,
    ExecutionProposal,
)
from services.learning_session.orchestration import (
    ActivityRunner,
    SessionScheduler,
    SessionStateManager,
)
from services.learning_session.recovery import AutoSaveService, OfflineBuffer, ResumeService

NOW = datetime(2026, 7, 23, 10, tzinfo=UTC)


def activity(**changes: Any) -> ExecutableActivity:
    base = ExecutableActivity(1, 10, 20, "Fractions", "exercise", 3, 300, 1, 30, True, True, (40,), True)
    return replace(base, **changes)


def proposal(*activities: ExecutableActivity, seconds: int = 900) -> ExecutionProposal:
    return ExecutionProposal(5, 7, 8, "proposal-5", seconds, "revision", "decision-v1", activities)


def session(status: SessionStatus = SessionStatus.RUNNING) -> LearningSession:
    return LearningSession(
        1,
        7,
        8,
        5,
        status,
        NOW,
        900,
        "v2",
        "curriculum-v1",
        "20",
        "decision-v1",
        "assessment-v1",
    )


def answer(key: str = "answer-1") -> StudentAnswer:
    return StudentAnswer(0, 1, 40, 1, AnswerType.INTEGER, "4", 4, NOW, 1000, True, False, key)


def checkpoint() -> SessionCheckpoint:
    return SessionCheckpoint(3, 1, 1, 40, 500, None, NOW)


def test_scheduler_is_deterministic_and_enforces_execution_contract() -> None:
    scheduler = SessionScheduler()
    second = activity(proposal_item_id=2, content_id=11, content_version_id=21, order=2)
    assert [item.content_id for item in scheduler.schedule(proposal(second, activity()))] == [10, 11]
    with pytest.raises(ValueError, match="Duplicate"):
        scheduler.schedule(proposal(activity(), replace(activity(), proposal_item_id=2, order=2)))
    with pytest.raises(ValueError, match="Approved"):
        scheduler.schedule(proposal(activity(approved=False)))
    with pytest.raises(ValueError, match="duration"):
        scheduler.schedule(proposal(activity(), seconds=200))
    with pytest.raises(ValueError, match="questions"):
        scheduler.schedule(proposal(activity(question_ids=())))
    with pytest.raises(ValueError, match="prerequisites"):
        scheduler.schedule(proposal(activity(prerequisites_satisfied=False)))


@pytest.mark.parametrize(
    ("answer_type", "method", "actual", "expected", "score"),
    [
        (AnswerType.INTEGER, AssessmentMethod.NUMERIC_EQUALITY, "04", 4, 100),
        (AnswerType.DECIMAL, AssessmentMethod.NUMERIC_TOLERANCE, "3,14", "3.15", 100),
        (AnswerType.FRACTION, AssessmentMethod.FRACTION_SIMPLIFICATION, "2/4", "1/2", 100),
        (AnswerType.BOOLEAN, AssessmentMethod.BOOLEAN, "vrai", True, 100),
        (AnswerType.FORMULA, AssessmentMethod.FORMULA, "x × 2", "x*2", 100),
        (AnswerType.ORDERING, AssessmentMethod.ORDERING, ["a", "b"], ["a", "c"], 50),
        (AnswerType.MATCHING, AssessmentMethod.MATCHING, {"a": "1"}, {"a": "1", "b": "2"}, 50),
    ],
)
def test_deterministic_assessment_strategies(
    answer_type: AnswerType,
    method: AssessmentMethod,
    actual: object,
    expected: object,
    score: float,
) -> None:
    result = DeterministicAssessmentEngine().assess(
        AssessmentRequest(answer_type, actual, expected, method, tolerance=0.01)
    )
    assert result.raw_score == score


def test_assessment_is_repeatable_and_applies_declared_penalties() -> None:
    request = AssessmentRequest(
        AnswerType.MCQ_MULTI,
        ["a"],
        ["a", "c"],
        AssessmentMethod.MCQ,
        correct_options=("a", "c"),
        hint_penalties=(5, 10),
        manual_penalty=2,
        time_bonus=3,
        feedback={"incorrect": "Relis la règle fournie."},
    )
    engine = DeterministicAssessmentEngine()
    assert engine.assess(request) == engine.assess(request)
    assert engine.assess(request).final_score == 36
    with pytest.raises(AnswerValidationError):
        engine.assess(replace(request, raw_answer="not-a-list"))
    assert engine.normalize(AnswerType.DECIMAL, "1,5") == Decimal("1.5")
    assert format_decimal_fr(engine.normalize(AnswerType.DECIMAL, "1,5")) == "1,5"
    assert engine.normalize(AnswerType.FRACTION, "2/4") == Fraction(1, 2)


def test_activity_runtime_state_machine_locks_submitted_answers() -> None:
    manager = SessionStateManager()
    state = ActivityExecutionState(1, ActivityExecutionStatus.NOT_STARTED)
    observed = []
    while state.status is not ActivityExecutionStatus.COMPLETED:
        state = manager.advance(state)
        observed.append(state.status)
    assert observed == list(ActivityExecutionStatus)[1:]
    assert state.answer_locked
    with pytest.raises(ValueError):
        manager.advance(state)


class MemoryRepository:
    def __init__(self) -> None:
        self.current = session()
        self.activities = [SessionActivity(1, 1, 10, 20, 1, "exercise", 3, 300)]
        self.checkpoint = checkpoint()
        self.autosaves = 0

    def list_activities(self, session_id: int) -> tuple[SessionActivity, ...]:
        return tuple(self.activities)

    def update_activity(self, item: SessionActivity) -> None:
        self.activities[0] = item

    def find_resumable(self, learner_id: int) -> LearningSession | None:
        return self.current

    def transition(self, session_id: int, expected: SessionStatus, target: SessionStatus, at: datetime) -> None:
        assert self.current.status is expected
        self.current = self.current.transition(target, at)

    def latest_checkpoint(self, session_id: int) -> SessionCheckpoint | None:
        return self.checkpoint

    def autosave(
        self, submitted: StudentAnswer, saved_checkpoint: SessionCheckpoint, event: SessionEvent
    ) -> StudentAnswer:
        self.autosaves += 1
        assert saved_checkpoint.session_id == event.session_id == 1
        return replace(submitted, answer_id=9, draft=True)


def test_activity_runner_executes_only_selected_activity() -> None:
    repository = MemoryRepository()
    runner = ActivityRunner(repository)  # type: ignore[arg-type]
    started = runner.start(repository.current, 1)
    assert started.status is ActivityStatus.RUNNING
    completed = runner.complete(repository.current, 1, 80, 4)
    assert completed.status is ActivityStatus.COMPLETED
    assert completed.score == 80


def test_autosave_and_resume_require_active_owned_session() -> None:
    repository = MemoryRepository()
    autosave = AutoSaveService(repository)
    saved = autosave.save(repository.current, answer(), checkpoint(), NOW)
    assert saved.answer_id == 9
    assert repository.autosaves == 1

    repository.current = replace(repository.current, status=SessionStatus.PAUSED)
    recovery = ResumeService(repository, repository).resume(7, NOW + timedelta(seconds=1))  # type: ignore[arg-type]
    assert recovery.integrity_valid
    assert repository.current.status is SessionStatus.RUNNING


def test_failed_autosave_is_buffered_idempotently() -> None:
    class FailingRepository:
        def autosave(self, *_: object) -> StudentAnswer:
            raise OSError("offline")

    buffer = OfflineBuffer()
    service = AutoSaveService(FailingRepository(), buffer)
    with pytest.raises(OSError, match="offline"):
        service.save(session(), answer(), checkpoint(), NOW)
    buffer.put(answer())
    assert buffer.pending() == (answer(),)
