"""LCAI-0035 — offline massive DNB archive ingestion pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from core.config import PROJECT_ROOT
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.catalog import (
    load_catalog,
    sync_manifest_from_catalog,
    write_catalog,
)
from services.brevet_referential.migrations import apply_brevet_content_migrations
from services.brevet_referential.models import fingerprint_text
from services.brevet_referential.pdf_parser import PARSER_VERSION, is_dnb_document, parse_dnb_pdf
from services.brevet_referential.skill_mapping import (
    curriculum_2027_compatibility,
    map_skills_for_statement,
)
from services.brevet_referential.traceability import count_archive_derived_without_parent

PDF_DIR = PROJECT_ROOT / "artifacts" / "LCAI-0035" / "pdfs"
REPORT_DIR = PROJECT_ROOT / "artifacts" / "LCAI-0035"
USER_AGENT = "LearningCoachAI-offline-ingest/1.0 (LCAI-0035; educational archival)"


@dataclass(slots=True)
class IngestStats:
    documents_seen: int = 0
    downloaded: int = 0
    download_errors: int = 0
    parsed: int = 0
    parse_errors: int = 0
    archives_upserted: int = 0
    questions_created: int = 0
    questions_existing: int = 0
    skipped_accessibility: int = 0
    skipped_year: int = 0
    skipped_subject: int = 0


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_filename(url: str, eduscol_id: str | None) -> str:
    if eduscol_id:
        return f"eduscol_{eduscol_id}.pdf"
    path = urlparse(url).path
    name = Path(path).name or "document.pdf"
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name[:180]


def download_document(url: str, dest: Path, timeout: int = 90) -> tuple[Path, str, int]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        raw = dest.read_bytes()
        return dest, hashlib.sha256(raw).hexdigest(), len(raw)
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"},
    )
    response.raise_for_status()
    raw = response.content
    if not raw.startswith(b"%PDF"):
        raise ValueError(f"Not a PDF ({response.headers.get('content-type')})")
    dest.write_bytes(raw)
    return dest, hashlib.sha256(raw).hexdigest(), len(raw)


def _log_event(
    store: BrevetContentStore,
    *,
    run_id: int | None,
    event_type: str,
    status: str | None = None,
    archive_id: int | None = None,
    document_id: int | None = None,
    detail: str | None = None,
) -> None:
    store.execute(
        """
        INSERT INTO archive_ingestion_events(
            run_id, archive_id, document_id, event_type, status, detail
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [run_id, archive_id, document_id, event_type, status, detail],
    )


def _start_run(
    store: BrevetContentStore,
    *,
    years_from: int | None,
    years_to: int | None,
    dry_run: bool,
) -> int:
    store.execute(
        """
        INSERT INTO archive_ingestion_runs(
            ticket, status, parser_version, years_from, years_to, dry_run
        ) VALUES ('LCAI-0035', 'RUNNING', ?, ?, ?, ?)
        """,
        [PARSER_VERSION, years_from, years_to, dry_run],
    )
    row = store.fetchone("SELECT max(run_id) FROM archive_ingestion_runs")
    return int(row[0]) if row and row[0] is not None else 0


def _finish_run(store: BrevetContentStore, run_id: int, status: str, summary: dict[str, Any]) -> None:
    store.execute(
        """
        UPDATE archive_ingestion_runs
        SET finished_at = now(), status = ?, summary_json = ?
        WHERE run_id = ?
        """,
        [status, json.dumps(summary, ensure_ascii=False), run_id],
    )


def _resolve_subject_id(store: BrevetContentStore, subject_code: str) -> int | None:
    return store.subject_id(subject_code)


def _upsert_archive(
    store: BrevetContentStore,
    entry: dict[str, Any],
    *,
    run_id: int,
) -> int:
    subject_id = _resolve_subject_id(store, str(entry["subject_code"]))
    if subject_id is None:
        raise ValueError(f"Unknown subject_code {entry['subject_code']}")
    identity = str(entry["exam_identity_key"])
    existing = store.fetchone(
        "SELECT archive_id FROM exam_archives_ref WHERE exam_identity_key = ? OR base_exam_identifier = ?",
        [identity, identity],
    )
    title = (
        f"DNB {entry.get('year')} {entry.get('subject_group')} "
        f"{entry.get('zone')} {entry.get('official_exam_code') or ''}"
    ).strip()
    if existing:
        archive_id = int(existing[0])
        # Avoid parent UPDATEs when possible; only set non-FK enrichment via INSERT events.
        store.execute(
            """
            INSERT INTO referential_events(event_type, entity_ref, detail)
            VALUES ('ArchiveReuse', ?, ?)
            """,
            [str(archive_id), f"run={run_id};identity={identity}"],
        )
        return archive_id
    store.execute(
        """
        INSERT INTO exam_archives_ref(
            year, session, zone, series, subject_id, official_title,
            official_source_url, correction_source_url, source_hash,
            base_exam_identifier, status, source_provider, source_document_url,
            document_variant, exam_identity, subject_group, exam_identity_key,
            landing_page_url, last_ingestion_run_id, import_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DISCOVERED', ?, ?, ?, ?, ?, ?, ?, ?, 'DISCOVERED')
        """,
        [
            entry.get("year"),
            entry.get("session") or "normale",
            entry.get("zone") or "unknown",
            entry.get("series") or "generale",
            subject_id,
            title,
            entry.get("document_url"),
            entry.get("landing_page_url"),
            entry.get("source_hash") or fingerprint_text(identity),
            identity,
            entry.get("source_provider") or "EDUSCOL",
            entry.get("document_url"),
            entry.get("document_variant") or "STANDARD",
            identity,
            entry.get("subject_group"),
            identity,
            entry.get("landing_page_url"),
            run_id,
        ],
    )
    row = store.fetchone(
        "SELECT archive_id FROM exam_archives_ref WHERE base_exam_identifier = ?",
        [identity],
    )
    assert row is not None
    return int(row[0])


def _upsert_document(
    store: BrevetContentStore,
    *,
    archive_id: int,
    entry: dict[str, Any],
    local_path: Path,
    digest: str,
    page_count: int | None,
    parse_status: str,
    parser_confidence: float | None,
) -> int:
    existing = store.fetchone(
        "SELECT document_id FROM exam_archive_documents_ref WHERE source_hash = ?",
        [digest],
    )
    if existing:
        return int(existing[0])
    store.execute(
        """
        INSERT INTO exam_archive_documents_ref(
            archive_id, exam_identity_key, source_provider, document_url, document_type,
            document_variant, local_path, source_hash, page_count, download_status,
            parse_status, mapping_status, validation_status, parser_version,
            extraction_method, parser_confidence, eduscol_document_id, official_exam_code,
            last_checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DOWNLOADED', ?, 'PENDING', 'REVIEW', ?,
                  'PYPDF_TEXT', ?, ?, ?, now())
        """,
        [
            archive_id,
            entry["exam_identity_key"],
            entry.get("source_provider") or "EDUSCOL",
            entry["document_url"],
            entry.get("document_type") or "SUBJECT",
            entry.get("document_variant") or "STANDARD",
            str(local_path),
            digest,
            page_count,
            parse_status,
            PARSER_VERSION,
            parser_confidence,
            entry.get("eduscol_document_id"),
            entry.get("official_exam_code"),
        ],
    )
    row = store.fetchone(
        "SELECT document_id FROM exam_archive_documents_ref WHERE source_hash = ?",
        [digest],
    )
    assert row is not None
    return int(row[0])


def _ensure_section(store: BrevetContentStore, archive_id: int, position: int, title: str) -> int:
    existing = store.fetchone(
        "SELECT section_id FROM exam_archive_sections_ref WHERE archive_id = ? AND position = ?",
        [archive_id, position],
    )
    if existing:
        return int(existing[0])
    store.execute(
        """
        INSERT INTO exam_archive_sections_ref(archive_id, position, title, section_type)
        VALUES (?, ?, ?, 'EXERCISE')
        """,
        [archive_id, position, title[:200]],
    )
    row = store.fetchone(
        "SELECT section_id FROM exam_archive_sections_ref WHERE archive_id = ? AND position = ?",
        [archive_id, position],
    )
    assert row is not None
    return int(row[0])


def _import_parsed(
    store: BrevetContentStore,
    *,
    run_id: int,
    archive_id: int,
    document_id: int,
    entry: dict[str, Any],
    parsed: Any,
    stats: IngestStats,
    map_only: bool = False,
) -> None:
    subject_code = str(entry["subject_code"])
    subject_id = _resolve_subject_id(store, subject_code)
    assert subject_id is not None
    year = entry.get("year") or parsed.year

    for section in parsed.sections:
        section_id = _ensure_section(store, archive_id, section.position, section.title)
        for q_index, question in enumerate(section.questions, start=1):
            locator = question.source_locator or f"doc:{document_id}|sec:{section.position}|q:{q_index}"
            fp = fingerprint_text(
                "OFFICIAL_ARCHIVE",
                entry["exam_identity_key"],
                section.position,
                question.question_number,
                question.subquestion_number or "",
                locator,
                question.statement[:500],
            )
            existing_c = store.fetchone("SELECT content_id FROM content_items WHERE fingerprint = ?", [fp])
            mapped = map_skills_for_statement(store, subject_code=subject_code, statement=question.statement)
            compat, compat_reason = curriculum_2027_compatibility(
                year=year,
                subject_group=str(entry.get("subject_group") or subject_code),
                mapped_skills=mapped,
            )
            skill_id = mapped[0]["skill_id"] if mapped else None
            chapter_id = mapped[0]["chapter_id"] if mapped else None
            title = (
                f"{entry.get('official_exam_code') or entry['exam_identity_key']} "
                f"{section.title} Q{question.question_number}"
                + (f".{question.subquestion_number}" if question.subquestion_number else "")
            )[:200]
            if existing_c:
                content_id = int(existing_c[0])
                stats.questions_existing += 1
            else:
                if map_only:
                    continue
                store.execute(
                    """
                    INSERT INTO content_items(
                        content_type, source_type, subject_id, chapter_id, title, statement,
                        answer_type, expected_answer, accepted_answers_json, correction, hint,
                        difficulty_score, difficulty_label, estimated_seconds, brevet_format,
                        curriculum_2027_compatible, runtime_playable, validation_status,
                        quality_score, fingerprint, semantic_fingerprint, usage_policy,
                        source_locator, official_exam_code
                    ) VALUES (
                        'EXAM_QUESTION', 'OFFICIAL_ARCHIVE', ?, ?, ?, ?,
                        'text', NULL, NULL, NULL, NULL,
                        0.6, 'Moyen', 180, ?,
                        ?, FALSE, 'REVIEW',
                        0.85, ?, ?, 'RESERVED_FOR_MOCK',
                        ?, ?
                    )
                    """,
                    [
                        subject_id,
                        chapter_id,
                        title,
                        question.statement,
                        question.question_kind or "EXAM_QUESTION",
                        compat,
                        fp,
                        fingerprint_text(question.statement),
                        locator,
                        entry.get("official_exam_code"),
                    ],
                )
                content_id = int(store.fetchone("SELECT content_id FROM content_items WHERE fingerprint = ?", [fp])[0])
                stats.questions_created += 1
                for skill in mapped:
                    exists_link = store.fetchone(
                        """
                        SELECT 1 FROM content_skill_links
                        WHERE content_id = ? AND skill_id = ? AND relation_type = 'PRIMARY'
                        """,
                        [content_id, skill["skill_id"]],
                    )
                    if not exists_link:
                        store.execute(
                            """
                            INSERT INTO content_skill_links(content_id, skill_id, relation_type, weight)
                            VALUES (?, ?, 'PRIMARY', 1.0)
                            """,
                            [content_id, skill["skill_id"]],
                        )

            existing_q = store.fetchone(
                """
                SELECT archive_question_id FROM exam_archive_questions_ref
                WHERE section_id = ? AND position = ?
                """,
                [section_id, q_index],
            )
            if existing_q is None and not map_only:
                store.execute(
                    """
                    INSERT INTO exam_archive_questions_ref(
                        section_id, position, original_question_reference, content_id,
                        points, curriculum_2027_compatible, compatibility_reason,
                        extraction_status, validation_status, statement,
                        support_required, source_page_start, source_page_end, source_locator,
                        correction_source, question_number, subquestion_number,
                        official_points, question_kind, shared_context_ref,
                        parser_confidence, extraction_method
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, 'EXTRACTED', 'REVIEW', ?,
                        FALSE, ?, ?, ?, 'NONE', ?, ?, ?, ?, ?, ?, 'PYPDF_TEXT'
                    )
                    """,
                    [
                        section_id,
                        q_index,
                        question.reference,
                        content_id,
                        question.points,
                        compat,
                        compat_reason,
                        question.statement,
                        question.source_page_start,
                        question.source_page_end,
                        locator,
                        question.question_number,
                        question.subquestion_number,
                        question.points,
                        question.question_kind,
                        question.shared_context_ref,
                        question.parser_confidence,
                    ],
                )
                aq = store.fetchone(
                    """
                    SELECT archive_question_id FROM exam_archive_questions_ref
                    WHERE section_id = ? AND position = ?
                    """,
                    [section_id, q_index],
                )
                if aq:
                    # Link content → archive question without updating FK parents broadly.
                    store.execute(
                        """
                        INSERT INTO referential_events(event_type, entity_ref, detail)
                        VALUES ('OfficialQuestionLinked', ?, ?)
                        """,
                        [str(content_id), f"archive_question_id={aq[0]};skill={skill_id}"],
                    )
            _log_event(
                store,
                run_id=run_id,
                event_type="ArchiveQuestionExtracted",
                status="OK",
                archive_id=archive_id,
                document_id=document_id,
                detail=locator,
            )


def filter_entries(
    entries: list[dict[str, Any]],
    *,
    years: tuple[int, int] | None,
    subject: str | None,
    archive_identity: str | None,
    include_accessibility: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in entries:
        if not include_accessibility and entry.get("document_variant", "STANDARD") != "STANDARD":
            continue
        year = entry.get("year")
        if years and year is not None and not (years[0] <= int(year) <= years[1]):
            continue
        if subject:
            subj = subject.upper()
            if subj not in {
                str(entry.get("subject_code", "")).upper(),
                str(entry.get("subject_group", "")).upper(),
                str(entry.get("subject", "")).upper(),
            }:
                continue
        if archive_identity and archive_identity not in {
            entry.get("exam_identity_key"),
            entry.get("base_exam_identifier"),
            str(entry.get("eduscol_document_id")),
        }:
            continue
        out.append(entry)
    return out


def run_ingestion(
    *,
    years: tuple[int, int] | None = (2018, 2026),
    subject: str | None = None,
    archive_id: str | None = None,
    download_only: bool = False,
    parse_only: bool = False,
    map_only: bool = False,
    validate_only: bool = False,
    resume: bool = True,
    force: bool = False,
    dry_run: bool = False,
    include_accessibility: bool = False,
    report: bool = True,
) -> dict[str, Any]:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    apply_brevet_content_migrations()
    write_catalog(include_accessibility=True)
    catalog = load_catalog()
    sync_manifest_from_catalog(catalog)
    entries = filter_entries(
        list(catalog.get("entries", [])),
        years=years,
        subject=subject,
        archive_identity=archive_id,
        include_accessibility=include_accessibility,
    )
    store = BrevetContentStore()
    stats = IngestStats()
    run_id = 0
    try:
        run_id = _start_run(
            store,
            years_from=years[0] if years else None,
            years_to=years[1] if years else None,
            dry_run=dry_run,
        )
        if validate_only:
            summary = _validation_summary(store)
            _finish_run(store, run_id, "VALIDATED", summary)
            if report:
                _write_reports(store, summary)
            return summary

        for entry in entries:
            stats.documents_seen += 1
            url = str(entry["document_url"])
            dest = (
                Path(entry["local_path"])
                if entry.get("local_path")
                else PDF_DIR / _safe_filename(url, entry.get("eduscol_document_id"))
            )
            try:
                if not parse_only and not map_only:
                    if dry_run:
                        _log_event(
                            store,
                            run_id=run_id,
                            event_type="DownloadSkippedDryRun",
                            status="DRY_RUN",
                            detail=url,
                        )
                        continue
                    path, digest, _size = download_document(url, dest)
                    entry["local_path"] = str(path)
                    entry["source_hash"] = digest
                    stats.downloaded += 1
                    _log_event(
                        store,
                        run_id=run_id,
                        event_type="ArchiveDownloaded",
                        status="OK",
                        detail=f"{url}|{digest[:16]}",
                    )
                else:
                    if not dest.exists():
                        stats.download_errors += 1
                        continue
                    path = dest
                    digest = entry.get("source_hash") or hashlib.sha256(path.read_bytes()).hexdigest()

                if download_only:
                    archive_id_db = _upsert_archive(store, entry, run_id=run_id)
                    _upsert_document(
                        store,
                        archive_id=archive_id_db,
                        entry=entry,
                        local_path=path,
                        digest=digest,
                        page_count=None,
                        parse_status="DOWNLOADED",
                        parser_confidence=None,
                    )
                    stats.archives_upserted += 1
                    continue

                if dry_run:
                    continue

                # Skip re-parse if document already imported and not forced.
                if resume and not force:
                    existing_doc = store.fetchone(
                        """
                        SELECT document_id, parse_status FROM exam_archive_documents_ref
                        WHERE source_hash = ?
                        """,
                        [digest],
                    )
                    if existing_doc and existing_doc[1] in {"PARSED", "SEGMENTED", "IMPORTED"}:
                        continue

                parsed = parse_dnb_pdf(path)
                if not is_dnb_document(parsed.full_text):
                    _log_event(
                        store,
                        run_id=run_id,
                        event_type="NonDnbSkipped",
                        status="SKIPPED",
                        detail=url,
                    )
                    continue
                # Enrich missing metadata from parser.
                if not entry.get("year") and parsed.year:
                    entry["year"] = parsed.year
                if not entry.get("official_exam_code") and parsed.official_exam_code:
                    entry["official_exam_code"] = parsed.official_exam_code

                archive_id_db = _upsert_archive(store, entry, run_id=run_id)
                stats.archives_upserted += 1
                document_id = _upsert_document(
                    store,
                    archive_id=archive_id_db,
                    entry=entry,
                    local_path=path,
                    digest=digest,
                    page_count=parsed.page_count,
                    parse_status="PARSED",
                    parser_confidence=parsed.parser_confidence,
                )
                _import_parsed(
                    store,
                    run_id=run_id,
                    archive_id=archive_id_db,
                    document_id=document_id,
                    entry=entry,
                    parsed=parsed,
                    stats=stats,
                    map_only=map_only,
                )
                store.execute(
                    """
                    UPDATE exam_archive_documents_ref
                    SET parse_status='IMPORTED', mapping_status='MAPPED', last_checked_at=now()
                    WHERE document_id=?
                    """,
                    [document_id],
                )
                # Status update on archive — may fail under FK constraints; ignore.
                try:
                    store.execute(
                        """
                        UPDATE exam_archives_ref
                        SET status='IMPORTED', import_status='IMPORTED',
                            parser_version=?, downloaded_at=now(), updated_at=now(),
                            source_hash=?, official_document_ref=?
                        WHERE archive_id=?
                        """,
                        [PARSER_VERSION, digest, str(path), archive_id_db],
                    )
                except Exception as exc:  # noqa: BLE001
                    _log_event(
                        store,
                        run_id=run_id,
                        event_type="ArchiveStatusUpdateSkipped",
                        status="WARN",
                        archive_id=archive_id_db,
                        detail=str(exc)[:300],
                    )
                stats.parsed += 1
                _log_event(
                    store,
                    run_id=run_id,
                    event_type="ArchiveParsed",
                    status="OK",
                    archive_id=archive_id_db,
                    document_id=document_id,
                    detail=f"sections={len(parsed.sections)}",
                )
            except Exception as exc:  # noqa: BLE001
                stats.parse_errors += 1
                _log_event(
                    store,
                    run_id=run_id,
                    event_type="IngestError",
                    status="ERROR",
                    detail=f"{url}|{exc}"[:800],
                )
                continue

        summary = {
            "ticket": "LCAI-0035",
            "run_id": run_id,
            "parser_version": PARSER_VERSION,
            "finished_at": _now(),
            "stats": asdict(stats),
            "entries_selected": len(entries),
            **_validation_summary(store),
        }
        _finish_run(store, run_id, "COMPLETED", summary)
        if report:
            _write_reports(store, summary)
        return summary
    except Exception as exc:
        if run_id:
            _finish_run(store, run_id, "ERROR", {"error": str(exc), "stats": asdict(stats)})
        raise
    finally:
        store.close()


def _validation_summary(store: BrevetContentStore) -> dict[str, Any]:
    official = store.fetchone("SELECT COUNT(*) FROM content_items WHERE source_type = 'OFFICIAL_ARCHIVE'")
    linked = store.fetchone(
        """
        SELECT COUNT(*) FROM exam_archive_questions_ref q
        JOIN content_items c ON c.content_id = q.content_id
        WHERE c.source_type = 'OFFICIAL_ARCHIVE'
        """
    )
    docs = store.fetchone("SELECT COUNT(*) FROM exam_archive_documents_ref")
    parsed_docs = store.fetchone(
        """
        SELECT COUNT(*) FROM exam_archive_documents_ref
        WHERE parse_status IN ('PARSED', 'SEGMENTED', 'IMPORTED')
        """
    )
    archives = store.fetchone("SELECT COUNT(*) FROM exam_archives_ref")
    orphans = count_archive_derived_without_parent(store)
    fake_prov = store.fetchone(
        """
        SELECT COUNT(*) FROM content_items
        WHERE source_type = 'OFFICIAL_ARCHIVE'
          AND (statement IS NULL OR length(statement) < 10)
        """
    )
    by_year = store.fetchall(
        """
        SELECT COALESCE(a.year, -1), COUNT(DISTINCT c.content_id)
        FROM content_items c
        LEFT JOIN exam_archive_questions_ref q ON q.content_id = c.content_id
        LEFT JOIN exam_archive_sections_ref s ON s.section_id = q.section_id
        LEFT JOIN exam_archives_ref a ON a.archive_id = s.archive_id
        WHERE c.source_type = 'OFFICIAL_ARCHIVE'
        GROUP BY 1
        ORDER BY 1
        """
    )
    official_count = int(official[0]) if official else 0
    return {
        "official_question_count": official_count,
        "official_questions_linked": int(linked[0]) if linked else 0,
        "documents_registered": int(docs[0]) if docs else 0,
        "documents_parsed": int(parsed_docs[0]) if parsed_docs else 0,
        "archives_total": int(archives[0]) if archives else 0,
        "ARCHIVE_DERIVED_WITHOUT_PARENT": orphans,
        "empty_official_statements": int(fake_prov[0]) if fake_prov else 0,
        "official_by_year": {str(y): int(n) for y, n in by_year},
        "pass_official_gt_3": official_count > 3,
        "pass_orphan_invariant": orphans == 0,
    }


def _write_reports(store: BrevetContentStore, summary: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "LCAI-0035_INGEST_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Coverage CSVs via views when available.
    try:
        rows = store.fetchall("SELECT * FROM v_official_archive_coverage_by_year")
        _rows_to_csv(
            REPORT_DIR / "LCAI-0035_ARCHIVE_COVERAGE_BY_YEAR.csv", rows, store, "v_official_archive_coverage_by_year"
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        rows = store.fetchall("SELECT * FROM v_official_archive_coverage_by_subject")
        _rows_to_csv(
            REPORT_DIR / "LCAI-0035_ARCHIVE_COVERAGE_BY_SUBJECT.csv",
            rows,
            store,
            "v_official_archive_coverage_by_subject",
        )
    except Exception:  # noqa: BLE001
        pass
    skill_rows = store.fetchall(
        """
        SELECT sub.code, ch.name, sk.code, sk.name, sk.brevet_importance,
               COUNT(DISTINCT c.content_id) AS official_question_count,
               COUNT(DISTINCT CASE WHEN c.curriculum_2027_compatible='TRUE' THEN c.content_id END),
               COUNT(DISTINCT a.year),
               COUNT(DISTINCT c.brevet_format)
        FROM skills sk
        JOIN chapters ch ON ch.chapter_id = sk.chapter_id
        JOIN curriculum_domains cd ON cd.domain_id = ch.domain_id
        JOIN subjects sub ON sub.subject_id = cd.subject_id
        LEFT JOIN content_skill_links l ON l.skill_id = sk.skill_id
        LEFT JOIN content_items c ON c.content_id = l.content_id AND c.source_type='OFFICIAL_ARCHIVE'
        LEFT JOIN exam_archive_questions_ref q ON q.content_id = c.content_id
        LEFT JOIN exam_archive_sections_ref s ON s.section_id = q.section_id
        LEFT JOIN exam_archives_ref a ON a.archive_id = s.archive_id
        GROUP BY 1,2,3,4,5
        ORDER BY official_question_count DESC, 1, 3
        """
    )
    lines = [
        "subject,chapter,skill_code,skill_name,brevet_importance,official_question_count,"
        "compatible_2027_count,years_present,unique_formats"
    ]
    for r in skill_rows:
        lines.append(",".join(_csv_escape(x) for x in r))
    (REPORT_DIR / "LCAI-0035_ARCHIVE_COVERAGE_BY_SKILL.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _csv_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    if any(ch in text for ch in ',"\n'):
        return '"' + text.replace('"', '""') + '"'
    return text


def _rows_to_csv(path: Path, rows: list[tuple[Any, ...]], store: BrevetContentStore, view: str) -> None:
    cols = [
        r[0]
        for r in store.fetchall(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = ?
            ORDER BY ordinal_position
            """,
            [view],
        )
    ]
    lines = [",".join(cols)]
    for row in rows:
        lines.append(",".join(_csv_escape(x) for x in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
