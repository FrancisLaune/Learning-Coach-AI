from __future__ import annotations
import random
from core.engine import create_question


def generate_from_bank(chapter: str, bank: dict[str, list[tuple]], difficulty: str = "Moyen") -> dict:
    item = random.choice(bank[chapter])
    question, answer, explanation, *rest = item
    accepted = rest[0] if rest else []

    if difficulty == "Difficile":
        question = (
            "Analyse précisément la situation et choisis la réponse la plus exacte. "
            "Une réponse non justifiée mentalement peut conduire à une erreur.\n\n" + question
        )
    elif difficulty == "Moyen":
        question = "Mobilise la notion du chapitre pour répondre.\n\n" + question

    return create_question(
        chapter=chapter,
        question=question,
        expected_answer=answer,
        explanation=explanation,
        accepted_answers=accepted,
    )
