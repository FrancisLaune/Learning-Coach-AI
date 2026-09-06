"""LCAI-0031 — Brevet skill prioritization (explainable, pure)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BrevetImportance(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


_IMPORTANCE_WEIGHT: dict[BrevetImportance, float] = {
    BrevetImportance.CRITICAL: 1.0,
    BrevetImportance.HIGH: 0.8,
    BrevetImportance.MEDIUM: 0.55,
    BrevetImportance.LOW: 0.3,
}


@dataclass(frozen=True, slots=True)
class SkillPriorityInput:
    skill_id: int
    label: str
    mastery_score: float  # 0..100
    importance: BrevetImportance = BrevetImportance.MEDIUM
    prerequisite_impact: float = 0.0  # 0..1 — how many dependent skills blocked
    revision_urgency: float = 0.0  # 0..1 — due / forgetting
    exam_frequency: float = 0.5  # 0..1 stub until annals metadata
    confidence: float = 0.5  # 0..1


@dataclass(frozen=True, slots=True)
class SkillPriorityResult:
    skill_id: int
    label: str
    priority: float
    importance: BrevetImportance
    mastery_gap: float
    reason: str


def mastery_gap(mastery_score: float) -> float:
    return max(0.0, min(1.0, (100.0 - float(mastery_score)) / 100.0))


def time_to_exam_factor(days_until_exam: int | None) -> float:
    """Closer exams raise priority (1.0 when ≤30 days, ~0.4 when far)."""
    if days_until_exam is None:
        return 0.7
    if days_until_exam <= 0:
        return 1.0
    if days_until_exam <= 30:
        return 1.0
    if days_until_exam <= 90:
        return 0.85
    if days_until_exam <= 180:
        return 0.65
    return 0.45


def score_skill(
    item: SkillPriorityInput,
    *,
    days_until_exam: int | None,
) -> SkillPriorityResult:
    gap = mastery_gap(item.mastery_score)
    importance = _IMPORTANCE_WEIGHT[item.importance]
    confidence_factor = max(0.35, min(1.0, 1.15 - float(item.confidence)))
    tte = time_to_exam_factor(days_until_exam)
    priority = (
        importance
        * max(0.05, gap)
        * (0.5 + 0.5 * max(0.0, min(1.0, item.prerequisite_impact)))
        * (0.5 + 0.5 * max(0.0, min(1.0, item.revision_urgency)))
        * (0.5 + 0.5 * max(0.0, min(1.0, item.exam_frequency)))
        * confidence_factor
        * tte
    )
    reasons: list[str] = []
    if item.importance in {BrevetImportance.CRITICAL, BrevetImportance.HIGH}:
        reasons.append(f"importante au Brevet ({item.importance.value})")
    if gap >= 0.4:
        reasons.append("actuellement fragile")
    if item.prerequisite_impact >= 0.5:
        reasons.append("nécessaire pour d'autres compétences")
    if item.revision_urgency >= 0.5:
        reasons.append("en révision due")
    if days_until_exam is not None and days_until_exam <= 90:
        reasons.append("proche de l'échéance DNB")
    if not reasons:
        reasons.append("utile à la consolidation du programme 3e")
    reason = "Cette compétence est prioritaire car elle est " + ", ".join(reasons) + "."
    return SkillPriorityResult(
        skill_id=item.skill_id,
        label=item.label,
        priority=round(priority, 4),
        importance=item.importance,
        mastery_gap=round(gap, 4),
        reason=reason,
    )


def prioritize_skills(
    items: tuple[SkillPriorityInput, ...] | list[SkillPriorityInput],
    *,
    days_until_exam: int | None,
    limit: int = 10,
) -> tuple[SkillPriorityResult, ...]:
    scored = [score_skill(item, days_until_exam=days_until_exam) for item in items]
    scored.sort(key=lambda row: (-row.priority, row.label.casefold()))
    return tuple(scored[: max(0, limit)])


def default_importance_for_subject(subject_code: str | None) -> BrevetImportance:
    code = (subject_code or "").upper()
    if code in {"MATHEMATICS", "FRENCH"}:
        return BrevetImportance.CRITICAL
    if code in {"HISTORY", "GEOGRAPHY", "EMC", "PHYSICS_CHEMISTRY", "SVT", "TECHNOLOGY"}:
        return BrevetImportance.HIGH
    return BrevetImportance.LOW
