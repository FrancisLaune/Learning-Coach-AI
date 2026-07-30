"""Generalized homework AI content completion (LCAI-0018B6)."""

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
    GeneratedHomeworkExerciseResult,
    HomeworkContentSelection,
    HomeworkGenerationResult,
    HomeworkRequest,
    LearnerPedagogicalContext,
)
from services.content.factory import ContentFactoryService
from services.homework.config import HomeworkAiFallbackSettings
from services.homework.curriculum_target import resolve_curriculum_targets
from services.homework.learner_context import LearnerContextService
from services.homework.runtime_persistence import is_playable_candidate, persist_playable_homework_exercise

LOGGER = logging.getLogger(__name__)


class HomeworkRuntimeRepository(Protocol):
    @property
    def database_path(self): ...

    def create_homework(self, request: HomeworkRequest, content_ids: tuple[int, ...]): ...

    def select_approved_content_detailed(self, request: HomeworkRequest) -> HomeworkContentSelection: ...

    def load_homework_runtime_results(self, homework_id: int) -> tuple[GeneratedHomeworkExerciseResult, ...]: ...


def new_correlation_id() -> str:
    return str(uuid.uuid4())


class HomeworkContentCompletionService:
    """Complete homework selections by generating validated runtime exercises for catalog deficits."""

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

    def complete_homework_selection(
        self,
        request: HomeworkRequest,
        *,
        correlation_id: str | None = None,
    ) -> HomeworkGenerationResult:
        return self.generate(request, correlation_id=correlation_id)

    def generate(self, request: HomeworkRequest, *, correlation_id: str | None = None) -> HomeworkGenerationResult:
        correlation = correlation_id or new_correlation_id()
        LOGGER.info("homework_generation_started correlation_id=%s learner_id=%s", correlation, request.learner_id)

        context = self.learner_context.build(request, correlation)
        selection = self.repository.select_approved_content_detailed(request)
        catalog_ids = selection.content_ids
        deficit = max(0, request.exercise_count - len(catalog_ids))
        LOGGER.info(
            "homework_deficit_computed correlation_id=%s catalog=%s deficit=%s",
            correlation,
            len(catalog_ids),
            deficit,
        )

        accepted: tuple[GeneratedContentCandidate, ...] = ()
        ai_requested = 0
        homework = self.repository.create_homework(request, catalog_ids)
        existing_results = self.repository.load_homework_runtime_results(homework.homework_id)
        still_needed = max(0, deficit - len(existing_results))
        if still_needed > 0:
            ai_requested = self.settings.generation_cap(still_needed)
            if self.content_factory is not None and ai_requested > 0:
                LOGGER.info("ai_completion_started correlation_id=%s requested=%s", correlation, ai_requested)
                accepted = self._generate_validated(context, request, ai_requested, correlation)
                LOGGER.info(
                    "ai_completion_completed correlation_id=%s accepted=%s",
                    correlation,
                    len(accepted),
                )
        elif deficit > 0 and existing_results:
            LOGGER.info(
                "ai_completion_reused correlation_id=%s existing=%s",
                correlation,
                len(existing_results),
            )

        if not catalog_ids and not accepted and not existing_results:
            raise ValueError(self._empty_message())

        generated_results: list[GeneratedHomeworkExerciseResult] = list(existing_results[:deficit])
        runtime_ids: list[int] = [
            int(item.generation_metadata["runtime_record_id"]) for item in generated_results
        ]
        parent_ref = request.assigned_by_ref if request.assigned_by_type == "PARENT" else None
        for offset, candidate in enumerate(accepted):
            persisted = persist_playable_homework_exercise(
                self.repository,
                candidate,
                homework_id=homework.homework_id,
                learner_id=request.learner_id,
                position=len(catalog_ids) + len(existing_results) + offset + 1,
                correlation_id=correlation,
                parent_ref=parent_ref,
            )
            generated_results.append(persisted)
            runtime_ids.append(int(persisted.generation_metadata["runtime_record_id"]))

        final_count = len(catalog_ids) + len(generated_results)
        degraded = final_count < request.exercise_count
        degradation_reason = None
        if degraded:
            degradation_reason = (
                "INSUFFICIENT_CATALOG_AND_AI"
                if deficit > len(generated_results)
                else "PARTIAL_CATALOG"
            )
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
            len(generated_results),
            final_count,
            degraded,
            degradation_reason,
            correlation,
            tuple(runtime_ids),
            tuple(generated_results),
        )

    def _generate_validated(
        self,
        context: LearnerPedagogicalContext,
        request: HomeworkRequest,
        quantity: int,
        correlation_id: str,
    ) -> tuple[GeneratedContentCandidate, ...]:
        targets = resolve_curriculum_targets(self.repository, request)
        known = set(context.recent_content_fingerprints)
        accepted: list[GeneratedContentCandidate] = []
        remaining = quantity
        attempts = 0
        target_index = 0
        while remaining > 0 and attempts <= self.settings.max_retry:
            attempts += 1
            target = targets[target_index % len(targets)]
            target_index += 1
            generation_request = ContentGenerationRequest(
                target,
                CanonicalContentType.PRACTICE,
                context.target_difficulty,
                PedagogicalIntent.PRACTICE,
                quantity=remaining,
                variation_constraints=tuple(known),
            )
            candidates = self.content_factory.generate_runtime_candidates(generation_request, remaining)
            for generated in candidates:
                fingerprint = normalized_content_fingerprint(generated.prompt)
                if fingerprint in known:
                    LOGGER.info("ai_candidate_rejected correlation_id=%s reason=duplicate", correlation_id)
                    continue
                if not is_playable_candidate(generated):
                    LOGGER.info("ai_candidate_rejected correlation_id=%s reason=not_playable", correlation_id)
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
                accepted.append(generated)
                known.add(fingerprint)
                remaining = quantity - len(accepted)
                if len(accepted) >= quantity:
                    break
            if not candidates or remaining <= 0:
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


# Backward-compatible alias for LCAI-0018B.
HomeworkAiFallbackOrchestrator = HomeworkContentCompletionService
