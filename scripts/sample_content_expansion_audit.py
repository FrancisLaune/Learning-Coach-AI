"""Create the deterministic stratified 70-item LCAI-0012C manual-audit sample."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GENERATION = Path("resources/content/expansion/lcai_0012c_generation.jsonl")
INVENTORY = Path("resources/content/expansion/lcai_0012c_draft_inventory.json")
OUTPUT = Path("resources/content/expansion/lcai_0012c_manual_audit.json")

GROUPS = {
    "mathematics": ({"MATHEMATICS"}, 10),
    "french": ({"FRENCH"}, 10),
    "languages": ({"ENGLISH", "SPANISH"}, 5),
    "humanities": ({"HISTORY", "GEOGRAPHY", "EMC"}, 5),
    "sciences": ({"SVT", "PHYSICS_CHEMISTRY"}, 5),
}


def _generation_index() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in GENERATION.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        histories[str(record["gap_key"])].append(record)
        for attempt in record.get("attempts", ()):
            candidate = attempt.get("candidate")
            if candidate is not None:
                result[str(candidate["code"])] = {
                    "gap_key": record["gap_key"],
                    "attempt": attempt["attempt"],
                    "validation_result": attempt["result"],
                }
    for metadata in result.values():
        history = histories[str(metadata["gap_key"])]
        first = history[0].get("attempts", [{}])[0].get("result")
        metadata["source_class"] = (
            "FIRST_PASS_ACCEPTED" if first == "PASS" and len(history) == 1 else "RETRY_OR_CORRECTIVE_RECOVERED"
        )
    return result


def _diverse(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    remaining = list(items)
    while remaining and len(selected) < count:
        remaining.sort(
            key=lambda item: (
                sum(
                    existing["subject"] == item["subject"]
                    and existing["content_type"] == item["content_type"]
                    and existing["difficulty"] == item["difficulty"]
                    for existing in selected
                ),
                item["source_class"] == "FIRST_PASS_ACCEPTED",
                item["subject"],
                item["content_type"],
                item["difficulty"],
                item["code"],
            )
        )
        selected.append(remaining.pop(0))
    return selected


def main() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    generation = _generation_index()
    for item in inventory:
        item.update(generation.get(item["code"], {"source_class": "FIRST_PASS_ACCEPTED"}))
    sample: list[dict[str, Any]] = []
    for grade in ("FR-4E", "FR-3E"):
        for group, (subjects, count) in GROUPS.items():
            eligible = [
                {**item, "audit_group": group}
                for item in inventory
                if item["grade"] == grade and item["subject"] in subjects
            ]
            chosen = _diverse(eligible, min(count, len(eligible)))
            sample.extend(chosen)
    audit = [
        {
            "sample_id": index,
            "code": item["code"],
            "grade": item["grade"],
            "audit_group": item["audit_group"],
            "subject": item["subject"],
            "chapter": item["chapter"],
            "skill": item["skill"],
            "content_type": item["content_type"],
            "difficulty": item["difficulty"],
            "source_class": item["source_class"],
            "prompt": item["prompt"],
            "expected_answer": item["expected_answer"],
            "explanation": item["explanation"],
            "manual_review": {
                "status": "PENDING",
                "curriculum_alignment": None,
                "answer_correctness": None,
                "difficulty_alignment": None,
                "pedagogical_quality": None,
                "notes": "",
            },
        }
        for index, item in enumerate(sample, 1)
    ]
    OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "sample_size": len(audit),
                "by_grade": {grade: sum(item["grade"] == grade for item in audit) for grade in ("FR-4E", "FR-3E")},
                "retry_or_corrective": sum(item["source_class"] == "RETRY_OR_CORRECTIVE_RECOVERED" for item in audit),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
