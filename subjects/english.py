from __future__ import annotations

from subjects._helpers import generate_from_bank

SUBJECT_NAME = "Anglais"
CHAPTERS = {
    "Present simple": {
        "summary": "Exprimer habitudes et vérités générales.",
        "method": "Base verbale, -s à la 3e personne.",
        "example": "He plays football.",
        "pitfalls": "Ne pas oublier do/does aux questions.",
        "key_points": ["Affirmatif", "Négatif", "Interrogatif"],
    },
    "Present continuous": {
        "summary": "Décrire une action en cours.",
        "method": "Be + verbe-ing.",
        "example": "They are studying.",
        "pitfalls": "Ne pas oublier l'auxiliaire be.",
        "key_points": ["am/is/are", "Verbe-ing"],
    },
    "Past simple": {
        "summary": "Raconter une action terminée dans le passé.",
        "method": "Verbe en -ed ou forme irrégulière.",
        "example": "She went yesterday.",
        "pitfalls": "Utiliser did aux questions et négations.",
        "key_points": ["Regular verbs", "Irregular verbs", "Did"],
    },
    "Present perfect": {
        "summary": "Relier une expérience passée au présent.",
        "method": "Have/has + participe passé.",
        "example": "I have visited London.",
        "pitfalls": "Ne pas l'utiliser avec une date passée terminée.",
        "key_points": ["Ever/never", "Since/for", "Already/yet"],
    },
    "Future": {
        "summary": "Parler de l'avenir.",
        "method": "Will ou be going to selon le sens.",
        "example": "I will call you.",
        "pitfalls": "Distinguer décision spontanée et intention.",
        "key_points": ["Will", "Going to"],
    },
    "Modaux": {
        "summary": "Exprimer capacité, obligation, conseil ou possibilité.",
        "method": "Modal + base verbale.",
        "example": "You must work.",
        "pitfalls": "Pas de -s après un modal.",
        "key_points": ["Can", "Must", "Should", "May"],
    },
    "Comparatifs et superlatifs": {
        "summary": "Comparer des personnes ou objets.",
        "method": "-er/-est ou more/most.",
        "example": "Tom is taller than Sam.",
        "pitfalls": "Attention aux formes irrégulières.",
        "key_points": ["Comparatif", "Superlatif", "Good/better/best"],
    },
    "Questions": {
        "summary": "Construire des questions correctes.",
        "method": "Auxiliaire + sujet + verbe.",
        "example": "Do you like music?",
        "pitfalls": "Respecter l'ordre des mots.",
        "key_points": ["Wh- words", "Do/does", "Did"],
    },
    "Prépositions": {
        "summary": "Utiliser les prépositions de lieu et de temps.",
        "method": "Apprendre les associations fréquentes.",
        "example": "in France, at school, on Monday.",
        "pitfalls": "Ne pas traduire mot à mot.",
        "key_points": ["in", "on", "at", "to"],
    },
    "Vocabulaire": {
        "summary": "Développer le vocabulaire courant.",
        "method": "Mémoriser par thèmes et contexte.",
        "example": "Library = bibliothèque.",
        "pitfalls": "Éviter les faux amis.",
        "key_points": ["School", "Family", "Travel", "Environment"],
    },
    "Compréhension": {
        "summary": "Comprendre un document écrit simple.",
        "method": "Repérer mots clés et connecteurs.",
        "example": "Usually = habituellement.",
        "pitfalls": "Ne pas chercher à traduire chaque mot.",
        "key_points": ["Main idea", "Details", "Inference"],
    },
}
BANK = {
    "Present simple": [
        ("Complete: He ___ football every Saturday. (play)", "plays", "Third person singular takes -s.")
    ],
    "Present continuous": [("Complete: They ___ now. (study)", "are studying", "Use be + verb-ing.")],
    "Past simple": [("Complete: Yesterday, she ___ to school. (go)", "went", "The past of go is went.")],
    "Present perfect": [("Complete: I ___ never ___ London. (visit)", "have visited", "Use have + past participle.")],
    "Future": [("Complete: Tomorrow, I ___ call you.", "will", "Will forms the simple future.")],
    "Modaux": [("Complete: You ___ wear a seat belt. (obligation)", "must", "Must expresses obligation.")],
    "Comparatifs et superlatifs": [("Complete: Tom is ___ than Sam. (tall)", "taller", "Short adjective + er.")],
    "Questions": [("Turn into a question: You like music.", "do you like music", "Do + subject + base verb.")],
    "Prépositions": [("Complete: I live ___ France.", "in", "Use in with countries.")],
    "Vocabulaire": [("Translate « bibliothèque ».", "library", "Bibliothèque means library.")],
    "Compréhension": [
        ("What does « usually » mean?", "habituellement", "Usually means habituellement.", ["d'habitude"])
    ],
}


def generate_question(chapter: str, difficulty: str = "Moyen") -> dict:
    return generate_from_bank(chapter, BANK, difficulty)
