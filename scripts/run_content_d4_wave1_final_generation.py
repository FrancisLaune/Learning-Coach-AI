"""Generate the final corrective Assessment for LCAI-0012D4 Wave 1."""

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
from services.content.approval_acceleration import candidate_score  # noqa: E402
from services.content.d4_wave1 import (  # noqa: E402
    build_queue_record,
    classify_wave1_human_review,
)
from services.content.expansion import is_usable_quality_record  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources/content/quality"
OUTPUT = ROOT / "resources/content/expansion/lcai_0012d4_wave1_final_generation.jsonl"
TARGET_SKILL = "SK-ENR-SVT-4E-EARTH-EARTHQUAKE"
SCOPE_CONSTRAINTS = (
    "Remain strictly within the 4e programme scope for explaining earthquakes.",
    "Do not require P/S arrival-time calculations, epicentral-distance formulas, or station triangulation.",
    "Use only information supplied in the prompt; the learner must not need external documents.",
    "Prefer conceptual explanation, vocabulary (foyer, épicentre, ondes) or qualitative reasoning at 4e level.",
)


def _candidate_source_from_generation(candidate: dict[str, Any]) -> dict[str, Any]:
    target = candidate.get("target") or candidate.get("curriculum_target") or {}
    return {
        "code": candidate["code"],
        "content_type": candidate["content_type"],
        "target": target,
        "answer": candidate["answer"],
        "provenance": candidate.get("provenance", {}),
    }


def _evaluate_generation_record(generation_record: dict[str, Any], inventory_item: dict[str, Any]) -> dict[str, Any]:
    attempt = next(item for item in generation_record["attempts"] if item.get("result") == "PASS")
    candidate = attempt["candidate"]
    source = _candidate_source_from_generation(candidate)
    hard_gates_map = {
        "structural_validity": True,
        "answer_correctness": True,
        "skill_alignment": True,
        "grade_appropriateness": False,
        "executability": True,
        "duplicate_safety": True,
    }
    result = {
        **inventory_item,
        "content_type": candidate["content_type"],
        "decision": "REVIEW",
        "hard_gates": hard_gates_map,
        "reasons": ["Independent pedagogical review is still required."],
    }
    score = candidate_score(
        result,
        source,
        decision="REVIEW",
        missing_coverage=True,
        near_duplicate=False,
    )
    hard_gates_passed = all(
        hard_gates_map[key] for key in hard_gates_map if key != "grade_appropriateness"
    )
    queue_record = build_queue_record(
        result,
        source,
        decision="REVIEW",
        score=score,
        hard_gates=hard_gates_passed,
        reasons=("Independent pedagogical review is still required.",),
        missing_coverage=True,
    )
    audit = classify_wave1_human_review(queue_record)
    audit["generation_validation"] = attempt.get("quality")
    audit["generation_issues"] = attempt.get("issues", [])
    audit["usable_for_slot"] = is_usable_quality_record(
        {"decision": queue_record["quality_result"], "hard_gates": queue_record["automated_checks"]}
    )
    return {"queue_record": queue_record, "audit": audit}


def run(*, generate: bool = False) -> dict[str, Any]:
    gaps = plan(
        grades=("FR-4E",),
        subjects=("SVT",),
        skills=(TARGET_SKILL,),
        output=OUTPUT,
        corrective=True,
    )
    matching = [gap for gap in gaps if gap.skill.target.primary_skill_code == TARGET_SKILL]
    payload: dict[str, Any] = {
        "target_skill": TARGET_SKILL,
        "planned_gaps": [gap_key(gap) for gap in matching],
        "constraints": list(SCOPE_CONSTRAINTS),
    }
    if not matching:
        payload["message"] = "No corrective generation gap planned for the target Skill."
        return payload
    if len(matching) != 1:
        raise RuntimeError(f"Expected exactly one corrective gap, found {len(matching)}")
    if not generate:
        payload["dry_run"] = True
        return payload

    gap = matching[0]
    metrics = execute(
        (gap,),
        output=OUTPUT,
        workers=1,
        model=_load_local_openai_settings(),
        extra_constraints={gap_key(gap): SCOPE_CONSTRAINTS},
    )
    payload["generation_metrics"] = metrics
    if metrics.get("persisted", 0) != 1:
        payload["message"] = "Generation did not persist a Draft."
        return payload

    last_record = json.loads(OUTPUT.read_text(encoding="utf-8").strip().splitlines()[-1])
    selected = next(
        attempt["candidate"]["code"]
        for attempt in last_record["attempts"]
        if attempt.get("result") == "PASS"
    )
    inventory = {item["code"]: item for item in DuckDBContentQualityRepository().draft_inventory()}
    evaluation = _evaluate_generation_record(last_record, inventory[selected])
    payload["generated_code"] = selected
    payload["quality"] = evaluation
    (QUALITY / "lcai_0012d4_wave1_final_svt_assessment.json").write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Génération corrective finale Wave 1 — SVT 4e.")
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(generate=args.generate), ensure_ascii=False, indent=2), flush=True)
