"""LCAI-0031 Phase 5 — unique Coach Brevet context + decisions."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from services.dnb.coach import (
    COACH_NAME,
    BrevetCoachContext,
    build_coach_system_briefing,
    build_coach_user_turn,
    coach_context_from_home,
)
from services.dnb.coach_decisions import decide_next_work, format_decision_for_student
from services.student_guidance.service import BREVET_COACH_PROMPT_PATH


def test_coach_briefing_includes_countdown_and_readiness() -> None:
    ctx = coach_context_from_home(
        display_name="Léa",
        objective="Préparer le DNB",
        today=date(2027, 1, 15),
    )
    briefing = build_coach_system_briefing(ctx)
    assert COACH_NAME in briefing or "Coach Brevet" in briefing
    assert "Léa" in briefing
    assert ctx.days_until_exam is not None
    assert str(ctx.days_until_exam) in briefing
    assert "Readiness" in briefing or "readiness" in briefing.casefold()


def test_coach_user_turn_embeds_briefing_every_exchange() -> None:
    ctx = BrevetCoachContext(
        display_name="Sam",
        days_until_exam=100,
        readiness_band="EN_COURS",
        priorities=("Équations — fragile",),
        exercise_statement="Résous 2x + 3 = 11",
        student_question="Par où commencer ?",
    )
    turn = build_coach_user_turn(ctx)
    assert "Sam" in turn
    assert "2x + 3 = 11" in turn
    assert "Par où commencer" in turn
    assert "Message de l'élève" in turn


def test_decide_next_work_prioritizes_exercise_then_priorities() -> None:
    with_ex = decide_next_work(
        BrevetCoachContext(exercise_statement="Calcule…", subject_label="Maths")
    )
    assert with_ex.decision_type == "EXERCISE_HELP"
    with_prio = decide_next_work(BrevetCoachContext(priorities=("Thalès — critique",)))
    assert with_prio.decision_type == "PRIORITY_WORK"
    assert "Thalès" in format_decision_for_student(with_prio)


def test_student_guidance_uses_brevet_coach_prompt() -> None:
    assert BREVET_COACH_PROMPT_PATH.name == "brevet_coach_system.md"
    assert BREVET_COACH_PROMPT_PATH.is_file()
    text = BREVET_COACH_PROMPT_PATH.read_text(encoding="utf-8")
    assert "Coach Brevet" in text
    assert "ONLY AI teacher" in text or "unique" in text.casefold()


def test_ui_revision_label_is_coach_brevet() -> None:
    root = Path(__file__).resolve().parents[1]
    unified = (root / "ui" / "unified_app.py").read_text(encoding="utf-8")
    assert "Recommandation du Coach Brevet" in unified
