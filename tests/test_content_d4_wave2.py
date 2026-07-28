from __future__ import annotations

import json
from pathlib import Path

from scripts.run_content_approval_d4_wave1 import _coverage_rows
from services.content.approval_coverage import tier
from services.content.d4_wave2 import LOT_SIZE_DEFAULT

ROOT = Path(__file__).parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"


def test_wave2_post_publication_coverage_state() -> None:
    rows = _coverage_rows()
    assert len(rows) == 372
    assert sum(tier(int(r["approved_practice"]) > 0, int(r["approved_assessment"]) > 0) == 1 for r in rows) == 176
    assert sum(tier(int(r["approved_practice"]) > 0, int(r["approved_assessment"]) > 0) == 2 for r in rows) == 16
    assert sum(tier(int(r["approved_practice"]) > 0, int(r["approved_assessment"]) > 0) == 3 for r in rows) == 180


def test_wave2_lot1_prioritizes_under_covered_subjects() -> None:
    lot1 = json.loads((QUALITY / "lcai_0012d4_wave2_lot1_skills.json").read_text(encoding="utf-8"))
    subjects = {row["subject"] for row in lot1}
    assert "HISTORY" in subjects
    assert "GEOGRAPHY" in subjects
    assert "MATHEMATICS" not in subjects
    assert len(lot1) == LOT_SIZE_DEFAULT
