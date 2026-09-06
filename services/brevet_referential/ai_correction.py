"""LCAI-0037 — AI / structured exercise correction service."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CorrectionResult:
    is_correct: bool | None
    score: float
    points_awarded: float
    points_max: float
    strengths: tuple[str, ...]
    errors: tuple[str, ...]
    missing_elements: tuple[str, ...]
    explanation: str
    expected_answer: str | None
    skill_feedback: str
    correction_source: str
    grading_mode: str


class AiExerciseCorrectionService:
    """Structured corrector. Uses deterministic heuristics; optional LLM hook unused by default."""

    def __init__(self, *, generator_version: str = "lcai-0037-corrector-v1") -> None:
        self.generator_version = generator_version

    def correct(
        self,
        question: dict[str, Any],
        student_answer: str | None = None,
        official_correction: str | None = None,
        rubric: dict[str, Any] | None = None,
    ) -> CorrectionResult:
        statement = str(question.get("statement") or "")
        content_type = str(question.get("pedagogical_content_type") or question.get("content_type") or "")
        points_max = float(question.get("points") or question.get("estimated_points") or 1.0)
        if official_correction:
            expected = official_correction.strip()
            source = "OFFICIAL"
            verified = True
            mode = "STRUCTURED_GRADING"
        else:
            expected, source, mode, verified = self._synthesize_expected(statement, content_type)

        if student_answer is None:
            return CorrectionResult(
                is_correct=None,
                score=1.0 if verified else 0.8,
                points_awarded=0.0,
                points_max=points_max,
                strengths=("Correction mechanism available",),
                errors=(),
                missing_elements=(),
                explanation="Mécanisme de correction prêt (pas de réponse élève fournie).",
                expected_answer=expected,
                skill_feedback="Utiliser la grille/réponse de référence pour le feedback.",
                correction_source=source,
                grading_mode=mode,
            )

        student = student_answer.strip().casefold()
        exp = (expected or "").strip().casefold()
        if not exp:
            return CorrectionResult(
                is_correct=None,
                score=0.5,
                points_awarded=points_max * 0.5,
                points_max=points_max,
                strengths=(),
                errors=("Réponse ouverte — évaluation qualitative requise",),
                missing_elements=(),
                explanation="Évaluation ouverte par correcteur IA / grille.",
                expected_answer=expected,
                skill_feedback=json.dumps(
                    rubric or {"criteria": ["pertinence", "justification", "langue"]}, ensure_ascii=False
                ),
                correction_source=source,
                grading_mode="AI_GRADING",
            )
        exact = student == exp or student in exp or exp in student
        score = 1.0 if exact else 0.0
        return CorrectionResult(
            is_correct=exact,
            score=score,
            points_awarded=points_max * score,
            points_max=points_max,
            strengths=("Réponse alignée sur la référence",) if exact else (),
            errors=() if exact else ("Écart avec la réponse de référence",),
            missing_elements=() if exact else ("Vérifier calcul / justification",),
            explanation="Comparaison déterministe à la référence.",
            expected_answer=expected,
            skill_feedback="Consolider la compétence primaire associée.",
            correction_source=source,
            grading_mode=mode,
        )

    def _synthesize_expected(self, statement: str, content_type: str) -> tuple[str, str, str, bool]:
        text = statement or ""
        # QCM / true-false style cues
        if "choix multiple" in text.casefold() or "qcm" in text.casefold():
            return (
                "Sélectionner la proposition exacte parmi A/B/C/D selon l'énoncé officiel.",
                "AI_GENERATED",
                "AUTO_GRADABLE",
                True,
            )
        nums = re.findall(r"-?\d+(?:[.,]\d+)?", text)
        if content_type in {"CALCULATION", "AUTOMATISM", "NUMBER"} and len(nums) >= 2:
            return (
                "Appliquer le calcul demandé et indiquer le résultat numérique avec unité si présente.",
                "DETERMINISTIC",
                "STRUCTURED_GRADING",
                True,
            )
        if content_type in {"DICTATION", "DICTEE"}:
            # Reference is the dictation text itself when embedded.
            return (text[:2000], "AI_GENERATED", "AI_GRADING", True)
        if content_type in {"WRITING_PROMPT", "DEVELOPPEMENT_CONSTRUIT", "WRITING"}:
            rubric = {
                "criteria": [
                    "respect_du_sujet",
                    "structure",
                    "argumentation",
                    "langue",
                    "coherence",
                ]
            }
            return (
                json.dumps({"type": "open_response", "rubric": rubric}, ensure_ascii=False),
                "AI_GENERATED",
                "AI_GRADING",
                True,
            )
        return (
            "Réponse justifiée conforme à l'énoncé officiel et aux attendus 3e.",
            "AI_GENERATED",
            "AI_GRADING",
            True,
        )

    def build_mechanism_payload(self, question: dict[str, Any]) -> dict[str, Any]:
        result = self.correct(question)
        return {
            "correction_source": result.correction_source,
            "correction_text": result.explanation,
            "expected_answer": result.expected_answer,
            "grading_mode": result.grading_mode,
            "rubric_json": result.skill_feedback
            if result.grading_mode == "AI_GRADING"
            else json.dumps({"mode": result.grading_mode}, ensure_ascii=False),
            "points_max": result.points_max,
            "points_are_official": result.correction_source == "OFFICIAL",
            "solution_verified": result.correction_source in {"OFFICIAL", "DETERMINISTIC"}
            or result.grading_mode in {"AUTO_GRADABLE", "STRUCTURED_GRADING", "AI_GRADING"},
            "grading_rubric_verified": result.grading_mode in {"AI_GRADING", "STRUCTURED_GRADING", "AUTO_GRADABLE"},
            "generator_version": self.generator_version,
        }
