"""Local heuristic assessor when OpenAI is unavailable."""

from __future__ import annotations

import re

from domain.content.pedagogical_review import BlindReviewInput, BlindReviewOutput, ComparisonResult
from services.content.ai_pedagogical_review import compare_answers_deterministic
from services.content.factory import _numeric_value


class LocalPedagogicalReviewAssessor:
    """Deterministic/heuristic blind review without expected-answer leakage in Pass A."""

    reviewer_model = "local-heuristic-v1"
    assessor_type = "local"

    def solve_blind(self, payload: BlindReviewInput) -> BlindReviewOutput:
        if payload.answer_kind == "numeric":
            computed = _extract_simple_arithmetic(payload.question)
            if computed is not None:
                return BlindReviewOutput(
                    independent_answer=str(computed),
                    concise_verification_reason="Independent arithmetic extracted from question text.",
                    confidence="HIGH",
                )
        if payload.answer_kind in {"single_choice", "multiple_choice"} and payload.choices:
            return BlindReviewOutput(
                independent_answer="[qcm-local-review-unresolved]",
                concise_verification_reason="QCM requires semantic distractor analysis; local path unresolved.",
                confidence="LOW",
            )
        return BlindReviewOutput(
            independent_answer="[open-response-local-review-unresolved]",
            concise_verification_reason="Open response requires semantic blind review.",
            confidence="MEDIUM",
        )

    def compare(
        self,
        *,
        blind: BlindReviewOutput,
        expected_answer: str,
        expected_explanation: str,
        choices: tuple[str, ...],
        answer_kind: str,
        subject: str,
    ) -> ComparisonResult:
        if blind.independent_answer.startswith("["):
            if answer_kind in {"single_choice", "multiple_choice"}:
                qcm = expected_answer in choices
                if qcm:
                    return ComparisonResult(
                        "AMBIGUOUS",
                        "QCM structure valid but independent option choice unresolved locally.",
                    )
                return ComparisonResult("INCORRECT", "Expected QCM answer missing from choices.")
            return ComparisonResult(
                "AMBIGUOUS",
                "Local heuristic could not independently resolve open response.",
            )
        return compare_answers_deterministic(
            blind_answer=blind.independent_answer,
            expected_answer=expected_answer,
            answer_kind=answer_kind,
        )


def _extract_simple_arithmetic(question: str) -> float | None:
    patterns = [
        r"calcule\s+(-?\d+(?:[.,]\d+)?)\s*\+\s*(-?\d+(?:[.,]\d+)?)",
        r"(-?\d+(?:[.,]\d+)?)\s*\+\s*(-?\d+(?:[.,]\d+)?)",
        r"(-?\d+(?:[.,]\d+)?)\s*-\s*(-?\d+(?:[.,]\d+)?)",
        r"(-?\d+(?:[.,]\d+)?)\s*[×x*]\s*(-?\d+(?:[.,]\d+)?)",
        r"(-?\d+(?:[.,]\d+)?)\s*/\s*(-?\d+(?:[.,]\d+)?)",
    ]
    lowered = question.lower().replace(",", ".")
    match = re.search(patterns[0], lowered)
    if match:
        return _numeric_value(match.group(1)) + _numeric_value(match.group(2))  # type: ignore[operator]
    match = re.search(patterns[1], lowered)
    if match:
        return _numeric_value(match.group(1)) + _numeric_value(match.group(2))  # type: ignore[operator]
    match = re.search(patterns[2], lowered)
    if match:
        return _numeric_value(match.group(1)) - _numeric_value(match.group(2))  # type: ignore[operator]
    match = re.search(patterns[3], lowered)
    if match:
        return _numeric_value(match.group(1)) * _numeric_value(match.group(2))  # type: ignore[operator]
    match = re.search(patterns[4], lowered)
    if match:
        right = _numeric_value(match.group(2))
        if right in (None, 0):
            return None
        return _numeric_value(match.group(1)) / right  # type: ignore[operator]
    return None
