from __future__ import annotations

LEVELS = ["Facile", "Moyen", "Difficile", "Brevet", "Expert"]


def recommend_level(current: str, accuracy: float, speed_index: float, attempts: int) -> str:
    try:
        idx = LEVELS.index(current)
    except ValueError:
        idx = 1
    if attempts >= 12 and accuracy >= 85 and speed_index >= 0.9:
        idx = min(len(LEVELS) - 1, idx + 1)
    elif attempts >= 8 and accuracy < 50:
        idx = max(0, idx - 1)
    return LEVELS[idx]


def coaching_message(accuracy: float, speed_index: float, current: str, recommended: str) -> str:
    if accuracy >= 85 and speed_index >= 0.9:
        return f"Très bonne maîtrise au niveau {current}. Le prochain entraînement est proposé au niveau {recommended}."
    if accuracy >= 80 and speed_index < 0.8:
        return "Les réponses sont justes, mais le temps de résolution reste élevé. Travaille les automatismes avant de monter encore."
    if accuracy < 65 and speed_index > 1.05:
        return "Tu réponds rapidement mais avec trop d’erreurs. Ralentis, relis la consigne et vérifie chaque étape."
    if accuracy < 50:
        return "Ce chapitre doit être repris progressivement : fiche de révision, exercices guidés, puis niveau moyen."
    return "Le niveau est en cours d’acquisition. Une nouvelle série ciblée permettra de consolider les acquis."
