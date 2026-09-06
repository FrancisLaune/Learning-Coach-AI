"""LCAI-0034 — offline Éduscol archive enrichment (no runtime scrape)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.archives import load_manifest

ACCESSIBILITY_MARKERS = (
    "arial 16",
    "arial 20",
    "arial 24",
    "braille",
    "dys",
    "accessibilite",
    "accessibilité",
)


def detect_document_variant(name_or_url: str) -> str:
    lowered = (name_or_url or "").casefold()
    for marker in ACCESSIBILITY_MARKERS:
        if marker in lowered:
            return marker.upper().replace(" ", "_")
    return "STANDARD"


def exam_identity_from_entry(entry: dict[str, Any]) -> str:
    return str(
        entry.get("exam_identity")
        or entry.get("base_exam_identifier")
        or f"{entry.get('year')}-{entry.get('session')}-{entry.get('zone')}-{entry.get('series')}-{entry.get('subject')}"
    )


def enrich_archives_from_manifest(store: BrevetContentStore) -> dict[str, Any]:
    """Enrich archive metadata without row UPDATEs on FK parents (DuckDB limitation)."""
    manifest = load_manifest()
    entries = manifest.get("entries", [])
    identities: set[str] = set()
    updated = 0
    for entry in entries:
        identity = exam_identity_from_entry(entry)
        identities.add(identity)
        variant = detect_document_variant(str(entry.get("notes") or entry.get("label") or ""))
        base_id = entry.get("base_exam_identifier")
        row = store.fetchone(
            "SELECT archive_id, source_provider, exam_identity FROM exam_archives_ref WHERE base_exam_identifier=?",
            [base_id],
        )
        if not row:
            continue
        updated += 1
        store.execute(
            """
            INSERT INTO referential_events(event_type, entity_ref, detail)
            VALUES ('ArchiveDiscovered', ?, ?)
            """,
            [
                str(row[0]),
                f"identity={identity};variant={variant};provider={row[1] or 'EDUSCOL'};exam_identity={row[2] or identity}",
            ],
        )
    # Ensure default provider visible for NULL legacy rows via view-friendly coalesce in reports.
    null_provider = store.fetchone(
        "SELECT COUNT(*) FROM exam_archives_ref WHERE source_provider IS NULL"
    )
    return {
        "manifest_entries": len(entries),
        "archives_enriched": updated,
        "unique_exam_identities": len(identities),
        "null_source_provider_rows": int(null_provider[0]) if null_provider else 0,
        "note": "Parent-table UPDATEs skipped due to DuckDB FK update limitations; provider defaults to EDUSCOL.",
    }


def ingest_local_archive_document(
    store: BrevetContentStore,
    *,
    archive_id: int,
    local_path: Path,
    extracted_questions: list[dict[str, Any]],
    parser_version: str = "lcai-0034-local-v1",
) -> dict[str, Any]:
    """Persist a locally downloaded/parsed official document (offline admin)."""
    raw = local_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    store.execute(
        """
        UPDATE exam_archives_ref SET
          source_hash=?,
          downloaded_at=now(),
          parser_version=?,
          status='PARSED',
          import_status='PARSED',
          official_document_ref=?,
          updated_at=now()
        WHERE archive_id=?
        """,
        [digest, parser_version, str(local_path), archive_id],
    )
    store.execute(
        """
        INSERT INTO referential_events(event_type, entity_ref, detail)
        VALUES ('ArchiveDownloaded', ?, ?)
        """,
        [str(archive_id), digest],
    )
    section = store.fetchone(
        "SELECT section_id FROM exam_archive_sections_ref WHERE archive_id=? ORDER BY position LIMIT 1",
        [archive_id],
    )
    if not section:
        store.execute(
            """
            INSERT INTO exam_archive_sections_ref(archive_id, position, title, section_type)
            VALUES (?, 1, 'Partie principale', 'MAIN')
            """,
            [archive_id],
        )
        section = store.fetchone(
            "SELECT section_id FROM exam_archive_sections_ref WHERE archive_id=? ORDER BY position LIMIT 1",
            [archive_id],
        )
    section_id = int(section[0])
    imported = 0
    for idx, q in enumerate(extracted_questions, start=1):
        existing = store.fetchone(
            "SELECT archive_question_id FROM exam_archive_questions_ref WHERE section_id=? AND position=?",
            [section_id, idx],
        )
        if existing:
            continue
        store.execute(
            """
            INSERT INTO exam_archive_questions_ref(
              section_id, position, original_question_reference, statement, expected_answer,
              correction, points, curriculum_2027_compatible, extraction_status, validation_status,
              support_required, correction_source, source_locator
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'EXTRACTED', 'REVIEW', ?, ?, ?)
            """,
            [
                section_id,
                idx,
                q.get("reference") or f"Q{idx}",
                q.get("statement"),
                q.get("expected_answer"),
                q.get("correction"),
                q.get("points"),
                q.get("curriculum_2027_compatible", "REVIEW"),
                bool(q.get("support_required", False)),
                q.get("correction_source", "NONE"),
                q.get("source_locator"),
            ],
        )
        imported += 1
        store.execute(
            """
            INSERT INTO referential_events(event_type, entity_ref, detail)
            VALUES ('ArchiveQuestionExtracted', ?, ?)
            """,
            [str(archive_id), f"pos={idx}"],
        )
    store.execute(
        """
        INSERT INTO referential_events(event_type, entity_ref, detail)
        VALUES ('ArchiveParsed', ?, ?)
        """,
        [str(archive_id), f"questions={imported}"],
    )
    return {"archive_id": archive_id, "sha256": digest, "questions_imported": imported}
