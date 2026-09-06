"""Deterministic submission pipeline ordered assessment → mastery → notification."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from domain.learning.models import LearnerAttempt, LearningEngineResult
from domain.learning_session.models import AnswerType, Assessment, AssessmentMethod, Attempt, StudentAnswer
from domain.learning_session.repositories import AssessmentRepository
from services.learning_session.assessment import DeterministicAssessmentEngine, serialize_normalized_answer
from services.learning_session.models import AssessmentRequest, AssessmentResult, SubmissionContext


class LearningProcessor(Protocol):
    def process(self, attempt: LearnerAttempt) -> LearningEngineResult: ...


class DecisionNotifier(Protocol):
    def notify_mastery_updated(self, result: LearningEngineResult) -> None: ...


class SubmissionService:
    """Persist a submitted answer only after the Learning Engine accepted its signal."""

    def __init__(
        self,
        repository: AssessmentRepository,
        learning: LearningProcessor,
        notifier: DecisionNotifier,
        assessment: DeterministicAssessmentEngine | None = None,
        *,
        ai_validator: Any | None = None,
    ) -> None:
        self.repository = repository
        self.learning = learning
        self.notifier = notifier
        self.assessment = assessment or DeterministicAssessmentEngine()
        self.ai_validator = ai_validator

    def submit(
        self,
        context: SubmissionContext,
        request: AssessmentRequest,
        *,
        statement: str = "",
    ) -> tuple[Attempt, AssessmentResult, LearningEngineResult]:
        result = self.assessment.assess(request)
        if not result.correct:
            result = self._maybe_accept_via_ai(request, result, statement=statement)
        answer = StudentAnswer(
            0,
            context.activity_id,
            context.question_id,
            context.attempt_number,
            request.answer_type,
            request.raw_answer,
            serialize_normalized_answer(request.answer_type, result.normalized_answer),
            context.occurred_at,
            context.elapsed_ms,
            False,
            True,
            context.idempotency_key,
        )
        signal = LearnerAttempt(
            context.idempotency_key,
            context.learner_id,
            context.skill_id,
            context.occurred_at,
            result.final_score / 100,
            request.difficulty,
            context.attempt_number,
            context.elapsed_ms / 1000,
            hints_used=len(request.hint_penalties),
        )
        learning_result = self.learning.process(signal)
        before = learning_result.mastery.previous.score
        after = learning_result.mastery.current.score
        assessment = Assessment(
            0,
            0,
            result.correct,
            result.final_score,
            result.manual_penalty,
            result.hint_penalty,
            max(0, -result.time_bonus),
            result.method,
            result.feedback,
            self.assessment.version,
        )
        attempt = Attempt(
            0,
            context.learner_id,
            context.activity_id,
            0,
            0,
            result.correct,
            before,
            after,
            context.elapsed_ms,
            len(request.hint_penalties),
        )
        payload: dict[str, Any] = asdict(learning_result)
        payload["learning_engine_version"] = "learning-engine-v1"
        saved = self.repository.save_cycle(answer, assessment, attempt, payload)
        self.notifier.notify_mastery_updated(learning_result)
        return saved, result, learning_result

    def _maybe_accept_via_ai(
        self,
        request: AssessmentRequest,
        result: AssessmentResult,
        *,
        statement: str = "",
    ) -> AssessmentResult:
        validator = self.ai_validator
        if validator is None:
            from services.learning_session.ai_answer_validation import ai_accepts_worked_answer

            validator = ai_accepts_worked_answer
        try:
            accepted = validator(request, statement=statement)
        except TypeError:
            accepted = validator(request)
        except Exception:
            return result
        if accepted is not True:
            return result
        feedback = dict(result.feedback or {})
        feedback["ai_validation"] = "accepted_worked_answer"
        return AssessmentResult(
            result.normalized_answer,
            100.0,
            100.0,
            True,
            result.hint_penalty,
            result.time_bonus,
            result.manual_penalty,
            result.mastery_delta if result.mastery_delta > 0 else 0.05,
            result.method,
            feedback,
            tuple(result.reasons) + ("ai_validation:accepted_worked_answer",),
        )

    def record_skip(
        self,
        context: SubmissionContext,
        *,
        current_mastery: float,
        feedback: dict[str, Any] | None = None,
    ) -> Attempt:
        """Persist a skipped question without changing mastery."""
        answer = StudentAnswer(
            0,
            context.activity_id,
            context.question_id,
            context.attempt_number,
            AnswerType.TEXT,
            "[passée]",
            "[passée]",
            context.occurred_at,
            context.elapsed_ms,
            False,
            True,
            context.idempotency_key,
        )
        assessment = Assessment(
            0,
            0,
            False,
            0.0,
            0.0,
            0.0,
            0.0,
            AssessmentMethod.EXACT_MATCH,
            dict(feedback or {}),
            "skip-v1",
        )
        attempt = Attempt(
            0,
            context.learner_id,
            context.activity_id,
            0,
            0,
            False,
            current_mastery,
            current_mastery,
            context.elapsed_ms,
            len(()),
        )
        payload: dict[str, Any] = {
            "skipped": True,
            "learning_engine_version": "skip-v1",
        }
        return self.repository.save_cycle(answer, assessment, attempt, payload)
