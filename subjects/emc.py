from __future__ import annotations

from typing import Any

from subjects._helpers import generate_from_bank

SUBJECT_NAME = "EMC"
CHAPTERS = {
    "Valeurs de la République": {
        "summary": "Comprendre liberté, égalité, fraternité et laïcité.",
        "method": "Définir chaque valeur et donner un exemple.",
        "example": "La liberté s'exerce dans le respect de la loi.",
        "pitfalls": "Une valeur n'est pas un droit absolu.",
        "key_points": ["Liberté", "Égalité", "Fraternité", "Laïcité"],
    },
    "Citoyenneté": {
        "summary": "Comprendre droits, devoirs et participation.",
        "method": "Relier citoyenneté française et européenne.",
        "example": "Vote à partir de 18 ans.",
        "pitfalls": "La citoyenneté ne se limite pas au vote.",
        "key_points": ["Vote", "Engagement", "Nationalité"],
    },
    "Laïcité": {
        "summary": "Comprendre neutralité de l'État et liberté de conscience.",
        "method": "Distinguer espace public, services publics et convictions privées.",
        "example": "L'État ne privilégie aucune religion.",
        "pitfalls": "La laïcité n'interdit pas les religions.",
        "key_points": ["Neutralité", "Liberté de conscience"],
    },
    "Libertés et droits": {
        "summary": "Connaître droits fondamentaux et leurs limites.",
        "method": "Relier droit, responsabilité et loi.",
        "example": "Liberté d'expression limitée par la loi.",
        "pitfalls": "Un droit implique souvent des responsabilités.",
        "key_points": ["DDHC", "Liberté", "Responsabilité"],
    },
    "Justice": {
        "summary": "Comprendre organisation et principes de la justice.",
        "method": "Distinguer civil, pénal et administratif.",
        "example": "Présomption d'innocence.",
        "pitfalls": "Un accusé n'est pas coupable avant jugement.",
        "key_points": ["Procès équitable", "Présomption", "Peine"],
    },
    "Médias et esprit critique": {
        "summary": "Évaluer la fiabilité d'une information.",
        "method": "Identifier source, date, auteur et preuves.",
        "example": "Croiser plusieurs sources.",
        "pitfalls": "Popularité ne signifie pas fiabilité.",
        "key_points": ["Source", "Désinformation", "Vérification"],
    },
}
BANK: dict[str, list[tuple[Any, ...]]] = {
    "Valeurs de la République": [
        (
            "Quelle est la devise de la République française ?",
            "liberté égalité fraternité",
            "C'est la devise officielle.",
        )
    ],
    "Citoyenneté": [("À quel âge vote-t-on en France ?", "18", "Le droit de vote s'exerce à 18 ans.")],
    "Laïcité": [("La laïcité garantit-elle la liberté de conscience ?", "oui", "Oui, elle la protège.")],
    "Libertés et droits": [
        (
            "Quel texte de 1789 proclame les droits fondamentaux ?",
            "déclaration des droits de l'homme et du citoyen",
            "La DDHC.",
            ["ddhc"],
        )
    ],
    "Justice": [
        (
            "Le principe selon lequel une personne est innocente avant jugement est la...",
            "présomption d'innocence",
            "C'est la présomption d'innocence.",
        )
    ],
    "Médias et esprit critique": [
        (
            "Une information volontairement fausse diffusée pour tromper est de la...",
            "désinformation",
            "C'est de la désinformation.",
            ["fake news"],
        )
    ],
}


def generate_question(chapter: str, difficulty: str = "Moyen") -> dict:
    return generate_from_bank(chapter, BANK, difficulty)
