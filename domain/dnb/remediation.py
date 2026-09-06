"""LCAI-0031 — Prerequisite remediation suggestions (pure)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PrerequisiteGap:
    target_skill_id: int
    target_label: str
    prerequisite_skill_id: int
    prerequisite_label: str
    prerequisite_grade_code: str | None = None


@dataclass(frozen=True, slots=True)
class RemediationPlan:
    target_skill_id: int
    target_label: str
    prerequisite_skill_id: int
    prerequisite_label: str
    estimated_minutes: int
    steps: tuple[str, ...]
    exit_criterion: str
    reason: str


def build_remediation_plan(
    gap: PrerequisiteGap,
    *,
    estimated_minutes: int = 15,
) -> RemediationPlan:
    minutes = max(8, min(25, int(estimated_minutes)))
    grade = gap.prerequisite_grade_code or "niveau antérieur"
    return RemediationPlan(
        target_skill_id=gap.target_skill_id,
        target_label=gap.target_label,
        prerequisite_skill_id=gap.prerequisite_skill_id,
        prerequisite_label=gap.prerequisite_label,
        estimated_minutes=minutes,
        steps=(
            f"Mettre en pause la compétence 3e « {gap.target_label} ».",
            f"Micro-remédiation sur le prérequis « {gap.prerequisite_label} » ({grade}).",
            "Faire un test de sortie court sur le prérequis.",
            f"Revenir à « {gap.target_label} » si le prérequis est restauré.",
        ),
        exit_criterion="Réussir le test de sortie du prérequis (seuil ≥ 70 %).",
        reason=(
            f"Échecs répétés sur « {gap.target_label} » : le prérequis "
            f"« {gap.prerequisite_label} » doit être consolidé avant de continuer."
        ),
    )
