"""LCAI-0031 — Oral du DNB preparation / simulation model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OralStage(StrEnum):
    CHOOSE_TOPIC = "CHOOSE_TOPIC"
    PROBLEM_STATEMENT = "PROBLEM_STATEMENT"
    OUTLINE = "OUTLINE"
    SUPPORT = "SUPPORT"
    SPEECH = "SPEECH"
    REHEARSAL = "REHEARSAL"
    TIMING = "TIMING"
    JURY_SIMULATION = "JURY_SIMULATION"
    FEEDBACK = "FEEDBACK"


class JuryQuestionKind(StrEnum):
    SIMPLE = "SIMPLE"
    PRECISION = "PRECISION"
    CHALLENGING = "CHALLENGING"
    JUSTIFICATION = "JUSTIFICATION"
    PERSONAL_REFLECTION = "PERSONAL_REFLECTION"


@dataclass(frozen=True, slots=True)
class OralProjectPlan:
    title: str
    problematique: str
    outline: tuple[str, ...]
    stages: tuple[OralStage, ...]
    target_minutes: int
    evaluation_dimensions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JuryQuestion:
    kind: JuryQuestionKind
    prompt: str


def default_oral_stages() -> tuple[OralStage, ...]:
    return (
        OralStage.CHOOSE_TOPIC,
        OralStage.PROBLEM_STATEMENT,
        OralStage.OUTLINE,
        OralStage.SUPPORT,
        OralStage.SPEECH,
        OralStage.REHEARSAL,
        OralStage.TIMING,
        OralStage.JURY_SIMULATION,
        OralStage.FEEDBACK,
    )


def build_oral_project(
    *,
    title: str,
    problematique: str,
    outline: tuple[str, ...] | list[str],
    target_minutes: int = 15,
) -> OralProjectPlan:
    clean_title = title.strip()
    clean_problem = problematique.strip()
    points = tuple(item.strip() for item in outline if str(item).strip())
    if not clean_title or not clean_problem or len(points) < 2:
        raise ValueError("L'oral nécessite un titre, une problématique et au moins deux parties.")
    return OralProjectPlan(
        title=clean_title,
        problematique=clean_problem,
        outline=points,
        stages=default_oral_stages(),
        target_minutes=max(10, min(20, int(target_minutes))),
        evaluation_dimensions=(
            "structure",
            "clarté",
            "maîtrise du sujet",
            "argumentation",
            "vocabulaire",
            "gestion du temps",
            "qualité des réponses au jury",
        ),
    )


def generate_jury_questions(project: OralProjectPlan) -> tuple[JuryQuestion, ...]:
    topic = project.title
    return (
        JuryQuestion(JuryQuestionKind.SIMPLE, f"Peux-tu résumer en une phrase le sujet « {topic} » ?"),
        JuryQuestion(
            JuryQuestionKind.PRECISION,
            f"Quelle étape de ton plan développe le mieux ta problématique : « {project.problematique} » ?",
        ),
        JuryQuestion(
            JuryQuestionKind.JUSTIFICATION,
            "Pourquoi as-tu choisi cet exemple plutôt qu'un autre pour convaincre le jury ?",
        ),
        JuryQuestion(
            JuryQuestionKind.CHALLENGING,
            "Quel contre-argument pourrait faire un membre du jury, et comment y répondrais-tu ?",
        ),
        JuryQuestion(
            JuryQuestionKind.PERSONAL_REFLECTION,
            "Qu'as-tu appris personnellement en préparant ce projet ?",
        ),
    )
