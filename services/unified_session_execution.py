"""Complete question-to-mastery flow composed from validated session engines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from domain.learning.models import LearningEngineResult
from domain.learning_session.models import (
    ActivityStatus,
    AnswerType,
    AssessmentMethod,
    SessionStatus,
)
from services.learning_session.models import AssessmentRequest, SubmissionContext
from services.learning_session.orchestration import ActivityRunner, LearningSessionService
from services.learning_session.submission import SubmissionService


@dataclass(frozen=True, slots=True)
class ExecutableQuestion:
    session_id: int
    activity_id: int
    activity_title: str
    skill_id: int
    question_id: int
    instructions: str
    context: str | None
    statement: str
    response_type: str
    options: tuple[tuple[str, str], ...]
    hints: tuple[tuple[int, str, float], ...]
    difficulty: int
    position: int
    total: int


@dataclass(frozen=True, slots=True)
class QuestionAssessmentView:
    correct: bool
    score: float
    explanation: str
    method: str
    advice: str
    mastery_before: float
    mastery_after: float
    session_completed: bool
    skipped: bool = False


@dataclass(frozen=True, slots=True)
class AnswerCorrectionItem:
    question_id: int
    position: int
    statement: str
    student_answer: str
    expected_answer: str
    correct: bool
    score: float
    explanation: str
    method: str


@dataclass(frozen=True, slots=True)
class QuestionMaterial:
    question: ExecutableQuestion
    expected_answer: Any
    tolerance: float
    solution_explanation: str
    solution_method: str
    solution_advice: str
    current_mastery: float
    previous_attempts: int


class SessionExecutionRepository(Protocol):
    def current_question(self, learner_id: int, session_id: int) -> QuestionMaterial | None: ...
    def used_hint_penalties(self, activity_id: int) -> tuple[float, ...]: ...
    def activity_question_count(self, activity_id: int) -> tuple[int, int]: ...
    def record_hint(self, activity_id: int, hint_id: int, hint_number: int, penalty: float, at: datetime) -> None: ...
    def complete_homework(self, session_id: int) -> None: ...
    def list_corrections(self, learner_id: int, session_id: int) -> tuple[AnswerCorrectionItem, ...]: ...


class DecisionRefreshNotifier:
    def __init__(self, enqueue: Any) -> None:
        self.enqueue = enqueue

    def notify_mastery_updated(self, result: LearningEngineResult) -> None:
        self.enqueue(result)


class UnifiedSessionExecutionService:
    def __init__(
        self,
        repository: SessionExecutionRepository,
        submission: SubmissionService,
        sessions: LearningSessionService,
        runner: ActivityRunner,
    ) -> None:
        self.repository = repository
        self.submission = submission
        self.sessions = sessions
        self.runner = runner

    def current(self, learner_id: int, session_id: int) -> ExecutableQuestion | None:
        material = self.current_material(learner_id, session_id)
        return None if material is None else material.question

    def current_material(self, learner_id: int, session_id: int) -> QuestionMaterial | None:
        session = self.sessions.repository.get(session_id)
        if session is None or session.learner_id != learner_id:
            raise PermissionError("SESSION_ACCESS_DENIED")
        return self.repository.current_question(learner_id, session_id)

    def submit(
        self,
        learner_id: int,
        session_id: int,
        raw_answer: Any,
        occurred_at: datetime,
        elapsed_ms: int,
    ) -> QuestionAssessmentView:
        session = self.sessions.repository.get(session_id)
        if session is None or session.learner_id != learner_id:
            raise PermissionError("SESSION_ACCESS_DENIED")
        if session.status is not SessionStatus.RUNNING:
            raise ValueError("La séance doit être démarrée avant de répondre.")
        material = self.repository.current_question(learner_id, session_id)
        if material is None:
            raise ValueError("Aucune question active.")
        activity = next(
            item
            for item in self.sessions.repository.list_activities(session_id)
            if item.activity_id == material.question.activity_id
        )
        if activity.status is ActivityStatus.NOT_STARTED:
            self.runner.start(session, activity.activity_id)
        answer_type, method = self._strategy(material.question.response_type)
        idempotency_key = (
            f"ui:{session_id}:{material.question.activity_id}:{material.question.question_id}:"
            f"{material.previous_attempts + 1}"
        )
        saved, assessment, learning = self.submission.submit(
            SubmissionContext(
                learner_id,
                material.question.skill_id,
                material.question.activity_id,
                material.question.question_id,
                material.previous_attempts + 1,
                occurred_at,
                elapsed_ms,
                idempotency_key,
            ),
            AssessmentRequest(
                answer_type,
                raw_answer,
                material.expected_answer,
                method,
                correct_options=(
                    tuple(str(item) for item in material.expected_answer)
                    if answer_type is AnswerType.MCQ_MULTI and isinstance(material.expected_answer, (list, tuple))
                    else ()
                ),
                tolerance=material.tolerance,
                hint_penalties=self.repository.used_hint_penalties(material.question.activity_id),
                difficulty=material.question.difficulty,
                current_mastery=material.current_mastery,
                previous_attempts=material.previous_attempts,
                feedback={"question_id": material.question.question_id},
            ),
        )
        answered, total = self.repository.activity_question_count(material.question.activity_id)
        if answered >= total:
            current = self.sessions.repository.get(session_id)
            assert current is not None
            self.runner.complete(
                current, material.question.activity_id, assessment.final_score, assessment.mastery_delta
            )
        session_completed = self._complete_if_finished(session_id, occurred_at)
        return QuestionAssessmentView(
            assessment.correct,
            assessment.final_score,
            material.solution_explanation,
            material.solution_method,
            material.solution_advice,
            saved.mastery_before,
            saved.mastery_after,
            session_completed,
            skipped=False,
        )

    def skip(
        self,
        learner_id: int,
        session_id: int,
        occurred_at: datetime,
        elapsed_ms: int,
    ) -> QuestionAssessmentView:
        """Advance past the current question without counting a success."""
        session = self.sessions.repository.get(session_id)
        if session is None or session.learner_id != learner_id:
            raise PermissionError("SESSION_ACCESS_DENIED")
        if session.status is not SessionStatus.RUNNING:
            raise ValueError("La séance doit être démarrée avant de passer une question.")
        material = self.repository.current_question(learner_id, session_id)
        if material is None:
            raise ValueError("Aucune question active.")
        activity = next(
            item
            for item in self.sessions.repository.list_activities(session_id)
            if item.activity_id == material.question.activity_id
        )
        if activity.status is ActivityStatus.NOT_STARTED:
            self.runner.start(session, activity.activity_id)
        idempotency_key = (
            f"ui-skip:{session_id}:{material.question.activity_id}:{material.question.question_id}:"
            f"{material.previous_attempts + 1}"
        )
        saved = self.submission.record_skip(
            SubmissionContext(
                learner_id,
                material.question.skill_id,
                material.question.activity_id,
                material.question.question_id,
                material.previous_attempts + 1,
                occurred_at,
                elapsed_ms,
                idempotency_key,
            ),
            current_mastery=material.current_mastery,
            feedback={
                "question_id": material.question.question_id,
                "skipped": True,
            },
        )
        answered, total = self.repository.activity_question_count(material.question.activity_id)
        if answered >= total:
            current = self.sessions.repository.get(session_id)
            assert current is not None
            self.runner.complete(current, material.question.activity_id, 0.0, 0.0)
        session_completed = self._complete_if_finished(session_id, occurred_at)
        explanation = material.solution_explanation or "Question passée — tu pourras y revenir plus tard en révision."
        return QuestionAssessmentView(
            False,
            0.0,
            explanation,
            material.solution_method or "PASSÉE",
            material.solution_advice or "Tu as choisi de passer. Continue sans te bloquer.",
            saved.mastery_before,
            saved.mastery_after,
            session_completed,
            skipped=True,
        )

    def use_hint(self, learner_id: int, session_id: int, hint_id: int, at: datetime) -> str:
        material = self.repository.current_question(learner_id, session_id)
        if material is None:
            raise ValueError("Aucune question active.")
        hint = next((item for item in material.question.hints if item[0] == hint_id), None)
        if hint is None:
            raise ValueError("Indice indisponible.")
        position = next(index for index, item in enumerate(material.question.hints, 1) if item[0] == hint_id)
        self.repository.record_hint(material.question.activity_id, hint_id, position, hint[2], at)
        return hint[1]

    def corrections(self, learner_id: int, session_id: int) -> tuple[AnswerCorrectionItem, ...]:
        session = self.sessions.repository.get(session_id)
        if session is None or session.learner_id != learner_id:
            raise PermissionError("SESSION_ACCESS_DENIED")
        return self.repository.list_corrections(learner_id, session_id)

    def _complete_if_finished(self, session_id: int, at: datetime) -> bool:
        activities = self.sessions.repository.list_activities(session_id)
        if activities and all(item.status is ActivityStatus.COMPLETED for item in activities):
            self.sessions.close_session(session_id, at)
            self.repository.complete_homework(session_id)
            return True
        return False

    @staticmethod
    def _strategy(response_type: str) -> tuple[AnswerType, AssessmentMethod]:
        normalized = response_type.strip().upper()
        mapping = {
            "INTEGER": (AnswerType.INTEGER, AssessmentMethod.NUMERIC_EQUALITY),
            "NUMBER": (AnswerType.DECIMAL, AssessmentMethod.NUMERIC_TOLERANCE),
            "DECIMAL": (AnswerType.DECIMAL, AssessmentMethod.NUMERIC_TOLERANCE),
            "FRACTION": (AnswerType.FRACTION, AssessmentMethod.FRACTION_SIMPLIFICATION),
            "BOOLEAN": (AnswerType.BOOLEAN, AssessmentMethod.BOOLEAN),
            "FORMULA": (AnswerType.FORMULA, AssessmentMethod.FORMULA),
            "MCQ_SINGLE": (AnswerType.MCQ_SINGLE, AssessmentMethod.EXACT_MATCH),
            "SINGLE_CHOICE": (AnswerType.MCQ_SINGLE, AssessmentMethod.EXACT_MATCH),
            "MCQ_MULTI": (AnswerType.MCQ_MULTI, AssessmentMethod.MCQ),
            "MULTIPLE_CHOICE": (AnswerType.MCQ_MULTI, AssessmentMethod.MCQ),
            "TEXT": (AnswerType.TEXT, AssessmentMethod.EXACT_MATCH),
            "SHORT_TEXT": (AnswerType.SHORT_TEXT, AssessmentMethod.EXACT_MATCH),
            "LONG_TEXT": (AnswerType.LONG_TEXT, AssessmentMethod.EXACT_MATCH),
        }
        return mapping.get(normalized, (AnswerType.TEXT, AssessmentMethod.EXACT_MATCH))
