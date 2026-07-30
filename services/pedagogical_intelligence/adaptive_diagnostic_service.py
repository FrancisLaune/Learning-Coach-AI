"""Adaptive diagnostic orchestration with real catalog content (LCAI-0019 Phase 2)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from application.dto.pedagogical_intelligence import (
    DiagnosticAnswerResultDTO,
    DiagnosticItemDTO,
    DiagnosticRunDTO,
    DiagnosticSummaryDTO,
)
from domain.learning.models import LearnerAttempt
from domain.learning_session.models import AnswerType
from domain.pedagogical_intelligence.engine import should_stop_diagnostic, update_diagnostic_confidence
from domain.pedagogical_intelligence.models import DiagnosticRun, ReadinessPathCode
from domain.pedagogical_intelligence.paths import path_by_code
from infrastructure.repositories.pedagogical_intelligence import DuckDBPedagogicalIntelligenceRepository
from services.learning.learning_engine_service import LearningEngineService
from services.learning_session.assessment import DeterministicAssessmentEngine
from services.learning_session.models import AssessmentRequest
from services.pedagogical_intelligence.diagnostic_content_selector import DiagnosticContentSelector

logger = logging.getLogger(__name__)


class AdaptiveDiagnosticService:
    TARGET_CONFIDENCE = 0.75

    def __init__(
        self,
        repository: DuckDBPedagogicalIntelligenceRepository,
        learning_engine: LearningEngineService,
        selector: DiagnosticContentSelector | None = None,
        assessment: DeterministicAssessmentEngine | None = None,
    ) -> None:
        self.repository = repository
        self.learning_engine = learning_engine
        self.selector = selector or DiagnosticContentSelector(repository)
        self.assessment = assessment or DeterministicAssessmentEngine()

    def start(self, learner_id: int, path_code: ReadinessPathCode) -> DiagnosticRunDTO:
        started = monotonic()
        existing = self.repository.active_diagnostic_run(learner_id)
        if existing is not None:
            return self._run_dto(existing)
        path = path_by_code(path_code)
        target_skill_ids = self.repository.target_skills_for_grade(path.target_grade_code)
        if not target_skill_ids:
            target_skill_ids = self.repository.target_skills_for_grade(path.source_grade_code)
        confidence_by_skill = {skill_id: 0.0 for skill_id in target_skill_ids}
        run = self.repository.create_diagnostic_run(
            learner_id=learner_id,
            path_code=path_code,
            target_skill_ids=target_skill_ids,
            current_skill_id=None,
            confidence_by_skill=confidence_by_skill,
        )
        self.repository.ensure_experience_profile(learner_id, self.repository.learner_context(learner_id)["display_name"])
        self.repository.set_diagnostic_status(learner_id, "PLANNED")
        item = self._attach_next_item(run, path.target_grade_code)
        logger.info(
            "pedagogical_intelligence.diagnostic.started",
            extra={"student_id": learner_id, "pathway_code": path_code, "duration_ms": round((monotonic() - started) * 1000)},
        )
        return self._run_dto(run, item)

    def next_item(self, *, run_id: int) -> DiagnosticItemDTO | None:
        run = self.repository.load_diagnostic_run(run_id)
        if run is None or run.status != "IN_PROGRESS":
            return None
        path = path_by_code(run.path_code)
        return self._attach_next_item(run, path.target_grade_code)

    def submit_answer(
        self,
        *,
        run_id: int,
        learner_id: int,
        exercise_id: int,
        answer: Any,
        elapsed_ms: int = 0,
    ) -> DiagnosticAnswerResultDTO:
        started = monotonic()
        run = self.repository.load_diagnostic_run(run_id)
        if run is None or run.status != "IN_PROGRESS" or run.learner_id != learner_id:
            raise ValueError("Diagnostic actif introuvable.")
        idempotency_key = f"pi-diag:{run_id}:{run.questions_asked + 1}:{exercise_id}"
        existing_answer = self.repository.load_diagnostic_answer(idempotency_key)
        if existing_answer is not None:
            next_item = self.next_item(run_id=run_id)
            return DiagnosticAnswerResultDTO(
                bool(existing_answer["correct"]),
                float(existing_answer["normalized_score"]),
                "Réponse déjà enregistrée.",
                0.0,
                0.0,
                next_item is not None,
                next_item,
            )

        content = self.repository.load_diagnostic_exercise(exercise_id)
        if content is None or run.current_skill_id != content.skill_id:
            raise ValueError("Exercice diagnostic invalide.")
        answer_type, method = self._answer_strategy(content.response_type)
        assessed = self.assessment.assess(
            AssessmentRequest(
                answer_type=answer_type,
                raw_answer=answer,
                expected_answer=content.expected_answer,
                method=method,
                difficulty=2,
                hint_penalties=(),
            )
        )
        correctness = assessed.final_score / 100
        now = datetime.now(UTC)
        attempt = LearnerAttempt(
            stable_id=idempotency_key,
            learner_id=learner_id,
            skill_id=content.skill_id,
            occurred_at=now,
            correctness=correctness,
            difficulty=2,
            elapsed_seconds=elapsed_ms / 1000,
        )
        engine_result = self.learning_engine.process(attempt)
        mastery_delta = engine_result.mastery.current.score - engine_result.mastery.previous.score

        confidence_by_skill = dict(run.confidence_by_skill)
        previous = confidence_by_skill.get(content.skill_id, 0.0)
        updated_confidence = update_diagnostic_confidence(previous, correctness)
        confidence_by_skill[content.skill_id] = updated_confidence
        assessed_skills = tuple(dict.fromkeys(run.assessed_skill_ids + (content.skill_id,)))
        questions_asked = run.questions_asked + 1

        self.repository.save_diagnostic_answer(
            run_id=run_id,
            learner_id=learner_id,
            skill_id=content.skill_id,
            exercise_id=exercise_id,
            sequence_number=questions_asked,
            normalized_score=assessed.final_score,
            correct=assessed.correct,
            elapsed_ms=elapsed_ms,
            answer_payload={"answer": answer},
            idempotency_key=idempotency_key,
        )

        stop = should_stop_diagnostic(
            questions_asked=questions_asked,
            confidence_by_skill=confidence_by_skill,
            target_skill_ids=run.target_skill_ids,
            assessed_skill_ids=assessed_skills,
            confidence_threshold=self.TARGET_CONFIDENCE,
        )
        if stop or self.selector.select(
            run_id=run_id,
            learner_id=learner_id,
            grade_code=path_by_code(run.path_code).target_grade_code,
            target_skill_ids=run.target_skill_ids,
            confidence_by_skill=confidence_by_skill,
            assessed_skill_ids=assessed_skills,
            used_exercise_ids=self.repository.used_diagnostic_exercises(run_id),
        ) is None:
            completed = DiagnosticRun(
                run.id,
                run.learner_id,
                run.path_code,
                "COMPLETED",
                questions_asked,
                run.target_skill_ids,
                assessed_skills,
                None,
                confidence_by_skill,
                run.started_at,
                now,
            )
            self.repository.save_diagnostic_run(completed)
            self.repository.set_diagnostic_status(learner_id, "COMPLETED")
            logger.info(
                "pedagogical_intelligence.diagnostic.completed",
                extra={"student_id": learner_id, "run_id": run_id, "duration_ms": round((monotonic() - started) * 1000)},
            )
            return DiagnosticAnswerResultDTO(
                assessed.correct,
                assessed.final_score,
                assessed.feedback or ("Correct." if assessed.correct else "À retravailler."),
                mastery_delta,
                updated_confidence - previous,
                False,
                None,
            )

        updated = DiagnosticRun(
            run.id,
            run.learner_id,
            run.path_code,
            "IN_PROGRESS",
            questions_asked,
            run.target_skill_ids,
            assessed_skills,
            content.skill_id,
            confidence_by_skill,
            run.started_at,
            None,
        )
        self.repository.save_diagnostic_run(updated)
        next_item = self._attach_next_item(updated, path_by_code(run.path_code).target_grade_code)
        logger.info(
            "pedagogical_intelligence.diagnostic.answer_submitted",
            extra={"student_id": learner_id, "run_id": run_id, "duration_ms": round((monotonic() - started) * 1000)},
        )
        return DiagnosticAnswerResultDTO(
            assessed.correct,
            assessed.final_score,
            assessed.feedback or ("Correct." if assessed.correct else "À retravailler."),
            mastery_delta,
            updated_confidence - previous,
            True,
            next_item,
        )

    def complete(self, *, run_id: int) -> DiagnosticSummaryDTO:
        run = self.repository.load_diagnostic_run(run_id)
        if run is None:
            raise ValueError("Run introuvable.")
        answers = self.repository.used_diagnostic_exercises(run_id)
        weak = tuple(
            self.repository.skill_label(skill_id)
            for skill_id, confidence in run.confidence_by_skill.items()
            if confidence < 0.55
        )
        strong = tuple(
            self.repository.skill_label(skill_id)
            for skill_id, confidence in run.confidence_by_skill.items()
            if confidence >= 0.75
        )
        avg_conf = sum(run.confidence_by_skill.values()) / max(1, len(run.confidence_by_skill))
        return DiagnosticSummaryDTO(
            str(run_id),
            str(run.learner_id),
            run.path_code,
            run.status,
            run.questions_asked,
            len(answers),
            avg_conf,
            avg_conf,
            weak,
            strong,
            run.completed_at or datetime.now(UTC),
            "completed" if run.status == "COMPLETED" else "manual",
        )

    def _attach_next_item(self, run: DiagnosticRun, grade_code: str) -> DiagnosticItemDTO | None:
        used = self.repository.used_diagnostic_exercises(run.id)
        candidate = self.selector.select(
            run_id=run.id,
            learner_id=run.learner_id,
            grade_code=grade_code,
            target_skill_ids=run.target_skill_ids,
            confidence_by_skill=run.confidence_by_skill,
            assessed_skill_ids=run.assessed_skill_ids,
            used_exercise_ids=used,
        )
        if candidate is None:
            return None
        self.repository.update_diagnostic_run_exercise(run.id, exercise_id=candidate.exercise_id, skill_id=candidate.skill_id)
        return DiagnosticItemDTO(
            str(run.id),
            str(candidate.exercise_id),
            str(candidate.skill_id),
            str(candidate.chapter_id),
            candidate.prompt,
            candidate.exercise_type,
            candidate.response_type,
            candidate.payload,
            run.questions_asked + 1,
        )

    def _run_dto(self, run: DiagnosticRun, item: DiagnosticItemDTO | None = None) -> DiagnosticRunDTO:
        if item is None and run.status == "IN_PROGRESS":
            path = path_by_code(run.path_code)
            item = self._attach_next_item(run, path.target_grade_code)
        return DiagnosticRunDTO(
            str(run.id),
            str(run.learner_id),
            run.path_code,
            run.status,
            item,
            run.questions_asked,
            self.TARGET_CONFIDENCE,
        )

    @staticmethod
    def _answer_strategy(response_type: str) -> tuple[AnswerType, Any]:
        from domain.learning_session.models import AssessmentMethod

        mapping = {
            "short_text": (AnswerType.SHORT_TEXT, AssessmentMethod.EXACT),
            "long_text": (AnswerType.LONG_TEXT, AssessmentMethod.RUBRIC),
            "decimal": (AnswerType.DECIMAL, AssessmentMethod.NUMERIC),
            "single_choice": (AnswerType.SINGLE_CHOICE, AssessmentMethod.EXACT),
            "true_false": (AnswerType.BOOLEAN, AssessmentMethod.EXACT),
        }
        return mapping.get(response_type, (AnswerType.SHORT_TEXT, AssessmentMethod.EXACT))
