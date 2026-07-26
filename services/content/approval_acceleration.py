"""Generic review classification and production-candidate ranking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ReviewReason(StrEnum):
    DETERMINISTIC_VERIFICATION_AVAILABLE = "DETERMINISTIC_VERIFICATION_AVAILABLE"
    OPEN_RESPONSE = "OPEN_RESPONSE"
    PEDAGOGICAL_JUDGEMENT_REQUIRED = "PEDAGOGICAL_JUDGEMENT_REQUIRED"
    AMBIGUOUS_EXPECTED_ANSWER = "AMBIGUOUS_EXPECTED_ANSWER"
    SCIENCE_LEVEL_REVIEW = "SCIENCE_LEVEL_REVIEW"
    LANGUAGE_PRODUCTION = "LANGUAGE_PRODUCTION"
    HISTORY_KNOWLEDGE_REVIEW = "HISTORY_KNOWLEDGE_REVIEW"
    SOURCE_DOCUMENT_REQUIRED = "SOURCE_DOCUMENT_REQUIRED"
    ORAL_MODALITY = "ORAL_MODALITY"
    DIFFICULTY_UNCERTAIN = "DIFFICULTY_UNCERTAIN"
    EXPLANATION_REVIEW = "EXPLANATION_REVIEW"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    code: str
    skill: str
    content_type: str
    decision: str
    score: int
    hard_gates_passed: bool
    reasons: tuple[str, ...]


def classify_review(
    result: dict[str, Any],
    source: dict[str, Any],
    *,
    near_duplicate: bool = False,
) -> tuple[ReviewReason, ...]:
    """Derive review reasons from the actual modality, discipline and wording."""
    reasons: list[ReviewReason] = []
    answer = source["answer"]
    kind = str(answer["kind"])
    subject = str(result["subject"])
    body = f"{result['prompt']} {result['explanation']}".casefold()
    if answer.get("independently_computed") is not None:
        reasons.append(ReviewReason.DETERMINISTIC_VERIFICATION_AVAILABLE)
    if kind == "open_response":
        reasons.append(ReviewReason.OPEN_RESPONSE)
        reasons.append(
            ReviewReason.LANGUAGE_PRODUCTION
            if subject in {"FRENCH", "ENGLISH", "SPANISH"}
            else ReviewReason.PEDAGOGICAL_JUDGEMENT_REQUIRED
        )
    elif kind == "structured" or kind in {"single_choice", "multiple_choice"}:
        reasons.append(ReviewReason.PEDAGOGICAL_JUDGEMENT_REQUIRED)
    elif kind == "exact_text":
        reasons.append(ReviewReason.AMBIGUOUS_EXPECTED_ANSWER)
    if subject in {"SVT", "PHYSICS_CHEMISTRY"} and kind != "numeric":
        reasons.append(ReviewReason.SCIENCE_LEVEL_REVIEW)
    if subject in {"HISTORY", "GEOGRAPHY", "EMC"} and kind not in {"numeric", "boolean"}:
        reasons.append(ReviewReason.HISTORY_KNOWLEDGE_REVIEW)
    if any(token in body for token in ("document ci-dessus", "document fourni", "audio", "écoute")):
        reasons.append(ReviewReason.SOURCE_DOCUMENT_REQUIRED)
    if any(token in body for token in ("à l'oral", "oralement", "prononce", "enregistre-toi")):
        reasons.append(ReviewReason.ORAL_MODALITY)
    if not result["hard_gates"].get("grade_appropriateness", False):
        reasons.append(ReviewReason.DIFFICULTY_UNCERTAIN)
    if len(result["explanation"].strip()) < 80:
        reasons.append(ReviewReason.EXPLANATION_REVIEW)
    if near_duplicate:
        reasons.append(ReviewReason.NEAR_DUPLICATE)
    if not reasons:
        reasons.append(ReviewReason.OTHER)
    return tuple(dict.fromkeys(reasons))


def automatic_resolution_possible(
    result: dict[str, Any], source: dict[str, Any], reasons: tuple[ReviewReason, ...]
) -> bool:
    """Resolve only independently checked Mathematics answers with every hard gate satisfied."""
    return bool(
        result["decision"] == "REVIEW"
        and result["subject"] == "MATHEMATICS"
        and source["answer"]["kind"] == "numeric"
        and source["answer"].get("independently_computed") is not None
        and all(value for key, value in result["hard_gates"].items() if key != "grade_appropriateness")
        and ReviewReason.SOURCE_DOCUMENT_REQUIRED not in reasons
        and ReviewReason.ORAL_MODALITY not in reasons
    )


def candidate_score(
    result: dict[str, Any],
    source: dict[str, Any],
    *,
    decision: str,
    missing_coverage: bool,
    near_duplicate: bool,
) -> int:
    if not all(value for key, value in result["hard_gates"].items() if key != "grade_appropriateness"):
        return 0
    score = {"PASS": 80, "REVIEW": 45, "REJECT": 0}[decision]
    answer = source["answer"]
    if answer.get("independently_computed") is not None:
        score += 10
    if answer["kind"] in {"single_choice", "multiple_choice"}:
        score += 5
    if missing_coverage:
        score += 5
    if result["prompt"].strip() and result["explanation"].strip():
        score += 3
    if near_duplicate:
        score -= 15
    return max(0, min(100, score))


def rank_candidates(candidates: list[RankedCandidate]) -> list[RankedCandidate]:
    return sorted(
        candidates,
        key=lambda item: (
            not item.hard_gates_passed,
            {"PASS": 0, "REVIEW": 1, "REJECT": 2}[item.decision],
            -item.score,
            item.code,
        ),
    )
