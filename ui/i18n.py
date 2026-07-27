"""Central French presentation labels for stable technical values."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

DEFAULT_LOCALE = "fr-FR"
DEFAULT_LANGUAGE = "Français"

LABELS: dict[str, str] = {
    "skill": "Compétence",
    "subskill": "Sous-compétence",
    "subject": "Matière",
    "grade": "Niveau",
    "chapter": "Chapitre",
    "domain": "Domaine",
    "exercise": "Exercice",
    "question": "Question",
    "answer": "Réponse",
    "expected_answer": "Réponse attendue",
    "explanation": "Explication",
    "correction": "Correction",
    "difficulty": "Difficulté",
    "practice": "Entraînement",
    "guided_practice": "Entraînement guidé",
    "assessment": "Évaluation",
    "diagnostic": "Diagnostic",
    "remediation": "Remédiation",
    "revision": "Révision",
    "mock_exam": "Brevet blanc",
    "homework": "Devoir",
    "progress": "Progression",
    "mastery": "Maîtrise",
    "weakness": "Point à renforcer",
    "strength": "Point fort",
    "recommendation": "Recommandation",
    "learning_objective": "Objectif d'apprentissage",
    "easy": "Facile",
    "medium": "Intermédiaire",
    "hard": "Difficile",
    "draft": "Brouillon",
    "review": "En révision",
    "approved": "Approuvé",
    "rejected": "Rejeté",
    "archived": "Archivé",
    "pending": "En attente",
    "enabled": "Activé",
    "disabled": "Désactivé",
    "ready": "Prêt",
    "running": "En cours",
    "paused": "En pause",
    "completed": "Terminé",
    "abandoned": "Arrêté",
    "pass": "Conforme",
    "keep_for_review": "Maintenir en révision",
    "approve": "Approuver",
    "reject": "Rejeter",
    "in_review": "En cours de révision",
    "skipped": "Ignoré pour cette session",
    "fragile": "Fragile",
    "not_started": "Non commencé",
    "improving": "En progression",
    "stable": "Stable",
}

SUBJECT_LABELS: dict[str, str] = {
    "MATHEMATICS": "Mathématiques",
    "FRENCH": "Français",
    "ENGLISH": "Anglais",
    "SPANISH": "Espagnol",
    "HISTORY": "Histoire",
    "GEOGRAPHY": "Géographie",
    "HISTORY_GEOGRAPHY": "Histoire-Géographie",
    "EMC": "EMC",
    "PHYSICS_CHEMISTRY": "Physique-Chimie",
    "SVT": "SVT",
}

GRADE_LABELS: dict[str, str] = {
    "FR-CM1": "CM1",
    "FR-CM2": "CM2",
    "FR-6E": "6e",
    "FR-5E": "5e",
    "FR-4E": "4e",
    "FR-3E": "3e",
}

PRIORITY_LABELS_FR: dict[str, str] = {
    "TIER1_IMMEDIATE": "🔴 P1 — Validation prioritaire : compétence complète immédiatement",
    "TIER1_PLAN": "🟠 P2 — Plan prioritaire : contribue à compléter une compétence",
    "TIER2_PROGRESS": "🟡 P3 — Progression : améliore une compétence partiellement couverte",
    "COVERAGE_USEFUL": "🔵 P4 — Couverture utile",
    "NO_TIER_IMPACT": "⚪ P5 — Sans impact immédiat sur la couverture",
    "HUMAN_REVIEW": "🟣 Revue pédagogique",
}


def label(value: Any, *, fallback: str | None = None) -> str:
    """Return a stable French UI label without mutating the technical value."""
    text = str(value)
    key = text.strip().casefold().replace("-", "_").replace(" ", "_")
    return LABELS.get(key, fallback if fallback is not None else text)


def subject_label(value: Any) -> str:
    text = str(value)
    return SUBJECT_LABELS.get(text.upper().replace("-", "_"), text)


def grade_label(value: Any) -> str:
    text = str(value)
    return GRADE_LABELS.get(text.upper(), text)


def status_label(value: Any, *, feminine: bool = False) -> str:
    translated = label(value)
    if feminine:
        return {
            "Prêt": "Prête",
            "Terminé": "Terminée",
            "Arrêté": "Arrêtée",
        }.get(translated, translated)
    return translated


def tier_label(value: int) -> str:
    return {
        1: "Compétence complète (Tier 1)",
        2: "Compétence partiellement couverte (Tier 2)",
        3: "Compétence non couverte (Tier 3)",
    }.get(value, f"Niveau de couverture {value}")


def format_date_fr(value: date | datetime) -> str:
    return value.strftime("%d/%m/%Y")


def format_number_fr(value: float, decimals: int = 0) -> str:
    rendered = f"{value:,.{decimals}f}"
    return rendered.replace(",", "\u00a0").replace(".", ",")


def format_duration(minutes: int) -> str:
    hours, remaining = divmod(minutes, 60)
    if not hours:
        return f"{remaining} min"
    return f"{hours} h" if not remaining else f"{hours} h {remaining} min"
