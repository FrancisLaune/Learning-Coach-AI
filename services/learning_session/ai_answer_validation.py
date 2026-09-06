"""Optional AI validation for worked student answers that fail deterministic grading."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from services.learning_session.assessment import _looks_like_worked_solution
from services.learning_session.models import AssessmentRequest

LOGGER = logging.getLogger(__name__)


def ai_accepts_worked_answer(
    request: AssessmentRequest,
    *,
    statement: str = "",
) -> bool | None:
    """Return True/False when AI can judge, or None when unavailable/unsafe to call."""
    raw = str(request.raw_answer or "")
    if not _looks_like_worked_solution(raw):
        return None
    try:
        from infrastructure.config.openai_settings import load_openai_api_key, load_openai_model
    except Exception:
        return None
    if not load_openai_api_key():
        return None
    try:
        from openai import OpenAI

        client = OpenAI()
        model = load_openai_model()
        prompt = (
            "Tu es un correcteur de collège. Dis si la réponse de l'élève aboutit au bon résultat "
            "attendu, même si la rédaction est longue (démarche complète). "
            "Ignore la forme exacte : accepte une conclusion équivalente (ex. A=4 ou 4). "
            "Réponds UNIQUEMENT en JSON compact : {\"correct\": true|false, \"reason\": \"...\"}.\n"
            f"Consigne: {(statement or '')[:500]}\n"
            f"Réponse attendue: {request.expected_answer!s}\n"
            f"Réponse élève:\n{raw[:2500]}"
        )
        completion = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": "Correcteur scolaire strict mais équitable. JSON only."},
                {"role": "user", "content": prompt},
            ],
        )
        content = (completion.choices[0].message.content or "").strip()
        payload = _parse_json_object(content)
        if payload is None:
            return None
        return bool(payload.get("correct"))
    except Exception:
        LOGGER.exception("AI answer validation failed")
        return None


def _parse_json_object(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None
