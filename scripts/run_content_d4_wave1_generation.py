"""Generate G2 complement contents for LCAI-0012D4 Wave 1 after existing-slot approval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.content.factory import CanonicalContentType
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from scripts.run_content_approval_d4_wave1 import run as rebuild_wave1
from scripts.run_content_expansion import _generate_one
from services.content.expansion import CoverageGap, coverage_gaps

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"
MAX_BATCH = 15


def _ready_complements() -> list[dict]:
    rebuild_wave1()
    complements = json.loads((QUALITY / "lcai_0012d4_wave1_g2_complements.json").read_text(encoding="utf-8"))
    return [item for item in complements if item["ready_to_generate"]]


def _gap_for_skill(skill_code: str, slot: str) -> CoverageGap | None:
    slot_type = CanonicalContentType.PRACTICE if slot == "practice" else CanonicalContentType.ASSESSMENT
    for gap in coverage_gaps(DuckDBContentFactoryRepository().active_skill_coverage()):
        if gap.skill.target.primary_skill_code != skill_code:
            continue
        if gap.slot.content_type != slot_type:
            continue
        return gap
    return None


def run(*, batch_size: int = MAX_BATCH, dry_run: bool = False) -> dict:
    ready = _ready_complements()
    if not ready:
        return {
            "generated": 0,
            "ready": 0,
            "message": "Aucun complément G2 prêt (approbation du slot existant requise).",
        }

    selected = ready[:batch_size]
    if dry_run:
        return {
            "generated": 0,
            "ready": len(ready),
            "planned": [{"skill": item["skill"], "slot": item["generate_slot"]} for item in selected],
            "dry_run": True,
        }

    output_path = ROOT / "resources" / "content" / "expansion" / "lcai_0012d4_wave1_generation.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated = 0
    with output_path.open("a", encoding="utf-8") as handle:
        for item in selected:
            gap = _gap_for_skill(str(item["skill"]), str(item["generate_slot"]))
            if gap is None:
                continue
            record = _generate_one(gap, None)
            record["wave"] = "LCAI-0012D4-WAVE1-G2-COMPLEMENT"
            record["skill"] = item["skill"]
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            generated += 1
    return {"generated": generated, "ready": len(ready), "output": str(output_path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Générer les compléments G2 Wave 1 approuvés.")
    parser.add_argument("--batch-size", type=int, default=MAX_BATCH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(batch_size=args.batch_size, dry_run=args.dry_run), ensure_ascii=False, indent=2))
