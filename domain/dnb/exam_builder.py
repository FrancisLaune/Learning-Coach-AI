"""LCAI-0031 — Build Brevet-style exams (distinct from personalized homework)."""

from __future__ import annotations

from dataclasses import dataclass

from domain.dnb.exam_templates import (
    BrevetExamCode,
    BrevetExamMode,
    BrevetExamSection,
    BrevetExamTemplate,
    sciences_template,
    template_for,
)
from domain.dnb.prioritizer import SkillPriorityResult


@dataclass(frozen=True, slots=True)
class BrevetExamBlueprint:
    mode: BrevetExamMode
    template: BrevetExamTemplate
    selected_science_pair: tuple[str, str] | None
    section_plan: tuple[BrevetExamSection, ...]
    target_skill_ids: tuple[int, ...]
    rules: tuple[str, ...]
    provenance_note: str


_SCIENCE_POOL = ("PHYSICS_CHEMISTRY", "SVT", "TECHNOLOGY")


def choose_science_pair(
    priorities: tuple[SkillPriorityResult, ...] | list[SkillPriorityResult] | None = None,
    preferred: tuple[str, str] | None = None,
) -> tuple[str, str]:
    if preferred is not None:
        left, right = preferred
        if left == right or left not in _SCIENCE_POOL or right not in _SCIENCE_POOL:
            raise ValueError("La paire sciences doit contenir deux disciplines distinctes du pool DNB.")
        return left, right
    # Adaptive: prefer fragile science subjects if labels/codes appear in priorities.
    ranked: list[str] = []
    for item in priorities or ():
        label = item.label.casefold()
        for code in _SCIENCE_POOL:
            token = code.replace("_", " ").casefold()
            short = code.split("_")[0].casefold()
            if code not in ranked and (token in label or short in label):
                ranked.append(code)
        if len(ranked) >= 2:
            break
    if len(ranked) >= 2:
        return ranked[0], ranked[1]
    return "PHYSICS_CHEMISTRY", "SVT"


def build_brevet_exam(
    exam_code: BrevetExamCode | str,
    *,
    mode: BrevetExamMode | str = BrevetExamMode.BREVET_STYLE,
    science_pair: tuple[str, str] | None = None,
    priorities: tuple[SkillPriorityResult, ...] | list[SkillPriorityResult] | None = None,
    target_skill_ids: tuple[int, ...] = (),
) -> BrevetExamBlueprint:
    """Create an exam blueprint respecting DNB format.

    Does not invent official archive content. OFFICIAL_ARCHIVE mode requires
    linking an archive id later; here it only returns the format shell.
    """
    resolved_mode = BrevetExamMode(str(mode))
    code = BrevetExamCode(str(exam_code))
    pair: tuple[str, str] | None = None
    if code is BrevetExamCode.SCIENCES:
        pair = choose_science_pair(priorities, preferred=science_pair)
        template = sciences_template(pair)
    else:
        template = template_for(code)

    if resolved_mode is BrevetExamMode.ADAPTIVE_BREVET and priorities:
        skill_ids = tuple(item.skill_id for item in priorities[:8]) or target_skill_ids
    else:
        skill_ids = target_skill_ids

    rules = (
        "Pas de correction immédiate pendant l'épreuve.",
        "Pas d'indices pendant l'épreuve.",
        "Chronométrage par section lorsque pertinent.",
        "Correction et feedback après soumission.",
    )
    if code is BrevetExamCode.MATHEMATICS:
        rules = (
            *rules,
            "Partie Automatismes sans calculatrice.",
            "Partie Raisonnement distincte — pas un faux brevet 100 % QCM.",
        )
    if resolved_mode is BrevetExamMode.OFFICIAL_ARCHIVE:
        provenance = "Format officiel — le contenu doit provenir d'une annale OFFICIAL_ARCHIVE validée."
    elif resolved_mode is BrevetExamMode.MOCK_EXAM:
        provenance = "Brevet blanc — simulation d'épreuve, distincte d'une annale officielle."
    elif resolved_mode is BrevetExamMode.ADAPTIVE_BREVET:
        provenance = "Esprit d'épreuve DNB, ciblage adaptatif des compétences fragiles."
    else:
        provenance = "Sujet type Brevet — format respecté, contenu catalogue/IA validé (non officiel)."

    return BrevetExamBlueprint(
        mode=resolved_mode,
        template=template,
        selected_science_pair=pair,
        section_plan=template.sections,
        target_skill_ids=skill_ids,
        rules=rules,
        provenance_note=provenance,
    )


def build_global_mock_exam(
    *,
    include_oral: bool = False,
    science_pair: tuple[str, str] | None = None,
) -> tuple[BrevetExamBlueprint, ...]:
    """Plan a multi-épreuve Brevet blanc (écrits ± oral)."""
    exams = [
        build_brevet_exam(BrevetExamCode.FRENCH, mode=BrevetExamMode.MOCK_EXAM),
        build_brevet_exam(BrevetExamCode.HISTORY_GEOGRAPHY_EMC, mode=BrevetExamMode.MOCK_EXAM),
        build_brevet_exam(
            BrevetExamCode.SCIENCES,
            mode=BrevetExamMode.MOCK_EXAM,
            science_pair=science_pair,
        ),
        build_brevet_exam(BrevetExamCode.MATHEMATICS, mode=BrevetExamMode.MOCK_EXAM),
    ]
    if include_oral:
        exams.append(build_brevet_exam(BrevetExamCode.ORAL, mode=BrevetExamMode.MOCK_EXAM))
    return tuple(exams)
