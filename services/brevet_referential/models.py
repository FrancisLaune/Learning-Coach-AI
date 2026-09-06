"""Shared helpers for brevet content referential."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

SUBJECT_MODULE_MAP: dict[str, tuple[str, str]] = {
    "mathematics": ("MATHEMATICS", "Mathématiques"),
    "french": ("FRENCH", "Français"),
    "history": ("HISTORY", "Histoire"),
    "geography": ("GEOGRAPHY", "Géographie"),
    "emc": ("EMC", "EMC"),
    "physics_chemistry": ("PHYSICS_CHEMISTRY", "Physique-Chimie"),
    "svt": ("SVT", "SVT"),
    "technology": ("TECHNOLOGY", "Technologie"),
}

# Chapters treated as CRITICAL / HIGH for coverage thresholds (ticket §19).
CRITICAL_CHAPTERS: dict[str, frozenset[str]] = {
    "MATHEMATICS": frozenset(
        {"Équations", "Pythagore", "Thalès", "Fonctions", "Proportionnalité", "Fractions"}
    ),
    "FRENCH": frozenset({"Expression écrite", "Compréhension", "Accords"}),
    "HISTORY": frozenset({"Seconde Guerre mondiale", "Guerre froide", "Révolution française"}),
}

HIGH_CHAPTERS: dict[str, frozenset[str]] = {
    "MATHEMATICS": frozenset({"Probabilités", "Statistiques", "Calcul littéral", "Pourcentages"}),
    "FRENCH": frozenset({"Conjugaison", "Homophones grammaticaux", "Orthographe"}),
    "PHYSICS_CHEMISTRY": frozenset({"Électricité", "Énergie", "Forces"}),
    "SVT": frozenset({"ADN et génétique", "Immunité", "Évolution"}),
}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_only).strip("_").upper()
    return cleaned or "X"


def fingerprint_text(*parts: Any) -> str:
    payload = "||".join(str(part or "").strip().casefold() for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def difficulty_score(label: str | None) -> float:
    mapping = {"Facile": 0.3, "Moyen": 0.55, "Difficile": 0.8}
    return mapping.get(str(label or "Moyen"), 0.55)


def importance_for(subject_code: str, chapter_name: str) -> str:
    if chapter_name in CRITICAL_CHAPTERS.get(subject_code, frozenset()):
        return "CRITICAL"
    if chapter_name in HIGH_CHAPTERS.get(subject_code, frozenset()):
        return "HIGH"
    return "MEDIUM"


def coverage_threshold(importance: str) -> tuple[int, int]:
    """Return (min_total, min_archive_derived)."""
    if importance == "CRITICAL":
        return 40, 10
    if importance == "HIGH":
        return 30, 8
    return 20, 5
