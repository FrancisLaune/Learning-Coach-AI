"""Heuristics for student answer input UX (multiline + scientific notation)."""

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
    "Notation attendue au clavier : utilise le point pour les décimales (ex. `3.14`), "
    "et pour une puissance de 10 écris `a × 10^n` ou `a e n` "
    "(ex. `2.5 × 10^3` ou `2.5e3`). Évite les exposants en exposant typographique."
)


def prefers_multiline_answer(response_type: str, statement: str = "", instructions: str = "") -> bool:
    normalized = (response_type or "").strip().upper().replace("-", "_").replace(" ", "_")
    if normalized in _ALWAYS_MULTILINE:
        return True
    blob = f"{statement} {instructions}".casefold()
    return any(token in blob for token in _MULTILINE_KEYWORDS)


def needs_scientific_notation_guide(statement: str = "", instructions: str = "", context: str = "") -> bool:
    blob = f"{statement} {instructions} {context}".casefold()
    return any(token in blob for token in _SCIENTIFIC_KEYWORDS)
