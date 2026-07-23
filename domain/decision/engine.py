"""Pure scheduler, selector, blockage detector and decision arbitration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta

from domain.decision.enums import PedagogicalStrategy, PriorityBand
from domain.decision.models import (
    Blockage,
    CandidateActivity,
    DecisionContext,
    DecisionExplanation,
    LearningDecision,
    PriorityScore,
    ScheduledActivity,
)
from domain.decision.policies import DecisionConfiguration


def detect_blockages(context: DecisionContext, config: DecisionConfiguration | None = None) -> tuple[Blockage, ...]:
    config = config or DecisionConfiguration()
    blockages: list[Blockage] = []
    for candidate in context.candidates:
        direct = context.prerequisite_graph.get(candidate.skill_id, candidate.prerequisite_ids)
        blocking = tuple(
            skill
            for skill in direct
            if skill not in context.mastery or context.mastery[skill].score < config.blocking_threshold
        )
        if blocking:
            chain = _prerequisite_chain(candidate.skill_id, context.prerequisite_graph)
            severity = max(
                0.0, 1 - min((context.mastery[s].score for s in blocking if s in context.mastery), default=0.0)
            )
            blockages.append(Blockage(candidate.skill_id, blocking, chain, severity, "blocking_prerequisite"))
    return tuple(sorted(blockages, key=lambda item: (-item.severity, item.skill_id)))


def _prerequisite_chain(skill_id: int, graph: dict[int, tuple[int, ...]]) -> tuple[int, ...]:
    result: list[int] = []
    seen: set[int] = set()

    def visit(node: int) -> None:
        if node in seen:
            return
        seen.add(node)
        for prerequisite in sorted(graph.get(node, ())):
            visit(prerequisite)
            result.append(prerequisite)

    visit(skill_id)
    return tuple(dict.fromkeys(result))


def prioritize(context: DecisionContext, config: DecisionConfiguration | None = None) -> tuple[PriorityScore, ...]:
    config = config or DecisionConfiguration()
    blockage_by_skill = {item.skill_id: item for item in detect_blockages(context, config)}
    scores: list[PriorityScore] = []
    for candidate in context.candidates:
        if not candidate.eligible:
            continue
        state = context.mastery.get(candidate.skill_id) or candidate.mastery
        reasons: list[str] = []
        rules: list[str] = []
        prerequisite_ids: tuple[int, ...] = ()
        if candidate.skill_id in blockage_by_skill:
            blockage = blockage_by_skill[candidate.skill_id]
            band = PriorityBand.BLOCKING_PREREQUISITE
            score = config.blocking_score + blockage.severity * 10
            prerequisite_ids = blockage.blocking_skill_ids
            reasons.append("Impossible de poursuivre tant que le prérequis n'est pas consolidé.")
            rules.append("BLOCKING_PREREQUISITE")
        elif state is not None and state.observations and state.score < config.fragile_threshold:
            band = PriorityBand.FRAGILE_SKILL
            score = config.fragile_score + (config.fragile_threshold - state.score) * 20
            reasons.append("Compétence fragile à consolider.")
            rules.append("FRAGILE_MASTERY")
        elif candidate.revision_due:
            band = PriorityBand.PERIODIC_REVISION
            score = config.revision_score
            reasons.append("Révision périodique arrivée à échéance.")
            rules.append("REVIEW_DUE")
        else:
            band = PriorityBand.NEW_SKILL
            score = config.new_skill_score
            reasons.append("Nouvelle compétence éligible dans le parcours.")
            rules.append("NEW_SKILL")
        if candidate.subject_id in context.journey.preferred_subjects:
            score += config.preferred_subject_bonus
            reasons.append("Matière préférée.")
            rules.append("PREFERRED_SUBJECT")
        if candidate.subject_id in context.journey.weak_subjects:
            score += config.weak_subject_bonus
            reasons.append("Matière prioritaire car fragile.")
            rules.append("WEAK_SUBJECT")
        if candidate.subject_id not in context.recent_subject_ids:
            score += config.variety_bonus
            rules.append("SUBJECT_VARIETY")
        deadline = context.journey.current_objective.target_date or context.journey.target_date
        if deadline:
            days = max(0, (deadline - context.now.date()).days)
            bonus = config.deadline_bonus_max * max(0, 1 - days / 90)
            score += bonus
            if bonus:
                reasons.append(f"Échéance dans {days} jours.")
                rules.append("OBJECTIVE_DEADLINE")
        scores.append(
            PriorityScore(candidate.id, band, round(score, 4), tuple(reasons), tuple(rules), prerequisite_ids)
        )
    return tuple(sorted(scores, key=lambda item: (item.band, -item.score, item.candidate_id)))


def next_window(context: DecisionContext) -> datetime:
    schedule = context.journey.weekly_schedule
    if not schedule:
        return context.now
    for offset in range(8):
        day = context.now + timedelta(days=offset)
        options = sorted((slot for slot in schedule if slot.weekday == day.weekday()), key=lambda slot: slot.start_time)
        for slot in options:
            candidate = day.replace(hour=slot.start_time.hour, minute=slot.start_time.minute, second=0, microsecond=0)
            if candidate >= context.now:
                return candidate
    return context.now


def select_candidates(context: DecisionContext, priorities: tuple[PriorityScore, ...]) -> tuple[CandidateActivity, ...]:
    by_id = {candidate.id: candidate for candidate in context.candidates if candidate.eligible}
    return tuple(by_id[priority.candidate_id] for priority in priorities if priority.candidate_id in by_id)


def build_plan(
    context: DecisionContext, ranked: tuple[CandidateActivity, ...], config: DecisionConfiguration
) -> tuple[ScheduledActivity, ...]:
    budget = context.journey.daily_duration_minutes
    if context.journey.vacation_mode:
        budget = max(config.minimum_activity_minutes, round(budget * config.vacation_duration_factor))
    scheduled_for = next_window(context)
    plan: list[ScheduledActivity] = []
    consumed = 0
    for candidate in ranked:
        remaining = budget - consumed
        if remaining < config.minimum_activity_minutes:
            break
        duration = min(candidate.estimated_minutes, remaining, config.maximum_activity_minutes)
        duration = max(config.minimum_activity_minutes, duration)
        difficulty = max(1, min(5, round((candidate.difficulty + context.journey.difficulty_preference) / 2)))
        plan.append(
            ScheduledActivity(
                candidate.id,
                candidate.skill_id,
                candidate.subject_id,
                scheduled_for + timedelta(minutes=consumed),
                duration,
                difficulty,
                len(plan) + 1,
            )
        )
        consumed += duration
    return tuple(plan)


def choose_strategy(context: DecisionContext, config: DecisionConfiguration) -> PedagogicalStrategy:
    return config.objective_strategies[context.journey.current_objective.kind]


def decide(context: DecisionContext, config: DecisionConfiguration | None = None) -> LearningDecision:
    config = config or DecisionConfiguration()
    priorities = prioritize(context, config)
    ranked = select_candidates(context, priorities)
    plan = build_plan(context, ranked, config)
    blockages = detect_blockages(context, config)
    selected = plan[0] if plan else None
    selected_priority = next(
        (item for item in priorities if selected and item.candidate_id == selected.candidate_id), None
    )
    reason = selected_priority.reasons[0] if selected_priority else "Aucune activité éligible."
    rules = selected_priority.rules if selected_priority else ("NO_ELIGIBLE_ACTIVITY",)
    explanation = DecisionExplanation(
        reason,
        selected_priority.reasons if selected_priority else ("Contraintes ou disponibilité insuffisantes.",),
        (f"Difficulté {selected.difficulty} issue de la préférence et du niveau candidat.",) if selected else (),
        ("Matière priorisée par fragilité, préférence, échéance et variété.",) if selected else (),
        (f"Durée limitée au budget quotidien de {context.journey.daily_duration_minutes} minutes.",),
        rules,
    )
    serializable = {
        "learner_id": context.journey.learner_id,
        "objective": context.journey.current_objective.id,
        "now": context.now.isoformat(),
        "candidates": [asdict(candidate) for candidate in context.candidates],
    }
    context_hash = hashlib.sha256(json.dumps(serializable, default=str, sort_keys=True).encode()).hexdigest()
    correlation_id = hashlib.sha256(f"{context_hash}:decision-v1".encode()).hexdigest()[:24]
    confidence_values = [state.confidence for state in context.mastery.values() if state.observations]
    confidence = sum(confidence_values) / len(confidence_values) if confidence_values else config.confidence_floor
    return LearningDecision(
        correlation_id,
        context.journey.learner_id,
        choose_strategy(context, config),
        context.journey.current_objective.id,
        selected,
        plan,
        priorities,
        blockages,
        explanation,
        round(confidence, 4),
        context.now,
        context_hash,
    )
