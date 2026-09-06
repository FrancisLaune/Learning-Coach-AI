"""LCAI-0031 — Brevet exam templates (format d'épreuve, not homework)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BrevetExamMode(StrEnum):
    OFFICIAL_ARCHIVE = "OFFICIAL_ARCHIVE"
    BREVET_STYLE = "BREVET_STYLE"
    ADAPTIVE_BREVET = "ADAPTIVE_BREVET"
    MOCK_EXAM = "MOCK_EXAM"


class BrevetExamCode(StrEnum):
    FRENCH = "FRENCH_WRITTEN"
    MATHEMATICS = "MATHEMATICS_WRITTEN"
    HISTORY_GEOGRAPHY_EMC = "HISTORY_GEOGRAPHY_EMC_WRITTEN"
    SCIENCES = "SCIENCES_WRITTEN"
    ORAL = "ORAL"


@dataclass(frozen=True, slots=True)
class BrevetExamSection:
    code: str
    label: str
    duration_minutes: int
    max_points: float
    calculator_allowed: bool | None
    question_types: tuple[str, ...]
    indicative_question_count: int
    notes: str = ""


@dataclass(frozen=True, slots=True)
class BrevetExamTemplate:
    exam_code: BrevetExamCode
    label: str
    subject_codes: tuple[str, ...]
    duration_minutes: int
    coefficient: float
    sections: tuple[BrevetExamSection, ...]
    score_out_of: float = 20.0
    correction_policy: str = "AFTER_SUBMISSION"
    allows_immediate_hints: bool = False

    @property
    def section_codes(self) -> tuple[str, ...]:
        return tuple(section.code for section in self.sections)


def mathematics_template() -> BrevetExamTemplate:
    return BrevetExamTemplate(
        exam_code=BrevetExamCode.MATHEMATICS,
        label="Mathématiques — écrit",
        subject_codes=("MATHEMATICS",),
        duration_minutes=120,
        coefficient=2.0,
        sections=(
            BrevetExamSection(
                code="AUTOMATISMS",
                label="Automatismes",
                duration_minutes=20,
                max_points=6.0,
                calculator_allowed=False,
                question_types=("short_numeric", "automatism", "mental_calc"),
                indicative_question_count=8,
                notes="Sans calculatrice — vitesse et précision.",
            ),
            BrevetExamSection(
                code="REASONING",
                label="Raisonnement et résolution de problèmes",
                duration_minutes=100,
                max_points=14.0,
                calculator_allowed=True,
                question_types=("problem", "reasoning", "justification", "multi_step"),
                indicative_question_count=5,
                notes="Justification et rédaction exigées — pas uniquement du QCM.",
            ),
        ),
    )


def french_template() -> BrevetExamTemplate:
    return BrevetExamTemplate(
        exam_code=BrevetExamCode.FRENCH,
        label="Français — écrit",
        subject_codes=("FRENCH",),
        duration_minutes=180,
        coefficient=2.0,
        sections=(
            BrevetExamSection(
                code="COMPREHENSION",
                label="Compréhension et interprétation",
                duration_minutes=70,
                max_points=10.0,
                calculator_allowed=None,
                question_types=("comprehension", "interpretation", "short_text"),
                indicative_question_count=8,
            ),
            BrevetExamSection(
                code="GRAMMAR",
                label="Grammaire et compétences linguistiques",
                duration_minutes=30,
                max_points=4.0,
                calculator_allowed=None,
                question_types=("grammar", "language"),
                indicative_question_count=6,
            ),
            BrevetExamSection(
                code="DICTATION",
                label="Dictée",
                duration_minutes=20,
                max_points=2.0,
                calculator_allowed=None,
                question_types=("dictation",),
                indicative_question_count=1,
            ),
            BrevetExamSection(
                code="WRITING",
                label="Rédaction",
                duration_minutes=60,
                max_points=4.0,
                calculator_allowed=None,
                question_types=("essay", "long_text"),
                indicative_question_count=1,
                notes="Évaluation structurée / IA — pas de comparaison exacte de chaîne.",
            ),
        ),
    )


def history_geography_emc_template() -> BrevetExamTemplate:
    return BrevetExamTemplate(
        exam_code=BrevetExamCode.HISTORY_GEOGRAPHY_EMC,
        label="Histoire-Géographie-EMC — écrit",
        subject_codes=("HISTORY", "GEOGRAPHY", "EMC"),
        duration_minutes=120,
        coefficient=2.0,
        sections=(
            BrevetExamSection(
                code="HISTORY_GEOGRAPHY",
                label="Histoire-Géographie",
                duration_minutes=90,
                max_points=15.0,
                calculator_allowed=None,
                question_types=("document_analysis", "landmarks", "constructed_response"),
                indicative_question_count=6,
                notes="Coefficient HG 1,5 au sein de l'épreuve globale.",
            ),
            BrevetExamSection(
                code="EMC",
                label="EMC",
                duration_minutes=30,
                max_points=5.0,
                calculator_allowed=None,
                question_types=("argumentation", "civics", "constructed_response"),
                indicative_question_count=3,
                notes="Coefficient EMC 0,5.",
            ),
        ),
    )


def sciences_template(
    selected_disciplines: tuple[str, str] = ("PHYSICS_CHEMISTRY", "SVT"),
) -> BrevetExamTemplate:
    left, right = selected_disciplines
    return BrevetExamTemplate(
        exam_code=BrevetExamCode.SCIENCES,
        label="Sciences — écrit",
        subject_codes=(left, right),
        duration_minutes=60,
        coefficient=2.0,
        sections=(
            BrevetExamSection(
                code=f"SCIENCE_{left}",
                label=left.replace("_", "-").title(),
                duration_minutes=30,
                max_points=10.0,
                calculator_allowed=True,
                question_types=("document_analysis", "graph", "scientific_reasoning", "protocol"),
                indicative_question_count=4,
            ),
            BrevetExamSection(
                code=f"SCIENCE_{right}",
                label=right.replace("_", "-").title(),
                duration_minutes=30,
                max_points=10.0,
                calculator_allowed=True,
                question_types=("document_analysis", "graph", "scientific_reasoning", "protocol"),
                indicative_question_count=4,
            ),
        ),
    )


def oral_template() -> BrevetExamTemplate:
    return BrevetExamTemplate(
        exam_code=BrevetExamCode.ORAL,
        label="Oral du DNB — soutenance",
        subject_codes=("ORAL",),
        duration_minutes=15,
        coefficient=0.0,
        sections=(
            BrevetExamSection(
                code="PRESENTATION",
                label="Présentation",
                duration_minutes=5,
                max_points=10.0,
                calculator_allowed=None,
                question_types=("oral_presentation",),
                indicative_question_count=1,
            ),
            BrevetExamSection(
                code="JURY",
                label="Échange avec le jury",
                duration_minutes=10,
                max_points=10.0,
                calculator_allowed=None,
                question_types=("oral_questions", "argumentation"),
                indicative_question_count=5,
            ),
        ),
    )


_TEMPLATES: dict[BrevetExamCode, BrevetExamTemplate] = {
    BrevetExamCode.FRENCH: french_template(),
    BrevetExamCode.MATHEMATICS: mathematics_template(),
    BrevetExamCode.HISTORY_GEOGRAPHY_EMC: history_geography_emc_template(),
    BrevetExamCode.SCIENCES: sciences_template(),
    BrevetExamCode.ORAL: oral_template(),
}


def template_for(exam_code: BrevetExamCode | str) -> BrevetExamTemplate:
    code = BrevetExamCode(str(exam_code))
    if code is BrevetExamCode.SCIENCES:
        return sciences_template()
    return _TEMPLATES[code]


def all_written_templates() -> tuple[BrevetExamTemplate, ...]:
    return (
        french_template(),
        mathematics_template(),
        history_geography_emc_template(),
        sciences_template(),
    )
