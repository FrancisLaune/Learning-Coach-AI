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


_UNIT_SUFFIX = re.compile(
    r"(?ix)\s*(?:cm|mm|m|km|g|kg|mg|l|ml|cl|€|\$|%|°|deg(?:rés?)?|euros?)\s*$"
)
_NUMBER_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])([+-]?(?:\d+(?:[.,]\d+)?|\d+[.,]\d+))(?![A-Za-z0-9_])"
)
_CONCLUSION_MARKERS = (
    "donc",
    "ainsi",
    "finalement",
    "au total",
    "on obtient",
    "on trouve",
    "résultat",
    "resultat",
    "réponse",
    "reponse",
    "conclusion",
)
_CONCLUSION_LINE = re.compile(
    r"(?im)^\s*(?:donc|ainsi|finalement|au\s+total|on\s+obtient|on\s+trouve|"
    r"résultat|resultat|réponse|reponse|conclusion)\s*[:.]?\s*(.+?)\s*$"
)
_EQUALS_CONCLUSION = re.compile(
    r"(?im)^\s*(?:[a-z]\s*)?=\s*([^\n=]+?)\s*$"
)


def _looks_like_worked_solution(value: Any) -> bool:
    text = str(value or "")
    if len(text) < 24:
        return False
    lowered = text.casefold()
    if any(marker in lowered for marker in _CONCLUSION_MARKERS):
        return True
    if "\n" in text or "dévelop" in lowered or "etape" in lowered or "étape" in lowered:
        return True
    return len(re.findall(r"=", text)) >= 2


def extract_concluding_value(value: Any) -> str | None:
    """Extract the final result from a worked multi-line solution when possible."""
    raw = unicodedata.normalize("NFKC", str(value or "")).replace("\r\n", "\n").replace("\r", "\n")
    if not raw.strip():
        return None
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    candidates: list[str] = []
    for line in lines:
        match = _CONCLUSION_LINE.match(line)
        if match:
            candidates.append(match.group(1).strip())
        match = _EQUALS_CONCLUSION.match(line)
        if match:
            candidates.append(match.group(1).strip())
    # Prefer "A = 4" style conclusions near the end.
    for line in reversed(lines):
        lowered = line.casefold()
        if any(marker in lowered for marker in _CONCLUSION_MARKERS) and "=" in line:
            right = line.split("=")[-1].strip()
            if right:
                candidates.append(right)
                break
        if re.fullmatch(r"[a-z]\s*=\s*.+", lowered):
            candidates.append(line.split("=", 1)[1].strip())
            break
    if not candidates and lines:
        last = lines[-1]
        if "=" in last:
            candidates.append(last.split("=")[-1].strip())
        else:
            candidates.append(last)
    for candidate in reversed(candidates):
        cleaned = _UNIT_SUFFIX.sub("", candidate).strip().strip(" .;")
        cleaned = re.sub(r"^(?:a|b|c|d|e|f|x|y|z)\s*=\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()
        if cleaned:
            return cleaned
    return None


def _coerce_numeric_text(value: Any) -> str:
    """For long worked answers, prefer the concluding value before strict parsing."""
    text = str(value or "").strip()
    if not text:
        return text
    compact = re.sub(r"\s+", "", text)
    if re.fullmatch(r"[+-]?(?:\d+(?:[.,]\d+)?|\d+[.,]\d+|\d+/\d+)", compact):
        return text
    if _looks_like_worked_solution(text) or any(ch.isalpha() for ch in text) or "\n" in text:
        extracted = extract_concluding_value(text)
        if extracted:
            return extracted
    return text


def _decimal(value: Any) -> Decimal:
    text = re.sub(r"\s+", "", _text(_coerce_numeric_text(value), lowercase=False))
    if not text:
        raise AnswerValidationError("Réponse numérique manquante. Exemples acceptés : 3,5 ou 3.5")
    try:
        return Decimal(text.replace(",", "."))
    except InvalidOperation:
        pass
    try:
        fraction = Fraction(text.replace(",", "."))
        return Decimal(fraction.numerator) / Decimal(fraction.denominator)
    except (ValueError, ZeroDivisionError, InvalidOperation) as exc:
        raise AnswerValidationError(
            "Réponse numérique invalide. Exemples acceptés : 3,5 ou 3.5"
        ) from exc


def format_decimal_fr(value: Decimal) -> str:
    """Render a decimal with the French comma separator."""
    return str(value).replace(".", ",")


def serialize_normalized_answer(answer_type: AnswerType, value: Any) -> Any:
    if answer_type is AnswerType.DECIMAL and isinstance(value, Decimal):
        return format_decimal_fr(value)
    return value


def _fraction(value: Any) -> Fraction:
    try:
        text = re.sub(r"\s+", "", _text(_coerce_numeric_text(value), lowercase=False))
        if not text:
            raise AnswerValidationError("Fraction manquante. Exemple accepté : 1/2")
        return Fraction(text.replace(",", "."))
    except AnswerValidationError:
        raise
    except (ValueError, ZeroDivisionError) as exc:
        raise AnswerValidationError("Fraction invalide. Exemple accepté : 1/2") from exc


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
    candidate = _coerce_numeric_text(value) if _looks_like_worked_solution(value) else value
    text = _text(candidate, lowercase=False).replace(" ", "").replace("×", "*").replace("÷", "/")
    if not text or not re.fullmatch(r"[A-Za-z0-9_+\-*/^().=]+", text):
        # Fallback: concluding expression without spaces.
        extracted = extract_concluding_value(value)
        if extracted:
            text = _text(extracted, lowercase=False).replace(" ", "").replace("×", "*").replace("÷", "/")
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


def _as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Fraction):
        return Decimal(value.numerator) / Decimal(value.denominator)
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    try:
        return _decimal(value)
    except AnswerValidationError:
        return None


def _numeric_equivalent(actual: Any, expected: Any, tolerance: float) -> bool:
    left = _as_decimal(actual)
    right = _as_decimal(expected)
    if left is None or right is None:
        return False
    limit = Decimal(str(tolerance if tolerance else 0))
    if limit == 0:
        limit = Decimal("0.000000001")
    return abs(left - right) <= limit


def _strip_units(value: Any) -> str:
    return _UNIT_SUFFIX.sub("", _text(value, lowercase=False)).strip()


def _extract_numbers(value: Any) -> tuple[Decimal, ...]:
    text = _text(value, lowercase=False)
    found: list[Decimal] = []
    for match in _NUMBER_TOKEN.finditer(text):
        parsed = _as_decimal(match.group(1))
        if parsed is not None:
            found.append(parsed)
    return tuple(found)


def _algebra_term_set(value: Any) -> frozenset[str] | None:
    """Canonical additive terms for simple expressions like ``2x+7`` / ``7+2x``."""
    raw = _text(value, lowercase=False).casefold()
    raw = raw.replace("×", "*").replace("·", "*").replace(" ", "")
    if not raw or not re.fullmatch(r"[0-9a-z+\-*/^().]+", raw):
        return None
    if not re.search(r"[a-z]", raw):
        return None
    raw = re.sub(r"(\d)\*([a-z])", r"\1\2", raw)
    raw = re.sub(r"([a-z])\*(\d)", r"\2\1", raw)
    raw = raw.replace("-", "+-")
    parts = [part for part in raw.split("+") if part]
    if not parts:
        return None
    normalized: list[str] = []
    for part in parts:
        term = part
        match = re.fullmatch(r"([+-]?)(\d+)([a-z](?:\^\d+)?)?", term)
        if match:
            sign, coef, var = match.groups()
            prefix = "-" if sign == "-" else ""
            term = f"{prefix}{coef}{var}" if var else f"{prefix}{coef}"
        normalized.append(term)
    return frozenset(normalized)


def _contains_expected_answer(actual: Any, expected: Any) -> bool:
    """True when the student answer contains the expected value (multi-line friendly)."""
    actual_text = _text(actual)
    expected_text = _text(_strip_units(expected))
    if not actual_text or not expected_text:
        return False
    if expected_text in actual_text:
        if len(expected_text) <= 2:
            return bool(re.search(rf"(?<![0-9a-z]){re.escape(expected_text)}(?![0-9a-z])", actual_text))
        return True
    compact_actual = re.sub(r"\s+", "", actual_text)
    compact_expected = re.sub(r"\s+", "", expected_text)
    if compact_expected and compact_expected in compact_actual and len(compact_expected) > 2:
        return True
    # Compare without punctuation differences around operators.
    soft_actual = re.sub(r"[^\w,+.\-^×*/=€%°]", "", actual_text)
    soft_expected = re.sub(r"[^\w,+.\-^×*/=€%°]", "", expected_text)
    return bool(soft_expected) and soft_expected in soft_actual and len(soft_expected) > 2


def _flexible_text_equivalent(actual: Any, expected: Any, tolerance: float) -> bool:
    """Accept pedagogically equivalent short answers beyond strict string equality."""
    concluding = extract_concluding_value(actual)
    if concluding and (
        _numeric_equivalent(concluding, expected, tolerance)
        or _text(concluding) == _text(_strip_units(expected))
        or _contains_expected_answer(concluding, expected)
    ):
        return True
    if _numeric_equivalent(actual, expected, tolerance):
        return True
    if _contains_expected_answer(actual, expected):
        return True
    actual_core = _strip_units(actual)
    expected_core = _strip_units(expected)
    if actual_core and expected_core and _text(actual_core) == _text(expected_core):
        return True
    if actual_core and expected_core and _numeric_equivalent(actual_core, expected_core, tolerance):
        return True
    expected_numbers = _extract_numbers(expected)
    if len(expected_numbers) == 1:
        target = expected_numbers[0]
        limit = Decimal(str(tolerance if tolerance else 0)) or Decimal("0.000000001")
        expected_text = _text(expected_core or expected)
        allow_numeric_probe = bool(
            re.fullmatch(r"[+-]?(?:\d+(?:[.,]\d+)?|\d+[.,]\d+)", expected_text)
            or _UNIT_SUFFIX.search(_text(expected, lowercase=False))
        )
        if allow_numeric_probe:
            conclusion_numbers = _extract_numbers(concluding) if concluding else ()
            if conclusion_numbers and abs(conclusion_numbers[-1] - target) <= limit:
                return True
            actual_numbers = _extract_numbers(actual)
            if actual_numbers and abs(actual_numbers[-1] - target) <= limit:
                return True
    probe = concluding if concluding else actual
    left_terms = _algebra_term_set(probe)
    right_terms = _algebra_term_set(expected)
    return left_terms is not None and right_terms is not None and left_terms == right_terms


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
            AssessmentMethod.FORMULA,
        }:
            if actual == expected:
                return 100.0
            if method is AssessmentMethod.EXACT_MATCH and _flexible_text_equivalent(
                actual, expected, request.tolerance
            ):
                return 100.0
            if method is AssessmentMethod.FORMULA and _flexible_text_equivalent(
                actual, expected, request.tolerance
            ):
                return 100.0
            return 0.0
        if method is AssessmentMethod.FRACTION_SIMPLIFICATION:
            if actual == expected:
                return 100.0
            if _numeric_equivalent(actual, expected, max(request.tolerance, 1e-9)):
                return 100.0
            return 0.0
        if method is AssessmentMethod.NUMERIC_EQUALITY:
            return 100.0 if Decimal(str(actual)) == Decimal(str(expected)) else 0.0
        if method is AssessmentMethod.NUMERIC_TOLERANCE:
            tolerance = Decimal(str(request.tolerance if request.tolerance else 0))
            return (
                100.0
                if abs(Decimal(str(actual)) - Decimal(str(expected))) <= tolerance
                else 0.0
            )
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
