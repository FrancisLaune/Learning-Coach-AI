"""Official DNB archive discovery/import (offline-safe pipeline)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import PROJECT_ROOT
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.models import fingerprint_text

MANIFEST_PATH = PROJECT_ROOT / "data" / "dnb_archive_manifest.json"

# EduScol landing pages (discovery only — runtime must not scrape).
EDUSCOL_DNB_HUB = "https://eduscol.education.fr/cid133202/diplome-national-du-brevet.html"


@dataclass(frozen=True, slots=True)
class ArchiveImportResult:
    archive_id: int | None
    status: str
    message: str
    duplicate: bool = False


def default_manifest_entries() -> list[dict[str, Any]]:
    years = (2018, 2019, 2021, 2022, 2023, 2024, 2025, 2026)
    subjects = (
        ("mathematics", "MATHEMATICS", "Mathématiques"),
        ("french", "FRENCH", "Français"),
        ("history_geography_emc", "HISTORY", "Histoire-Géographie-EMC"),
        ("sciences", "PHYSICS_CHEMISTRY", "Sciences"),
    )
    zones = ("metropole", "centres_etrangers")
    entries: list[dict[str, Any]] = []
    for year in years:
        for zone in zones:
            for subject_key, code, label in subjects:
                entries.append(
                    {
                        "year": year,
                        "session": "normale",
                        "zone": zone,
                        "series": "generale",
                        "subject": subject_key,
                        "subject_code": code,
                        "label": label,
                        "source_url": EDUSCOL_DNB_HUB,
                        "correction_url": EDUSCOL_DNB_HUB,
                        "status": "DISCOVERED",
                        "base_exam_identifier": f"{year}-normale-{zone}-generale-{subject_key}",
                        "notes": "Source hub Éduscol — PDF à télécharger hors runtime puis importer.",
                    }
                )
    return entries


def write_manifest(path: Path | None = None) -> Path:
    target = path or MANIFEST_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target
    payload = {
        "version": "DNB-ARCHIVE-MANIFEST-V1",
        "source_authority": "Éduscol — Ministère de l'Éducation nationale",
        "entries": default_manifest_entries(),
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    target = write_manifest(path)
    return json.loads(target.read_text(encoding="utf-8"))


def ingest_dnb_archive(
    *,
    source_url: str,
    year: int,
    session: str,
    zone: str,
    series: str,
    subject: str,
    store: BrevetContentStore | None = None,
    local_text: str | None = None,
) -> ArchiveImportResult:
    """Register an archive and optionally import questions from local extracted text.

    Does not scrape the web. Provide `local_text` after offline download/parse.
    """
    store = store or BrevetContentStore()
    subject_code = subject.upper()
    aliases = {
        "MATHEMATICS": "MATHEMATICS",
        "MATHS": "MATHEMATICS",
        "FRENCH": "FRENCH",
        "FRANCAIS": "FRENCH",
        "HISTORY": "HISTORY",
        "HISTORY_GEOGRAPHY_EMC": "HISTORY",
        "SCIENCES": "PHYSICS_CHEMISTRY",
        "PHYSICS_CHEMISTRY": "PHYSICS_CHEMISTRY",
    }
    subject_code = aliases.get(subject_code, subject_code)
    subject_id = store.subject_id(subject_code)
    if subject_id is None:
        return ArchiveImportResult(None, "REJECTED", f"Unknown subject {subject}")
    base_id = f"{year}-{session}-{zone}-{series}-{subject_code.lower()}"
    source_hash = hashlib.sha256(f"{source_url}|{base_id}".encode()).hexdigest()
    existing = store.fetchone(
        """
        SELECT archive_id, status FROM exam_archives_ref
        WHERE year = ? AND session = ? AND zone = ? AND series = ? AND subject_id = ?
          AND base_exam_identifier = ?
        """,
        [year, session, zone, series, subject_id, base_id],
    )
    if existing and local_text is None:
        return ArchiveImportResult(int(existing[0]), str(existing[1]), "Already registered", duplicate=True)

    con = store.connect()
    if existing is None:
        con.execute(
            """
            INSERT INTO exam_archives_ref(
                year, session, zone, series, subject_id, official_title,
                official_source_url, correction_source_url, source_hash,
                base_exam_identifier, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                year,
                session,
                zone,
                series,
                subject_id,
                f"DNB {year} {subject_code} {zone}",
                source_url,
                source_url,
                source_hash,
                base_id,
                "DISCOVERED" if local_text is None else "PARSED",
            ],
        )
    archive_id = int(
        con.execute(
            """
            SELECT archive_id FROM exam_archives_ref
            WHERE base_exam_identifier = ? AND subject_id = ?
            """,
            [base_id, subject_id],
        ).fetchone()[0]
    )
    if local_text is None:
        return ArchiveImportResult(archive_id, "DISCOVERED", "Manifest entry registered (no local text)")

    section = con.execute(
        "SELECT section_id FROM exam_archive_sections_ref WHERE archive_id = ? AND position = 1",
        [archive_id],
    ).fetchone()
    if section is None:
        con.execute(
            """
            INSERT INTO exam_archive_sections_ref(archive_id, position, title, section_type)
            VALUES (?, 1, 'Sujet', 'MAIN')
            """,
            [archive_id],
        )
        section_id = int(
            con.execute(
                "SELECT section_id FROM exam_archive_sections_ref WHERE archive_id = ? AND position = 1",
                [archive_id],
            ).fetchone()[0]
        )
    else:
        section_id = int(section[0])

    paragraphs = [p.strip() for p in local_text.split("\n\n") if p.strip()]
    for index, paragraph in enumerate(paragraphs[:30], start=1):
        fp = fingerprint_text("OFFICIAL_ARCHIVE", base_id, index, paragraph)
        existing_c = con.execute(
            "SELECT content_id FROM content_items WHERE fingerprint = ?", [fp]
        ).fetchone()
        if existing_c is None:
            con.execute(
                """
                INSERT INTO content_items(
                    content_type, source_type, subject_id, chapter_id, title, statement,
                    answer_type, expected_answer, accepted_answers_json, correction, hint,
                    difficulty_score, difficulty_label, estimated_seconds, brevet_format,
                    curriculum_2027_compatible, runtime_playable, validation_status,
                    quality_score, fingerprint, semantic_fingerprint, usage_policy
                ) VALUES (
                    'EXAM_QUESTION', 'OFFICIAL_ARCHIVE', ?, NULL, ?, ?,
                    'text', NULL, NULL, NULL, NULL,
                    0.6, 'Moyen', 120, 'EXAM_QUESTION',
                    'REVIEW', TRUE, 'REVIEW',
                    0.8, ?, ?, 'RESERVED_FOR_MOCK'
                )
                """,
                [
                    subject_id,
                    f"Annale {year} Q{index}",
                    paragraph,
                    fp,
                    fingerprint_text(paragraph),
                ],
            )
            content_id = int(
                con.execute(
                    "SELECT content_id FROM content_items WHERE fingerprint = ?", [fp]
                ).fetchone()[0]
            )
        else:
            content_id = int(existing_c[0])
        exists_q = con.execute(
            """
            SELECT archive_question_id FROM exam_archive_questions_ref
            WHERE section_id = ? AND position = ?
            """,
            [section_id, index],
        ).fetchone()
        if exists_q is None:
            con.execute(
                """
                INSERT INTO exam_archive_questions_ref(
                    section_id, position, original_question_reference, content_id,
                    curriculum_2027_compatible, extraction_status, validation_status
                ) VALUES (?, ?, ?, ?, 'REVIEW', 'EXTRACTED', 'REVIEW')
                """,
                [section_id, index, f"Q{index}", content_id],
            )
    con.execute(
        "UPDATE exam_archives_ref SET status = 'IMPORTED' WHERE archive_id = ?",
        [archive_id],
    )
    return ArchiveImportResult(
        archive_id, "IMPORTED", f"Imported {min(len(paragraphs), 30)} questions"
    )


def import_manifest_discovered(store: BrevetContentStore | None = None) -> dict[str, int]:
    store = store or BrevetContentStore()
    data = load_manifest()
    created = 0
    duplicates = 0
    for entry in data.get("entries", []):
        result = ingest_dnb_archive(
            source_url=str(entry.get("source_url") or EDUSCOL_DNB_HUB),
            year=int(entry["year"]),
            session=str(entry.get("session") or "normale"),
            zone=str(entry.get("zone") or "metropole"),
            series=str(entry.get("series") or "generale"),
            subject=str(entry.get("subject_code") or entry.get("subject") or "MATHEMATICS"),
            store=store,
        )
        if result.duplicate:
            duplicates += 1
        elif result.archive_id is not None:
            created += 1
    return {
        "registered": created,
        "duplicates": duplicates,
        "total_entries": len(data.get("entries", [])),
    }
