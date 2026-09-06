"""LCAI-0031 Phase 6 — navigation cible Objectif Brevet (§33)."""

from __future__ import annotations

# Student primary nav (ticket §33)
STUDENT_PAGES: tuple[str, ...] = (
    "Accueil",
    "Mon programme",
    "Réviser",
    "S'entraîner",
    "Devoir personnalisé",
    "Sujets Brevet",
    "Brevets blancs",
    "Oral",
    "Mes résultats",
    "Coach Brevet",
)

# Legacy labels → §33 (session aliases + deferred navigation)
STUDENT_PAGE_ALIASES: dict[str, str] = {
    "Tableau de bord": "Accueil",
    "Accueil": "Accueil",
    "Ma séance": "S'entraîner",
    "Ma séance IA": "S'entraîner",
    "Devoirs": "Devoir personnalisé",
    "Révision": "Réviser",
    "Mes progrès": "Mon programme",
    "Mon planning": "Mon programme",
    "Profil": "Accueil",
    "Mon professeur IA": "Coach Brevet",
    "Professeur IA": "Coach Brevet",
}

PARENT_PAGES: tuple[str, ...] = (
    "Mes enfants",
    "Vue générale",
    "Progression",
    "Résultats",
    "Préparation Brevet",
    "Contrôle continu",
    "Alertes & recommandations",
    "Devoirs",
)

PARENT_PAGE_ALIASES: dict[str, str] = {
    "Tableau de bord": "Vue générale",
    "Recommandations": "Alertes & recommandations",
    "Programme": "Préparation Brevet",
    "Planning": "Résultats",
    "Profil élève": "Progression",
}


def resolve_student_page(page: str | None) -> str | None:
    if page is None:
        return None
    return STUDENT_PAGE_ALIASES.get(page, page)


def resolve_parent_page(page: str | None) -> str | None:
    if page is None:
        return None
    return PARENT_PAGE_ALIASES.get(page, page)
