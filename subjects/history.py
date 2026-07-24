from __future__ import annotations

from typing import Any

from subjects._helpers import generate_from_bank

SUBJECT_NAME = "Histoire"
CHAPTERS = {
    "Révolution française": {
        "summary": "Comprendre la rupture politique de 1789.",
        "method": "Retenir causes, événements majeurs et conséquences.",
        "example": "Prise de la Bastille : 14 juillet 1789.",
        "pitfalls": "Ne pas réduire la Révolution à un seul événement.",
        "key_points": ["1789", "DDHC", "République"],
    },
    "Empire napoléonien": {
        "summary": "Étudier Napoléon et la diffusion des principes révolutionnaires.",
        "method": "Relier réformes intérieures et conquêtes.",
        "example": "Sacre en 1804.",
        "pitfalls": "Distinguer Consulat et Empire.",
        "key_points": ["Code civil", "1804", "Waterloo"],
    },
    "Industrialisation": {
        "summary": "Comprendre les transformations économiques et sociales.",
        "method": "Relier innovations, usines et urbanisation.",
        "example": "Machine à vapeur et charbon.",
        "pitfalls": "Ne pas oublier les conditions ouvrières.",
        "key_points": ["Usine", "Charbon", "Chemin de fer"],
    },
    "Société au XIXe siècle": {
        "summary": "Étudier bourgeoisie, ouvriers et mouvements sociaux.",
        "method": "Comparer modes de vie et revendications.",
        "example": "Développement du prolétariat.",
        "pitfalls": "Ne pas confondre classe sociale et ordre.",
        "key_points": ["Bourgeoisie", "Prolétariat", "Syndicats"],
    },
    "Colonisation": {
        "summary": "Comprendre conquêtes, domination et résistances.",
        "method": "Identifier motivations et conséquences.",
        "example": "Empire colonial français.",
        "pitfalls": "Éviter une vision uniquement européenne.",
        "key_points": ["Métropole", "Colonie", "Indigénat"],
    },
    "Première Guerre mondiale": {
        "summary": "Comprendre une guerre totale et la violence de masse.",
        "method": "Retenir 1914-1918, tranchées et mobilisation.",
        "example": "Verdun en 1916.",
        "pitfalls": "Distinguer front et arrière.",
        "key_points": ["1914-1918", "Tranchées", "Armistice"],
    },
    "Totalitarismes": {
        "summary": "Comparer nazisme et stalinisme.",
        "method": "Étudier parti unique, terreur et propagande.",
        "example": "Staline en URSS, Hitler en Allemagne.",
        "pitfalls": "Ne pas effacer les différences idéologiques.",
        "key_points": ["Propagande", "Terreur", "Parti unique"],
    },
    "Seconde Guerre mondiale": {
        "summary": "Comprendre guerre d'anéantissement et génocide.",
        "method": "Retenir 1939-1945 et les grandes phases.",
        "example": "Débarquement de 1944.",
        "pitfalls": "Distinguer Shoah et persécutions générales.",
        "key_points": ["1939-1945", "Shoah", "Résistance"],
    },
    "Guerre froide": {
        "summary": "Comprendre l'affrontement États-Unis/URSS.",
        "method": "Étudier blocs, crises et détente.",
        "example": "Mur de Berlin.",
        "pitfalls": "Pas d'affrontement militaire direct entre les deux superpuissances.",
        "key_points": ["Blocs", "Berlin", "1962", "1991"],
    },
    "Construction européenne": {
        "summary": "Comprendre les étapes de l'intégration européenne.",
        "method": "Retenir CECA, CEE, Maastricht et élargissements.",
        "example": "Traité de Maastricht en 1992.",
        "pitfalls": "Distinguer Europe géographique et Union européenne.",
        "key_points": ["1951", "1957", "1992"],
    },
}
BANK: dict[str, list[tuple[Any, ...]]] = {
    "Révolution française": [("En quelle année débute la Révolution française ?", "1789", "Elle commence en 1789.")],
    "Empire napoléonien": [("En quelle année Napoléon devient-il empereur ?", "1804", "Il est sacré en 1804.")],
    "Industrialisation": [
        (
            "Quelle source d'énergie domine la première industrialisation ?",
            "charbon",
            "Le charbon alimente les machines.",
        )
    ],
    "Société au XIXe siècle": [
        ("Comment appelle-t-on la classe ouvrière salariée ?", "prolétariat", "Il s'agit du prolétariat.")
    ],
    "Colonisation": [
        ("Un territoire dominé par une puissance étrangère est une...", "colonie", "Il s'agit d'une colonie.")
    ],
    "Première Guerre mondiale": [
        ("Dates de la Première Guerre mondiale ?", "1914-1918", "Elle dure de 1914 à 1918.", ["1914 à 1918"])
    ],
    "Totalitarismes": [
        (
            "Quel dirigeant est associé à l'URSS totalitaire ?",
            "staline",
            "Joseph Staline dirige l'URSS.",
            ["joseph staline"],
        )
    ],
    "Seconde Guerre mondiale": [
        ("Dates de la Seconde Guerre mondiale ?", "1939-1945", "Elle dure de 1939 à 1945.", ["1939 à 1945"])
    ],
    "Guerre froide": [
        (
            "Quelles sont les deux superpuissances rivales ?",
            "états-unis et urss",
            "États-Unis et URSS.",
            ["urss et états-unis", "usa et urss"],
        )
    ],
    "Construction européenne": [
        ("Quel traité crée l'Union européenne en 1992 ?", "maastricht", "Le traité de Maastricht.")
    ],
}


def generate_question(chapter: str, difficulty: str = "Moyen") -> dict:
    return generate_from_bank(chapter, BANK, difficulty)
