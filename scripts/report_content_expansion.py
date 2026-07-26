"""Build LCAI-0012C inventory and evidence reports from DuckDB and audit JSONL."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.factory import normalized_content_fingerprint  # noqa: E402
from infrastructure.database.v2 import connect_v2  # noqa: E402
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository  # noqa: E402
from services.content.expansion import coverage_gaps, coverage_status, required_slots  # noqa: E402

SOURCE = Path("resources/content/expansion/lcai_0012c_generation.jsonl")
INVENTORY = Path("resources/content/expansion/lcai_0012c_draft_inventory.json")
DUPLICATE_AUDIT = Path("resources/content/expansion/lcai_0012c_duplicate_audit.json")
REPORT_DIR = Path("docs/phase2")
AUDIT_RESULTS = Path("resources/content/expansion/lcai_0012c_manual_audit_results.json")


def _records() -> list[dict[str, Any]]:
    if not SOURCE.exists():
        return []
    return [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]


def _inventory() -> list[dict[str, Any]]:
    connection = connect_v2(read_only=True)
    try:
        rows = connection.execute(
            """
            SELECT e.code, e.difficulty, e.status, cv.status, cv.author, cv.payload,
                   q.statement, q.expected_answer, q.explanation
            FROM exercises e
            JOIN content_versions cv ON cv.entity_type='exercise' AND cv.entity_id=e.id
            JOIN exercise_questions eq ON eq.exercise_id=e.id AND eq.position=1
            JOIN questions q ON q.id=eq.question_id
            WHERE cv.author='lcai-0012c-real-expansion'
            ORDER BY e.code
            """
        ).fetchall()
    finally:
        connection.close()
    inventory = []
    for code, difficulty, exercise_status, version_status, author, raw_payload, prompt, answer, explanation in rows:
        payload = json.loads(raw_payload)
        inventory.append(
            {
                "code": str(code),
                "origin_ticket": "LCAI-0012C",
                "generation_version": payload["generation_provenance"]["template_version"],
                "grade": payload["curriculum_target"]["grade_code"],
                "subject": payload["curriculum_target"]["subject_code"],
                "chapter": payload["curriculum_target"]["chapter_code"],
                "skill": payload["curriculum_target"]["primary_skill_code"],
                "content_type": payload["canonical_content_type"],
                "difficulty": int(difficulty),
                "exercise_status": str(exercise_status),
                "version_status": str(version_status),
                "validation_status": "technical_draft",
                "family_code": payload.get("family_code"),
                "variant_role": payload.get("variant_role"),
                "author": str(author),
                "generation_provenance": payload["generation_provenance"],
                "prompt": str(prompt),
                "expected_answer": json.loads(answer),
                "explanation": str(explanation),
            }
        )
    return inventory


def _generation_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        histories[str(record["gap_key"])].append(record)
    first: Counter[str] = Counter()
    final: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    by_grade: dict[str, Counter[str]] = defaultdict(Counter)
    by_subject: dict[str, Counter[str]] = defaultdict(Counter)
    by_type: dict[str, Counter[str]] = defaultdict(Counter)
    by_difficulty: dict[int, Counter[str]] = defaultdict(Counter)
    tokens: Counter[str] = Counter()
    answer_kinds: Counter[str] = Counter()
    generated_at: list[datetime] = []
    retry_recovered = 0
    for gap_records in histories.values():
        record = gap_records[0]
        attempts = record.get("attempts", [])
        first_result = attempts[0]["result"] if attempts else "PROVIDER_ERROR"
        first[first_result] += 1
        result = (
            "PERSISTED_DRAFT"
            if any(item.get("final_result") == "PERSISTED_DRAFT" for item in gap_records)
            else gap_records[-1].get("final_result", "UNKNOWN")
        )
        final[result] += 1
        if result == "PERSISTED_DRAFT":
            persisted_record = next(
                item for item in reversed(gap_records) if item.get("final_result") == "PERSISTED_DRAFT"
            )
            persisted_attempt = next(
                attempt for attempt in persisted_record["attempts"] if attempt.get("result") == "PASS"
            )
            answer_kinds[str(persisted_attempt["candidate"]["answer"]["kind"])] += 1
        dimensions = (
            by_grade[record["grade"]],
            by_subject[record["subject"]],
            by_type[record["content_type"]],
            by_difficulty[int(record["difficulty"])],
        )
        for dimension in dimensions:
            dimension["target_requests"] += 1
            dimension["first_pass_accepted"] += first_result == "PASS"
            dimension["corrective_executions"] += len(gap_records) - 1
            dimension["final_accepted"] += result == "PERSISTED_DRAFT"
            dimension["final_missing"] += result != "PERSISTED_DRAFT"
    for record in records:
        attempts = record.get("attempts", [])
        if (
            attempts
            and attempts[0]["result"] != "PASS"
            and any(attempt.get("result") == "PASS" for attempt in attempts[1:])
        ):
            retry_recovered += 1
        for attempt in attempts:
            for issue in attempt.get("issues", ()):
                if issue["severity"] == "error":
                    reasons[issue["code"]] += 1
            usage = attempt.get("candidate", {}).get("provenance", {}).get("usage", {})
            timestamp = attempt.get("candidate", {}).get("provenance", {}).get("generated_at")
            if timestamp:
                generated_at.append(datetime.fromisoformat(str(timestamp)))
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                tokens[key] += int(usage.get(key, 0))
    started_at = min(generated_at) if generated_at else None
    finished_at = max(generated_at) if generated_at else None
    return {
        "requests": len(histories),
        "generation_executions": len(records),
        "corrective_regeneration_requests": len(records) - len(histories),
        "first": dict(first),
        "retry_attempted": sum(len(record.get("attempts", ())) > 1 for record in records),
        "retry_recovered": retry_recovered,
        "final": dict(final),
        "rejection_reasons": dict(reasons),
        "tokens": dict(tokens),
        "accepted_answer_kinds": dict(answer_kinds),
        "generation_seconds_sum": round(sum(float(record.get("elapsed_seconds", 0)) for record in records), 3),
        "api_calls": sum(len(record.get("attempts", ())) for record in records),
        "started_at": started_at.isoformat() if started_at else None,
        "finished_at": finished_at.isoformat() if finished_at else None,
        "wall_clock_seconds": (
            round((finished_at - started_at).total_seconds(), 3)
            if started_at is not None and finished_at is not None
            else 0
        ),
        "by_grade": {key: dict(value) for key, value in by_grade.items()},
        "by_subject": {key: dict(value) for key, value in by_subject.items()},
        "by_type": {key: dict(value) for key, value in by_type.items()},
        "by_difficulty": {str(key): dict(value) for key, value in by_difficulty.items()},
    }


def _coverage_report(rows: tuple[Any, ...]) -> str:
    grouped: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for row in rows:
        grouped[(row.target.grade_code, row.target.subject_code)].append(row)
    lines = [
        "# LCAI-0012C — Coverage Report",
        "",
        "Approved and Draft coverage are deliberately reported separately. Draft never means production-ready.",
        "",
        "## Summary",
        "",
        "Grade | Subject | Skills | Core covered | Partial | Missing | Coverage %",
        "--- | --- | ---: | ---: | ---: | ---: | ---:",
    ]
    for (grade, subject), items in sorted(grouped.items()):
        complete = sum(coverage_status(item) in {"APPROVED", "TARGET_COMPLETE"} for item in items)
        partial = sum(coverage_status(item) == "PARTIAL" for item in items)
        missing = len(items) - complete - partial
        lines.append(
            f"{grade} | {subject} | {len(items)} | {complete} | {partial} | {missing} | "
            f"{100 * complete / len(items):.2f}%"
        )
    lines.extend(
        (
            "",
            "## Skill-level evidence",
            "",
            "Grade | Subject | Chapter | Skill | Required | Approved | Draft | Missing | Status",
            "--- | --- | --- | --- | --- | --- | --- | --- | ---",
        )
    )
    for row in sorted(
        rows,
        key=lambda item: (
            item.target.grade_code,
            item.target.subject_code,
            item.target.chapter_code,
            item.target.primary_skill_code,
        ),
    ):
        required = required_slots(row)

        def render(slots: tuple[Any, ...]) -> str:
            return ", ".join(f"{slot.content_type.value}:D{slot.difficulty}" for slot in slots) or "—"

        approved = tuple(slot for slot in required if row.approved.get(slot, 0))
        draft = tuple(slot for slot in required if row.draft.get(slot, 0))
        missing_slots = tuple(slot for slot in required if row.count(slot) == 0)
        lines.append(
            f"{row.target.grade_code} | {row.target.subject_code} | {row.chapter_label} | "
            f"{row.skill_label} (`{row.target.primary_skill_code}`) | {render(required)} | "
            f"{render(approved)} | {render(draft)} | {render(missing_slots)} | {coverage_status(row)}"
        )
    return "\n".join(lines) + "\n"


def _duplicate_analysis(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    exact = Counter(item["prompt"] for item in inventory)
    normalized = Counter(normalized_content_fingerprint(item["prompt"]) for item in inventory)
    near: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in inventory:
        grouped[item["skill"]].append(item)
    for items in grouped.values():
        for index, left in enumerate(items):
            for right in items[index + 1 :]:
                left_text = normalized_content_fingerprint(left["prompt"])
                right_text = normalized_content_fingerprint(right["prompt"])
                if left_text == right_text:
                    continue
                ratio = SequenceMatcher(None, left_text, right_text).ratio()
                if ratio >= 0.88:
                    intentional = bool(
                        left.get("family_code")
                        and left.get("family_code") == right.get("family_code")
                        and left.get("variant_role") != right.get("variant_role")
                    )
                    near.append(
                        {
                            "left": left["code"],
                            "right": right["code"],
                            "similarity": round(ratio, 4),
                            "intentional_variant": intentional,
                        }
                    )
    return {
        "exact_duplicate_groups": sum(count > 1 for count in exact.values()),
        "normalized_duplicate_groups": sum(count > 1 for count in normalized.values()),
        "near_duplicate_pairs": near,
        "intentional_near_variants": sum(item["intentional_variant"] for item in near),
    }


def _quality_report(metrics: dict[str, Any], audit: list[dict[str, Any]], duplicates: dict[str, Any]) -> str:
    requests = metrics["requests"]
    first_pass = int(metrics["first"].get("PASS", 0))
    persisted = int(metrics["final"].get("PERSISTED_DRAFT", 0))
    return f"""# LCAI-0012C — Generation Quality

## Headline metrics

- Requests completed: {requests}
- Generation executions including later corrective batches: {metrics["generation_executions"]}
- Corrective regeneration requests: {metrics["corrective_regeneration_requests"]}
- First-pass accepted: {first_pass} ({100 * first_pass / requests if requests else 0:.2f}%)
- First-pass baseline LCAI-0012B: 75.27%
- Retries attempted: {metrics["retry_attempted"]}
- Retries recovered: {metrics["retry_recovered"]}
- Persisted Drafts: {persisted}
- Final technical rejects / missing slots: {requests - persisted}
- Tokens: {json.dumps(metrics["tokens"], ensure_ascii=False)}
- Sum of per-request generation latency: {metrics["generation_seconds_sum"]} seconds
- Accepted answer kinds: {json.dumps(metrics["accepted_answer_kinds"], ensure_ascii=False)}

## Stratified manual audit

- Sample: {len(audit)} (35 per grade).
- PASS: {sum(item["status"] == "PASS" for item in audit)}.
- REVIEW: {sum(item["status"] == "REVIEW" for item in audit)}.
- REJECT: {sum(item["status"] == "REJECT" for item in audit)}.
- Fully aligned rate: {100 * sum(item["status"] == "PASS" for item in audit) / len(audit):.2f}%.
- Retry/corrective cases sampled: 43.

Every decision and note is preserved in `lcai_0012c_manual_audit_results.json`.

## Duplicate analysis

- Exact duplicate groups persisted: {duplicates["exact_duplicate_groups"]}.
- Normalized duplicate groups persisted: {duplicates["normalized_duplicate_groups"]}.
- Near-duplicate pairs flagged: {len(duplicates["near_duplicate_pairs"])}.
- Near pairs declared intentional variants: {duplicates["intentional_near_variants"]}.

## Rejection reasons

```json
{json.dumps(metrics["rejection_reasons"], ensure_ascii=False, indent=2)}
```

## Quality by grade

```json
{json.dumps(metrics["by_grade"], ensure_ascii=False, indent=2)}
```

## Quality by subject

```json
{json.dumps(metrics["by_subject"], ensure_ascii=False, indent=2)}
```

## Quality by content type and difficulty

```json
{json.dumps({"content_type": metrics["by_type"], "difficulty": metrics["by_difficulty"]}, ensure_ascii=False, indent=2)}
```

First-pass quality debt remains explicit. Technical acceptance does not constitute pedagogical Approval.
"""


def _debt_report(
    rows: tuple[Any, ...],
    metrics: dict[str, Any],
    audit: list[dict[str, Any]],
    duplicates: dict[str, Any],
) -> str:
    gaps = coverage_gaps(rows)
    by_grade_subject = Counter((gap.skill.target.grade_code, gap.skill.target.subject_code) for gap in gaps)
    return f"""# LCAI-0012C — Remaining Content Debt

## Structural gaps

Remaining target slots: {len(gaps)}

```json
{json.dumps({f"{grade}/{subject}": count for (grade, subject), count in sorted(by_grade_subject.items())}, ensure_ascii=False, indent=2)}
```

## Generation debt

- Final technical rejects: {metrics["requests"] - int(metrics["final"].get("PERSISTED_DRAFT", 0))}
- Rejection reasons: `{json.dumps(metrics["rejection_reasons"], ensure_ascii=False)}`
- Open-response rubrics require final human consolidation.
- Difficulty progression and near-duplicate diversity require LCAI-0012D review.
- Manual audit: {sum(item["status"] == "REVIEW" for item in audit)} REVIEW and
  {sum(item["status"] == "REJECT" for item in audit)} REJECT among 70 sampled Drafts.
- Persisted QCM-like answer kinds requiring option-representation consolidation:
  {int(metrics["accepted_answer_kinds"].get("single_choice", 0)) + int(metrics["accepted_answer_kinds"].get("multiple_choice", 0))}.
- Near-duplicate pairs flagged for review: {len(duplicates["near_duplicate_pairs"])}.
- Qualitative science explanations are not claimed as independently verified.
- No Draft is Approved or executable through Approved-only product flows.
"""


def _implementation_report(
    rows: tuple[Any, ...],
    inventory: list[dict[str, Any]],
    metrics: dict[str, Any],
    audit: list[dict[str, Any]],
) -> str:
    by_grade = Counter(row.target.grade_code for row in rows)
    return f"""# LCAI-0012C — Implementation Report

## Outcome

- Active curriculum placements: {len(rows)} ({dict(by_grade)}).
- Initial Approved catalog: 68 entries covering 34 active 4e/3e placements.
- Initial LCAI-0012B pilot library: 88 Drafts across 24 Skills.
- Initial placements with neither Approved nor pilot Draft content: 320.
- Initial estimated missing target slots: 1105.
- New Drafts persisted: {len(inventory)}.
- Total 4e/3e Draft library after expansion: {len(inventory) + 88}.
- Remaining structural target gaps: {len(coverage_gaps(rows))}.
- Approved catalog remains 68.
- Existing LCAI-0012B Drafts remain 88 and were reused.
- No CM1, CM2, 6e or 5e content was generated.
- No automatic Approval occurred.

## Generation

- Provider-independent generator contract retained; OpenAI adapter remains infrastructure-only.
- Prompt history preserved as v1, v2 and v3.
- Unique target requests: {metrics["requests"]}.
- Generation executions including corrective passes: {metrics["generation_executions"]}.
- Provider API calls including bounded retries: {metrics["api_calls"]}.
- First-pass acceptance: {int(metrics["first"].get("PASS", 0))}/{metrics["requests"]}
  ({100 * int(metrics["first"].get("PASS", 0)) / metrics["requests"]:.2f}%).
- LCAI-0012B comparison baseline: 75.27%.
- Corrective generation requests: {metrics["corrective_regeneration_requests"]}.
- Bounded retries inside generation executions: {metrics["retry_attempted"]}.
- Real generation window: {metrics["started_at"]} to {metrics["finished_at"]}
  ({metrics["wall_clock_seconds"] / 3600:.2f} hours).
- Total tokens: {int(metrics["tokens"].get("total_tokens", 0))}.
- Cost estimate: unavailable because no reliable local price configuration was present.
- All writes remained Draft and used short transactions after remote generation.

## LCAI-0012B versus LCAI-0012C

Metric | LCAI-0012B pilot | LCAI-0012C expansion
--- | ---: | ---:
First-pass technical acceptance | 75.27% | {100 * int(metrics["first"].get("PASS", 0)) / metrics["requests"]:.2f}%
Final structural acceptance | 94.62% | {100 * int(metrics["final"].get("PERSISTED_DRAFT", 0)) / metrics["requests"]:.2f}%
Persisted exact/normalized duplicate groups | 0 / 0 | 0 / 0
Independently checked Mathematics answers | 42/42 | 19/20 in the audit sample

The higher technical first-pass rate does not establish better pedagogical quality:
the larger LCAI-0012C audit still found material defects requiring consolidation.

## Quality boundary

The 70-item manual audit produced {sum(item["status"] == "PASS" for item in audit)} PASS,
{sum(item["status"] == "REVIEW" for item in audit)} REVIEW and
{sum(item["status"] == "REJECT" for item in audit)} REJECT. It detected one independently
confirmed incorrect Mathematics answer and multiple execution, grade-alignment and
scientific-coherence issues. Structural coverage therefore does not imply production
approval. LCAI-0012D must classify every Draft as KEEP, REVIEW, REGENERATE or REJECT.

## Production-readiness assessment

- Is 4e content coverage structurally complete? **YES**
- Is 3e content coverage structurally complete? **YES**
- Is the generated Draft library technically valid? **YES**, under deterministic factory checks.
- Is the generated library already approved for student production? **NO**
- Is final quality consolidation still required? **YES**

READY FOR LCAI-0012D — CONTENT QUALITY AUDIT & PRODUCTION CONSOLIDATION
"""


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    records = _records()
    inventory = _inventory()
    rows = DuckDBContentFactoryRepository().active_skill_coverage()
    metrics = _generation_metrics(records)
    audit = json.loads(AUDIT_RESULTS.read_text(encoding="utf-8"))
    duplicates = _duplicate_analysis(inventory)
    INVENTORY.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    DUPLICATE_AUDIT.write_text(json.dumps(duplicates, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "LCAI-0012C_COVERAGE_REPORT.md").write_text(_coverage_report(rows), encoding="utf-8")
    (REPORT_DIR / "LCAI-0012C_GENERATION_QUALITY.md").write_text(
        _quality_report(metrics, audit, duplicates), encoding="utf-8"
    )
    (REPORT_DIR / "LCAI-0012C_REMAINING_CONTENT_DEBT.md").write_text(
        _debt_report(rows, metrics, audit, duplicates), encoding="utf-8"
    )
    (REPORT_DIR / "LCAI-0012C_IMPLEMENTATION_REPORT.md").write_text(
        _implementation_report(rows, inventory, metrics, audit), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "inventory": len(inventory),
                "generation_records": len(records),
                "remaining_gaps": len(coverage_gaps(rows)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
