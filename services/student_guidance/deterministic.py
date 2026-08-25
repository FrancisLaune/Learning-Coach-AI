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


def _formula_help_from_statement(statement: str | None) -> str | None:
    text = (statement or "").casefold()
    if not text:
        return None
    if "volume" in text and "cube" in text:
        return (
            "Formule utile : volume d'un cube V = a³ "
            "(a = longueur d'une arête). Multiplie a × a × a, puis précise l'unité (ex. cm³)."
        )
    if "volume" in text and ("pavé" in text or "parallélépipède" in text):
        return "Formule utile : volume d'un pavé V = L × l × h. Multiplie longueur, largeur et hauteur."
    if "aire" in text and "carré" in text:
        return "Formule utile : aire d'un carré A = a² (a = côté)."
    if "aire" in text and "rectangle" in text:
        return "Formule utile : aire d'un rectangle A = L × l."
    if "aire" in text and "triangle" in text:
        return "Formule utile : aire d'un triangle A = (base × hauteur) / 2."
    if "périmètre" in text and "cercle" in text:
        return "Formule utile : périmètre d'un cercle P = 2 × π × r (ou π × diamètre)."
    if "pythagore" in text or ("triangle rectangle" in text and ("hypoténuse" in text or "côté" in text)):
        return "Formule utile (Pythagore) : a² + b² = c², avec c l'hypoténuse."
    if "puissance" in text or "exposant" in text:
        return (
            "Rappel : une puissance s'écrit base^exposant. "
            "La base est le nombre multiplié ; l'exposant est le nombre de facteurs. "
            "Au clavier, écris par exemple `2^5` (pas 2⁵)."
        )
    if "convertir" in text or "conversion" in text or ("litre" in text and "centilitre" in text):
        return (
            "Rappel conversions de volumes : 1 L = 100 cL = 1000 mL. "
            "Pour passer des litres aux centilitres, multiplie par 100."
        )
    if "moyenne" in text:
        return "Formule utile : moyenne = somme des valeurs / nombre de valeurs."
    if "pourcentage" in text or "%" in text:
        return "Méthode utile : pourcentage = (partie / total) × 100."
    if "équation" in text or "résoudre" in text:
        return "Méthode utile : isole l'inconnue en faisant la même opération de chaque côté de l'égalité."
    return None


def homework_during(
    help_level: int = 1,
    *,
    statement: str | None = None,
    hint_text: str | None = None,
    notion_reminder: str | None = None,
    method_outline: str | None = None,
) -> HomeworkGuidanceResponse:
    """Single explicit help: formula/method + clear explanation (no progressive levels)."""
    del help_level
    parts: list[str] = []
    formula = _formula_help_from_statement(statement)
    if formula:
        parts.append(formula)
    if hint_text and hint_text.strip():
        parts.append(f"Aide détaillée : {hint_text.strip()}")
    if notion_reminder and notion_reminder.strip():
        parts.append(f"Rappel de notion : {notion_reminder.strip()}")
    if method_outline and method_outline.strip():
        parts.append(f"Démarche : {method_outline.strip()}")
    if not parts:
        excerpt = " ".join((statement or "").split())
        if len(excerpt) > 160:
            excerpt = excerpt[:157].rstrip() + "…"
        parts.append(
            "Aide détaillée : repère ce que l'on te demande, note les données utiles, "
            "applique la règle du chapitre, puis écris clairement le résultat final."
        )
        if excerpt:
            parts.append(f"Consigne : « {excerpt} ».")
    message = " ".join(parts)
    return HomeworkGuidanceResponse(
        source=GuidanceSource.DETERMINISTIC,
        phase="DURING",
        message=message,
        help_level=1,
        suggested_actions=("Relire la consigne", "Retour au devoir"),
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
