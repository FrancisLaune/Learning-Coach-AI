"""Domain types for independent AI pedagogical pre-validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AIReviewDecision = Literal[
    "AI_PREVALIDATED",
    "AI_PREVALIDATED_HIGH",
    "AI_PREVALIDATED_WITH_WARNING",
    "TEACHER_REVIEW_REQUIRED",
    "AI_REJECTED",
]
CalibratedDecision = Literal[
    "AI_PREVALIDATED_HIGH",
    "AI_PREVALIDATED_WITH_WARNING",
    "TEACHER_REVIEW_REQUIRED",
    "AI_REJECTED",
]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
AnswerMatch = Literal["CORRECT", "ACCEPTABLE_VARIANT", "PARTIALLY_CORRECT", "INCORRECT", "AMBIGUOUS"]
ReviewerRole = Literal["PRIMARY", "SECOND_OPINION"]

AI_REVIEW_PIPELINE_VERSION = "lcai-0012d4-ai-review-v2"
CAMPAIGN_ID = "LCAI-0012D4-WAVE2"
REVIEW_MODE_OPENAI = "OPENAI_LLM"
REVIEW_MODE_LOCAL = "LOCAL_HEURISTIC"
ASSESSOR_TYPE_OPENAI = "openai"
ASSESSOR_TYPE_LOCAL = "local"


def build_review_idempotency_key(
    *,
    candidate_version_id: int,
    pipeline_version: str,
    assessor_type: str,
    model_identifier: str,
) -> str:
    return f"{candidate_version_id}:{pipeline_version}:{assessor_type}:{model_identifier}"


@dataclass(frozen=True, slots=True)
class BlindReviewInput:
    grade: str
    subject: str
    chapter: str
    skill_code: str
    content_type: str
    answer_kind: str
    question: str
    choices: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BlindReviewOutput:
    independent_answer: str
    concise_verification_reason: str
    confidence: Confidence
    reviewer_role: ReviewerRole = "PRIMARY"
    used_expected_answer: bool = False


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    match: AnswerMatch
    concise_reason: str


@dataclass(frozen=True, slots=True)
class QcmIntegrity:
    correct_option_present: bool
    uniqueness: bool
    distractor_validity: bool
    structure_valid: bool
    concise_reason: str

    @property
    def passes_mandatory(self) -> bool:
        return self.correct_option_present and self.uniqueness and self.structure_valid


@dataclass(frozen=True, slots=True)
class PedagogicalScores:
    answer_correctness: int
    explanation_correctness: int
    question_clarity: int
    grade_appropriateness: int
    skill_alignment: int
    curriculum_alignment: int
    pedagogical_quality: int
    executability: int
    ambiguity: int
    factual_reliability: int

    def as_dict(self) -> dict[str, int]:
        return {
            "answer_correctness": self.answer_correctness,
            "explanation_correctness": self.explanation_correctness,
            "question_clarity": self.question_clarity,
            "grade_appropriateness": self.grade_appropriateness,
            "skill_alignment": self.skill_alignment,
            "curriculum_alignment": self.curriculum_alignment,
            "pedagogical_quality": self.pedagogical_quality,
            "executability": self.executability,
            "ambiguity": self.ambiguity,
            "factual_reliability": self.factual_reliability,
        }


@dataclass(frozen=True, slots=True)
class AIPedagogicalReviewRecord:
    candidate_version_id: int
    campaign_id: str
    grade: str
    subject: str
    skill_code: str
    content_type: str
    reviewer_model: str
    review_timestamp: str
    ai_review_pipeline_version: str
    blind_answer: str
    expected_answer_match: AnswerMatch
    scores: PedagogicalScores
    confidence: Confidence
    decision: AIReviewDecision
    fact_check_required: bool
    concise_reason: str
    qcm_integrity: QcmIntegrity | None = None
    second_opinion_used: bool = False
    reviewer_independence_note: str = "Blind Pass A excluded expected answer and generator reasoning."
    provenance: str = "AI_PREVALIDATION"
    extra: dict[str, Any] = field(default_factory=dict)

    def audit_dict(self) -> dict[str, Any]:
        assessor_type = str(self.extra.get("assessor_type", ASSESSOR_TYPE_OPENAI))
        review_mode = str(self.extra.get("review_mode", REVIEW_MODE_OPENAI))
        authoritative = bool(self.extra.get("authoritative_ai_review", True))
        idempotency_key = build_review_idempotency_key(
            candidate_version_id=self.candidate_version_id,
            pipeline_version=self.ai_review_pipeline_version,
            assessor_type=assessor_type,
            model_identifier=self.reviewer_model,
        )
        payload = {
            "candidate_version_id": self.candidate_version_id,
            "campaign_id": self.campaign_id,
            "grade": self.grade,
            "subject": self.subject,
            "skill_code": self.skill_code,
            "content_type": self.content_type,
            "reviewer_model": self.reviewer_model,
            "review_timestamp": self.review_timestamp,
            "ai_review_pipeline_version": self.ai_review_pipeline_version,
            "review_idempotency_key": idempotency_key,
            "assessor_type": assessor_type,
            "review_mode": review_mode,
            "authoritative_ai_review": authoritative,
            "blind_answer": self.blind_answer,
            "expected_answer_match": self.expected_answer_match,
            "confidence": self.confidence,
            "decision": self.decision,
            "fact_check_required": self.fact_check_required,
            "concise_reason": self.concise_reason,
            "provenance": self.provenance,
            "second_opinion_used": self.second_opinion_used,
            "reviewer_independence_note": self.reviewer_independence_note,
        }
        payload.update(self.scores.as_dict())
        if self.qcm_integrity is not None:
            payload["qcm_integrity"] = {
                "QCM_CORRECT_OPTION_PRESENT": self.qcm_integrity.correct_option_present,
                "QCM_UNIQUENESS": self.qcm_integrity.uniqueness,
                "QCM_DISTRACTOR_VALIDITY": self.qcm_integrity.distractor_validity,
                "QCM_STRUCTURE_VALID": self.qcm_integrity.structure_valid,
                "concise_reason": self.qcm_integrity.concise_reason,
            }
        payload.update(self.extra)
        return payload
