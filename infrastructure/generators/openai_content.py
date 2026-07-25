"""OpenAI structured-output adapter for the real LCAI-0012B pilot."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from domain.content.factory import (
    AnswerKind,
    AnswerSpecification,
    ContentGenerationRequest,
    GeneratedContentCandidate,
    GenerationProvenance,
)


class _GeneratedItem(BaseModel):
    title: str
    instructions: str
    prompt: str
    answer_kind: str
    expected_answer: str
    options: list[str] = Field(default_factory=list)
    independently_computed_answer: str | None = None
    explanation: str
    hints: list[str] = Field(default_factory=list)
    correct_feedback: str = ""
    incorrect_feedback: str = ""
    misconception_target: str | None = None
    family_code: str
    variant_role: str
    difficulty_justification: str


class _GeneratedBatch(BaseModel):
    candidates: list[_GeneratedItem]


class OpenAIContentGenerator:
    """Infrastructure-only OpenAI adapter implementing ContentGenerator."""

    def __init__(
        self,
        context_provider: Any,
        *,
        model: str | None = None,
        template_path: Path | None = None,
    ) -> None:
        from openai import OpenAI

        self.client = OpenAI()
        self.context_provider = context_provider
        self.model: str = model or os.getenv("OPENAI_CONTENT_MODEL") or "gpt-5.6"
        self.template_path = template_path or (
            Path(__file__).resolve().parents[2] / "resources" / "content" / "pilot" / "prompts" / "lcai_0012b_v1.txt"
        )

    def generate(self, request: ContentGenerationRequest) -> tuple[GeneratedContentCandidate, ...]:
        context = self.context_provider.generation_context(request.target)
        system_prompt = self.template_path.read_text(encoding="utf-8")
        payload = {
            "request": {
                "grade": request.target.grade_code,
                "subject": request.target.subject_code,
                "chapter": context["chapter_label"],
                "primary_skill": context["skill_label"],
                "subskill": context.get("subskill_label"),
                "prerequisites": context["prerequisites"],
                "content_type": request.content_type.value,
                "pedagogical_intent": request.pedagogical_intent.value,
                "difficulty": request.difficulty,
                "quantity": request.quantity,
                "variation_constraints": request.variation_constraints,
                "misconception_target": request.misconception_target,
                "learner_language": request.language_code,
            },
            "constraints": {
                "curriculum_scope": "Strictly remain within the declared 4e/3e curriculum Skill.",
                "student_facing_language": "French except the learner production required in English or Spanish.",
                "synthetic_sources": "Never invent quotations, statistics or sources presented as authentic.",
                "open_response": "Use structured success criteria, not one fictional exact answer.",
                "assessment": "No hints for assessment.",
            },
        }
        started = perf_counter()
        completion = self.client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format=_GeneratedBatch,
        )
        elapsed_ms = round((perf_counter() - started) * 1000)
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI returned no parsed content candidate batch")
        usage = completion.usage
        usage_metadata = (
            {
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            }
            if usage is not None
            else {}
        )
        generated_at = datetime.now(UTC)
        candidates = tuple(
            self._to_candidate(request, item, index, generated_at, elapsed_ms, usage_metadata)
            for index, item in enumerate(parsed.candidates, 1)
        )
        if len(candidates) != request.quantity:
            raise ValueError(f"Generator returned {len(candidates)} candidates; expected {request.quantity}")
        return candidates

    def _to_candidate(
        self,
        request: ContentGenerationRequest,
        item: _GeneratedItem,
        index: int,
        generated_at: datetime,
        latency_ms: int,
        usage: dict[str, int | float],
    ) -> GeneratedContentCandidate:
        try:
            answer_kind = AnswerKind(item.answer_kind)
        except ValueError as error:
            raise ValueError(f"Unsupported generated answer kind: {item.answer_kind}") from error
        independently_computed = item.independently_computed_answer if answer_kind is AnswerKind.NUMERIC else None
        suffix = request.target.primary_skill_code.removeprefix("SK-").replace("_", "-")
        timestamp = generated_at.strftime("%Y%m%d%H%M%S")
        return GeneratedContentCandidate(
            code=f"PILOT-0012B-AI-{suffix}-{request.content_type.value.upper()}-{timestamp}-{index}",
            title=item.title,
            instructions=item.instructions,
            prompt=item.prompt,
            answer=AnswerSpecification(
                answer_kind,
                item.expected_answer,
                tuple(item.options),
                independently_computed=independently_computed,
            ),
            explanation=item.explanation,
            target=request.target,
            content_type=request.content_type,
            pedagogical_intent=request.pedagogical_intent,
            difficulty=request.difficulty,
            provenance=GenerationProvenance(
                "openai_structured_output",
                self.model,
                "lcai-0012b-generation-spec-v1",
                "lcai-0012b-prompt-v1",
                "phase2-lcai-0011c",
                generated_at,
                latency_ms,
                usage,
            ),
            hints=tuple(item.hints),
            feedback={
                "correct": item.correct_feedback,
                "incorrect": item.incorrect_feedback,
            },
            family_code=item.family_code,
            variant_role=item.variant_role,
            misconception_target=item.misconception_target,
            language_code=request.language_code,
            metadata={
                "difficulty_justification": item.difficulty_justification,
                "review_required": True,
                "real_generation_pilot": True,
            },
        )
