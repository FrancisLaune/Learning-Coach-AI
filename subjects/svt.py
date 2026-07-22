from __future__ import annotations

from subjects._helpers import generate_from_bank

SUBJECT_NAME = "SVT"
CHAPTERS = {
    "Cellule": {
        "summary": "Comprendre l'organisation cellulaire du vivant.",
        "method": "Identifier membrane, cytoplasme et noyau.",
        "example": "Le noyau contient l'ADN.",
        "pitfalls": "Toutes les cellules n'ont pas la même forme.",
        "key_points": ["Membrane", "Cytoplasme", "Noyau"],
    },
    "ADN et génétique": {
        "summary": "Comprendre support et transmission de l'information génétique.",
        "method": "Relier ADN, chromosome, gène et caractère.",
        "example": "Un gène est une portion d'ADN.",
        "pitfalls": "Un caractère dépend souvent de plusieurs facteurs.",
        "key_points": ["ADN", "Chromosome", "Gène", "Allèle"],
    },
    "Reproduction": {
        "summary": "Comprendre reproduction humaine et développement.",
        "method": "Étudier gamètes, fécondation et embryon.",
        "example": "Fécondation = union des gamètes.",
        "pitfalls": "Ne pas confondre fécondation et grossesse.",
        "key_points": ["Gamètes", "Fécondation", "Embryon"],
    },
    "Évolution": {
        "summary": "Comprendre diversité et sélection naturelle.",
        "method": "Relier variations, environnement et reproduction.",
        "example": "Darwin et sélection naturelle.",
        "pitfalls": "L'évolution ne poursuit pas un but.",
        "key_points": ["Mutation", "Sélection", "Ancêtre commun"],
    },
    "Immunité": {
        "summary": "Comprendre défenses innées et adaptatives.",
        "method": "Distinguer antigène, anticorps et lymphocytes.",
        "example": "Vaccination et mémoire immunitaire.",
        "pitfalls": "Antibiotiques inefficaces contre les virus.",
        "key_points": ["Antigène", "Anticorps", "Vaccin"],
    },
    "Nutrition et digestion": {
        "summary": "Comprendre transformation et absorption des aliments.",
        "method": "Suivre le trajet digestif et les nutriments.",
        "example": "Absorption dans l'intestin grêle.",
        "pitfalls": "Digestion n'est pas seulement broyage.",
        "key_points": ["Enzymes", "Nutriments", "Intestin"],
    },
    "Respiration et circulation": {
        "summary": "Comprendre échanges gazeux et transport sanguin.",
        "method": "Relier poumons, cœur et organes.",
        "example": "Le sang transporte O₂ et nutriments.",
        "pitfalls": "Ne pas confondre respiration et ventilation.",
        "key_points": ["Alvéoles", "Cœur", "Vaisseaux"],
    },
    "Écosystèmes": {
        "summary": "Comprendre interactions entre êtres vivants et milieu.",
        "method": "Construire chaînes et réseaux alimentaires.",
        "example": "Producteurs, consommateurs, décomposeurs.",
        "pitfalls": "Un écosystème comprend biotope et biocénose.",
        "key_points": ["Biotope", "Biocénose", "Réseau trophique"],
    },
    "Climat": {
        "summary": "Comprendre effet de serre et changement climatique.",
        "method": "Relier activités humaines, gaz et conséquences.",
        "example": "CO₂ issu des combustibles fossiles.",
        "pitfalls": "Météo et climat ne sont pas synonymes.",
        "key_points": ["Effet de serre", "CO₂", "Adaptation"],
    },
    "Géologie": {
        "summary": "Comprendre dynamique interne de la Terre.",
        "method": "Relier plaques, séismes et volcanisme.",
        "example": "Magma en profondeur, lave en surface.",
        "pitfalls": "Tous les volcans ne fonctionnent pas de la même manière.",
        "key_points": ["Plaques", "Séisme", "Volcan"],
    },
}
BANK = {
    "Cellule": [("Quel organite contient généralement l'information génétique ?", "noyau", "Le noyau contient l'ADN.")],
    "ADN et génétique": [
        ("Quel support porte l'information génétique ?", "adn", "L'ADN porte l'information génétique.")
    ],
    "Reproduction": [("L'union d'un spermatozoïde et d'un ovule s'appelle...", "fécondation", "C'est la fécondation.")],
    "Évolution": [
        ("Quel scientifique est associé à la sélection naturelle ?", "darwin", "Charles Darwin.", ["charles darwin"])
    ],
    "Immunité": [
        ("Une substance reconnue par le système immunitaire est un...", "antigène", "Il s'agit d'un antigène.")
    ],
    "Nutrition et digestion": [
        ("Dans quel organe débute la digestion de l'amidon ?", "bouche", "Elle débute dans la bouche.")
    ],
    "Respiration et circulation": [("Quel organe propulse le sang ?", "coeur", "Le cœur propulse le sang.", ["cœur"])],
    "Écosystèmes": [("L'ensemble des êtres vivants d'un milieu est la...", "biocénose", "C'est la biocénose.")],
    "Climat": [
        (
            "Quel gaz est principalement émis par la combustion des énergies fossiles ?",
            "dioxyde de carbone",
            "Il s'agit du CO₂.",
            ["co2"],
        )
    ],
    "Géologie": [("Une roche liquide en profondeur est du...", "magma", "En profondeur, c'est le magma.")],
}


def generate_question(chapter: str, difficulty: str = "Moyen") -> dict:
    return generate_from_bank(chapter, BANK, difficulty)
