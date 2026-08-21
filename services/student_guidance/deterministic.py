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
    "L'aide enrichie est temporairement indisponible. "
    "Les conseils de base restent accessibles."
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


def homework_during(
    help_level: int,
    *,
    statement: str | None = None,
    hint_text: str | None = None,
    notion_reminder: str | None = None,
    method_outline: str | None = None,
) -> HomeworkGuidanceResponse:
    """Progressive useful aids: indice → notion → démarche (no full solution before level 6)."""
    level = max(1, min(7, int(help_level)))
    excerpt = " ".join((statement or "").split())
    if len(excerpt) > 120:
        excerpt = excerpt[:117].rstrip() + "…"

    if level == 1:
        message = (
            "Indice utile : repère dans la consigne ce que l'on te demande exactement "
            "(calculer, simplifier, justifier…)."
        )
        if excerpt:
            message += f" Consigne : « {excerpt} »."
    elif level == 2:
        message = hint_text or (
            "Indice utile : isole les données numériques et les unités, puis reformule la question en une phrase courte."
        )
    elif level == 3:
        message = notion_reminder or (
            "Rappel de notion : quelle règle ou définition du chapitre s'applique ici ? "
            "Écris-la avant de calculer."
        )
    elif level == 4:
        message = method_outline or (
            "Démarche : (1) note les données, (2) choisis la méthode, (3) calcule une étape, "
            "(4) vérifie l'ordre de grandeur."
        )
    elif level == 5:
        message = (
            "Piste guidée : avance une seule étape maintenant, sans viser la réponse finale. "
            "Si tu bloques, passe à l'aide suivante."
        )
    elif level == 6:
        message = (
            "Solution guidée (sans spoiler complet) : décompose le problème en sous-questions "
            "et valide chaque résultat intermédiaire."
        )
    else:
        message = (
            "Corrigé expliqué : tu peux consulter la correction après avoir tenté une réponse, "
            "ou si la politique du devoir l'autorise."
        )

    return HomeworkGuidanceResponse(
        source=GuidanceSource.DETERMINISTIC,
        phase="DURING",
        message=message,
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
