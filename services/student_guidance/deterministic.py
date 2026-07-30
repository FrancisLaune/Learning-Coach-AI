"""Deterministic guidance fallbacks for LCAI-0020."""

from __future__ import annotations

from application.dto.student_guidance import (
    GuidanceSource,
    HomeworkGuidanceResponse,
    ResultExplanationContext,
    RevisionGuidanceContext,
    RevisionPriority,
    StudentHomeContext,
    WelcomeGuidance,
)

DEGRADED_NOTICE = (
    "Le Professeur IA est temporairement indisponible. "
    "Les analyses et recommandations de base restent accessibles."
)


def build_deterministic_welcome(context: StudentHomeContext, *, degraded: bool = False) -> WelcomeGuidance:
    if context.homework_overdue:
        hw = context.homework_overdue[0]
        primary = f"Terminer le devoir en retard : {hw.subject_label}"
    elif context.homework_todo:
        hw = context.homework_todo[0]
        primary = f"Commencer le devoir : {hw.subject_label}"
    elif context.revision_priorities:
        primary = f"Réviser : {context.revision_priorities[0].skill_label}"
    else:
        primary = "Consulter ton tableau de bord et lancer une courte activité."

    secondary: list[str] = []
    if context.homework_todo and len(context.homework_todo) > 1:
        secondary.append(f"Devoir suivant : {context.homework_todo[1].subject_label}")
    if context.fragile_skills:
        secondary.append(f"Compétence fragile : {context.fragile_skills[0].label}")

    greeting = (
        f"Bonjour {context.display_name}. "
        f"Priorité du jour : {primary}. "
        f"Objectif : {context.objective}."
    )
    if context.fragile_skills:
        greeting += f" Point de vigilance : {context.fragile_skills[0].label}."
    return WelcomeGuidance(
        source=GuidanceSource.DETERMINISTIC,
        greeting=greeting,
        primary_action=primary,
        secondary_actions=tuple(secondary[:2]),
        mission_label=primary,
        degraded_notice=DEGRADED_NOTICE if degraded else "",
    )


def build_ai_welcome(context: StudentHomeContext, ai_message: str) -> WelcomeGuidance:
    primary = build_deterministic_welcome(context).primary_action
    return WelcomeGuidance(
        source=GuidanceSource.AI,
        greeting=ai_message.strip(),
        primary_action=primary,
        secondary_actions=build_deterministic_welcome(context).secondary_actions,
        mission_label=primary,
    )


def homework_before(context_subject: str, exercise_count: int, minutes: int | None) -> str:
    duration = f"{minutes} minutes" if minutes else "la durée indiquée"
    return (
        f"Objectif : réaliser {exercise_count} exercice(s) en {context_subject}. "
        f"Durée estimée : {duration}. "
        "Conseil : lis chaque consigne entièrement avant de commencer et note ta méthode."
    )


def homework_during(help_level: int) -> HomeworkGuidanceResponse:
    messages = {
        1: "Relis la consigne et souligne les mots importants.",
        2: "Rappelle-toi la notion vue en cours sur ce chapitre.",
        3: "Cherche un indice : quelle opération ou quelle règle s'applique ici ?",
        4: "Commence par la première étape, sans viser la réponse finale.",
        5: "Voici une démarche analogue : identifie les données, choisis la méthode, vérifie l'unité.",
        6: "Solution guidée : avance étape par étape et vérifie chaque résultat intermédiaire.",
        7: "Consulte la correction uniquement si la politique du devoir l'autorise.",
    }
    level = max(1, min(7, int(help_level)))
    return HomeworkGuidanceResponse(
        source=GuidanceSource.DETERMINISTIC,
        phase="DURING",
        message=messages[level],
        help_level=level,
        suggested_actions=("Indice suivant", "Retour au devoir"),
    )


def explain_result(context: ResultExplanationContext) -> str:
    parts = [context.score_summary]
    if context.strengths:
        parts.append("Points forts : " + ", ".join(context.strengths) + ".")
    if context.weaknesses:
        parts.append("Points à consolider : " + ", ".join(context.weaknesses) + ".")
    parts.append(context.deterministic_recommendation)
    return " ".join(parts)


def revision_guidance(priority: RevisionPriority, *, source: GuidanceSource, message: str, degraded: bool) -> RevisionGuidanceContext:
    return RevisionGuidanceContext(
        priority=priority,
        source=source,
        message=message,
        degraded_notice=DEGRADED_NOTICE if degraded else "",
    )
