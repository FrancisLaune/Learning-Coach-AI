"""Repair missing Wave-2 campaign metadata from authoritative evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from services.content.d4_wave2 import (
    REVIEW_CAMPAIGN,
    REVIEW_QUEUE_STATUS_ACTIVE,
    WAVE_BAND_TIER3,
)

REPAIR_PROVENANCE = "lcai-0012d4-wave2-campaign-metadata-repair-v1"


def _load_wave2_version_index(quality_dir: Path) -> dict[int, dict[str, Any]]:
    index: dict[int, dict[str, Any]] = {}
    for lot_number in (1, 2):
        for filename in (
            f"lcai_0012d4_wave2_lot{lot_number}_review_queue.json",
            f"lcai_0012d4_wave2_lot{lot_number}_generated_candidates.json",
        ):
            path = quality_dir / filename
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if filename.endswith("_generated_candidates.json"):
                for entry in payload:
                    record = entry.get("queue_record") or entry
                    version_id = int(record["version_id"])
                    index[version_id] = {
                        "lot_number": lot_number,
                        "candidate_source": "generated",
                        "target_slot": record.get("content_type") or entry.get("slot"),
                    }
            else:
                for record in payload:
                    version_id = int(record["version_id"])
                    index[version_id] = {
                        "lot_number": lot_number,
                        "candidate_source": str(record.get("candidate_source", "existing")),
                        "target_slot": record.get("target_slot") or record.get("content_type"),
                    }
    return index


def repair_wave2_campaign_metadata(
    item: dict[str, Any],
    audit: dict[str, Any],
    *,
    quality_dir: Path,
) -> dict[str, Any]:
    """Restore Wave-2 campaign fields when authoritative evidence proves membership."""
    if str(item.get("review_campaign", "")) == REVIEW_CAMPAIGN:
        return item
    campaign_id = str(audit.get("campaign_id", ""))
    if campaign_id != REVIEW_CAMPAIGN:
        return item
    version_id = int(item["version_id"])
    index = _load_wave2_version_index(quality_dir)
    queue_evidence = index.get(version_id)
    if queue_evidence is None and not audit.get("authoritative_ai_review"):
        return item

    repaired = dict(item)
    repaired["review_campaign"] = REVIEW_CAMPAIGN
    repaired["review_queue_status"] = REVIEW_QUEUE_STATUS_ACTIVE
    repaired["wave_band"] = WAVE_BAND_TIER3
    if queue_evidence:
        repaired["lot_number"] = queue_evidence["lot_number"]
        repaired["candidate_source"] = queue_evidence["candidate_source"]
        if not repaired.get("target_slot"):
            repaired["target_slot"] = queue_evidence.get("target_slot")
    else:
        repaired.setdefault("candidate_source", "generated")
        repaired.setdefault("lot_number", 1)
    repaired["campaign_metadata_repair"] = {
        "repair_version": REPAIR_PROVENANCE,
        "repaired_at": datetime.now(UTC).isoformat(),
        "authoritative_campaign_id": campaign_id,
        "authoritative_review_idempotency_key": audit.get("review_idempotency_key"),
        "evidence_sources": [
            source
            for source in (
                "authoritative_ai_review",
                "wave2_lot_queue" if queue_evidence else None,
            )
            if source
        ],
        "version_id": version_id,
        "skill_code": audit.get("skill_code") or item.get("skill"),
    }
    return repaired
