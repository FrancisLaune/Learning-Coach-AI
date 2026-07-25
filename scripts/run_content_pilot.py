"""Run the bounded LCAI-0012B deterministic pilot once."""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.factory import (
    AnswerSpecification,
    CanonicalContentType,
    ContentGenerationRequest,
    GeneratedContentCandidate,
    IssueSeverity,
    PedagogicalIntent,
    normalized_content_fingerprint,
)
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from services.content.factory import CandidateValidator, QualityAssessor
from services.content.pilot import DeterministicPilotGenerator, pilot_specifications


def main() -> None:
    specifications = pilot_specifications()
    generator = DeterministicPilotGenerator(specifications)
    repository = DuckDBContentFactoryRepository()
    validator = CandidateValidator()
    assessor = QualityAssessor()
    canonical: list[GeneratedContentCandidate] = []
    for specification in specifications:
        for content_type, intent, difficulty in (
            (CanonicalContentType.GUIDED_PRACTICE, PedagogicalIntent.SCAFFOLD, 1),
            (CanonicalContentType.WORKED_EXAMPLE, PedagogicalIntent.MODEL, 2),
            (CanonicalContentType.ASSESSMENT, PedagogicalIntent.CHECK, 3),
            (CanonicalContentType.REMEDIATION, PedagogicalIntent.REMEDIATE, 1),
        ):
            request = ContentGenerationRequest(specification.target, content_type, difficulty, intent)
            canonical.extend(generator.generate(request))

    first_pass = list(canonical)
    for index in (10, 61):
        original = first_pass[index]
        first_pass[index] = replace(
            original,
            answer=AnswerSpecification(
                original.answer.kind,
                original.answer.expected,
                original.answer.options,
                original.answer.tolerance,
                "__deliberately_inconsistent_pilot_answer__",
            ),
        )

    known: dict[str, tuple[str | None, str | None]] = {}
    accepted = []
    rejected: list[tuple[int, tuple[str, ...]]] = []
    warning_count = 0
    for index, item in enumerate(first_pass):
        report = validator.validate(
            item,
            target_errors=repository.validate_target(item.target),
            known_fingerprints=known,
        )
        warning_count += report.count(IssueSeverity.WARNING)
        if report.valid:
            accepted.append(item)
            known[normalized_content_fingerprint(item.prompt)] = (item.family_code, item.variant_role)
        else:
            rejected.append(
                (index, tuple(issue.code for issue in report.issues if issue.severity is IssueSeverity.ERROR))
            )

    retry_accepted = []
    for index, _reasons in rejected:
        repaired = canonical[index]
        report = validator.validate(
            repaired,
            target_errors=repository.validate_target(repaired.target),
            known_fingerprints=known,
        )
        if report.valid:
            retry_accepted.append(repaired)
            known[normalized_content_fingerprint(repaired.prompt)] = (repaired.family_code, repaired.variant_role)

    final_candidates = accepted + retry_accepted
    technically_persistable = 0
    for item in final_candidates:
        quality = assessor.assess(item, validator.validate(item, target_errors=repository.validate_target(item.target)))
        if quality.eligible_for_review:
            technically_persistable += 1

    result = {
        "selected_skills": len(specifications),
        "requested": len(canonical),
        "generated": len(first_pass),
        "first_pass_valid": len(accepted),
        "first_pass_warnings": warning_count,
        "first_pass_rejected": len(rejected),
        "rejection_reasons": dict(Counter(reason for _, reasons in rejected for reason in reasons)),
        "retries": len(rejected),
        "post_retry_valid": len(final_candidates),
        "post_retry_rejected": len(canonical) - len(final_candidates),
        "technically_persistable": technically_persistable,
        "persisted_now": 0,
        "persistence_policy": "deterministic test candidates never enter the production pilot database",
        "approved_total": sum(row.approved_count for row in repository.approved_coverage()),
        "by_type": dict(Counter(item.content_type.value for item in final_candidates)),
        "by_difficulty": dict(Counter(item.difficulty for item in final_candidates)),
        "by_subject": dict(Counter(item.target.subject_code for item in final_candidates)),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
