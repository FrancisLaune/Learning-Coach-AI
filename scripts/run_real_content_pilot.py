"""Generate the bounded LCAI-0012B real-model pilot and export its audit package."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.factory import (  # noqa: E402
    CanonicalContentType,
    ContentGenerationRequest,
    GeneratedContentCandidate,
    IssueSeverity,
    PedagogicalIntent,
    normalized_content_fingerprint,
)
from infrastructure.generators.openai_content import OpenAIContentGenerator  # noqa: E402
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository  # noqa: E402
from services.content.factory import CandidateValidator, QualityAssessor  # noqa: E402
from services.content.pilot import pilot_specifications  # noqa: E402

OUTPUT = Path("resources/content/pilot/lcai_0012b_real_candidates.json")


def _intent(content_type: CanonicalContentType) -> PedagogicalIntent:
    return {
        CanonicalContentType.LESSON: PedagogicalIntent.INTRODUCE,
        CanonicalContentType.WORKED_EXAMPLE: PedagogicalIntent.MODEL,
        CanonicalContentType.GUIDED_PRACTICE: PedagogicalIntent.SCAFFOLD,
        CanonicalContentType.PRACTICE: PedagogicalIntent.PRACTICE,
        CanonicalContentType.ASSESSMENT: PedagogicalIntent.CHECK,
        CanonicalContentType.DIAGNOSTIC: PedagogicalIntent.DIAGNOSE,
        CanonicalContentType.REMEDIATION: PedagogicalIntent.REMEDIATE,
        CanonicalContentType.CHALLENGE: PedagogicalIntent.EXTEND,
        CanonicalContentType.REVISION: PedagogicalIntent.CONSOLIDATE,
    }[content_type]


def _plan() -> list[ContentGenerationRequest]:
    specifications = pilot_specifications()
    types = (
        CanonicalContentType.WORKED_EXAMPLE,
        CanonicalContentType.GUIDED_PRACTICE,
        CanonicalContentType.PRACTICE,
        CanonicalContentType.ASSESSMENT,
        CanonicalContentType.DIAGNOSTIC,
        CanonicalContentType.REMEDIATION,
        CanonicalContentType.CHALLENGE,
        CanonicalContentType.REVISION,
    )
    requests = [
        ContentGenerationRequest(
            specification.target,
            content_type,
            2,
            _intent(content_type),
            3,
            ("vary context, representation and reasoning path",),
            specification.misconception if content_type is CanonicalContentType.REMEDIATION else None,
        )
        for index, specification in enumerate(specifications)
        for content_type in (types[index % len(types)],)
    ]
    for specification in specifications[:5]:
        requests.extend(
            ContentGenerationRequest(
                specification.target,
                CanonicalContentType.PRACTICE,
                difficulty,
                PedagogicalIntent.PRACTICE,
                1,
                ("keep the same competency while increasing genuine reasoning complexity",),
            )
            for difficulty in (1, 2, 3)
        )
    for specification in specifications[:3]:
        requests.extend(
            (
                ContentGenerationRequest(
                    specification.target,
                    CanonicalContentType.DIAGNOSTIC,
                    1,
                    PedagogicalIntent.DIAGNOSE,
                    1,
                    ("distinguish this misconception from a calculation or reading error",),
                    specification.misconception,
                ),
                ContentGenerationRequest(
                    specification.target,
                    CanonicalContentType.REMEDIATION,
                    1,
                    PedagogicalIntent.REMEDIATE,
                    1,
                    ("address the same misconception diagnosed by the paired activity",),
                    specification.misconception,
                ),
            )
        )
    return requests


def _candidate_record(
    candidate: GeneratedContentCandidate,
    validation: Any,
    quality: Any,
    *,
    attempt: int,
    persisted: bool = False,
) -> dict[str, Any]:
    data = asdict(candidate)
    data["answer"]["kind"] = candidate.answer.kind.value
    data["content_type"] = candidate.content_type.value
    data["pedagogical_intent"] = candidate.pedagogical_intent.value
    data["provenance"]["generated_at"] = candidate.provenance.generated_at.isoformat()
    return {
        "candidate": data,
        "attempt": attempt,
        "validation_result": (
            "REJECT"
            if not validation.valid
            else "PASS_WITH_WARNINGS"
            if validation.count(IssueSeverity.WARNING)
            else "PASS"
        ),
        "validation_issues": [
            {
                "stage": issue.stage,
                "code": issue.code,
                "message": issue.message,
                "severity": issue.severity.value,
            }
            for issue in validation.issues
        ],
        "quality": asdict(quality),
        "persisted_as_draft": persisted,
    }


def generate(start_request: int = 1, end_request: int | None = None, output: Path = OUTPUT) -> dict[str, Any]:
    repository = DuckDBContentFactoryRepository()
    generator = OpenAIContentGenerator(repository)
    validator = CandidateValidator()
    assessor = QualityAssessor()
    full_plan = _plan()
    stop = end_request or len(full_plan)
    requests = full_plan[start_request - 1 : stop]
    records: list[dict[str, Any]] = []
    accepted: list[GeneratedContentCandidate] = []
    failures: list[dict[str, Any]] = []
    retries = 0
    known = repository.known_fingerprints()
    started = perf_counter()
    for position, request in enumerate(requests, 1):
        absolute_position = start_request + position - 1
        print(
            f"[{absolute_position}/{len(full_plan)}] {request.target.grade_code} "
            f"{request.target.primary_skill_code} {request.content_type.value} d{request.difficulty}",
            flush=True,
        )
        candidates: tuple[GeneratedContentCandidate, ...] = ()
        for attempt in (1, 2):
            try:
                candidates = generator.generate(request)
                break
            except Exception as error:
                failures.append(
                    {
                        "request": absolute_position,
                        "attempt": attempt,
                        "error_type": type(error).__name__,
                        "message": str(error)[:500],
                    }
                )
                if attempt == 1:
                    retries += 1
        if not candidates:
            continue
        retry_candidates: list[GeneratedContentCandidate] = []
        for candidate in candidates:
            validation = validator.validate(
                candidate,
                target_errors=repository.validate_target(candidate.target),
                known_fingerprints=known,
            )
            quality = assessor.assess(candidate, validation)
            records.append(_candidate_record(candidate, validation, quality, attempt=1))
            if validation.valid:
                accepted.append(candidate)
                known[normalized_content_fingerprint(candidate.prompt)] = (
                    candidate.family_code,
                    candidate.variant_role,
                )
            else:
                retry_candidates.append(candidate)
        if retry_candidates:
            retries += 1
            try:
                regenerated = generator.generate(request)
            except Exception as error:
                failures.append(
                    {
                        "request": absolute_position,
                        "attempt": 2,
                        "error_type": type(error).__name__,
                        "message": str(error)[:500],
                    }
                )
                continue
            for candidate in regenerated:
                validation = validator.validate(
                    candidate,
                    target_errors=repository.validate_target(candidate.target),
                    known_fingerprints=known,
                )
                quality = assessor.assess(candidate, validation)
                records.append(_candidate_record(candidate, validation, quality, attempt=2))
                if validation.valid:
                    accepted.append(candidate)
                    known[normalized_content_fingerprint(candidate.prompt)] = (
                        candidate.family_code,
                        candidate.variant_role,
                    )
    elapsed = perf_counter() - started
    first_pass = [record for record in records if record["attempt"] == 1]
    final_codes = {candidate.code for candidate in accepted}
    result = {
        "pilot": "LCAI-0012B",
        "generator_layer": "real_generation_pilot",
        "model": generator.model,
        "selected_skills": len(pilot_specifications()),
        "request_range": [start_request, stop],
        "planned_requests": len(requests),
        "requested_candidates": sum(request.quantity for request in requests),
        "generated_records_including_retries": len(records),
        "first_pass_pass": sum(record["validation_result"] == "PASS" for record in first_pass),
        "first_pass_pass_with_warnings": sum(
            record["validation_result"] == "PASS_WITH_WARNINGS" for record in first_pass
        ),
        "first_pass_rejected": sum(record["validation_result"] == "REJECT" for record in first_pass),
        "retries": retries,
        "final_accepted_unique": len(final_codes),
        "generation_failures": failures,
        "elapsed_seconds": round(elapsed, 3),
        "total_tokens": sum(
            int(record["candidate"]["provenance"]["usage"].get("total_tokens", 0)) for record in records
        ),
        "candidates": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--start-request", type=int, default=1)
    parser.add_argument("--end-request", type=int)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if not args.generate:
        parser.error("--generate is required; generation is never implicit")
    result = generate(args.start_request, args.end_request, args.output)
    print(
        json.dumps(
            {key: value for key, value in result.items() if key not in {"candidates", "generation_failures"}},
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
