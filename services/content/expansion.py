"""Coverage planning primitives for the controlled LCAI-0012C expansion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.content.factory import (
    CanonicalContentType,
    ContentGenerationRequest,
    CurriculumTarget,
    PedagogicalIntent,
)

TARGET_GRADES = ("FR-4E", "FR-3E")
GUIDED_PRACTICE_TYPES = frozenset({"practice", "guided_practice"})


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

    def request(self, *, extra_constraints: tuple[str, ...] = ()) -> ContentGenerationRequest:
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
                *extra_constraints,
            ),
            language_code="fr-FR",
        )


def slot_index_key(skill_code: str, slot: ContentSlot) -> tuple[str, str, int]:
    """Normalize a production slot to the quality-audit lookup key."""
    content_type = slot.content_type.value
    if content_type in GUIDED_PRACTICE_TYPES:
        content_type = "practice"
    return (skill_code, content_type, slot.difficulty)


def build_slot_quality_index(results: list[dict[str, Any]]) -> dict[tuple[str, str, int], list[dict[str, Any]]]:
    """Group quality-audit records by Skill and canonical production slot."""
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for record in results:
        content_type = str(record.get("content_type", ""))
        if content_type not in {"practice", "assessment", "guided_practice"}:
            continue
        if content_type in GUIDED_PRACTICE_TYPES:
            content_type = "practice"
        key = (str(record["skill"]), content_type, int(record["difficulty"]))
        grouped.setdefault(key, []).append(record)
    return grouped


def is_usable_quality_record(record: dict[str, Any]) -> bool:
    """Return True when a Draft remains a corrective-generation blocker."""
    if str(record.get("decision")) == "REJECT":
        return False
    gates = record.get("hard_gates") or {}
    required = (
        "structural_validity",
        "answer_correctness",
        "skill_alignment",
        "executability",
        "duplicate_safety",
    )
    return all(bool(gates.get(name)) for name in required)


def slot_has_usable_candidate(
    skill: ActiveSkillCoverage,
    slot: ContentSlot,
    quality_index: dict[tuple[str, str, int], list[dict[str, Any]]],
) -> bool:
    """Approved production or at least one audited usable Draft blocks replacement."""
    if skill.approved.get(slot, 0) > 0:
        return True
    if skill.draft.get(slot, 0) == 0:
        return False
    records = quality_index.get(slot_index_key(skill.target.primary_skill_code, slot), ())
    if not records:
        return True
    return any(is_usable_quality_record(record) for record in records)


def generation_gaps(
    rows: tuple[ActiveSkillCoverage, ...],
    quality_index: dict[tuple[str, str, int], list[dict[str, Any]]],
) -> tuple[CoverageGap, ...]:
    """Return slots that still need replacement generation after unusable Drafts."""
    gaps = [
        CoverageGap(skill, slot, priority_for(skill))
        for skill in rows
        for slot in required_slots(skill)
        if not slot_has_usable_candidate(skill, slot, quality_index)
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
