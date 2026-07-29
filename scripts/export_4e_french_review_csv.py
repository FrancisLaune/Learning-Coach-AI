"""Export FR-4E French content candidates to CSV for human review."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "resources" / "content" / "quality"
OUTPUT = QUALITY / "lcai_4e_french_review_queue.csv"

SUBJECT_LABEL = "Français"
GRADE = "FR-4E"
SUBJECT = "FRENCH"


def _flatten(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " | ".join(_flatten(item) for item in value)
    if isinstance(value, dict):
        return " | ".join(f"{key}={_flatten(val)}" for key, val in value.items())
    return str(value).replace("\r", " ").replace("\n", " ")


def _recommended_action(decision: str, content_type: str) -> str:
    if decision == "PASS":
        return "Publier en production (si pas déjà fait)"
    if decision == "REJECT":
        return "Rejeter / regénérer"
    if decision == "REVIEW":
        return "Revue humaine pédagogique requise"
    return "À classifier"


def main() -> None:
    results = json.loads((QUALITY / "lcai_0012d_quality_results.json").read_text(encoding="utf-8"))
    rows = [
        item
        for item in results
        if item.get("grade") == GRADE and item.get("subject") == SUBJECT
    ]
    rows.sort(key=lambda item: (
        {"REVIEW": 0, "PASS": 1, "REJECT": 2}.get(str(item.get("decision")), 9),
        str(item.get("skill")),
        str(item.get("content_type")),
        str(item.get("code")),
    ))

    fieldnames = [
        "grade",
        "subject_code",
        "subject_label",
        "skill_code",
        "chapter_code",
        "content_type",
        "decision",
        "recommended_action",
        "status",
        "content_id",
        "version_id",
        "code",
        "difficulty",
        "structural_pass",
        "approval_candidate",
        "hard_gates_summary",
        "reasons_summary",
    ]

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in rows:
            decision = str(item.get("decision") or "")
            writer.writerow(
                {
                    "grade": item.get("grade"),
                    "subject_code": item.get("subject"),
                    "subject_label": SUBJECT_LABEL,
                    "skill_code": item.get("skill"),
                    "chapter_code": item.get("chapter"),
                    "content_type": item.get("content_type"),
                    "decision": decision,
                    "recommended_action": _recommended_action(decision, str(item.get("content_type"))),
                    "status": item.get("status"),
                    "content_id": item.get("content_id"),
                    "version_id": item.get("version_id"),
                    "code": item.get("code"),
                    "difficulty": item.get("difficulty"),
                    "structural_pass": item.get("structural_pass"),
                    "approval_candidate": item.get("approval_candidate"),
                    "hard_gates_summary": _flatten(item.get("hard_gates")),
                    "reasons_summary": _flatten(item.get("reasons")),
                }
            )

    review_count = sum(1 for item in rows if item.get("decision") == "REVIEW")
    pass_count = sum(1 for item in rows if item.get("decision") == "PASS")
    reject_count = sum(1 for item in rows if item.get("decision") == "REJECT")
    print(f"Exported {len(rows)} rows to {OUTPUT}")
    print(f"  REVIEW={review_count}  PASS={pass_count}  REJECT={reject_count}")


if __name__ == "__main__":
    main()
