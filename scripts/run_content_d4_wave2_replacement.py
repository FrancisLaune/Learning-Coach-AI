"""Generate one replacement Practice for a blocked Wave-2 slot."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository  # noqa: E402
from scripts.run_content_expansion import (  # noqa: E402
    _load_local_openai_settings,
    execute,
    gap_key,
    plan,
)
from services.content.d4_wave2 import (  # noqa: E402
    REVIEW_CAMPAIGN,
    evaluate_generated_candidate,
    normalize_wave2_review_item,
)

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"
EXPANSION = ROOT / "resources" / "content" / "expansion"

TARGET_SKILL = "SK-ENR-HISTORY-3E-AFTER1945-NEW_CONFLICTS"
TARGET_SLOT = "practice"
LOT_NUMBER = 1
OUTPUT = EXPANSION / "lcai_0012d4_wave2_lot1_replacement_new_conflicts_practice.jsonl"

OPEN_RESPONSE_CONSTRAINTS = (
    "Use answer_kind open_response only; do not produce QCM or choice-based items.",
    "Provide a short open question with an expected answer expressed as observable criteria.",
    "Remain strictly within 3e History programme on post-1945 conflicts.",
)


def run(*, generate: bool = False) -> dict[str, Any]:
    gaps = [
        gap
        for gap in plan(
            skills=(TARGET_SKILL,),
            output=OUTPUT,
            corrective=True,
        )
        if gap.skill.target.primary_skill_code == TARGET_SKILL
        and gap.slot.content_type.value in {"practice", "guided_practice"}
    ]
    payload: dict[str, Any] = {
        "target_skill": TARGET_SKILL,
        "target_slot": TARGET_SLOT,
        "planned_gaps": [gap_key(gap) for gap in gaps],
        "constraints": list(OPEN_RESPONSE_CONSTRAINTS),
    }
    if not gaps:
        payload["message"] = "No replacement gap planned."
        return payload
    if not generate:
        payload["dry_run"] = True
        return payload

    metrics = execute(
        tuple(gaps[:1]),
        output=OUTPUT,
        workers=1,
        model=_load_local_openai_settings(),
        extra_constraints={gap_key(gaps[0]): OPEN_RESPONSE_CONSTRAINTS},
    )
    payload["generation_metrics"] = metrics
    if metrics.get("persisted", 0) != 1:
        payload["message"] = "Replacement generation did not persist."
        return payload

    record = json.loads(OUTPUT.read_text(encoding="utf-8").strip().splitlines()[-1])
    code = next(
        attempt["candidate"]["code"]
        for attempt in record["attempts"]
        if attempt.get("result") == "PASS"
    )
    inventory = {item["code"]: item for item in DuckDBContentQualityRepository().draft_inventory()}
    evaluated = evaluate_generated_candidate(record, inventory[code])
    if evaluated is None:
        payload["message"] = "Replacement candidate failed Wave-2 QC."
        return payload

    from scripts.run_content_approval_d4_wave1 import _coverage_rows

    coverage_row = next(row for row in _coverage_rows() if row["skill"] == TARGET_SKILL)
    normalized = normalize_wave2_review_item(
        evaluated,
        coverage_row,
        candidate_source="generated",
        alternate_count=0,
        lot_number=LOT_NUMBER,
    )
    replacement = {
        "skill": TARGET_SKILL,
        "slot": TARGET_SLOT,
        "queue_record": normalized,
        "gap_key": record["gap_key"],
        "replacement_for": "blocked_multiple_choice_practice",
    }
    generated_path = QUALITY / "lcai_0012d4_wave2_lot1_generated_candidates.json"
    existing = json.loads(generated_path.read_text(encoding="utf-8")) if generated_path.exists() else []
    existing = [item for item in existing if not (item["skill"] == TARGET_SKILL and item["slot"] == TARGET_SLOT)]
    existing.append(replacement)
    generated_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["replacement"] = replacement
    payload["review_campaign"] = REVIEW_CAMPAIGN
    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(generate=args.generate), ensure_ascii=False, indent=2), flush=True)
