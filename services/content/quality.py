"""Explainable hard-gate quality decisions for generated educational content."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from domain.content.factory import normalized_content_fingerprint


class AuditDecision(StrEnum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class GateResult:
    structural_validity: bool
    answer_correctness: bool
    skill_alignment: bool
    grade_appropriateness: bool
    executability: bool
    duplicate_safety: bool

    @property
    def passed(self) -> bool:
        return all(
            (
                self.structural_validity,
                self.answer_correctness,
                self.skill_alignment,
                self.grade_appropriateness,
                self.executability,
                self.duplicate_safety,
            )
        )


def structural_issues(item: dict[str, Any], candidate: dict[str, Any] | None) -> tuple[str, ...]:
    issues: list[str] = []
    target = (candidate or {}).get("target") or item["payload"].get("curriculum_target", {})
    expected = {
        "program_code": item["program"],
        "grade_code": item["grade"],
        "subject_code": item["subject"],
        "chapter_code": item["chapter"],
        "primary_skill_code": item["skill"],
    }
    for key, value in expected.items():
        if target.get(key) != value:
            issues.append(f"invalid_{key}")
    if item["curriculum_relation_count"] != 1:
        issues.append("invalid_chapter_skill_relation")
    if item["difficulty"] not in (1, 2, 3):
        issues.append("invalid_difficulty")
    if not item["prompt"].strip():
        issues.append("empty_prompt")
    if not item["explanation"].strip():
        issues.append("empty_explanation")
    if item["stored_answer"] in (None, "", [], {}):
        issues.append("malformed_answer")
    if candidate is None:
        issues.append("missing_generation_provenance")
    elif candidate.get("language_code", "fr-FR") != "fr-FR":
        issues.append("incompatible_language")
    return tuple(issues)


def qcm_issues(candidate: dict[str, Any], persisted: dict[str, Any] | None) -> tuple[str, ...]:
    answer = candidate["answer"]
    options = [str(item).strip() for item in answer.get("options", [])]
    normalized = [normalized_content_fingerprint(item) for item in options]
    expected = (
        [str(item) for item in answer["expected"]] if answer["kind"] == "multiple_choice" else [str(answer["expected"])]
    )
    issues: list[str] = []
    if len(options) < 2:
        issues.append("missing_choices")
    if len(set(normalized)) != len(normalized):
        issues.append("duplicate_choices")
    if not set(expected).issubset(set(options)):
        issues.append("correct_answer_not_in_choices")
    if persisted is None:
        issues.append("choices_not_persisted")
    else:
        persisted_options = persisted["options"]
        if [item["label"] for item in persisted_options] != options:
            issues.append("persisted_choices_mismatch")
        correct = [item["label"] for item in persisted_options if item["correct"]]
        if set(correct) != set(expected):
            issues.append("persisted_correct_answer_mismatch")
        if [item["sequence"] for item in persisted_options] != list(range(1, len(options) + 1)):
            issues.append("unstable_choice_order")
    return tuple(issues)


def promotion_eligible(decision: AuditDecision, confidence: float, gates: GateResult) -> bool:
    """Return candidacy only; human approval remains a separate existing workflow."""
    return decision is AuditDecision.PASS and confidence >= 0.95 and gates.passed
