"""Revalidate, consolidate and optionally persist real LCAI-0012B pilot shards."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict, deque
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.factory import (  # noqa: E402
    AnswerKind,
    AnswerSpecification,
    CanonicalContentType,
    CurriculumTarget,
    GeneratedContentCandidate,
    GenerationProvenance,
    IssueSeverity,
    PedagogicalIntent,
    normalized_content_fingerprint,
)
from infrastructure.database.v2 import connect_v2  # noqa: E402
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository  # noqa: E402
from scripts.run_real_content_pilot import _plan  # noqa: E402
from services.content.factory import CandidateValidator, QualityAssessor  # noqa: E402

OUTPUT = Path("resources/content/pilot/lcai_0012b_real_candidates.json")
MANUAL_REVIEW_EXCLUSIONS = {
    "PILOT-0012B-AI-FRENCH-3E-REWRITE-WORKED_EXAMPLE-20260725213844-1": "Style reformulation is too broad for the expected grammatical rewriting focus.",
    "PILOT-0012B-AI-ENR-SVT-4E-EARTH-EARTHQUAKE-REMEDIATION-20260725213831-2": "Logarithmic magnitude calculation is above the intended 4e remediation scope.",
}


def _candidate(data: dict[str, Any]) -> GeneratedContentCandidate:
    answer = data["answer"]
    kind = AnswerKind(answer["kind"])
    computed = answer.get("independently_computed") if kind is AnswerKind.NUMERIC else None
    target = data["target"]
    provenance = data["provenance"]
    return GeneratedContentCandidate(
        code=data["code"],
        title=data["title"],
        instructions=data["instructions"],
        prompt=data["prompt"],
        answer=AnswerSpecification(
            kind,
            answer["expected"],
            tuple(answer.get("options", ())),
            answer.get("tolerance"),
            computed,
        ),
        explanation=data["explanation"],
        target=CurriculumTarget(
            target["program_code"],
            target["grade_code"],
            target["subject_code"],
            target["chapter_code"],
            target["primary_skill_code"],
            target.get("subskill_code"),
            tuple(target.get("secondary_skill_codes", ())),
        ),
        content_type=CanonicalContentType(data["content_type"]),
        pedagogical_intent=PedagogicalIntent(data["pedagogical_intent"]),
        difficulty=int(data["difficulty"]),
        provenance=GenerationProvenance(
            provenance["generator_type"],
            provenance["generator_identifier"],
            provenance["specification_version"],
            provenance["template_version"],
            provenance["curriculum_version"],
            datetime.fromisoformat(provenance["generated_at"]),
            provenance.get("latency_ms"),
            provenance.get("usage", {}),
        ),
        hints=tuple(data.get("hints", ())),
        feedback=data.get("feedback", {}),
        family_code=data.get("family_code"),
        variant_role=data.get("variant_role"),
        misconception_target=data.get("misconception_target"),
        language_code=data.get("language_code", "fr-FR"),
        metadata=data.get("metadata", {}),
    )


def _key(candidate: GeneratedContentCandidate) -> tuple[str, str, int]:
    return candidate.target.primary_skill_code, candidate.content_type.value, candidate.difficulty


def _candidate_data(candidate: GeneratedContentCandidate) -> dict[str, Any]:
    data = asdict(candidate)
    data["answer"]["kind"] = candidate.answer.kind.value
    data["content_type"] = candidate.content_type.value
    data["pedagogical_intent"] = candidate.pedagogical_intent.value
    data["provenance"]["generated_at"] = candidate.provenance.generated_at.isoformat()
    return data


def consolidate(*, persist: bool = False) -> dict[str, Any]:
    repository = DuckDBContentFactoryRepository()
    validator = CandidateValidator()
    assessor = QualityAssessor()
    shards = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(Path("resources/content/pilot").glob("lcai_0012b_real_candidates_part*.json"))
    ]
    first_batches: dict[tuple[str, str, int], deque[list[GeneratedContentCandidate]]] = defaultdict(deque)
    retry_batches: dict[tuple[str, str, int], deque[list[GeneratedContentCandidate]]] = defaultdict(deque)
    source_failures = [failure for shard in shards for failure in shard["generation_failures"]]
    for shard in shards:
        grouped: dict[tuple[str, str, int, str, int], list[GeneratedContentCandidate]] = defaultdict(list)
        for record in shard["candidates"]:
            item = _candidate(record["candidate"])
            batch_key = (*_key(item), item.provenance.generated_at.isoformat(), int(record["attempt"]))
            grouped[batch_key].append(item)
        for batch_key, items in grouped.items():
            target = first_batches if batch_key[-1] == 1 else retry_batches
            target[batch_key[:3]].append(items)

    known = repository.approved_fingerprints()
    accepted: list[GeneratedContentCandidate] = []
    audit_records: list[dict[str, Any]] = []
    first_pass_valid = first_pass_warnings = first_pass_rejected = 0
    retry_count = retry_valid = retry_rejected = 0
    for request_number, request in enumerate(_plan(), 1):
        key = (request.target.primary_skill_code, request.content_type.value, request.difficulty)
        if not first_batches[key]:
            audit_records.append({"request": request_number, "result": "GENERATION_FAILURE", "key": key})
            continue
        batch = first_batches[key].popleft()
        selected: list[GeneratedContentCandidate] = []
        for item in batch:
            report = validator.validate(
                item,
                target_errors=repository.validate_target(item.target),
                known_fingerprints=known,
            )
            if report.valid:
                selected.append(item)
                first_pass_valid += 1
                first_pass_warnings += report.count(IssueSeverity.WARNING)
            else:
                first_pass_rejected += 1
            audit_records.append(
                {
                    "request": request_number,
                    "attempt": 1,
                    "candidate_code": item.code,
                    "result": "PASS_WITH_WARNINGS"
                    if report.valid and report.count(IssueSeverity.WARNING)
                    else "PASS"
                    if report.valid
                    else "REJECT",
                    "issues": [
                        {"code": issue.code, "severity": issue.severity.value, "stage": issue.stage}
                        for issue in report.issues
                    ],
                    "quality": {
                        **assessor.assess(item, report).dimensions,
                        "score": assessor.assess(item, report).score,
                    },
                }
            )
        needed = request.quantity - len(selected)
        if needed > 0 and retry_batches[key]:
            retry_count += 1
            for item in retry_batches[key].popleft():
                if needed == 0:
                    break
                report = validator.validate(
                    item,
                    target_errors=repository.validate_target(item.target),
                    known_fingerprints=known,
                )
                if report.valid:
                    selected.append(item)
                    retry_valid += 1
                    needed -= 1
                else:
                    retry_rejected += 1
                audit_records.append(
                    {
                        "request": request_number,
                        "attempt": 2,
                        "candidate_code": item.code,
                        "result": "PASS" if report.valid else "REJECT",
                        "issues": [
                            {"code": issue.code, "severity": issue.severity.value, "stage": issue.stage}
                            for issue in report.issues
                        ],
                    }
                )
        for item in selected[: request.quantity]:
            accepted.append(item)
            known[normalized_content_fingerprint(item.prompt)] = (item.family_code, item.variant_role)

    persisted = 0
    manual_rejections = [
        {"code": item.code, "reason": MANUAL_REVIEW_EXCLUSIONS[item.code]}
        for item in accepted
        if item.code in MANUAL_REVIEW_EXCLUSIONS
    ]
    accepted = [item for item in accepted if item.code not in MANUAL_REVIEW_EXCLUSIONS]
    if persist:
        anchor = connect_v2()
        try:
            for item in accepted:
                if not repository.has_candidate(item.code):
                    repository.persist_draft(item, "lcai-0012b-real-pilot")
                    persisted += 1
        finally:
            anchor.close()

    duplicate_issues = Counter(
        issue["code"]
        for record in audit_records
        for issue in record.get("issues", ())
        if issue["code"] in {"normalized_duplicate", "intentional_variant"}
    )
    result = {
        "pilot": "LCAI-0012B",
        "generator_layer": "real_generation_pilot",
        "model": shards[0]["model"] if shards else None,
        "selected_skills": 24,
        "requested_candidates": sum(request.quantity for request in _plan()),
        "raw_generated_records_including_retries": sum(len(shard["candidates"]) for shard in shards),
        "first_pass_valid": first_pass_valid,
        "first_pass_warnings": first_pass_warnings,
        "first_pass_rejected": first_pass_rejected,
        "retries_used": retry_count,
        "post_retry_valid": len(accepted),
        "post_retry_rejected_or_missing": sum(request.quantity for request in _plan()) - len(accepted),
        "manual_pedagogical_rejections": manual_rejections,
        "retry_candidates_valid": retry_valid,
        "retry_candidates_rejected": retry_rejected,
        "source_generation_failures": source_failures,
        "persisted_now": persisted,
        "approved_count": sum(row.approved_count for row in repository.approved_coverage()),
        "total_tokens_including_discarded_retries": sum(int(shard["total_tokens"]) for shard in shards),
        "elapsed_seconds_parallel_wall_clock": max(float(shard["elapsed_seconds"]) for shard in shards),
        "accepted_by_subject": dict(Counter(item.target.subject_code for item in accepted)),
        "accepted_by_type": dict(Counter(item.content_type.value for item in accepted)),
        "accepted_by_difficulty": dict(Counter(item.difficulty for item in accepted)),
        "duplicate_analysis": dict(duplicate_issues),
        "accepted_candidates": [
            {
                "code": item.code,
                "grade": item.target.grade_code,
                "subject": item.target.subject_code,
                "chapter": item.target.chapter_code,
                "skill": item.target.primary_skill_code,
                "content_type": item.content_type.value,
                "difficulty": item.difficulty,
                "prompt": item.prompt,
                "expected_answer": item.answer.expected,
                "answer_kind": item.answer.kind.value,
                "explanation": item.explanation,
                "hints": item.hints,
                "misconception_target": item.misconception_target,
                "family_code": item.family_code,
                "variant_role": item.variant_role,
                "provenance": {
                    "generator": item.provenance.generator_type,
                    "model": item.provenance.generator_identifier,
                    "generated_at": item.provenance.generated_at.isoformat(),
                    "template_version": item.provenance.template_version,
                    "latency_ms": item.provenance.latency_ms,
                    "usage": item.provenance.usage,
                },
                "candidate_data": _candidate_data(item),
            }
            for item in accepted
        ],
        "validation_audit": audit_records,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    result = consolidate(persist=args.persist)
    print(
        json.dumps(
            {key: value for key, value in result.items() if key not in {"accepted_candidates", "validation_audit"}},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
