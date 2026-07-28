"""Deterministic grade-appropriateness assessment with optional AI support."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

GradeAssessmentStatus = Literal[
    "GRADE_MATCH_CONFIRMED",
    "GRADE_PEDAGOGICALLY_APPROPRIATE",
    "GRADE_WARNING",
    "GRADE_FAIL",
]

_GRADE_CODE_PATTERN = re.compile(
    r"^(?:FR-)?(?P<token>3E|4E|5E|6E|CM1|CM2)$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class GradeAssessment:
    status: GradeAssessmentStatus
    gate_pass: bool
    concise_reason: str
    candidate_grade: str
    chapter_grade_token: str | None
    skill_grade_token: str | None
    curriculum_exact: bool
    ai_grade_score: int | None
    evidence: tuple[str, ...]


def grade_token(grade_code: str) -> str:
    normalized = str(grade_code or "").strip().upper()
    match = _GRADE_CODE_PATTERN.match(normalized)
    if match:
        return match.group("token").upper()
    if normalized.startswith("FR-"):
        return normalized[3:].upper()
    return normalized


def _token_in_code(code: str, token: str) -> bool:
    if not code or not token:
        return False
    normalized = str(code).upper()
    token_upper = token.upper()
    if token_upper in normalized:
        return True
    if token_upper in {"3E", "4E", "5E", "6E"}:
        return f"-{token_upper}-" in normalized or normalized.endswith(f"-{token_upper}")
    return False


def _extract_code_grade(code: str) -> str | None:
    normalized = str(code or "").upper()
    for token in ("CM2", "CM1", "6E", "5E", "4E", "3E"):
        if _token_in_code(normalized, token):
            return token
    return None


def assess_grade_appropriateness(
    item: dict[str, Any],
    *,
    ai_grade_score: int | None = None,
) -> GradeAssessment:
    """Assess whether content matches its declared curriculum grade."""
    candidate_grade = str(item.get("grade", ""))
    chapter = str(item.get("chapter", ""))
    skill = str(item.get("skill_code") or item.get("skill", ""))
    token = grade_token(candidate_grade)
    checks = item.get("automated_checks") or {}
    curriculum_exact = bool(checks.get("skill_alignment", False))
    chapter_token = _extract_code_grade(chapter)
    skill_token = _extract_code_grade(skill)
    difficulty = item.get("difficulty")
    evidence: list[str] = []

    if not token:
        return GradeAssessment(
            status="GRADE_FAIL",
            gate_pass=False,
            concise_reason="Candidate grade code is missing or unsupported.",
            candidate_grade=candidate_grade,
            chapter_grade_token=chapter_token,
            skill_grade_token=skill_token,
            curriculum_exact=curriculum_exact,
            ai_grade_score=ai_grade_score,
            evidence=("missing_candidate_grade",),
        )

    if not curriculum_exact:
        return GradeAssessment(
            status="GRADE_FAIL",
            gate_pass=False,
            concise_reason="Curriculum mapping is not exact for this candidate.",
            candidate_grade=candidate_grade,
            chapter_grade_token=chapter_token,
            skill_grade_token=skill_token,
            curriculum_exact=False,
            ai_grade_score=ai_grade_score,
            evidence=("curriculum_mapping_mismatch",),
        )

    chapter_match = chapter_token == token if chapter_token else _token_in_code(chapter, token)
    skill_match = skill_token == token if skill_token else _token_in_code(skill, token)
    evidence.append(f"candidate_grade={token}")
    if chapter_token:
        evidence.append(f"chapter_grade={chapter_token}")
    if skill_token:
        evidence.append(f"skill_grade={skill_token}")

    if not chapter_match or not skill_match:
        return GradeAssessment(
            status="GRADE_FAIL",
            gate_pass=False,
            concise_reason="Candidate grade does not match chapter or skill curriculum codes.",
            candidate_grade=candidate_grade,
            chapter_grade_token=chapter_token,
            skill_grade_token=skill_token,
            curriculum_exact=curriculum_exact,
            ai_grade_score=ai_grade_score,
            evidence=tuple(evidence + ["grade_code_mismatch"]),
        )

    if difficulty not in (1, 2, 3, None):
        return GradeAssessment(
            status="GRADE_WARNING",
            gate_pass=False,
            concise_reason="Difficulty level is outside the expected 1-3 range.",
            candidate_grade=candidate_grade,
            chapter_grade_token=chapter_token,
            skill_grade_token=skill_token,
            curriculum_exact=curriculum_exact,
            ai_grade_score=ai_grade_score,
            evidence=tuple(evidence + ["invalid_difficulty"]),
        )

    if ai_grade_score is not None and ai_grade_score < 70:
        return GradeAssessment(
            status="GRADE_FAIL",
            gate_pass=False,
            concise_reason="AI pedagogical review detected a material grade-level mismatch.",
            candidate_grade=candidate_grade,
            chapter_grade_token=chapter_token,
            skill_grade_token=skill_token,
            curriculum_exact=curriculum_exact,
            ai_grade_score=ai_grade_score,
            evidence=tuple(evidence + ["ai_grade_mismatch"]),
        )

    if ai_grade_score is not None and ai_grade_score >= 80:
        return GradeAssessment(
            status="GRADE_PEDAGOGICALLY_APPROPRIATE",
            gate_pass=True,
            concise_reason="Curriculum grade mapping is exact and AI confirms pedagogical appropriateness.",
            candidate_grade=candidate_grade,
            chapter_grade_token=chapter_token,
            skill_grade_token=skill_token,
            curriculum_exact=curriculum_exact,
            ai_grade_score=ai_grade_score,
            evidence=tuple(evidence + ["curriculum_exact", "ai_grade_confirmed"]),
        )

    if ai_grade_score is not None and 70 <= ai_grade_score < 80:
        return GradeAssessment(
            status="GRADE_WARNING",
            gate_pass=False,
            concise_reason="Curriculum mapping is exact but AI grade appropriateness remains borderline.",
            candidate_grade=candidate_grade,
            chapter_grade_token=chapter_token,
            skill_grade_token=skill_token,
            curriculum_exact=curriculum_exact,
            ai_grade_score=ai_grade_score,
            evidence=tuple(evidence + ["ai_grade_borderline"]),
        )

    return GradeAssessment(
        status="GRADE_MATCH_CONFIRMED",
        gate_pass=True,
        concise_reason="Curriculum grade mapping is exact across candidate, chapter and skill.",
        candidate_grade=candidate_grade,
        chapter_grade_token=chapter_token,
        skill_grade_token=skill_token,
        curriculum_exact=curriculum_exact,
        ai_grade_score=ai_grade_score,
        evidence=tuple(evidence + ["curriculum_exact"]),
    )


def grade_assessment_to_dict(assessment: GradeAssessment) -> dict[str, Any]:
    return {
        "status": assessment.status,
        "gate_pass": assessment.gate_pass,
        "concise_reason": assessment.concise_reason,
        "candidate_grade": assessment.candidate_grade,
        "chapter_grade_token": assessment.chapter_grade_token,
        "skill_grade_token": assessment.skill_grade_token,
        "curriculum_exact": assessment.curriculum_exact,
        "ai_grade_score": assessment.ai_grade_score,
        "evidence": list(assessment.evidence),
    }


def apply_grade_assessment(
    item: dict[str, Any],
    *,
    ai_grade_score: int | None = None,
) -> dict[str, Any]:
    """Attach grade assessment and sync automated_checks.grade_appropriateness."""
    assessment = assess_grade_appropriateness(item, ai_grade_score=ai_grade_score)
    enriched = dict(item)
    enriched["grade_assessment"] = grade_assessment_to_dict(assessment)
    checks = dict(enriched.get("automated_checks") or {})
    checks["grade_appropriateness"] = assessment.gate_pass
    enriched["automated_checks"] = checks
    return enriched
