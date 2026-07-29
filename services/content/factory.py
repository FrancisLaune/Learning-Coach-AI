"""Application services for safe generation, validation and coverage analysis."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Protocol

from domain.content.factory import (
    AnswerKind,
    CanonicalContentType,
    ContentGenerationRequest,
    ContentGenerator,
    FactoryValidationIssue,
    FactoryValidationReport,
    GeneratedContentCandidate,
    GenerationReport,
    IssueSeverity,
    QualityAssessment,
    normalized_content_fingerprint,
)


class ContentFactoryRepository(Protocol):
    def validate_target(self, target: object) -> tuple[str, ...]: ...
    def known_fingerprints(self) -> dict[str, tuple[str | None, str | None]]: ...
    def persist_draft(self, candidate: GeneratedContentCandidate, author: str) -> None: ...


@dataclass(frozen=True, slots=True)
class CoverageRow:
    program_code: str
    grade_code: str
    subject_code: str
    chapter_code: str
    skill_code: str
    approved_count: int
    by_type: dict[str, int]
    by_difficulty: dict[int, int]


class CoverageRepository(Protocol):
    def approved_coverage(self) -> tuple[CoverageRow, ...]: ...


class CandidateValidator:
    """Deterministic checks; uncertain pedagogy remains explicitly reviewable."""

    _unsafe = re.compile(r"<\s*script|javascript:|(?:^|\s)(?:DROP|DELETE)\s+TABLE", re.IGNORECASE)

    def validate(
        self,
        candidate: GeneratedContentCandidate,
        *,
        target_errors: tuple[str, ...] = (),
        known_fingerprints: dict[str, tuple[str | None, str | None]] | None = None,
    ) -> FactoryValidationReport:
        issues: list[FactoryValidationIssue] = []
        for error in target_errors:
            issues.append(self._issue("curriculum", "invalid_curriculum_target", error))
        required = {
            "code": candidate.code,
            "title": candidate.title,
            "prompt": candidate.prompt,
            "explanation": candidate.explanation,
        }
        for name, value in required.items():
            if not value.strip():
                issues.append(self._issue("schema", f"missing_{name}", f"{name} is required"))
        if candidate.difficulty not in (1, 2, 3):
            issues.append(self._issue("difficulty", "invalid_difficulty", "Difficulty must be 1, 2 or 3"))
        if candidate.answer.expected in (None, "", [], {}) and candidate.answer.kind is not AnswerKind.OPEN_RESPONSE:
            issues.append(self._issue("answer", "missing_answer", "A deterministic expected answer is required"))
        self._validate_answer(candidate, issues)
        body = " ".join((candidate.instructions, candidate.prompt, candidate.explanation))
        if self._unsafe.search(body):
            issues.append(self._issue("safety", "unsafe_content", "Executable or destructive content is forbidden"))
        if candidate.content_type is CanonicalContentType.ASSESSMENT and candidate.hints:
            issues.append(
                self._issue("pedagogy", "assessment_has_hints", "Assessment hints require review", warning=True)
            )
        if not candidate.hints and candidate.content_type not in {
            CanonicalContentType.ASSESSMENT,
            CanonicalContentType.DIAGNOSTIC,
        }:
            issues.append(self._issue("pedagogy", "no_optional_hint", "No optional hint supplied", info=True))
        if len(candidate.explanation.strip()) < 20:
            issues.append(self._issue("pedagogy", "short_explanation", "Explanation may be too short", warning=True))
        fingerprint = normalized_content_fingerprint(candidate.prompt)
        known = (known_fingerprints or {}).get(fingerprint)
        if known:
            family, role = known
            intentional = bool(
                candidate.family_code
                and family == candidate.family_code
                and candidate.variant_role
                and role != candidate.variant_role
            )
            if intentional:
                issues.append(
                    self._issue(
                        "duplicate",
                        "intentional_variant",
                        "Normalized wording matches a declared pedagogical family variant",
                        info=True,
                    )
                )
            else:
                issues.append(self._issue("duplicate", "normalized_duplicate", "Duplicate candidate detected"))
        return FactoryValidationReport(tuple(issues))

    @staticmethod
    def _issue(
        stage: str, code: str, message: str, *, warning: bool = False, info: bool = False
    ) -> FactoryValidationIssue:
        severity = IssueSeverity.INFO if info else IssueSeverity.WARNING if warning else IssueSeverity.ERROR
        return FactoryValidationIssue(stage, code, message, severity)

    def _validate_answer(self, candidate: GeneratedContentCandidate, issues: list[FactoryValidationIssue]) -> None:
        answer = candidate.answer
        if answer.tolerance is not None and answer.tolerance < 0:
            issues.append(self._issue("answer", "invalid_tolerance", "Tolerance cannot be negative"))
        if answer.independently_computed is not None:
            consistent = answer.expected == answer.independently_computed
            if answer.kind is AnswerKind.NUMERIC:
                numeric_expected = _numeric_value(answer.expected)
                independently_computed = _numeric_value(answer.independently_computed)
                if numeric_expected is None or independently_computed is None:
                    consistent = False
                else:
                    consistent = math.isclose(
                        numeric_expected,
                        independently_computed,
                        abs_tol=answer.tolerance or _rounding_tolerance(answer.expected),
                    )
            if not consistent:
                issues.append(self._issue("answer", "answer_contradiction", "Independent computation disagrees"))
        if answer.kind is AnswerKind.NUMERIC and _numeric_value(answer.expected) is None:
            issues.append(self._issue("answer", "invalid_numeric_format", "Numeric answer must contain one value"))
        if answer.kind in {AnswerKind.SINGLE_CHOICE, AnswerKind.MULTIPLE_CHOICE}:
            normalized = [normalized_content_fingerprint(option) for option in answer.options]
            if len(normalized) < 2 or len(set(normalized)) != len(normalized):
                issues.append(self._issue("answer", "invalid_choices", "Choices must be distinct"))
            expected = (
                {str(answer.expected)} if answer.kind is AnswerKind.SINGLE_CHOICE else {str(x) for x in answer.expected}
            )
            if not expected.issubset(set(answer.options)):
                issues.append(self._issue("answer", "answer_not_in_choices", "Correct answer must reference a choice"))


_NUMERIC_ANSWER = re.compile(
    r"^\s*(-?\d+(?:[.,]\d+)?(?:\s*/\s*-?\d+(?:[.,]\d+)?)?)"
    r"\s*(?:€|%|°|[A-Za-zÀ-ÿ]+(?:[²³])?(?:/[A-Za-zÀ-ÿ]+(?:[²³])?)?)?"
    r"(?:\s*\(arrondi[^)]*\))?\s*$",
    re.IGNORECASE,
)


def _numeric_value(value: object) -> float | None:
    match = _NUMERIC_ANSWER.fullmatch(str(value))
    if match is None:
        return None
    raw = match.group(1).replace(" ", "").replace(",", ".")
    try:
        if "/" in raw:
            numerator, denominator = raw.split("/", 1)
            return float(numerator) / float(denominator)
        return float(raw)
    except (ValueError, ZeroDivisionError):
        return None


def _rounding_tolerance(value: object) -> float:
    match = _NUMERIC_ANSWER.fullmatch(str(value))
    if match is None or "/" in match.group(1):
        return 0.0
    normalized = match.group(1).replace(",", ".")
    decimals = len(normalized.rsplit(".", 1)[1]) if "." in normalized else 0
    return 0.5 * 10 ** (-decimals)


class QualityAssessor:
    def assess(self, candidate: GeneratedContentCandidate, report: FactoryValidationReport) -> QualityAssessment:
        dimensions = {
            "curriculum_alignment": 100 if not any(i.stage == "curriculum" for i in report.issues) else 0,
            "answer_integrity": 100 if not any(i.stage == "answer" for i in report.issues) else 0,
            "pedagogical_completeness": max(0, 100 - 20 * sum(i.stage == "pedagogy" for i in report.issues)),
            "traceability": 100
            if candidate.provenance.template_version and candidate.provenance.curriculum_version
            else 40,
            "safety": 100 if not any(i.stage == "safety" for i in report.issues) else 0,
        }
        blockers = tuple(i.code for i in report.issues if i.severity is IssueSeverity.ERROR)
        return QualityAssessment(dimensions, round(sum(dimensions.values()) / len(dimensions)), not blockers, blockers)


class ContentFactoryService:
    def __init__(
        self,
        generator: ContentGenerator,
        repository: ContentFactoryRepository,
        validator: CandidateValidator | None = None,
    ) -> None:
        self.generator = generator
        self.repository = repository
        self.validator = validator or CandidateValidator()

    def generate_drafts(self, request: ContentGenerationRequest, author: str) -> GenerationReport:
        target_errors = self.repository.validate_target(request.target)
        if target_errors:
            return GenerationReport(request.quantity, 0, 0, 0, request.quantity, 0, 0, failure_reasons=target_errors)
        candidates = self.generator.generate(request)
        known = self.repository.known_fingerprints()
        valid = warnings = rejected = duplicates = persisted = 0
        codes: list[str] = []
        failures: list[str] = []
        for candidate in candidates:
            report = self.validator.validate(
                candidate, target_errors=self.repository.validate_target(candidate.target), known_fingerprints=known
            )
            warnings += report.count(IssueSeverity.WARNING)
            if any(i.code == "normalized_duplicate" for i in report.issues):
                duplicates += 1
            if not report.valid:
                rejected += 1
                failures.extend(i.code for i in report.issues if i.severity is IssueSeverity.ERROR)
                continue
            valid += 1
            self.repository.persist_draft(candidate, author)
            persisted += 1
            codes.append(candidate.code)
            known[normalized_content_fingerprint(candidate.prompt)] = (candidate.family_code, candidate.variant_role)
        return GenerationReport(
            request.quantity,
            len(candidates),
            valid,
            warnings,
            rejected,
            duplicates,
            persisted,
            tuple(codes),
            tuple(failures),
        )

    def generate_runtime_candidates(
        self, request: ContentGenerationRequest, quantity: int | None = None
    ) -> tuple[GeneratedContentCandidate, ...]:
        """Validate generated candidates without persisting Approved/Draft catalogue rows."""
        target_quantity = request.quantity if quantity is None else quantity
        runtime_request = ContentGenerationRequest(
            request.target,
            request.content_type,
            request.difficulty,
            request.pedagogical_intent,
            quantity=target_quantity,
            variation_constraints=request.variation_constraints,
            misconception_target=request.misconception_target,
            language_code=request.language_code,
        )
        target_errors = self.repository.validate_target(runtime_request.target)
        if target_errors:
            return ()
        candidates = self.generator.generate(runtime_request)
        accepted: list[GeneratedContentCandidate] = []
        known = self.repository.known_fingerprints()
        for candidate in candidates:
            report = self.validator.validate(
                candidate,
                target_errors=self.repository.validate_target(candidate.target),
                known_fingerprints=known,
            )
            if not report.valid:
                continue
            accepted.append(candidate)
            known[normalized_content_fingerprint(candidate.prompt)] = (candidate.family_code, candidate.variant_role)
            if len(accepted) >= target_quantity:
                break
        return tuple(accepted)


class ContentCoverageService:
    def __init__(self, repository: CoverageRepository) -> None:
        self.repository = repository

    def rows(self) -> tuple[CoverageRow, ...]:
        return self.repository.approved_coverage()

    def zero_coverage(self) -> tuple[CoverageRow, ...]:
        return tuple(row for row in self.rows() if row.approved_count == 0)

    def gaps(self) -> dict[str, tuple[str, ...]]:
        rows = self.rows()
        return {
            "zero_approved": tuple(row.skill_code for row in rows if row.approved_count == 0),
            "missing_practice": tuple(row.skill_code for row in rows if row.by_type.get("practice", 0) == 0),
            "missing_assessment": tuple(row.skill_code for row in rows if row.by_type.get("assessment", 0) == 0),
            "missing_remediation": tuple(row.skill_code for row in rows if row.by_type.get("remediation", 0) == 0),
        }
