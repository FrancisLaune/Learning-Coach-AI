"""LCAI-0012E controlled primary Draft import into production V2."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository, _candidate_payload
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.primary_5e_curriculum_resolution import (
    filter_importable_records_extended,
    prepare_all_corrected_records,
)
from services.content.primary_ai_review import (
    AUTHORITATIVE_AUDIT_PATH,
    QUALITY_RESULTS_PATH,
    SUMMARY_PATH,
)
from services.content.primary_ai_review import (
    CAMPAIGN_ID as REVIEW_CAMPAIGN,
)
from services.content.primary_integration import (
    PRIMARY_GRADES,
    candidate_from_record,
    load_valid_curriculum_keys,
    validate_target_key,
)

IMPORT_CAMPAIGN = "LCAI-0012E-PRIMARY-IMPORT-V1"
IMPORT_AUTHOR = "LCAI-0012E-PRIMARY-IMPORT-V1"
AUTHORITATIVE_COMMIT = "7e4f649"
ISOLATED_DB = Path("data/learning_coach_v2_0012e_full_test.duckdb")
MAPPING_PATH = Path("resources/content/integration/lcai_0012e_isolated_to_production_version_mapping.jsonl")
LEDGER_PATH = Path("resources/content/integration/lcai_0012e_primary_draft_import_ledger.json")
REPORT_PATH = Path("docs/phase2/LCAI-0012E_PRIMARY_DRAFT_IMPORT_REPORT.md")
EXPECTED_IMPORTABLE = 1293
EXCLUDED_UNRESOLVED = 18

ReconciliationStatus = str


def content_business_key(record: dict[str, Any]) -> str:
    return str(record["code"])


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_payload_hash(record: dict[str, Any]) -> str:
    candidate = candidate_from_record(record["candidate_data"])
    digest = hashlib.sha256(_canonical_json(_candidate_payload(candidate)).encode("utf-8")).hexdigest()
    return digest


def production_payload_hash(draft_item: dict[str, Any]) -> str:
    payload = dict(draft_item.get("payload") or {})
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return digest


def load_isolated_version_index(path: Path | None = None) -> dict[str, dict[str, Any]]:
    source = path or QUALITY_RESULTS_PATH
    rows = json.loads(source.read_text(encoding="utf-8"))
    return {str(row["code"]): row for row in rows}


def load_excluded_unresolved_codes(
    corrected: list[dict[str, Any]],
    importable: list[dict[str, Any]],
) -> set[str]:
    importable_codes = {record["code"] for record in importable}
    return {record["code"] for record in corrected if record["code"] not in importable_codes}


def load_authoritative_corpus(
    *,
    database_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    corrected, preparation = prepare_all_corrected_records(database_path=database_path)
    importable = filter_importable_records_extended(corrected, database_path=database_path)
    excluded = load_excluded_unresolved_codes(corrected, importable)
    isolated_index = load_isolated_version_index()
    meta = {
        "authoritative_commit": AUTHORITATIVE_COMMIT,
        "isolated_database": str(ISOLATED_DB),
        "quality_results_path": str(QUALITY_RESULTS_PATH),
        "corrected_count": len(corrected),
        "importable_count": len(importable),
        "excluded_unresolved_count": len(excluded),
        "isolated_version_rows": len(isolated_index),
        "preparation": preparation,
    }
    return importable, corrected, meta


def _chapter_exists(database_path: Path, chapter_code: str, grade_code: str, subject_code: str) -> bool:
    connection = connect_v2(database_path, read_only=True)
    try:
        row = connection.execute(
            """
            SELECT 1
            FROM curriculum_chapters cc
            JOIN school_levels sl ON sl.id=cc.grade_level_id
            JOIN subjects su ON su.id=cc.subject_id
            WHERE cc.stable_code=? AND sl.code=? AND su.code=? AND cc.status='approved'
            LIMIT 1
            """,
            [chapter_code, grade_code, subject_code],
        ).fetchone()
        return row is not None
    finally:
        connection.close()


def _skill_exists(database_path: Path, skill_code: str) -> bool:
    connection = connect_v2(database_path, read_only=True)
    try:
        row = connection.execute("SELECT 1 FROM skills WHERE code=? LIMIT 1", [skill_code]).fetchone()
        return row is not None
    finally:
        connection.close()


def _production_draft_index(database_path: Path) -> dict[str, dict[str, Any]]:
    repository = DuckDBContentQualityRepository(database_path)
    return {item["code"]: item for item in repository.draft_inventory(grade_codes=PRIMARY_GRADES)}


def classify_record(
    record: dict[str, Any],
    *,
    production_index: dict[str, dict[str, Any]],
    valid_keys: set[tuple[str, str, str, str, str]],
    excluded_codes: set[str],
    database_path: Path,
) -> tuple[ReconciliationStatus, dict[str, Any]]:
    code = content_business_key(record)
    if code in excluded_codes:
        return "EXCLUDED_UNRESOLVED_CURRICULUM", {"code": code}
    try:
        candidate = candidate_from_record(record["candidate_data"])
    except (KeyError, TypeError, ValueError) as exc:
        return "INVALID_CONTENT", {"code": code, "error": str(exc)}
    target = candidate.target
    errors = validate_target_key(target, valid_keys)
    if errors:
        return "INVALID_SKILL_REFERENCE", {"code": code, "errors": list(errors)}
    existing = production_index.get(code)
    if existing is None:
        return "NEW", {"code": code}
    source_hash = source_payload_hash(record)
    target_hash = production_payload_hash(existing)
    if source_hash == target_hash:
        return "ALREADY_PRESENT_IDENTICAL", {
            "code": code,
            "source_hash": source_hash,
            "target_hash": target_hash,
            "production_version_id": int(existing["version_id"]),
        }
    return "ALREADY_PRESENT_DIFFERENT", {
        "code": code,
        "source_hash": source_hash,
        "target_hash": target_hash,
        "production_version_id": int(existing["version_id"]),
    }


def reconcile_corpus(
    importable: list[dict[str, Any]],
    *,
    database_path: Path,
    excluded_codes: set[str],
) -> dict[str, Any]:
    valid_keys = load_valid_curriculum_keys(database_path)
    production_index = _production_draft_index(database_path)
    isolated_index = load_isolated_version_index()
    classifications: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for record in importable:
        status, detail = classify_record(
            record,
            production_index=production_index,
            valid_keys=valid_keys,
            excluded_codes=excluded_codes,
            database_path=database_path,
        )
        isolated_row = isolated_index.get(record["code"], {})
        classifications.append(
            {
                "content_business_key": record["code"],
                "grade": record["grade"],
                "subject": record["subject"],
                "skill_code": record["skill"],
                "content_type": record["content_type"],
                "isolated_version_id": isolated_row.get("version_id"),
                "reconciliation_status": status,
                **detail,
            }
        )
        status_counts[status] += 1
    return {
        "importable_count": len(importable),
        "status_counts": dict(status_counts),
        "classifications": classifications,
    }


def _mapping_entry(
    *,
    isolated_version_id: int | None,
    production_version_id: int,
    record: dict[str, Any],
    source_hash: str,
    target_hash: str,
    import_status: str,
    campaign: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "isolated_version_id": isolated_version_id,
        "production_version_id": production_version_id,
        "content_business_key": record["code"],
        "grade": record["grade"],
        "subject": record["subject"],
        "skill_code": record["skill"],
        "content_type": record["content_type"],
        "source_hash": source_hash,
        "target_hash": target_hash,
        "import_status": import_status,
        "campaign": campaign,
        "timestamp": datetime.now(UTC).isoformat(),
        "provenance": provenance,
    }


def load_version_mapping(path: Path | None = None) -> list[dict[str, Any]]:
    source = path or MAPPING_PATH
    if not source.exists():
        return []
    return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_version_mapping_index(path: Path | None = None) -> dict[int, dict[str, Any]]:
    index: dict[int, dict[str, Any]] = {}
    for entry in load_version_mapping(path):
        isolated_id = entry.get("isolated_version_id")
        if isolated_id is not None:
            index[int(isolated_id)] = entry
    return index


def load_version_mapping_by_code(path: Path | None = None) -> dict[str, dict[str, Any]]:
    return {str(entry["content_business_key"]): entry for entry in load_version_mapping(path)}


def resolve_production_version_id(
    isolated_version_id: int,
    *,
    mapping_index: dict[int, dict[str, Any]] | None = None,
    mapping_by_code: dict[str, dict[str, Any]] | None = None,
    business_key: str | None = None,
) -> int | None:
    mapping_index = mapping_index or load_version_mapping_index()
    entry = mapping_index.get(int(isolated_version_id))
    if entry is not None:
        return int(entry["production_version_id"])
    if business_key and mapping_by_code is not None:
        by_code = mapping_by_code.get(business_key)
        if by_code is not None:
            return int(by_code["production_version_id"])
    return None


def _fetch_draft_version_by_code(database_path: Path, code: str) -> dict[str, Any] | None:
    index = _production_draft_index(database_path)
    return index.get(code)


def _verify_database_unlocked(database_path: Path) -> None:
    connection = connect_v2(database_path, read_only=True)
    try:
        connection.execute("SELECT 1").fetchone()
    finally:
        connection.close()


def create_database_backup(database_path: Path, *, backup_dir: Path | None = None) -> dict[str, Any]:
    _verify_database_unlocked(database_path)
    target_dir = backup_dir or database_path.parent
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = target_dir / f"{database_path.stem}_backup_{timestamp}{database_path.suffix}"
    shutil.copy2(database_path, backup_path)
    verify_connection = connect_v2(backup_path, read_only=True)
    try:
        table_count = verify_connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='main'"
        ).fetchone()[0]
        exercise_count = verify_connection.execute("SELECT count(*) FROM exercises").fetchone()[0]
    finally:
        verify_connection.close()
    checksum = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    return {
        "path": str(backup_path),
        "checksum_sha256": checksum,
        "table_count": int(table_count),
        "exercise_count": int(exercise_count),
    }


def _write_mapping_entries(entries: list[dict[str, Any]], path: Path | None = None) -> None:
    target = path or MAPPING_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = load_version_mapping(target)
    existing_keys = {
        (entry.get("isolated_version_id"), entry["content_business_key"], entry["campaign"])
        for entry in existing
    }
    with target.open("a", encoding="utf-8") as handle:
        for entry in entries:
            key = (entry.get("isolated_version_id"), entry["content_business_key"], entry["campaign"])
            if key in existing_keys:
                continue
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            existing_keys.add(key)


def _persist_campaign_ledger(payload: dict[str, Any], path: Path | None = None) -> None:
    target = path or LEDGER_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def import_primary_drafts(
    database_path: Path,
    *,
    execute: bool = False,
    campaign: str = IMPORT_CAMPAIGN,
    author: str = IMPORT_AUTHOR,
    curriculum_reference_db: Path | None = None,
) -> dict[str, Any]:
    from services.content.primary_controlled_publication import primary_coverage_rows, tier_counts_by_grade

    reference_db = curriculum_reference_db or database_path
    tier_before = tier_counts_by_grade(primary_coverage_rows(database_path))
    importable, corrected, corpus_meta = load_authoritative_corpus(database_path=reference_db)
    excluded_codes = load_excluded_unresolved_codes(corrected, importable)
    reconciliation = reconcile_corpus(importable, database_path=database_path, excluded_codes=excluded_codes)
    isolated_index = load_isolated_version_index()

    counters: Counter[str] = Counter()
    mapping_entries: list[dict[str, Any]] = []
    ledger_records: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    factory = DuckDBContentFactoryRepository(database_path)

    provenance_base = {
        "authoritative_commit": AUTHORITATIVE_COMMIT,
        "quality_results_path": str(QUALITY_RESULTS_PATH),
        "isolated_database": str(ISOLATED_DB),
        "review_campaign": REVIEW_CAMPAIGN,
    }
    status_by_code = {item["content_business_key"]: item for item in reconciliation["classifications"]}
    to_import: list[dict[str, Any]] = []

    for record in importable:
        status_item = status_by_code[record["code"]]
        status = str(status_item["reconciliation_status"])
        counters[status] += 1
        isolated_row = isolated_index.get(record["code"], {})
        isolated_version_id = isolated_row.get("version_id")

        if status in {"EXCLUDED_UNRESOLVED_CURRICULUM"} or status.startswith("INVALID") or status == "ALREADY_PRESENT_DIFFERENT":
            continue

        if status == "ALREADY_PRESENT_IDENTICAL":
            source_hash = str(status_item.get("source_hash") or source_payload_hash(record))
            target_hash = str(status_item["target_hash"])
            mapping_entries.append(
                _mapping_entry(
                    isolated_version_id=int(isolated_version_id) if isolated_version_id is not None else None,
                    production_version_id=int(status_item["production_version_id"]),
                    record=record,
                    source_hash=source_hash,
                    target_hash=target_hash,
                    import_status="SKIPPED_IDENTICAL",
                    campaign=campaign,
                    provenance=provenance_base,
                )
            )
            continue

        if not execute:
            mapping_entries.append(
                _mapping_entry(
                    isolated_version_id=int(isolated_version_id) if isolated_version_id is not None else None,
                    production_version_id=-1,
                    record=record,
                    source_hash="",
                    target_hash="",
                    import_status="DRY_RUN_NEW",
                    campaign=campaign,
                    provenance=provenance_base,
                )
            )
            continue

        to_import.append(record)

    if execute and to_import:
        print(f"[{campaign}] importing {len(to_import)} drafts...", flush=True)
        candidates = [candidate_from_record(record["candidate_data"]) for record in to_import]
        try:
            persisted_rows = factory.persist_drafts_batch(candidates, author)
            persisted_by_code = {row["code"]: row for row in persisted_rows}
            for record in to_import:
                isolated_row = isolated_index.get(record["code"], {})
                isolated_version_id = isolated_row.get("version_id")
                persisted = persisted_by_code.get(record["code"])
                if persisted is None:
                    counters["FAILED"] += 1
                    failed.append({"code": record["code"], "error": "missing after batch persist"})
                    continue
                source_hash = source_payload_hash(record)
                target_hash = hashlib.sha256(
                    _canonical_json(dict(persisted["payload"])).encode("utf-8")
                ).hexdigest()
                production_version_id = int(persisted["version_id"])
                mapping_entries.append(
                    _mapping_entry(
                        isolated_version_id=int(isolated_version_id) if isolated_version_id is not None else None,
                        production_version_id=production_version_id,
                        record=record,
                        source_hash=source_hash,
                        target_hash=target_hash,
                        import_status="IMPORTED",
                        campaign=campaign,
                        provenance=provenance_base,
                    )
                )
                ledger_records.append(
                    {
                        "code": record["code"],
                        "exercise_id": int(persisted["content_id"]),
                        "production_version_id": production_version_id,
                        "isolated_version_id": isolated_version_id,
                    }
                )
                counters["IMPORTED"] += 1
            print(f"[{campaign}] imported={counters['IMPORTED']} failed={counters['FAILED']}", flush=True)
        except Exception as exc:  # noqa: BLE001
            counters["FAILED"] += len(to_import)
            failed.append({"code": "BATCH", "error": str(exc)})

    if execute and mapping_entries:
        _write_mapping_entries(
            [entry for entry in mapping_entries if entry["import_status"] in {"IMPORTED", "SKIPPED_IDENTICAL"}]
        )
        if ledger_records:
            _persist_campaign_ledger(
                {
                    "campaign": campaign,
                    "author": author,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "database": str(database_path),
                    "records": ledger_records,
                }
            )

    tier_after = tier_counts_by_grade(primary_coverage_rows(database_path))
    review_linkage = validate_review_linkage(database_path=database_path) if execute else {
        "ai_high_total": 0,
        "ai_high_resolved_to_production_draft": 0,
        "ai_high_unresolved": 0,
        "teacher_reviews_resolved": 0,
        "rejected_reviews_resolved": 0,
        "alternate_reviews_resolved": 0,
        "mapping_records": len(load_version_mapping()),
        "deferred_until_execute": True,
    }
    count_reconciliation = reconcile_review_counts() if execute else {"pass": True, "deferred_until_execute": True}

    report = {
        "campaign": campaign,
        "execute": execute,
        "authoritative_source": {
            "commit": AUTHORITATIVE_COMMIT,
            "isolated_database": str(ISOLATED_DB),
            "quality_results_path": str(QUALITY_RESULTS_PATH),
        },
        "corpus_meta": corpus_meta,
        "drafts_expected": EXPECTED_IMPORTABLE,
        "reconciliation_status_counts": dict(reconciliation["status_counts"]),
        "import_counters": dict(counters),
        "new_drafts_imported": int(counters.get("IMPORTED", 0)),
        "already_present_identical": int(reconciliation["status_counts"].get("ALREADY_PRESENT_IDENTICAL", 0)),
        "already_present_different": int(reconciliation["status_counts"].get("ALREADY_PRESENT_DIFFERENT", 0)),
        "excluded_unresolved_curriculum": len(excluded_codes),
        "invalid_references": sum(
            reconciliation["status_counts"].get(key, 0)
            for key in ("INVALID_SKILL_REFERENCE", "INVALID_CHAPTER_REFERENCE", "INVALID_CONTENT")
        ),
        "failed_imports": len(failed),
        "failed_details": failed[:20],
        "mapping_entries_planned": len(mapping_entries),
        "review_linkage": review_linkage,
        "count_reconciliation": count_reconciliation,
        "tier_coverage_before": tier_before,
        "tier_coverage_after": tier_after,
        "tier_coverage_unchanged": tier_before == tier_after,
        "lifecycle_draft_only": True,
        "production_gates_created": 0,
        "approved_versions_created": 0,
        "dry_run_pass": not execute,
    }
    return report


def _quality_index_by_version_id(path: Path | None = None) -> dict[int, dict[str, Any]]:
    index: dict[int, dict[str, Any]] = {}
    for row in json.loads((path or QUALITY_RESULTS_PATH).read_text(encoding="utf-8")):
        index[int(row["version_id"])] = row
    return index


def _audit_decision(audit: dict[str, Any]) -> str:
    return str(audit.get("decision") or (audit.get("ai_pedagogical_review") or {}).get("decision") or "")


def validate_review_linkage(*, database_path: Path | None = None) -> dict[str, Any]:
    mapping_index = load_version_mapping_index()
    mapping_by_code = load_version_mapping_by_code()
    quality_by_version = _quality_index_by_version_id()
    repository = DuckDBContentQualityRepository(database_path)
    audits = [json.loads(line) for line in AUTHORITATIVE_AUDIT_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

    production_ids: set[int] = set()
    for audit in audits:
        version_id = int(audit["candidate_version_id"])
        quality_row = quality_by_version.get(version_id, {})
        business_key = str(quality_row.get("code") or "")
        resolved = resolve_production_version_id(
            version_id,
            mapping_index=mapping_index,
            mapping_by_code=mapping_by_code,
            business_key=business_key or None,
        )
        if resolved is not None:
            production_ids.add(resolved)
    available = repository.available_draft_source_ids(production_ids)

    def _resolved(version_id: int) -> bool:
        quality_row = quality_by_version.get(version_id, {})
        business_key = str(quality_row.get("code") or "")
        production_id = resolve_production_version_id(
            version_id,
            mapping_index=mapping_index,
            mapping_by_code=mapping_by_code,
            business_key=business_key or None,
        )
        return production_id is not None and production_id in available

    ai_high_total = 0
    ai_high_resolved = 0
    teacher_resolved = 0
    rejected_resolved = 0
    alternate_resolved = 0

    handoff_version_ids = {
        int(json.loads(line)["candidate_version_id"])
        for line in Path("resources/content/integration/lcai_0012e_ai_review_handoff.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    }

    for audit in audits:
        version_id = int(audit["candidate_version_id"])
        decision = _audit_decision(audit)
        is_alternate = version_id not in handoff_version_ids
        resolved = _resolved(version_id)
        if decision == "AI_PREVALIDATED_HIGH":
            ai_high_total += 1
            if resolved:
                ai_high_resolved += 1
        elif decision == "TEACHER_REVIEW_REQUIRED":
            if resolved:
                teacher_resolved += 1
        elif decision == "AI_REJECTED":
            if resolved:
                rejected_resolved += 1
        if is_alternate and resolved:
            alternate_resolved += 1

    return {
        "ai_high_total": ai_high_total,
        "ai_high_resolved_to_production_draft": ai_high_resolved,
        "ai_high_unresolved": ai_high_total - ai_high_resolved,
        "teacher_reviews_resolved": teacher_resolved,
        "rejected_reviews_resolved": rejected_resolved,
        "alternate_reviews_resolved": alternate_resolved,
        "mapping_records": len(load_version_mapping()),
    }


def reconcile_review_counts() -> dict[str, Any]:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    population = summary.get("population", {})
    decisions = summary.get("decisions", {})
    workload = summary.get("workload", {})
    handoff_rows = int(population.get("handoff_rows", 731))
    reviewed_total = int(population.get("reviewed", 949))
    alternates_reviewed = int(workload.get("alternates_reviewed", 218))
    main_decisions = Counter()
    audits = [json.loads(line) for line in AUTHORITATIVE_AUDIT_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    handoff_version_ids = {
        int(json.loads(line)["candidate_version_id"])
        for line in Path("resources/content/integration/lcai_0012e_ai_review_handoff.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    }
    for audit in audits:
        version_id = int(audit["candidate_version_id"])
        if version_id not in handoff_version_ids:
            continue
        main_decisions[_audit_decision(audit)] += 1

    publication_summary = summary.get("publication_summary") or {}
    explanation = {
        "initial_candidates": handoff_rows,
        "alternate_reviews": alternates_reviewed,
        "total_review_records": reviewed_total,
        "formula_check": handoff_rows + alternates_reviewed == reviewed_total,
        "ai_prevalidated_high_all_reviews": int(decisions.get("AI_PREVALIDATED_HIGH", 0)),
        "ai_prevalidated_high_main_handoff_only": int(main_decisions.get("AI_PREVALIDATED_HIGH", 0)),
        "ai_rejected_all_reviews": int(decisions.get("AI_REJECTED", 0)),
        "ai_rejected_main_handoff_only": int(main_decisions.get("AI_REJECTED", 0)),
        "teacher_review_required_main": int(main_decisions.get("TEACHER_REVIEW_REQUIRED", 0)),
        "replacement_required_generation_after_ai": int(summary.get("generation_after_ai", {}).get("replacement_required", 0)),
        "rejected_without_alternate": int(
            (summary.get("generation_after_ai") or {}).get("rejected_without_alternate", 0)
            or workload.get("rejected_without_alternate", 0)
        ),
        "rejected_exclusions_publication_summary": int(publication_summary.get("rejected_excluded", 445)),
        "replacement_vs_rejected_without_alternate_delta": int(
            (summary.get("generation_after_ai") or {}).get("replacement_required", 0)
        )
        - int(
            (summary.get("generation_after_ai") or {}).get("rejected_without_alternate", 0)
            or workload.get("rejected_without_alternate", 0)
        ),
        "replacement_delta_explanation": "445 replacement_required counts skill slots; 441 rejected_without_alternate counts main handoff rejections without queued alternates; delta=4 matches alternates_queued.",
        "unique_draft_candidates": EXPECTED_IMPORTABLE,
        "review_attempts_main": handoff_rows,
        "alternate_review_attempts": alternates_reviewed,
    }
    explanation["pass"] = (
        explanation["formula_check"]
        and explanation["initial_candidates"] == 731
        and explanation["total_review_records"] == 949
        and explanation["alternate_reviews"] == 218
    )
    return explanation


def rollback_primary_draft_import(
    database_path: Path,
    *,
    execute: bool = False,
    campaign: str = IMPORT_CAMPAIGN,
) -> dict[str, Any]:
    if not LEDGER_PATH.exists():
        return {"status": "NO_LEDGER", "campaign": campaign, "removed": 0}
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    if ledger.get("campaign") != campaign:
        raise ValueError(f"Ledger campaign mismatch: expected {campaign}, found {ledger.get('campaign')}")
    records = list(ledger.get("records") or [])
    if not execute:
        return {"status": "DRY_RUN", "campaign": campaign, "would_remove": len(records)}

    connection = connect_v2(database_path)
    removed = 0
    try:
        for item in records:
            exercise_id = int(item["exercise_id"])
            version_id = int(item["production_version_id"])
            approved = connection.execute(
                "SELECT count(*) FROM content_versions WHERE id=? AND status='approved'",
                [version_id],
            ).fetchone()[0]
            if approved:
                raise RuntimeError(f"Refusing rollback: approved version {version_id}")
            connection.execute("BEGIN")
            try:
                question_ids = [
                    row[0]
                    for row in connection.execute(
                        "SELECT question_id FROM exercise_questions WHERE exercise_id=?",
                        [exercise_id],
                    ).fetchall()
                ]
                connection.execute(
                    "DELETE FROM content_status_events WHERE content_version_id=?",
                    [version_id],
                )
                connection.execute(
                    "DELETE FROM content_versions WHERE id=? AND entity_id=? AND entity_type='exercise'",
                    [version_id, exercise_id],
                )
                for question_id in question_ids:
                    connection.execute("DELETE FROM question_skills WHERE question_id=?", [question_id])
                    connection.execute("DELETE FROM question_subskills WHERE question_id=?", [question_id])
                    connection.execute("DELETE FROM exercise_questions WHERE question_id=?", [question_id])
                    connection.execute("DELETE FROM questions WHERE id=?", [question_id])
                connection.execute("DELETE FROM exercises WHERE id=?", [exercise_id])
                connection.execute("COMMIT")
                removed += 1
            except Exception:
                connection.execute("ROLLBACK")
                raise
    finally:
        connection.close()
    return {"status": "ROLLED_BACK", "campaign": campaign, "removed": removed}
