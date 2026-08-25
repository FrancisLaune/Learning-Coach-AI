"""LCAI-0030-C — adaptation by outcomes + useful progressive aids."""

from __future__ import annotations

from services.homework.exercise_selection import (
    LearnerOutcomeSignals,
    categorize_row,
    panachage_select,
    strategy_from_outcomes,
    target_difficulty_from_outcomes,
)
from services.student_guidance.deterministic import homework_during


def test_strategy_reinforces_after_failures() -> None:
    strategy = strategy_from_outcomes(LearnerOutcomeSignals(avg_score=0.3, failure_streak=3))
    assert strategy.consolidation_share > strategy.stretch_share
    assert strategy.stretch_share <= 0.10


def test_strategy_stretches_after_successes() -> None:
    strategy = strategy_from_outcomes(LearnerOutcomeSignals(avg_score=0.8, success_streak=4))
    assert strategy.stretch_share > strategy.consolidation_share


def test_target_difficulty_rises_with_success_streak() -> None:
    signals = LearnerOutcomeSignals(avg_score=0.8, success_streak=4, avg_last_difficulty=3)
    assert target_difficulty_from_outcomes(signals) == 4


def test_target_difficulty_falls_with_failure_streak() -> None:
    signals = LearnerOutcomeSignals(avg_score=0.3, failure_streak=3, avg_last_difficulty=3)
    assert target_difficulty_from_outcomes(signals) == 2


def test_panachage_uses_reinforcement_mix_on_failures() -> None:
    rows = [
        (1, 10, 100, 2),
        (2, 10, 100, 3),
        (3, 11, 101, 3),
        (4, 11, 101, 4),
        (5, 12, 102, 2),
        (6, 12, 102, 4),
        (7, 13, 103, 2),
        (8, 13, 103, 3),
    ]
    strategy = strategy_from_outcomes(LearnerOutcomeSignals(failure_streak=3, avg_score=0.3))
    selected = panachage_select(rows, target=3, exercise_count=6, strategy=strategy)
    buckets = [categorize_row(int(row[3]), 3) for row in selected]
    assert buckets.count("CONSOLIDATION") >= buckets.count("STRETCH")


def test_useful_aid_is_explicit_and_single_level() -> None:
    response = homework_during(1, statement="Calcule le volume d'un cube d'arête 3 cm")
    assert "V = a³" in response.message or "a × a × a" in response.message
    assert response.help_level == 1
    for level in (1, 2, 3, 4, 5):
        msg = homework_during(level, hint_text="Soustrais le même nombre au numérateur et au dénominateur.").message
        assert msg
        assert "solution complète" not in msg.lower()


def test_aid_includes_provided_hint() -> None:
    response = homework_during(2, hint_text="Divise numérateur et dénominateur par 2.")
    assert "Divise numérateur" in response.message
