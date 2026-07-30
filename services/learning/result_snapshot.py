"""Restore persisted Learning Engine snapshots for idempotent retries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from domain.learning.enums import MasteryLevel, Trend
from domain.learning.models import (
    AttemptEvaluation,
    DifficultyRecommendation,
    ExamReadiness,
    ForgettingAdjustment,
    LearningEngineMetrics,
    LearningEngineResult,
    MasteryState,
    MasteryUpdate,
    ProgressState,
    TransitionReadiness,
)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _tuple_str(values: Any) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(str(item) for item in values)


def _tuple_int(values: Any) -> tuple[int, ...]:
    if not values:
        return ()
    return tuple(int(item) for item in values)


def _mastery_state(data: dict[str, Any]) -> MasteryState:
    return MasteryState(
        int(data["learner_id"]),
        int(data["skill_id"]),
        float(data["score"]),
        MasteryLevel(str(data["level"])),
        int(data["observations"]),
        int(data["successes"]),
        int(data["failures"]),
        int(data["success_streak"]),
        int(data["failure_streak"]),
        _parse_datetime(data.get("last_activity_at")),
        _parse_datetime(data.get("last_success_at")),
        int(data["last_difficulty"]),
        None if data.get("last_grade_code") is None else str(data["last_grade_code"]),
        float(data["confidence"]),
        Trend(str(data["trend"])),
        float(data["stability"]),
        None if data.get("origin_grade_code") is None else str(data["origin_grade_code"]),
        bool(data.get("prerequisite_for_future", False)),
    )


def _attempt_evaluation(data: dict[str, Any]) -> AttemptEvaluation:
    return AttemptEvaluation(
        float(data["score"]),
        float(data["quality_effect"]),
        float(data["difficulty_effect"]),
        float(data["time_effect"]),
        float(data["hint_effect"]),
        float(data["attempt_effect"]),
        float(data["phase_effect"]),
        float(data["confidence"]),
        _tuple_str(data.get("reasons")),
    )


def _forgetting(data: dict[str, Any]) -> ForgettingAdjustment:
    return ForgettingAdjustment(
        float(data["observed_score"]),
        float(data["adjusted_score"]),
        float(data["degradation"]),
        _parse_datetime(data["next_revision_at"]) or datetime.now(),
        float(data["confidence"]),
        _tuple_str(data.get("reasons")),
    )


def _difficulty(data: dict[str, Any]) -> DifficultyRecommendation:
    return DifficultyRecommendation(
        int(data["previous"]),
        int(data["recommended"]),
        str(data["reason"]),
        _tuple_str(data.get("signals")),
        _tuple_str(data.get("positive_factors")),
        _tuple_str(data.get("negative_factors")),
        float(data["confidence"]),
        _tuple_str(data.get("alerts")),
    )


def _progress(data: dict[str, Any] | None) -> ProgressState | None:
    if not data:
        return None
    return ProgressState(
        str(data["scope_type"]),
        int(data["scope_id"]),
        float(data["score"]),
        float(data["coverage"]),
        float(data["confidence"]),
        int(data["mastered"]),
        int(data["fragile"]),
        int(data["not_evaluated"]),
        Trend(str(data["trend"])),
        _tuple_str(data.get("reasons")),
    )


def _transition(data: dict[str, Any] | None) -> TransitionReadiness | None:
    if not data:
        return None
    return TransitionReadiness(
        str(data["current_grade_code"]),
        str(data["target_grade_code"]),
        float(data["score"]),
        float(data["coverage"]),
        float(data["confidence"]),
        _tuple_int(data.get("acquired_skills")),
        _tuple_int(data.get("fragile_skills")),
        _tuple_int(data.get("blocking_skills")),
        _tuple_str(data.get("reasons")),
    )


def _exam(data: dict[str, Any] | None) -> ExamReadiness | None:
    if not data:
        return None
    subject_scores = data.get("subject_scores") or {}
    return ExamReadiness(
        str(data["examination_code"]),
        float(data["score"]),
        {int(key): float(value) for key, value in subject_scores.items()},
        float(data["coverage"]),
        _tuple_int(data.get("mastered_skills")),
        _tuple_int(data.get("fragile_skills")),
        _tuple_int(data.get("not_evaluated_skills")),
        float(data["confidence"]),
        Trend(str(data["trend"])),
        _tuple_str(data.get("reasons")),
    )


def restore_learning_engine_result(payload: dict[str, Any]) -> LearningEngineResult:
    mastery = payload["mastery"]
    metrics = payload["metrics"]
    return LearningEngineResult(
        str(payload["attempt_id"]),
        _attempt_evaluation(payload["evaluation"]),
        _forgetting(payload["forgetting"]),
        MasteryUpdate(
            _mastery_state(mastery["previous"]),
            _mastery_state(mastery["current"]),
            _attempt_evaluation(mastery["signal"]),
            float(mastery["delta"]),
            _tuple_str(mastery.get("reasons")),
        ),
        _difficulty(payload["difficulty"]),
        _progress(payload.get("progress")),
        _transition(payload.get("transition")),
        _exam(payload.get("exam")),
        tuple(payload.get("events") or ()),
        LearningEngineMetrics(
            int(metrics["duration_ms"]),
            int(metrics["events_produced"]),
            int(metrics["updates"]),
            int(metrics["calculations"]),
            int(metrics.get("errors", 0)),
        ),
        already_processed=bool(payload.get("already_processed", False)),
    )
