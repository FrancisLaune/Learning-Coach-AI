"""OpenAI adapter for blind pedagogical review (Pass A + comparison)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from domain.content.pedagogical_review import BlindReviewInput, BlindReviewOutput, ComparisonResult, Confidence
from infrastructure.config.openai_settings import verify_openai_pedagogical_assessor


class _BlindSolution(BaseModel):
    independent_answer: str
    concise_verification_reason: str
    confidence: Confidence


class _ComparisonVerdict(BaseModel):
    match: str
    concise_reason: str


class OpenAIPedagogicalReviewAssessor:
    """Blind Pass A and semantic comparison via structured OpenAI output."""

    def __init__(self, *, model: str | None = None) -> None:
        from openai import OpenAI

        verification = verify_openai_pedagogical_assessor()
        self.client = OpenAI()
        self.model = model or verification["model"]
        self.assessor_type = "openai"
        self.api_key_source = verification.get("api_key_source", "unknown")

    def solve_blind(self, payload: BlindReviewInput) -> BlindReviewOutput:
        system = (
            "Tu es un relecteur pédagogique indépendant. "
            "Résous la question sans supposer de réponse attendue fournie par un générateur. "
            "Réponds de façon concise. Ne produis pas de chaîne de raisonnement détaillée."
        )
        user_payload: dict[str, Any] = {
            "grade": payload.grade,
            "subject": payload.subject,
            "chapter": payload.chapter,
            "skill_code": payload.skill_code,
            "content_type": payload.content_type,
            "answer_kind": payload.answer_kind,
            "question": payload.question,
            "choices": list(payload.choices),
        }
        response = self.client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": str(user_payload)},
            ],
            response_format=_BlindSolution,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI blind review returned no structured output.")
        return BlindReviewOutput(
            independent_answer=parsed.independent_answer,
            concise_verification_reason=parsed.concise_verification_reason,
            confidence=parsed.confidence,
            used_expected_answer=False,
        )

    def compare(
        self,
        *,
        blind: BlindReviewOutput,
        expected_answer: str,
        expected_explanation: str,
        choices: tuple[str, ...],
        answer_kind: str,
        subject: str,
    ) -> ComparisonResult:
        system = (
            "Compare la réponse indépendante à la réponse attendue. "
            "Pour les réponses ouvertes, accepte les variantes sémantiques valides. "
            "Retourne CORRECT, ACCEPTABLE_VARIANT, PARTIALLY_CORRECT, INCORRECT ou AMBIGUOUS."
        )
        payload = {
            "independent_answer": blind.independent_answer,
            "expected_answer": expected_answer,
            "expected_explanation": expected_explanation,
            "choices": list(choices),
            "answer_kind": answer_kind,
            "subject": subject,
        }
        response = self.client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": str(payload)},
            ],
            response_format=_ComparisonVerdict,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI comparison returned no structured output.")
        match = parsed.match
        allowed = {"CORRECT", "ACCEPTABLE_VARIANT", "PARTIALLY_CORRECT", "INCORRECT", "AMBIGUOUS"}
        if match not in allowed:
            match = "AMBIGUOUS"
        return ComparisonResult(match=match, concise_reason=parsed.concise_reason)  # type: ignore[arg-type]
