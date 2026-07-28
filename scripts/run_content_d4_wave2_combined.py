"""Rebuild combined Wave-2 review artifacts for lots 1+2."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.repositories.content_quality import DuckDBContentQualityRepository  # noqa: E402
from scripts.run_content_approval_d4_wave1 import _coverage_rows  # noqa: E402
from services.content.approval_coverage import tier  # noqa: E402
from services.content.d4_wave2 import (  # noqa: E402
    build_skill_review_bundles,
    load_lot_review_queues,
    prioritize_skill_bundles,
    summarize_wave2_review_bundles,
)

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"


def _patch_lot1_queue_with_replacements(queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    replacement_path = QUALITY / "lcai_0012d4_wave2_lot1_generated_candidates.json"
    if not replacement_path.exists():
        return queue
    replacements = json.loads(replacement_path.read_text(encoding="utf-8"))
    by_skill_slot = {
        (str(item["skill"]), str(item["slot"])): item["queue_record"]
        for item in replacements
    }
    patched: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in queue:
        key = (str(item["skill"]), str(item["target_slot"]))
        replacement = by_skill_slot.get(key)
        if replacement is not None:
            patched.append(replacement)
            seen.add(key)
            continue
        patched.append(item)
        seen.add(key)
    for key, replacement in by_skill_slot.items():
        if key not in seen:
            patched.append(replacement)
    return patched


def run(*, lots: tuple[int, ...] = (1, 2)) -> dict[str, Any]:
    coverage_rows = _coverage_rows()
    review_statuses = DuckDBContentQualityRepository().approval_queue_review_statuses()
    queue = load_lot_review_queues(QUALITY, lots=lots)
    if 1 in lots:
        queue = _patch_lot1_queue_with_replacements(queue)
    bundles = build_skill_review_bundles(queue, review_statuses)
    bundles = prioritize_skill_bundles(bundles, coverage_rows)
    summary = summarize_wave2_review_bundles(bundles)
    baseline = sum(
        tier(int(row["approved_practice"]) > 0, int(row["approved_assessment"]) > 0) == 1 for row in coverage_rows
    )
    payload = {
        "lots": list(lots),
        "baseline_tier1": baseline,
        "summary": summary,
        "skills": bundles,
    }
    (QUALITY / "lcai_0012d4_wave2_combined_review.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2), flush=True)
