"""Heuristics for student answer input UX (multiline + notation guides)."""

from __future__ import annotations

_ALWAYS_MULTILINE = frozenset(
    {
        "LONG_TEXT",
        "LONGTEXT",
        "MULTI_LINE",
        "MULTILINE",
        "ESSAY",
        "PARAGRAPH",
        "OPEN_QUESTION",
        "TEXT",
        "SHORT_TEXT",
        "SHORTTEXT",
        "STRING",
        "FREE_TEXT",
        "FREETEXT",
        "INTEGER",
        "NUMBER",
        "DECIMAL",
        "FRACTION",
        "FORMULA",
    }
)
_MULTILINE_KEYWORDS = (
    "plusieurs lignes",
    "ligne 1",
    "ligne 2",
    "explique",
    "rédige",
    "rédiger",
    "justifie",
    "justifier",
    "développe",
    "développer",
    "montre que",
    "prouve",
    "étape par étape",
    "étapes",
)
_SCIENTIFIC_KEYWORDS = (
    "notation scientifique",
    "puissance de 10",
    "×10",
    "x10^",
    "10^",
    "exposant",
    "scientifique",
)

SCIENTIFIC_NOTATION_GUIDE = (
    "Notation attendue au clavier : utilise le point ou la virgule pour les décimales "
    "(ex. `3.14` ou `3,14`), et pour une puissance de 10 écris `a × 10^n` ou `a e n` "
    "(ex. `2.5 × 10^3` ou `2.5e3`)."
)

_DEFAULT_NOTATION_GUIDE = (
    "Tu peux écrire ta réponse sur plusieurs lignes. "
    "Indique clairement le résultat final (nombre, expression ou phrase). "
    "Les décimales s'écrivent avec une virgule ou un point (ex. `3,5` ou `3.5`). "
    "Les unités sont acceptées (ex. `10 cm`, `12,50 €`)."
)


def prefers_multiline_answer(response_type: str, statement: str = "", instructions: str = "") -> bool:
    """Prefer multi-line input for almost all free-text / numeric answers."""
    del statement, instructions
    normalized = (response_type or "").strip().upper().replace("-", "_").replace(" ", "_")
    return normalized not in {"MCQ_SINGLE", "MCQ_MULTI", "SINGLE_CHOICE", "MULTIPLE_CHOICE", "BOOLEAN"}


def needs_scientific_notation_guide(statement: str = "", instructions: str = "", context: str = "") -> bool:
    blob = f"{statement} {instructions} {context}".casefold()
    return any(token in blob for token in _SCIENTIFIC_KEYWORDS)


def notation_guide_for_response_type(
    response_type: str,
    *,
    statement: str = "",
    instructions: str = "",
    context: str = "",
) -> str:
    """Explicit expected notation shown at the start of an exercise."""
    normalized = (response_type or "").strip().upper().replace("-", "_").replace(" ", "_")
    if needs_scientific_notation_guide(statement, instructions, context):
        return SCIENTIFIC_NOTATION_GUIDE
    if normalized in {"INTEGER", "NUMBER", "DECIMAL"}:
        return (
            "Notation attendue : un nombre. Tu peux utiliser la virgule ou le point "
            "(ex. `12` ou `3,5`). Les unités sont acceptées si la consigne le demande."
        )
    if normalized == "FRACTION":
        return "Notation attendue : une fraction (ex. `1/2` ou `3/4`) ou un décimal équivalent."
    if normalized == "FORMULA":
        return (
            "Notation attendue : une expression mathématique en texte "
            "(ex. `2x+7`, `a^2`, `V=a^3`). Évite les exposants typographiques."
        )
    if normalized in {"MCQ_SINGLE", "SINGLE_CHOICE", "MCQ_MULTI", "MULTIPLE_CHOICE", "BOOLEAN"}:
        return "Choisis la ou les réponses proposées."
    return _DEFAULT_NOTATION_GUIDE
