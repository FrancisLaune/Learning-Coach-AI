"""Coverage planning primitives for the controlled LCAI-0012C expansion."""

from __future__ import annotations

from dataclasses import dataclass

from domain.content.factory import (
    CanonicalContentType,
    ContentGenerationRequest,
    CurriculumTarget,
    PedagogicalIntent,
)

TARGET_GRADES = ("FR-4E", "FR-3E")


@dataclass(frozen=True, slots=True)
class ContentSlot:
    content_type: CanonicalContentType
    difficulty: int


@dataclass(frozen=True, slots=True)
class ActiveSkillCoverage:
    target: CurriculumTarget
    grade_label: str
    subject_label: str
    chapter_label: str
    skill_label: str
    subskills: tuple[tuple[str, str], ...]
    prerequisites: tuple[str, ...]
    downstream_dependencies: int
    approved: dict[ContentSlot, int]
    draft: dict[ContentSlot, int]

    def count(self, slot: ContentSlot) -> int:
        return self.approved.get(slot, 0) + self.draft.get(slot, 0)


@dataclass(frozen=True, slots=True)
class CoverageGap:
    skill: ActiveSkillCoverage
    slot: ContentSlot
    priority: int

    def request(self) -> ContentGenerationRequest:
        intent = {
            CanonicalContentType.PRACTICE: PedagogicalIntent.PRACTICE,
            CanonicalContentType.ASSESSMENT: PedagogicalIntent.CHECK,
            CanonicalContentType.DIAGNOSTIC: PedagogicalIntent.DIAGNOSE,
            CanonicalContentType.REMEDIATION: PedagogicalIntent.REMEDIATE,
        }[self.slot.content_type]
        return ContentGenerationRequest(
            self.skill.target,
            self.slot.content_type,
            self.slot.difficulty,
            intent,
            variation_constraints=(
                "Vary context, representation and reasoning rather than only names or numbers.",
                "Remain independently assessable for the declared disciplinary Skill.",
            ),
            language_code="fr-FR",
        )


def required_slots(skill: ActiveSkillCoverage) -> tuple[ContentSlot, ...]:
    """Return the deliberately non-cartesian pedagogical target for one Skill."""
    slots = [
        ContentSlot(CanonicalContentType.PRACTICE, 2),
        ContentSlot(CanonicalContentType.ASSESSMENT, 2),
    ]
    if skill.target.subject_code in {"MATHEMATICS", "FRENCH"}:
        slots.extend(
            (
                ContentSlot(CanonicalContentType.PRACTICE, 1),
                ContentSlot(CanonicalContentType.PRACTICE, 3),
            )
        )
    if skill.target.subject_code in {"MATHEMATICS", "FRENCH"} and (
        skill.prerequisites or skill.downstream_dependencies
    ):
        slots.extend(
            (
                ContentSlot(CanonicalContentType.DIAGNOSTIC, 2),
                ContentSlot(CanonicalContentType.REMEDIATION, 1),
            )
        )
    return tuple(slots)


def priority_for(skill: ActiveSkillCoverage) -> int:
    if skill.target.grade_code == "FR-3E" and skill.target.subject_code in {"MATHEMATICS", "FRENCH"}:
        return 1
    if skill.target.grade_code == "FR-4E" and skill.target.subject_code in {"MATHEMATICS", "FRENCH"}:
        return 2
    return 3 if skill.target.grade_code == "FR-3E" else 4


def coverage_gaps(rows: tuple[ActiveSkillCoverage, ...]) -> tuple[CoverageGap, ...]:
    gaps = [
        CoverageGap(skill, slot, priority_for(skill))
        for skill in rows
        for slot in required_slots(skill)
        if skill.count(slot) == 0
    ]
    return tuple(
        sorted(
            gaps,
            key=lambda gap: (
                gap.priority,
                gap.skill.target.subject_code,
                gap.skill.target.chapter_code,
                gap.skill.target.primary_skill_code,
                gap.slot.content_type.value,
                gap.slot.difficulty,
            ),
        )
    )


def coverage_status(skill: ActiveSkillCoverage) -> str:
    required = required_slots(skill)
    approved = sum(bool(skill.approved.get(slot, 0)) for slot in required)
    covered = sum(skill.count(slot) > 0 for slot in required)
    if approved == len(required):
        return "APPROVED"
    if covered == len(required):
        return "TARGET_COMPLETE"
    if covered:
        return "PARTIAL"
    return "MISSING"
