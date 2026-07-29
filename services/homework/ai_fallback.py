"""Runtime AI fallback orchestration for 4e homework (LCAI-0018B)."""

from __future__ import annotations

import logging
import uuid
from typing import Protocol

from domain.content.factory import (
    CanonicalContentType,
    ContentGenerationRequest,
    GeneratedContentCandidate,
    IssueSeverity,
    PedagogicalIntent,
    normalized_content_fingerprint,
)
from domain.unified_experience.models import (
    HomeworkContentSelection,
    HomeworkGenerationResult,
    HomeworkRequest,
    LearnerPedagogicalContext,
    RuntimeExerciseCandidate,
)
from services.content.factory import ContentFactoryService
from services.homework.config import HomeworkAiFallbackSettings
from services.homework.curriculum_target import resolve_curriculum_target
from services.homework.learner_context import LearnerContextService

LOGGER = logging.getLogger(__name__)
FOUR_E_GRADE_CODE = "FR-4E"


class HomeworkRuntimeRepository(Protocol):
    @property
    def database_path(self): ...

    def create_homework(self, request: HomeworkRequest, content_ids: tuple[int, ...]): ...

    def select_approved_content_detailed(self, request: HomeworkRequest) -> HomeworkContentSelection: ...

    def persist_homework_runtime_exercises(
        self,
        homework_id: int,
        learner_id: int,
        exercises: tuple[RuntimeExerciseCandidate, ...],
        *,
        start_position: int,
    ) -> tuple[int, ...]: ...


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def candidate_from_generated(
    generated: GeneratedContentCandidate,
    *,
    correlation_id: str,
    skill_ids: tuple[int, ...],
) -> RuntimeExerciseCandidate:
    fingerprint = normalized_content_fingerprint(generated.prompt)
    expected = str(generated.answer.expected)
    return RuntimeExerciseCandidate(
        temporary_id=generated.code,
        title=generated.title,
        statement=generated.prompt,
        instructions=generated.instructions,
        expected_answer=expected,
        correction=expected,
        explanation=generated.explanation,
        solving_method=generated.metadata.get("solving_method", ""),
        hints=generated.hints,
        skill_ids=skill_ids,
        sub_skill_ids=(),
        prerequisite_ids=(),
        difficulty=generated.difficulty,
        exercise_type=generated.content_type.value,
        estimated_duration=int(generated.metadata.get("estimated_duration", 5)),
        common_mistakes=tuple(generated.metadata.get("common_mistakes", ()) or ()),
        success_criteria=tuple(generated.metadata.get("success_criteria", ("Réponse correcte",)) or ("Réponse correcte",)),
        source="ai_runtime_fallback",
        generator_model=generated.provenance.generator_identifier,
        prompt_template_version=generated.provenance.template_version,
        content_fingerprint=fingerprint,
        validation_result={"valid": True, "issues": []},
        generated_at=generated.provenance.generated_at,
        correlation_id=correlation_id,
    )


def runtime_payload(candidate: RuntimeExerciseCandidate) -> dict[str, object]:
    return {
        "title": candidate.title,
        "statement": candidate.statement,
        "instructions": candidate.instructions,
        "expected_answer": candidate.expected_answer,
        "correction": candidate.correction,
        "explanation": candidate.explanation,
        "hints": list(candidate.hints),
        "exercise_type": candidate.exercise_type,
        "estimated_duration": candidate.estimated_duration,
    }


class HomeworkAiFallbackOrchestrator:
    def __init__(
        self,
        repository: HomeworkRuntimeRepository,
        *,
        content_factory: ContentFactoryService | None = None,
        learner_context: LearnerContextService | None = None,
        settings: HomeworkAiFallbackSettings | None = None,
    ) -> None:
        self.repository = repository
        self.content_factory = content_factory
        self.learner_context = learner_context or LearnerContextService(repository)
        self.settings = settings or HomeworkAiFallbackSettings.from_environment()

    def generate(self, request: HomeworkRequest, *, correlation_id: str | None = None) -> HomeworkGenerationResult:
        correlation = correlation_id or new_correlation_id()
        LOGGER.info("homework_generation_started correlation_id=%s learner_id=%s", correlation, request.learner_id)

        context = self.learner_context.build(request, correlation)
        if context.grade_code != FOUR_E_GRADE_CODE:
            raise ValueError("HOMEWORK_AI_FALLBACK_GRADE_NOT_SUPPORTED")

        selection = self.repository.select_approved_content_detailed(request)
        catalog_ids = selection.content_ids
        deficit = max(0, request.exercise_count - len(catalog_ids))
        LOGGER.info(
            "homework_deficit_computed correlation_id=%s catalog=%s deficit=%s",
            correlation,
            len(catalog_ids),
            deficit,
        )

        accepted: tuple[RuntimeExerciseCandidate, ...] = ()
        ai_requested = 0
        if deficit > 0:
            ai_requested = self.settings.generation_cap(deficit)
            if self.content_factory is not None and ai_requested > 0:
                LOGGER.info("ai_fallback_started correlation_id=%s requested=%s", correlation, ai_requested)
                accepted = self._generate_validated(context, request, ai_requested, correlation)
                LOGGER.info(
                    "ai_fallback_completed correlation_id=%s accepted=%s",
                    correlation,
                    len(accepted),
                )

        if not catalog_ids and not accepted:
            raise ValueError(self._empty_message())

        homework = self.repository.create_homework(request, catalog_ids)
        runtime_ids: tuple[int, ...] = ()
        if accepted:
            runtime_ids = self.repository.persist_homework_runtime_exercises(
                homework.homework_id,
                request.learner_id,
                accepted,
                start_position=len(catalog_ids) + 1,
            )

        final_count = len(catalog_ids) + len(accepted)
        degraded = final_count < request.exercise_count
        degradation_reason = None
        if degraded:
            degradation_reason = "INSUFFICIENT_CATALOG_AND_AI" if deficit > len(accepted) else "PARTIAL_CATALOG"
            LOGGER.warning(
                "homework_generation_degraded correlation_id=%s final=%s requested=%s reason=%s",
                correlation,
                final_count,
                request.exercise_count,
                degradation_reason,
            )

        LOGGER.info(
            "homework_generation_completed correlation_id=%s final=%s degraded=%s",
            correlation,
            final_count,
            degraded,
        )
        return HomeworkGenerationResult(
            homework,
            request.exercise_count,
            len(catalog_ids),
            ai_requested,
            len(accepted),
            final_count,
            degraded,
            degradation_reason,
            correlation,
            runtime_ids,
        )

    def _generate_validated(
        self,
        context: LearnerPedagogicalContext,
        request: HomeworkRequest,
        quantity: int,
        correlation_id: str,
    ) -> tuple[RuntimeExerciseCandidate, ...]:
        generation_request = ContentGenerationRequest(
            resolve_curriculum_target(self.repository, request),
            CanonicalContentType.PRACTICE,
            context.target_difficulty,
            PedagogicalIntent.PRACTICE,
            quantity=quantity,
            variation_constraints=tuple(context.recent_content_fingerprints),
        )
        known = set(context.recent_content_fingerprints)
        accepted: list[RuntimeExerciseCandidate] = []
        remaining = quantity
        attempts = 0
        while remaining > 0 and attempts <= self.settings.max_retry:
            attempts += 1
            candidates = self.content_factory.generate_runtime_candidates(generation_request, remaining)
            for generated in candidates:
                fingerprint = normalized_content_fingerprint(generated.prompt)
                if fingerprint in known:
                    LOGGER.info("ai_candidate_rejected correlation_id=%s reason=duplicate", correlation_id)
                    continue
                report = self.content_factory.validator.validate(
                    generated,
                    target_errors=self.content_factory.repository.validate_target(generated.target),
                    known_fingerprints=self.content_factory.repository.known_fingerprints(),
                )
                if not report.valid:
                    LOGGER.info(
                        "ai_candidate_rejected correlation_id=%s issues=%s",
                        correlation_id,
                        [issue.code for issue in report.issues if issue.severity is IssueSeverity.ERROR],
                    )
                    continue
                accepted.append(
                    candidate_from_generated(
                        generated,
                        correlation_id=correlation_id,
                        skill_ids=context.skill_ids,
                    )
                )
                known.add(fingerprint)
                remaining = quantity - len(accepted)
                if len(accepted) >= quantity:
                    break
            if not candidates:
                break
            generation_request = ContentGenerationRequest(
                generation_request.target,
                generation_request.content_type,
                generation_request.difficulty,
                generation_request.pedagogical_intent,
                quantity=remaining,
                variation_constraints=generation_request.variation_constraints,
            )
        return tuple(accepted[:quantity])

    @staticmethod
    def _empty_message() -> str:
        return (
            "Aucun contenu approuvé ni exercice IA validé ne correspond à cette sélection. "
            "Élargissez la sélection ou réessayez plus tard."
        )
