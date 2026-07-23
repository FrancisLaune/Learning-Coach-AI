"""Pure deterministic calculators for longitudinal learning."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from math import exp

from domain.learning.enums import MasteryLevel, PrerequisiteCondition, Trend
from domain.learning.models import (
    AttemptEvaluation,
    CurriculumContext,
    DifficultyRecommendation,
    ExamReadiness,
    ForgettingAdjustment,
    LearnerAttempt,
    LearnerJourneyContext,
    MasteryState,
    MasteryUpdate,
    PrerequisiteStatus,
    ProgressState,
    TransitionReadiness,
)
from domain.learning.policies import LearningEngineConfiguration


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def mastery_level(score: float, config: LearningEngineConfiguration) -> MasteryLevel:
    if score < config.emerging_threshold:
        return MasteryLevel.NOT_STARTED
    if score < config.developing_threshold:
        return MasteryLevel.EMERGING
    if score < config.proficient_threshold:
        return MasteryLevel.DEVELOPING
    if score < config.mastered_threshold:
        return MasteryLevel.PROFICIENT
    return MasteryLevel.MASTERED


def evaluate_attempt(
    attempt: LearnerAttempt, journey: LearnerJourneyContext, config: LearningEngineConfiguration
) -> AttemptEvaluation:
    if not 0 <= attempt.correctness <= 1 or not 1 <= attempt.difficulty <= 5:
        raise ValueError("Correctness and difficulty are outside supported bounds")
    quality = attempt.correctness
    difficulty = 0.85 + (attempt.difficulty - 1) * 0.075
    hints = max(0.45, 1 - attempt.hints_used * config.hint_penalty)
    retries = max(0.50, 1 - max(0, attempt.attempt_number - 1) * config.retry_penalty)
    time = 1.0
    reasons = [f"quality:{quality:.3f}", f"difficulty:{difficulty:.3f}"]
    if attempt.elapsed_seconds is not None and attempt.expected_seconds:
        ratio = attempt.elapsed_seconds / attempt.expected_seconds
        if ratio < config.fast_time_floor_ratio:
            time = 0.85
            reasons.append("time:possibly_random")
        elif ratio > config.slow_time_ratio:
            time = max(0.75, 1 - (ratio - config.slow_time_ratio) * 0.05)
            reasons.append("time:slow")
    phase = config.phase_multipliers.get(journey.phase, 1.0)
    revision = 1.04 if attempt.is_revision else 1.0
    score = quality * difficulty * hints * retries * time * phase * revision
    if attempt.solution_revealed:
        score = min(score, config.solution_cap)
        reasons.append("solution_revealed")
    if attempt.abandoned:
        score = min(score, config.abandonment_cap)
        reasons.append("abandoned")
    declared = 0.7 if attempt.declared_confidence is None else clamp(attempt.declared_confidence)
    confidence = clamp(0.65 + 0.25 * declared - 0.08 * attempt.hints_used)
    return AttemptEvaluation(clamp(score), quality, difficulty, time, hints, retries, phase, confidence, tuple(reasons))


def apply_forgetting(state: MasteryState, at: datetime, config: LearningEngineConfiguration) -> ForgettingAdjustment:
    if not config.forgetting_enabled or state.last_activity_at is None:
        return ForgettingAdjustment(
            state.score,
            state.score,
            0,
            at + timedelta(days=30),
            state.confidence,
            ("forgetting_disabled_or_unobserved",),
        )
    days = max(0.0, (at - state.last_activity_at).total_seconds() / 86400)
    resilience = clamp(
        0.35 + state.stability * 0.40 + min(state.observations, 20) / 50 + state.last_difficulty / 50,
        high=0.90,
    )
    adjusted = state.score * exp(-config.forgetting_daily_rate * days * (1 - resilience))
    adjusted = max(min(state.score, config.forgetting_floor), adjusted)
    degradation = max(0.0, state.score - adjusted)
    interval = max(1, round(7 + 35 * resilience + 20 * adjusted))
    confidence = clamp(state.confidence * exp(-0.003 * days))
    return ForgettingAdjustment(
        state.score,
        adjusted,
        degradation,
        at + timedelta(days=interval),
        confidence,
        (f"elapsed_days:{days:.2f}", f"resilience:{resilience:.3f}"),
    )


def update_mastery(
    previous: MasteryState,
    evaluation: AttemptEvaluation,
    attempt: LearnerAttempt,
    journey: LearnerJourneyContext,
    forgetting: ForgettingAdjustment,
    config: LearningEngineConfiguration,
) -> MasteryUpdate:
    base = forgetting.adjusted_score
    positive = evaluation.score >= 0.55
    rate = config.mastery_learning_rate if positive else config.mastery_error_rate
    target = evaluation.score
    delta = (target - base) * rate * (0.65 + 0.35 * evaluation.confidence)
    score = clamp(base + delta)
    observations = previous.observations + 1
    successes = previous.successes + int(positive)
    failures = previous.failures + int(not positive)
    success_streak = previous.success_streak + 1 if positive else 0
    failure_streak = previous.failure_streak + 1 if not positive else 0
    confidence = clamp(1 - exp(-observations / 6) * (1 - evaluation.confidence * 0.3))
    stability = clamp(previous.stability * 0.82 + (0.18 * evaluation.score if positive else 0.04))
    trend = Trend.IMPROVING if delta > 0.015 else Trend.DECLINING if delta < -0.015 else Trend.STABLE
    current = replace(
        previous,
        score=score,
        level=mastery_level(score, config),
        observations=observations,
        successes=successes,
        failures=failures,
        success_streak=success_streak,
        failure_streak=failure_streak,
        last_activity_at=attempt.occurred_at,
        last_success_at=attempt.occurred_at if positive else previous.last_success_at,
        last_difficulty=attempt.difficulty,
        last_grade_code=journey.current_grade.code,
        confidence=confidence,
        trend=trend,
        stability=stability,
    )
    return MasteryUpdate(
        previous,
        current,
        evaluation,
        delta,
        (f"base_after_forgetting:{base:.3f}", f"learning_rate:{rate:.3f}", f"delta:{delta:.3f}"),
    )


def recommend_difficulty(
    state: MasteryState,
    forgetting: ForgettingAdjustment,
    prerequisites: tuple[PrerequisiteStatus, ...],
    journey: LearnerJourneyContext,
    config: LearningEngineConfiguration,
) -> DifficultyRecommendation:
    previous = max(1, min(5, state.last_difficulty))
    positive: list[str] = []
    negative: list[str] = []
    alerts: list[str] = []
    fragile = any(
        p.condition in (PrerequisiteCondition.FRAGILE, PrerequisiteCondition.NOT_ACQUIRED) for p in prerequisites
    )
    recommended = previous
    if fragile:
        negative.append("fragile_prerequisite")
        alerts.append("prerequisite_gap")
        recommended -= 1
    elif (
        state.success_streak >= config.difficulty_up_observations
        and state.confidence >= config.minimum_confidence_to_raise
        and forgetting.adjusted_score >= config.proficient_threshold
    ):
        positive.append("stable_success_streak")
        recommended += 1
    elif state.failure_streak >= config.difficulty_down_failures:
        negative.append("repeated_failures")
        recommended -= 1
    elif forgetting.degradation > 0.12:
        negative.append("old_mastery_requires_verification")
        recommended = min(recommended, 3)
    if journey.phase.value.endswith("preparation") and state.score >= config.developing_threshold:
        positive.append("preparation_phase")
    recommended = max(1, min(5, recommended))
    reason = positive[0] if positive else negative[0] if negative else "maintain_difficulty"
    return DifficultyRecommendation(
        previous,
        recommended,
        reason,
        tuple(positive + negative),
        tuple(positive),
        tuple(negative),
        state.confidence,
        tuple(alerts),
    )


def evaluate_prerequisites(
    states: dict[int, MasteryState], prerequisite_ids: tuple[int, ...], config: LearningEngineConfiguration
) -> tuple[PrerequisiteStatus, ...]:
    result = []
    for skill_id in prerequisite_ids:
        state = states.get(skill_id)
        if state is None or state.observations == 0:
            condition = PrerequisiteCondition.NOT_EVALUATED
        elif state.score >= config.proficient_threshold and state.confidence >= 0.5:
            condition = PrerequisiteCondition.ACQUIRED
        elif state.score >= config.developing_threshold:
            condition = PrerequisiteCondition.FRAGILE
        else:
            condition = PrerequisiteCondition.NOT_ACQUIRED
        result.append(
            PrerequisiteStatus(
                skill_id,
                condition,
                None if state is None else state.score,
                0 if state is None else state.confidence,
                None if state is None else state.origin_grade_code,
            )
        )
    return tuple(result)


def calculate_progress(
    scope_type: str,
    scope_id: int,
    contexts: tuple[CurriculumContext, ...],
    states: dict[int, MasteryState],
    config: LearningEngineConfiguration,
) -> ProgressState:
    total = sum(c.weight for c in contexts)
    evaluated = [c for c in contexts if c.skill_id in states and states[c.skill_id].observations]
    coverage = sum(c.weight for c in evaluated) / total if total else 0
    mastery = (
        sum(states[c.skill_id].score * c.weight for c in evaluated) / sum(c.weight for c in evaluated)
        if evaluated
        else 0
    )
    score = mastery * (1 - config.coverage_weight) + coverage * config.coverage_weight
    confidence = (
        sum(states[c.skill_id].confidence * c.weight for c in evaluated) / sum(c.weight for c in evaluated)
        if evaluated
        else 0
    )
    mastered = sum(states[c.skill_id].level is MasteryLevel.MASTERED for c in evaluated)
    fragile = sum(states[c.skill_id].score < config.proficient_threshold for c in evaluated)
    trend_values = [states[c.skill_id].trend for c in evaluated]
    trend = (
        Trend.IMPROVING
        if trend_values.count(Trend.IMPROVING) > trend_values.count(Trend.DECLINING)
        else Trend.DECLINING
        if trend_values.count(Trend.DECLINING) > trend_values.count(Trend.IMPROVING)
        else Trend.STABLE
    )
    return ProgressState(
        scope_type,
        scope_id,
        clamp(score),
        coverage,
        confidence,
        mastered,
        fragile,
        len(contexts) - len(evaluated),
        trend,
        (f"weighted_mastery:{mastery:.3f}", f"coverage:{coverage:.3f}"),
    )


def calculate_transition(
    journey: LearnerJourneyContext,
    contexts: tuple[CurriculumContext, ...],
    states: dict[int, MasteryState],
    config: LearningEngineConfiguration,
) -> TransitionReadiness | None:
    if journey.target_grade is None:
        return None
    required = tuple(c for c in contexts if c.required)
    progress = calculate_progress("grade", journey.target_grade.rank, required, states, config)
    acquired = tuple(
        c.skill_id for c in required if c.skill_id in states and states[c.skill_id].score >= config.proficient_threshold
    )
    fragile = tuple(
        c.skill_id
        for c in required
        if c.skill_id in states
        and config.developing_threshold <= states[c.skill_id].score < config.proficient_threshold
    )
    blocking = tuple(
        c.skill_id
        for c in required
        if c.skill_id not in states or states[c.skill_id].score < config.developing_threshold
    )
    penalty = min(0.35, len(blocking) / max(1, len(required)) * config.prerequisite_weight)
    return TransitionReadiness(
        journey.current_grade.code,
        journey.target_grade.code,
        clamp(progress.score - penalty),
        progress.coverage,
        progress.confidence,
        acquired,
        fragile,
        blocking,
        progress.reasons + (f"blocking:{len(blocking)}",),
    )


def calculate_exam(
    examination_code: str,
    contexts: tuple[CurriculumContext, ...],
    states: dict[int, MasteryState],
    config: LearningEngineConfiguration,
) -> ExamReadiness:
    stable_exam_id = sum((index + 1) * ord(char) for index, char in enumerate(examination_code))
    progress = calculate_progress("exam", stable_exam_id, contexts, states, config)
    subject_scores = {
        subject: calculate_progress(
            "subject", subject, tuple(c for c in contexts if c.subject_id == subject), states, config
        ).score
        for subject in {c.subject_id for c in contexts}
    }
    mastered = tuple(
        c.skill_id for c in contexts if c.skill_id in states and states[c.skill_id].score >= config.mastered_threshold
    )
    fragile = tuple(
        c.skill_id for c in contexts if c.skill_id in states and states[c.skill_id].score < config.proficient_threshold
    )
    unseen = tuple(c.skill_id for c in contexts if c.skill_id not in states or not states[c.skill_id].observations)
    return ExamReadiness(
        examination_code,
        progress.score,
        subject_scores,
        progress.coverage,
        mastered,
        fragile,
        unseen,
        progress.confidence,
        progress.trend,
        progress.reasons,
    )
