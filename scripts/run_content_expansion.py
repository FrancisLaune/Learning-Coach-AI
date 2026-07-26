"""Plan and execute restartable LCAI-0012C real-generation batches."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import tomllib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.factory import (  # noqa: E402
    GeneratedContentCandidate,
    IssueSeverity,
    normalized_content_fingerprint,
)
from infrastructure.database.v2 import connect_v2  # noqa: E402
from infrastructure.generators.openai_content import OpenAIContentGenerator  # noqa: E402
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository  # noqa: E402
from services.content.expansion import CoverageGap, coverage_gaps  # noqa: E402
from services.content.factory import CandidateValidator, QualityAssessor  # noqa: E402

DEFAULT_OUTPUT = Path("resources/content/expansion/lcai_0012c_generation.jsonl")
PROMPT = Path("resources/content/expansion/prompts/lcai_0012c_v3.txt")
_local = threading.local()


def _load_local_openai_settings() -> str | None:
    path = Path(".streamlit/secrets.toml")
    if not path.exists():
        return os.getenv("OPENAI_CONTENT_MODEL")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    section = data.get("openai", {})
    key = section.get("api_key") or data.get("OPENAI_API_KEY")
    if key:
        os.environ["OPENAI_API_KEY"] = str(key)
    model = section.get("model") or data.get("OPENAI_CONTENT_MODEL")
    return str(model) if model else os.getenv("OPENAI_CONTENT_MODEL")


def _generator(repository: DuckDBContentFactoryRepository, model: str | None) -> OpenAIContentGenerator:
    current = getattr(_local, "generator", None)
    if current is None:
        current = OpenAIContentGenerator(
            repository,
            model=model,
            template_path=PROMPT,
            candidate_prefix="DRAFT-0012C-AI",
            specification_version="lcai-0012c-generation-spec-v1",
            template_version="lcai-0012c-prompt-v3",
            metadata={
                "origin_ticket": "LCAI-0012C",
                "validation_status": "technical_draft",
                "review_required": True,
            },
        )
        _local.generator = current
    return current


def gap_key(gap: CoverageGap) -> str:
    target = gap.skill.target
    return "|".join(
        (
            target.grade_code,
            target.subject_code,
            target.chapter_code,
            target.primary_skill_code,
            gap.slot.content_type.value,
            str(gap.slot.difficulty),
        )
    )


def _candidate_data(candidate: GeneratedContentCandidate) -> dict[str, Any]:
    data = asdict(candidate)
    data["answer"]["kind"] = candidate.answer.kind.value
    data["content_type"] = candidate.content_type.value
    data["pedagogical_intent"] = candidate.pedagogical_intent.value
    data["provenance"]["generated_at"] = candidate.provenance.generated_at.isoformat()
    return data


def _generate_one(gap: CoverageGap, model: str | None) -> dict[str, Any]:
    repository = DuckDBContentFactoryRepository()
    validator = CandidateValidator()
    assessor = QualityAssessor()
    request = gap.request()
    attempts: list[dict[str, Any]] = []
    started = perf_counter()
    for attempt in (1, 2):
        try:
            candidates = _generator(repository, model).generate(request)
        except Exception as error:
            attempts.append(
                {
                    "attempt": attempt,
                    "result": "PROVIDER_ERROR",
                    "reason": type(error).__name__,
                    "message": str(error)[:500],
                }
            )
            continue
        candidate = candidates[0]
        validation = validator.validate(
            candidate,
            target_errors=repository.validate_target(candidate.target),
            known_fingerprints=repository.known_fingerprints(),
        )
        quality = assessor.assess(candidate, validation)
        attempts.append(
            {
                "attempt": attempt,
                "result": "PASS" if validation.valid else "REJECT",
                "issues": [
                    {
                        "stage": issue.stage,
                        "code": issue.code,
                        "severity": issue.severity.value,
                        "message": issue.message,
                    }
                    for issue in validation.issues
                ],
                "warnings": validation.count(IssueSeverity.WARNING),
                "quality": asdict(quality),
                "candidate": _candidate_data(candidate),
            }
        )
        if validation.valid:
            break
    return {
        "ticket": "LCAI-0012C",
        "gap_key": gap_key(gap),
        "priority": gap.priority,
        "grade": gap.skill.target.grade_code,
        "subject": gap.skill.target.subject_code,
        "chapter": gap.skill.target.chapter_code,
        "skill": gap.skill.target.primary_skill_code,
        "content_type": gap.slot.content_type.value,
        "difficulty": gap.slot.difficulty,
        "attempts": attempts,
        "elapsed_seconds": round(perf_counter() - started, 3),
    }


def _completed_keys(output: Path, *, include_rejected: bool = True) -> set[str]:
    if not output.exists():
        return set()
    completed: set[str] = set()
    for line in output.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            if include_rejected or record.get("final_result") == "PERSISTED_DRAFT":
                completed.add(str(record["gap_key"]))
    return completed


def plan(
    *,
    priorities: tuple[int, ...] = (),
    grades: tuple[str, ...] = (),
    subjects: tuple[str, ...] = (),
    output: Path = DEFAULT_OUTPUT,
    retry_rejected: bool = False,
) -> tuple[CoverageGap, ...]:
    rows = DuckDBContentFactoryRepository().active_skill_coverage()
    completed = _completed_keys(output, include_rejected=not retry_rejected)
    return tuple(
        gap
        for gap in coverage_gaps(rows)
        if (not priorities or gap.priority in priorities)
        and (not grades or gap.skill.target.grade_code in grades)
        and (not subjects or gap.skill.target.subject_code in subjects)
        and gap_key(gap) not in completed
    )


def execute(gaps: tuple[CoverageGap, ...], *, output: Path, workers: int, model: str | None) -> dict[str, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    repository = DuckDBContentFactoryRepository()
    validator = CandidateValidator()
    metrics: Counter[str] = Counter()
    generated: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_generate_one, gap, model): gap for gap in gaps}
        for position, future in enumerate(as_completed(futures), 1):
            record = future.result()
            generated.append(record)
            print(f"[generated {position}/{len(gaps)}] {record['gap_key']}", flush=True)

    # DuckDB connections now all use one configuration: every remote call and
    # read-only validation connection has completed before the write phase.
    known = repository.known_fingerprints()
    anchor = connect_v2()
    try:
        stream = output.open("a", encoding="utf-8")
        for position, record in enumerate(generated, 1):
            attempts = record["attempts"]
            first = attempts[0] if attempts else {"result": "PROVIDER_ERROR"}
            metrics["requests"] += 1
            metrics[f"first_{first['result'].lower()}"] += 1
            if len(attempts) > 1:
                metrics["retries"] += 1
            selected = next(
                (attempt["candidate"] for attempt in attempts if attempt["result"] == "PASS"),
                None,
            )
            if selected is not None:
                from scripts.consolidate_content_pilot import _candidate

                candidate = _candidate(selected)
                validation = validator.validate(
                    candidate,
                    known_fingerprints=known,
                )
                exists = anchor.execute("SELECT count(*) FROM exercises WHERE code=?", [candidate.code]).fetchone()[0]
                if validation.valid and not exists:
                    repository.persist_draft(candidate, "lcai-0012c-real-expansion")
                    known[normalized_content_fingerprint(candidate.prompt)] = (
                        candidate.family_code,
                        candidate.variant_role,
                    )
                    record["final_result"] = "PERSISTED_DRAFT"
                    metrics["persisted"] += 1
                else:
                    record["final_result"] = "DUPLICATE_OR_REVALIDATION_REJECT"
                    metrics["final_rejected"] += 1
            else:
                record["final_result"] = "FINAL_REJECT"
                metrics["final_rejected"] += 1
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"[persisted {position}/{len(gaps)}] {record['gap_key']} {record['final_result']}", flush=True)
    finally:
        stream.close()
        anchor.close()
    return dict(metrics)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--priority", type=int, action="append", default=[])
    parser.add_argument("--grade", action="append", default=[])
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retry-rejected", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    gaps = plan(
        priorities=tuple(args.priority),
        grades=tuple(args.grade),
        subjects=tuple(args.subject),
        output=args.output,
        retry_rejected=args.retry_rejected,
    )
    if args.limit is not None:
        gaps = gaps[: args.limit]
    summary = {
        "active_skills": len(DuckDBContentFactoryRepository().active_skill_coverage()),
        "remaining_requests": len(gaps),
        "by_priority": dict(Counter(gap.priority for gap in gaps)),
        "by_grade": dict(Counter(gap.skill.target.grade_code for gap in gaps)),
        "by_subject": dict(Counter(gap.skill.target.subject_code for gap in gaps)),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    if not args.generate:
        return
    if not gaps:
        return
    model = _load_local_openai_settings()
    print(json.dumps(execute(gaps, output=args.output, workers=args.workers, model=model), indent=2), flush=True)


if __name__ == "__main__":
    main()
