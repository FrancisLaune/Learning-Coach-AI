"""Student UX — homework cancel, evaluations, multiline answer heuristics."""

from __future__ import annotations

from datetime import UTC, datetime

from domain.unified_experience.models import (
    ASSIGNMENT_KIND_EVALUATION,
    HOMEWORK_QUESTION_PRESETS,
    AssignmentStatus,
    AssignmentType,
    DifficultyMode,
    HomeworkAssignment,
    HomeworkRequest,
)
from services.homework.evaluation_sizing import (
    plan_evaluation_from_catalog_rows,
    score_percent_to_out_of_20,
)
from services.learning_session.answer_input import (
    needs_scientific_notation_guide,
    prefers_multiline_answer,
)


def test_evaluation_kind_and_homework_presets() -> None:
    assert HOMEWORK_QUESTION_PRESETS == (10, 20, 30, 40)
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
        "AFTER_SUBMISSION",
        ASSIGNMENT_KIND_EVALUATION,
    )
    assert item.is_evaluation is True
    request = HomeworkRequest(
        1,
        "STUDENT",
        "learner:1",
        AssignmentType.GLOBAL_SUBJECT,
        3,
        4,
        (),
        (),
        DifficultyMode.ADAPTIVE,
        10,
        45,
        None,
        "AFTER_SUBMISSION",
        ASSIGNMENT_KIND_EVALUATION,
    )
    assert request.is_evaluation is True
    assert request.correction_policy == "AFTER_SUBMISSION"


def test_plan_evaluation_respects_45_minute_budget() -> None:
    rows = [(i, 1, 1, 2 + (i % 3), "exercise", 5) for i in range(1, 30)]
    plan = plan_evaluation_from_catalog_rows(rows, max_minutes=45)
    assert 5 <= plan.exercise_count <= 40
    assert plan.estimated_minutes <= 45
    assert plan.score_out_of == 20
    assert abs(plan.points_per_question * plan.exercise_count - 20) < 0.2


def test_score_percent_to_out_of_20() -> None:
    assert score_percent_to_out_of_20(100) == 20.0
    assert score_percent_to_out_of_20(50) == 10.0
    assert score_percent_to_out_of_20(None) is None


def test_prefers_multiline_for_long_text_and_keywords() -> None:
    assert prefers_multiline_answer("LONG_TEXT") is True
    assert prefers_multiline_answer("SHORT_TEXT", statement="Calcule 2+2") is True
    assert prefers_multiline_answer("TEXT", statement="Explique ta démarche étape par étape") is True
    assert prefers_multiline_answer("MCQ_SINGLE") is False


def test_scientific_notation_guide_detection() -> None:
    from services.learning_session.answer_input import notation_guide_for_response_type

    assert needs_scientific_notation_guide(statement="Écris en notation scientifique") is True
    assert needs_scientific_notation_guide(statement="Calcule 3 + 4") is False
    guide = notation_guide_for_response_type("SHORT_TEXT", statement="Calcule le volume")
    assert "plusieurs lignes" in guide.casefold() or "décimal" in guide.casefold() or "virgule" in guide.casefold()


def test_power_notation_guide_for_power_questions() -> None:
    from services.learning_session.answer_input import (
        POWER_NOTATION_GUIDE,
        needs_power_notation_guide,
        notation_guide_for_response_type,
    )

    statement = "Écrire 2 × 2 × 2 × 2 × 2 sous forme d’une puissance."
    assert needs_power_notation_guide(statement=statement) is True
    guide = notation_guide_for_response_type("SHORT_TEXT", statement=statement)
    assert guide == POWER_NOTATION_GUIDE
    assert "2^5" in guide
    assert "^" in guide


def test_history_rows_label_evaluation_sessions() -> None:
    from services.learning_session.experience import SessionListItem
    from ui.v2_experience import _history_rows

    session = SessionListItem(
        42,
        "COMPLETED",
        datetime.now(tz=UTC),
        600,
        80.0,
        1.5,
        100.0,
    )
    rows = _history_rows((session,), session_kinds={42: "Évaluation"})
    assert rows[0]["Type"] == "Évaluation"
    assert rows[0]["Score"] == "80 %"
