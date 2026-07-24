from __future__ import annotations

import inspect
import random
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

LEVELS = ["Facile", "Moyen", "Difficile", "Brevet", "Expert"]


def normalize_text(value: str) -> str:
    value = str(value or "").strip().lower().replace("’", "'")
    value = "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn")
    value = re.sub(r"[.,;:!?()\[\]{}]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def is_correct(question: dict[str, Any], answer: str) -> bool:
    if question["answer_type"] == "number":
        try:
            clean = str(answer).strip().replace(",", ".")
            match = re.match(r"^[-+]?\d+(?:\.\d+)?", clean)
            if not match:
                return False
            actual = float(match.group(0))
            expected_value = float(question["expected_answer"])
            return abs(actual - expected_value) <= max(0.001, abs(expected_value) * 0.001)
        except (TypeError, ValueError):
            return False
    candidates = [str(question["expected_answer"])]
    accepted = question.get("accepted_answers", "")
    candidates += [x for x in accepted.split("||") if x] if isinstance(accepted, str) else list(accepted or [])
    normalized_actual = normalize_text(answer)
    return any(normalized_actual == normalize_text(c) for c in candidates)


def create_question(
    chapter: str,
    question: str,
    expected_answer: Any,
    explanation: str,
    answer_type: str = "text",
    unit: str = "",
    accepted_answers: Sequence[Any] | None = None,
) -> dict[str, Any]:
    return {
        "chapter": chapter,
        "question": question,
        "expected_answer": expected_answer,
        "explanation": explanation,
        "answer_type": answer_type,
        "unit": unit,
        "accepted_answers": accepted_answers or [],
    }


def _generate(module: Any, chapter: str, difficulty: str) -> dict[str, Any]:
    try:
        params = inspect.signature(module.generate_question).parameters
        q = (
            module.generate_question(chapter, difficulty=difficulty)
            if "difficulty" in params
            else module.generate_question(chapter)
        )
    except (TypeError, ValueError):
        q = module.generate_question(chapter)
    q = dict(q)
    q["difficulty"] = difficulty
    q.setdefault(
        "target_seconds",
        {"Facile": 45, "Moyen": 70, "Difficile": 100, "Brevet": 130, "Expert": 170}.get(difficulty, 90),
    )
    return q


def _decorate_variant(q: dict[str, Any], difficulty: str, variant: int) -> dict[str, Any]:
    q = dict(q)
    prefixes = {
        "Facile": ["Application directe", "Question guidée"],
        "Moyen": ["Application", "Mise en situation"],
        "Difficile": ["Raisonnement en plusieurs étapes", "Question approfondie"],
        "Brevet": ["Niveau Brevet", "Exercice type examen"],
        "Expert": ["Défi expert", "Problème de synthèse"],
    }
    prefix = random.choice(prefixes.get(difficulty, [difficulty]))
    q["question"] = f"{prefix} · variante {variant}\n\n{q['question']}"
    return q


def build_question_set(
    subject_module: Any,
    count: int,
    chapters: Sequence[str] | None = None,
    difficulty: str = "Moyen",
) -> list[dict[str, Any]]:
    selected = list(chapters or subject_module.CHAPTERS.keys())
    if not selected:
        raise ValueError("Au moins un chapitre doit être sélectionné.")
    result: list[dict[str, Any]] = []
    signatures: set[str] = set()
    cycle: list[str] = []
    while len(cycle) < count:
        block = selected.copy()
        random.shuffle(block)
        cycle.extend(block)
    for chapter in cycle[:count]:
        q = _generate(subject_module, chapter, difficulty)
        sig = normalize_text(q.get("question", ""))
        if sig in signatures:
            q = _decorate_variant(q, difficulty, len(result) + 1)
        signatures.add(normalize_text(q.get("question", "")))
        result.append(q)
    return result


def build_progressive_set(
    subject_module: Any,
    count: int,
    chapters: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    selected = list(chapters or subject_module.CHAPTERS.keys())
    levels = LEVELS
    result: list[dict[str, Any]] = []
    for i in range(count):
        level = levels[min(len(levels) - 1, int(i * len(levels) / max(1, count)))]
        chapter = selected[i % len(selected)]
        q = _generate(subject_module, chapter, level)
        q = _decorate_variant(q, level, i + 1)
        result.append(q)
    random.shuffle(result[: max(1, count // 5)])
    return result


def build_exam(
    subject_module: Any,
    count: int,
    chapters: Sequence[str] | None = None,
    difficulty: str = "Moyen",
) -> list[dict[str, Any]]:
    return build_question_set(subject_module, count, chapters, difficulty)
