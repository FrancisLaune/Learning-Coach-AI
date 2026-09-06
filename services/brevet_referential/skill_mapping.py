"""LCAI-0035 — conservative skill mapping for official archive questions."""

from __future__ import annotations

import re
from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore

# Keyword → skill code fragments (matched against skills.code / skills.name).
KEYWORD_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("pythagore", ("PYTHAGORE",)),
    ("thalès", ("THALES",)),
    ("thales", ("THALES",)),
    ("équation", ("EQUATION",)),
    ("equation", ("EQUATION",)),
    ("fonction", ("FONCTION",)),
    ("probabilit", ("PROBABILIT",)),
    ("statisti", ("STATISTI",)),
    ("proportionn", ("PROPORTION",)),
    ("pourcentage", ("POURCENT",)),
    ("fraction", ("FRACTION",)),
    ("puissance", ("PUISSANCE",)),
    ("volume", ("VOLUME", "GEOMETR")),
    ("aire", ("AIRE", "GEOMETR")),
    ("triangle", ("GEOMETR", "TRIANGLE")),
    ("algorithm", ("ALGORITHM", "SCRATCH", "PROGRAM")),
    ("scratch", ("ALGORITHM", "SCRATCH")),
    ("électri", ("ELECTRIC",)),
    ("electric", ("ELECTRIC",)),
    ("énergie", ("ENERGIE",)),
    ("energie", ("ENERGIE",)),
    ("séisme", ("SEISME", "TECTON", "SVT")),
    ("seisme", ("SEISME", "TECTON")),
    ("volcan", ("VOLCAN", "SVT")),
    ("adn", ("ADN", "GENET")),
    ("dictée", ("ORTHOGRAPHE", "DICTEE", "ACCORD")),
    ("conjugaison", ("CONJUGAISON",)),
    ("grammaire", ("GRAMMAIRE", "ACCORD")),
    ("rédaction", ("EXPRESSION", "REDACTION")),
    ("vichy", ("GUERRE", "WW2", "SECONDE_GUERRE")),
    ("résistance", ("GUERRE", "RESISTANCE")),
    ("citoyenneté", ("EMC", "CITOYEN")),
]


def list_skills_for_subject(store: BrevetContentStore, subject_code: str) -> list[dict[str, Any]]:
    rows = store.fetchall(
        """
        SELECT sk.skill_id, sk.code, sk.name, sk.brevet_importance, ch.chapter_id, ch.name
        FROM skills sk
        JOIN chapters ch ON ch.chapter_id = sk.chapter_id
        JOIN curriculum_domains cd ON cd.domain_id = ch.domain_id
        JOIN subjects sub ON sub.subject_id = cd.subject_id
        WHERE sub.code = ? AND sk.active = TRUE
        """,
        [subject_code],
    )
    return [
        {
            "skill_id": int(r[0]),
            "code": str(r[1]),
            "name": str(r[2]),
            "importance": str(r[3]),
            "chapter_id": int(r[4]),
            "chapter": str(r[5]),
        }
        for r in rows
    ]


def map_skills_for_statement(
    store: BrevetContentStore,
    *,
    subject_code: str,
    statement: str,
    max_skills: int = 2,
) -> list[dict[str, Any]]:
    """Return best-effort skill matches; empty => REVIEW mapping required."""
    skills = list_skills_for_subject(store, subject_code)
    if not skills:
        # HG-EMC archive may map to HISTORY subject_code while text spans geo/emc.
        if subject_code == "HISTORY":
            for alt in ("GEOGRAPHY", "EMC"):
                skills.extend(list_skills_for_subject(store, alt))
        if subject_code == "PHYSICS_CHEMISTRY":
            for alt in ("SVT", "TECHNOLOGY"):
                skills.extend(list_skills_for_subject(store, alt))
    text = (statement or "").casefold()
    scored: list[tuple[float, dict[str, Any]]] = []
    for skill in skills:
        score = 0.0
        code_l = skill["code"].casefold()
        name_l = skill["name"].casefold()
        if name_l and name_l in text:
            score += 3.0
        for token in re.split(r"[_\s]+", code_l):
            if len(token) >= 5 and token in text:
                score += 1.5
        for keyword, fragments in KEYWORD_RULES:
            if keyword in text and any(frag.casefold() in code_l or frag.casefold() in name_l for frag in fragments):
                score += 2.0
        if score > 0:
            scored.append((score, skill))
    scored.sort(key=lambda item: (-item[0], item[1]["code"]))
    return [item[1] for item in scored[:max_skills]]


def curriculum_2027_compatibility(
    *,
    year: int | None,
    subject_group: str,
    mapped_skills: list[dict[str, Any]],
) -> tuple[str, str]:
    """Conservative compatibility — uncertain mappings stay REVIEW."""
    if not mapped_skills:
        return "REVIEW", "Aucun mapping compétence fiable; validation humaine requise."
    if year is not None and year >= 2024:
        return "REVIEW", "Sujet récent mappé automatiquement; confirmation humaine requise."
    if subject_group in {"FRENCH", "HISTORY_GEOGRAPHY_EMC"}:
        return "REVIEW", "Format littéraire/HG nécessite revue humaine de compatibilité 2027."
    return "REVIEW", "Compatibilité 2027 non confirmée automatiquement (politique LCAI-0035)."
