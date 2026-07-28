"""Tests for grade appropriateness assessment."""

from __future__ import annotations

from services.content.grade_appropriateness import apply_grade_assessment, assess_grade_appropriateness


def _item(**overrides: object) -> dict:
    base = {
        "grade": "FR-3E",
        "chapter": "CH-GEOGRAPHY-3E-EU",
        "skill": "SK-ENR-GEOGRAPHY-3E-EU-WORLD",
        "skill_code": "SK-ENR-GEOGRAPHY-3E-EU-WORLD",
        "difficulty": 2,
        "automated_checks": {
            "structural_validity": True,
            "answer_correctness": True,
            "skill_alignment": True,
            "grade_appropriateness": False,
            "executability": True,
        },
    }
    base.update(overrides)
    return base


def test_grade_check_exact_match() -> None:
    result = assess_grade_appropriateness(_item())
    assert result.status == "GRADE_MATCH_CONFIRMED"
    assert result.gate_pass is True


def test_wrong_grade_blocked() -> None:
    result = assess_grade_appropriateness(_item(grade="FR-4E"))
    assert result.status == "GRADE_FAIL"
    assert result.gate_pass is False


def test_valid_grade_no_legacy_false_negative() -> None:
    enriched = apply_grade_assessment(_item(), ai_grade_score=88)
    assert enriched["automated_checks"]["grade_appropriateness"] is True
    assert enriched["grade_assessment"]["status"] == "GRADE_PEDAGOGICALLY_APPROPRIATE"


def test_curriculum_mismatch_fails() -> None:
    result = assess_grade_appropriateness(
        _item(automated_checks={"skill_alignment": False}),
    )
    assert result.status == "GRADE_FAIL"
