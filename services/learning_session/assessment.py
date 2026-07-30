"""Deterministic answer normalization, validation, scoring and rendering DTOs."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any

from domain.learning_session.models import AnswerType, AssessmentMethod
from services.learning_session.models import AssessmentRequest, AssessmentResult, QuestionView


class AnswerValidationError(ValueError):
    pass


def _text(value: Any, *, lowercase: bool = True) -> str:
    normalized = unicodedata.normalize("NFKC", str(value))
    normalized = " ".join(normalized.strip().split())
    return normalized.casefold() if lowercase else normalized


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(_text(value, lowercase=False).replace(",", "."))
    except InvalidOperation as exc:
        raise AnswerValidationError("Invalid numeric answer") from exc


def format_decimal_fr(value: Decimal) -> str:
    """Render a decimal with the French comma separator."""
    return str(value).replace(".", ",")


def serialize_normalized_answer(answer_type: AnswerType, value: Any) -> Any:
    if answer_type is AnswerType.DECIMAL and isinstance(value, Decimal):
        return format_decimal_fr(value)
    return value


def _fraction(value: Any) -> Fraction:
    try:
        text = _text(value, lowercase=False).replace(" ", "")
        return Fraction(text.replace(",", "."))
    except (ValueError, ZeroDivisionError) as exc:
        raise AnswerValidationError("Invalid fraction answer") from exc


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    token = _text(value)
    if token in {"true", "vrai", "1", "yes", "oui"}:
        return True
    if token in {"false", "faux", "0", "no", "non"}:
        return False
    raise AnswerValidationError("Invalid boolean answer")


def _formula(value: Any) -> str:
    text = _text(value, lowercase=False).replace(" ", "").replace("×", "*").replace("÷", "/")
    if not text or not re.fullmatch(r"[A-Za-z0-9_+\-*/^().=]+", text):
        raise AnswerValidationError("Invalid formula syntax")
    balance = 0
    for character in text:
        balance += character == "("
        balance -= character == ")"
        if balance < 0:
            raise AnswerValidationError("Invalid formula parentheses")
    if balance:
        raise AnswerValidationError("Invalid formula parentheses")
    return text


class DeterministicAssessmentEngine:
    version = "deterministic-assessment-v1"

    def assess(self, request: AssessmentRequest) -> AssessmentResult:
        normalized = self.normalize(request.answer_type, request.raw_answer)
        expected = self.normalize(request.answer_type, request.expected_answer)
        raw_score = self._score(request, normalized, expected)
        hint_penalty = sum(max(0.0, item) for item in request.hint_penalties)
        final = max(0.0, min(100.0, raw_score - hint_penalty - request.manual_penalty + request.time_bonus))
        mastery_delta = self._mastery_delta(request, final)
        reasons = (
            f"strategy:{request.method.value}",
            f"raw_score:{raw_score:.4f}",
            f"hint_penalty:{hint_penalty:.4f}",
            f"time_bonus:{request.time_bonus:.4f}",
            f"manual_penalty:{request.manual_penalty:.4f}",
        )
        return AssessmentResult(
            normalized,
            raw_score,
            final,
            raw_score == 100,
            hint_penalty,
            request.time_bonus,
            request.manual_penalty,
            mastery_delta,
            request.method,
            dict(request.feedback or {}),
            reasons,
        )

    @staticmethod
    def normalize(answer_type: AnswerType, value: Any) -> Any:
        if value is None:
            raise AnswerValidationError("Answer is required")
        if answer_type is AnswerType.INTEGER:
            number = _decimal(value)
            if number != number.to_integral_value():
                raise AnswerValidationError("Expected an integer")
            return int(number)
        if answer_type is AnswerType.DECIMAL:
            return _decimal(value)
        if answer_type is AnswerType.FRACTION:
            return _fraction(value)
        if answer_type is AnswerType.BOOLEAN:
            return _boolean(value)
        if answer_type is AnswerType.FORMULA:
            return _formula(value)
        if answer_type in {AnswerType.MCQ_MULTI, AnswerType.ORDERING}:
            if not isinstance(value, (list, tuple)):
                raise AnswerValidationError("Expected a list answer")
            return tuple(_text(item, lowercase=False) for item in value)
        if answer_type is AnswerType.MATCHING:
            if not isinstance(value, dict):
                raise AnswerValidationError("Expected a matching object")
            return tuple(sorted((_text(k, lowercase=False), _text(v, lowercase=False)) for k, v in value.items()))
        text = _text(value)
        if len(text) > 10000:
            raise AnswerValidationError("Answer is too long")
        return text

    @staticmethod
    def _score(request: AssessmentRequest, actual: Any, expected: Any) -> float:
        method = request.method
        if method in {
            AssessmentMethod.EXACT_MATCH,
            AssessmentMethod.BOOLEAN,
            AssessmentMethod.FRACTION_SIMPLIFICATION,
            AssessmentMethod.FORMULA,
        }:
            return 100.0 if actual == expected else 0.0
        if method is AssessmentMethod.NUMERIC_EQUALITY:
            return 100.0 if Decimal(actual) == Decimal(expected) else 0.0
        if method is AssessmentMethod.NUMERIC_TOLERANCE:
            return 100.0 if abs(Decimal(actual) - Decimal(expected)) <= Decimal(str(request.tolerance)) else 0.0
        if method is AssessmentMethod.MCQ:
            selected = set(actual if isinstance(actual, tuple) else (actual,))
            correct = set(request.correct_options or (str(expected),))
            if not correct:
                raise AnswerValidationError("MCQ requires correct options")
            if not request.partial_scoring:
                return 100.0 if selected == correct else 0.0
            good = len(selected & correct)
            wrong = len(selected - correct)
            missing = len(correct - selected)
            return max(0.0, 100.0 * (good - wrong) / max(1, good + wrong + missing))
        if method is AssessmentMethod.ORDERING:
            if len(expected) == 0:
                raise AnswerValidationError("Ordering requires expected elements")
            matches = sum(left == right for left, right in zip(actual, expected, strict=False))
            return 100.0 * matches / len(expected)
        if method is AssessmentMethod.MATCHING:
            expected_pairs = dict(expected)
            actual_pairs = dict(actual)
            if not expected_pairs:
                raise AnswerValidationError("Matching requires expected pairs")
            matches = sum(actual_pairs.get(key) == value for key, value in expected_pairs.items())
            return 100.0 * matches / len(expected_pairs)
        raise AnswerValidationError(f"Unsupported assessment method: {method.value}")

    @staticmethod
    def _mastery_delta(request: AssessmentRequest, final_score: float) -> float:
        success_signal = (final_score / 100 - 0.5) * 20
        difficulty_factor = 0.8 + 0.1 * request.difficulty
        mastery_factor = 1.2 - 0.4 * request.current_mastery
        attempt_factor = 1 / max(1, request.previous_attempts + 1)
        return max(-100.0, min(100.0, success_signal * difficulty_factor * mastery_factor * attempt_factor))


class QuestionRenderer:
    """Build a framework-neutral view; rendering remains an UI responsibility."""

    @staticmethod
    def render(
        *,
        question_id: int,
        instructions: str,
        context: str | None,
        statement: str,
        response_type: str,
        options: tuple[tuple[str, str], ...] = (),
        hints_available: int = 0,
        readonly: bool = False,
    ) -> QuestionView:
        if not statement.strip() or hints_available < 0:
            raise AnswerValidationError("Question rendering data is incomplete")
        return QuestionView(
            question_id,
            instructions,
            context,
            statement,
            response_type,
            options,
            hints_available,
            readonly,
        )
