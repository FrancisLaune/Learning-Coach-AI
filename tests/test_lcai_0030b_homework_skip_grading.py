"""LCAI-0030-B — skip question + tolerant grading."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import pytest

from domain.learning_session.models import AnswerType, AssessmentMethod
from services.learning_session.assessment import AnswerValidationError, DeterministicAssessmentEngine
from services.learning_session.models import AssessmentRequest


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        ("3,5", "3.5"),
        ("3.5", "3,5"),
        (" 3 , 5 ", "3.5"),
        ("1/2", "0.5"),
        ("0,5", "1/2"),
    ],
)
def test_decimal_formats_are_accepted_as_equivalent(actual: str, expected: str) -> None:
    result = DeterministicAssessmentEngine().assess(
        AssessmentRequest(
            AnswerType.DECIMAL,
            actual,
            expected,
            AssessmentMethod.NUMERIC_TOLERANCE,
            tolerance=0.0,
        )
    )
    assert result.correct is True
    assert result.raw_score == 100
    assert result.normalized_answer == Decimal("3.5") or result.normalized_answer == Decimal("0.5")


def test_text_answers_accept_numeric_equivalence() -> None:
    result = DeterministicAssessmentEngine().assess(
        AssessmentRequest(AnswerType.TEXT, "3,5", "3.5", AssessmentMethod.EXACT_MATCH)
    )
    assert result.correct is True


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        ("10", "10 cm"),
        ("10 cm", "10"),
        ("12,50", "12,50 €"),
        ("Cinq cahiers coûtent 12,50 €", "12,50 €"),
        ("7+2x", "2x + 7"),
        ("2x+7", "7 + 2x"),
        ("2^5", "2^5"),
    ],
)
def test_short_text_accepts_equivalent_math_answers(actual: str, expected: str) -> None:
    result = DeterministicAssessmentEngine().assess(
        AssessmentRequest(AnswerType.SHORT_TEXT, actual, expected, AssessmentMethod.EXACT_MATCH)
    )
    assert result.correct is True
    assert result.raw_score == 100


def test_short_text_accepts_answer_contained_in_multiline() -> None:
    result = DeterministicAssessmentEngine().assess(
        AssessmentRequest(
            AnswerType.SHORT_TEXT,
            "Le volume du cube est 27 cm³.\nV = a³ = 3×3×3 = 27",
            "27",
            AssessmentMethod.EXACT_MATCH,
        )
    )
    assert result.correct is True
    assert result.raw_score == 100


def test_short_text_still_rejects_wrong_math_answers() -> None:
    result = DeterministicAssessmentEngine().assess(
        AssessmentRequest(AnswerType.SHORT_TEXT, "9", "10 cm", AssessmentMethod.EXACT_MATCH)
    )
    assert result.correct is False


def test_fraction_accepts_equivalent_decimal() -> None:
    result = DeterministicAssessmentEngine().assess(
        AssessmentRequest(
            AnswerType.FRACTION,
            "0.5",
            "1/2",
            AssessmentMethod.FRACTION_SIMPLIFICATION,
        )
    )
    assert result.correct is True
    assert result.normalized_answer == Fraction(1, 2)


def test_invalid_numeric_message_is_actionable() -> None:
    with pytest.raises(AnswerValidationError, match="3,5"):
        DeterministicAssessmentEngine().normalize(AnswerType.DECIMAL, "abc")


def test_skip_view_flag_defaults_false() -> None:
    from services.unified_session_execution import QuestionAssessmentView

    view = QuestionAssessmentView(True, 100, "ok", "m", "", 0.4, 0.5, False)
    assert view.skipped is False
