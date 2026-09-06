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


def test_worked_algebra_solution_accepted_for_integer_expected() -> None:
    worked = """
On part de :
A = (1/2)(4x - 6) + 3(x + 2) - (5x - 1)
1. Développer chaque partie
(1/2)(4x-6)=2x-3
3(x+2)=3x+6
-(5x-1)=-5x+1
Donc :
A=2x-3+3x+6-5x+1
2. Regrouper les termes en x
2x+3x-5x=0
3. Regrouper les nombres
-3+6+1=4
Donc :
A=4
"""
    result = DeterministicAssessmentEngine().assess(
        AssessmentRequest(
            AnswerType.INTEGER,
            worked,
            4,
            AssessmentMethod.NUMERIC_EQUALITY,
        )
    )
    assert result.correct is True
    assert result.normalized_answer == 4


def test_worked_solution_accepted_as_short_text() -> None:
    worked = "Développement puis réduction.\nDonc :\nA=4"
    result = DeterministicAssessmentEngine().assess(
        AssessmentRequest(
            AnswerType.SHORT_TEXT,
            worked,
            "4",
            AssessmentMethod.EXACT_MATCH,
        )
    )
    assert result.correct is True


def test_ai_validation_can_accept_when_deterministic_fails() -> None:
    from services.learning_session.submission import SubmissionService

    service = SubmissionService(
        repository=None,  # type: ignore[arg-type]
        learning=None,  # type: ignore[arg-type]
        notifier=None,  # type: ignore[arg-type]
        ai_validator=lambda request, statement="": True,
    )
    rejected = DeterministicAssessmentEngine().assess(
        AssessmentRequest(AnswerType.SHORT_TEXT, "ma demarche longue aboutit a 4", "999", AssessmentMethod.EXACT_MATCH)
    )
    assert rejected.correct is False
    accepted = service._maybe_accept_via_ai(
        AssessmentRequest(AnswerType.SHORT_TEXT, "ma demarche longue aboutit a 4", "999", AssessmentMethod.EXACT_MATCH),
        rejected,
        statement="Réduis A",
    )
    assert accepted.correct is True
    assert accepted.feedback.get("ai_validation") == "accepted_worked_answer"


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
