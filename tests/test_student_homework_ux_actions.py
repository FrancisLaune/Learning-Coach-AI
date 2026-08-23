"""Student UX — homework cancel, evaluations, multiline answer heuristics."""

from __future__ import annotations

from datetime import UTC, datetime

from domain.unified_experience.models import (
    CORRECTION_POLICY_EVALUATION,
    EVALUATION_QUESTION_PRESETS,
    AssignmentStatus,
    AssignmentType,
    DifficultyMode,
    HomeworkAssignment,
)
from services.learning_session.answer_input import (
    needs_scientific_notation_guide,
    prefers_multiline_answer,
)


def test_evaluation_presets_and_marker() -> None:
    assert EVALUATION_QUESTION_PRESETS == (10, 20, 30, 40)
    assert CORRECTION_POLICY_EVALUATION == "EVALUATION"
    item = HomeworkAssignment(
        1,
        2,
        AssignmentType.GLOBAL_SUBJECT,
        AssignmentStatus.READY,
        3,
        "Mathématiques",
        DifficultyMode.ADAPTIVE,
        20,
        45,
        None,
        (1, 2),
        None,
        "STUDENT",
        datetime.now(tz=UTC),
        CORRECTION_POLICY_EVALUATION,
    )
    assert item.is_evaluation is True


def test_prefers_multiline_for_long_text_and_keywords() -> None:
    assert prefers_multiline_answer("LONG_TEXT") is True
    assert prefers_multiline_answer("SHORT_TEXT", statement="Calcule 2+2") is False
    assert prefers_multiline_answer("TEXT", statement="Explique ta démarche étape par étape") is True


def test_scientific_notation_guide_detection() -> None:
    assert needs_scientific_notation_guide(statement="Écris en notation scientifique") is True
    assert needs_scientific_notation_guide(statement="Calcule 3 + 4") is False
