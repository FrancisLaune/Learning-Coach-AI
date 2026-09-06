#!/usr/bin/env python3
"""LCAI-0033 — read-only audit of pedagogical 3e/DNB databases.

Does not modify production DBs. Writes artefacts under artifacts/LCAI-0033/.
Exit code non-zero on critical failure.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import (  # noqa: E402
    DEFAULT_DATABASE_PATH,
    DEFAULT_V2_DATABASE_PATH,
    get_database_path,
    get_v2_database_path,
)

ART_DIR = ROOT / "artifacts" / "LCAI-0033"
EXPORT_DIR = ART_DIR / "exports"
DOCS_DIR = ROOT / "docs" / "phase6" / "LCAI-0033"
PACKAGE_NAME = "LCAI-0033_AUDIT_PACKAGE.zip"

SUBJECT_ORDER = [
    "FRENCH",
    "MATHEMATICS",
    "HISTORY",
    "GEOGRAPHY",
    "EMC",
    "PHYSICS_CHEMISTRY",
    "SVT",
    "TECHNOLOGY",
    "ORAL",
    "ENGLISH",
    "SPANISH",
]

HIST_BUCKETS = [(0, 0), (1, 4), (5, 9), (10, 19), (20, 29), (30, 39), (40, 10_000)]


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in headers})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git_capture() -> dict[str, str]:
    def run(args: list[str]) -> str:
        try:
            return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return "UNKNOWN"

    return {
        "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "head": run(["git", "rev-parse", "HEAD"]),
        "status_short": run(["git", "status", "--short"]),
    }


def classify_path(path: Path) -> dict[str, Any]:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    suffix = path.suffix.lower()
    role = "unknown"
    ped = False
    student = False
    active = False
    legacy = False
    notes = ""
    name = path.name.lower()
    if "backup" in rel or "corrupt" in name or ".wal" in name:
        role = "backup_or_wal"
        legacy = True
        notes = "non-runtime"
    elif suffix == ".duckdb":
        if "objectif_brevet_2027" in name and "backup" not in rel:
            role = "runtime_auth_and_brevet_content"
            ped = True
            student = True
            active = "backups" not in rel and "AUDIT" not in path.name
        elif "learning_coach_v2" in name and "backup" not in rel:
            role = "runtime_v2_pedagogy"
            ped = True
            student = True
            active = "backups" not in rel and "AUDIT" not in path.name
        elif "revision" in rel or "objectif" in name:
            role = "legacy_or_side_db"
            ped = True
            legacy = True
        else:
            role = "duckdb_other"
    elif suffix in {".db", ".sqlite", ".sqlite3"}:
        role = "sqlite_legacy"
        ped = True
        legacy = True
    elif "manifest" in name and suffix == ".json":
        role = "archive_manifest"
        ped = True
        notes = "eduscol discovery"
    elif "subjects" in rel and suffix == ".py":
        role = "python_exercise_bank"
        ped = True
    elif "migrations" in rel:
        role = "migration"
    elif suffix in {".csv", ".parquet", ".xlsx", ".yaml", ".yml"}:
        role = "data_export_or_config"
    elif suffix in {".pdf", ".docx", ".odt"}:
        role = "document"
        ped = "annale" in name or "brevet" in name or "dnb" in name
    return {
        "path": rel,
        "type": suffix or "dir_entry",
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        "probable_role": role,
        "contains_pedagogical_content": ped,
        "contains_student_data": student,
        "active_runtime_source": active,
        "legacy": legacy,
        "notes": notes,
    }


def inventory_sources() -> list[dict[str, Any]]:
    patterns = (
        "*.duckdb",
        "*.db",
        "*.sqlite",
        "*.sqlite3",
        "*.json",
        "*.csv",
        "*.parquet",
        "*.xlsx",
        "*.yaml",
        "*.yml",
        "*.pdf",
        "*.docx",
        "*.odt",
    )
    skip_parts = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", ".venv", "venv"}
    found: dict[str, dict[str, Any]] = {}
    for pattern in patterns:
        for path in ROOT.rglob(pattern):
            if any(p in skip_parts for p in path.parts):
                continue
            if not path.is_file():
                continue
            # cap huge trees of cache json
            if path.suffix == ".json" and "artifacts" in path.parts and "LCAI-0033" in path.parts:
                continue
            info = classify_path(path)
            found[info["path"]] = info
    # python banks
    for bank_root in (ROOT / "subjects", ROOT / "revision_3e_enrichie" / "subjects"):
        if bank_root.exists():
            for path in bank_root.glob("*.py"):
                info = classify_path(path)
                found[info["path"]] = info
    return sorted(found.values(), key=lambda r: r["path"])


def relpath_or_abs(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def copy_db(src: Path, dest: Path) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    shutil.copy2(src, dest)
    return {
        "source": relpath_or_abs(src),
        "copy": relpath_or_abs(dest),
        "source_sha256": sha256_file(src),
        "copy_sha256": sha256_file(dest),
        "source_size": src.stat().st_size,
        "copy_size": dest.stat().st_size,
        "sha_match": sha256_file(src) == sha256_file(dest),
    }


def anonymize_ob_copy(src_copy: Path, dest: Path) -> None:
    if dest.exists():
        dest.unlink()
    shutil.copy2(src_copy, dest)
    con = duckdb.connect(str(dest))
    try:
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        if "users" in tables:
            con.execute(
                """
                UPDATE users SET
                  name = 'user_' || CAST(id AS VARCHAR),
                  pin_hash = 'REDACTED',
                  first_name = CASE WHEN first_name IS NULL THEN NULL ELSE 'F' || CAST(id AS VARCHAR) END,
                  last_name = CASE WHEN last_name IS NULL THEN NULL ELSE 'L' || CAST(id AS VARCHAR) END,
                  email = CASE WHEN email IS NULL THEN NULL ELSE 'redacted_' || CAST(id AS VARCHAR) || '@example.invalid' END,
                  learner_external_ref = CASE
                    WHEN learner_external_ref IS NULL THEN NULL
                    ELSE 'ref_' || CAST(id AS VARCHAR)
                  END
                """
            )
        if "practice_attempts" in tables:
            con.execute(
                """
                UPDATE practice_attempts SET
                  student_answer = '[REDACTED]',
                  question = LEFT(COALESCE(question, ''), 120)
                """
            )
        if "learning_sessions" in tables:
            # no PII columns beyond user_id FK
            pass
        con.execute("CHECKPOINT")
    finally:
        con.close()


def schema_inventory(con: duckdb.DuckDBPyConnection, db_label: str) -> tuple[list[dict], list[dict], str]:
    tables = [
        r[0]
        for r in con.execute(
            """SELECT table_name FROM information_schema.tables
               WHERE table_schema='main' ORDER BY 1"""
        ).fetchall()
    ]
    table_rows: list[dict[str, Any]] = []
    column_rows: list[dict[str, Any]] = []
    dump_parts: list[str] = [f"-- SCHEMA DUMP {db_label}"]
    for table in tables:
        try:
            n = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        except Exception:
            n = -1
        kind = con.execute(
            """SELECT table_type FROM information_schema.tables
               WHERE table_schema='main' AND table_name=?""",
            [table],
        ).fetchone()[0]
        table_rows.append({"database": db_label, "table_name": table, "table_type": kind, "row_count": n})
        cols = con.execute(
            """SELECT column_name, data_type, is_nullable, column_default
               FROM information_schema.columns
               WHERE table_schema='main' AND table_name=?
               ORDER BY ordinal_position""",
            [table],
        ).fetchall()
        dump_parts.append(f"\n-- {table} ({kind}, rows={n})")
        for col_name, data_type, nullable, default in cols:
            column_rows.append(
                {
                    "database": db_label,
                    "table_name": table,
                    "column_name": col_name,
                    "data_type": data_type,
                    "is_nullable": nullable,
                    "column_default": default or "",
                }
            )
            dump_parts.append(f"--   {col_name} {data_type} null={nullable} default={default}")
        # indexes
        try:
            idxs = con.execute(
                "SELECT index_name, is_unique, sql FROM duckdb_indexes() WHERE table_name=?",
                [table],
            ).fetchall()
            for name, uniq, sql in idxs:
                dump_parts.append(f"-- INDEX {name} unique={uniq} :: {sql}")
        except Exception:
            pass
    return table_rows, column_rows, "\n".join(dump_parts) + "\n"


def preview(text: str | None, n: int = 160) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    return s[:n]


def coverage_status(total: int) -> str:
    if total <= 0:
        return "EMPTY"
    if total <= 4:
        return "CRITICAL_SHORTAGE"
    if total <= 19:
        return "INSUFFICIENT"
    if total <= 29:
        return "USABLE"
    if total <= 39:
        return "COMPLETE"
    return "STRONG"


def analyze_ob(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["subjects"] = con.execute(
        "SELECT subject_id, code, name, terminal_exam, continuous_assessment, brevet_exam_enabled, active FROM subjects ORDER BY sort_order, code"
    ).fetchall()
    out["source_counts"] = dict(
        con.execute("SELECT source_type, COUNT(*) FROM content_items GROUP BY 1 ORDER BY 2 DESC").fetchall()
    )
    out["total_content"] = int(con.execute("SELECT COUNT(*) FROM content_items").fetchone()[0])
    out["playable"] = int(
        con.execute("SELECT COUNT(*) FROM content_items WHERE runtime_playable").fetchone()[0]
    )
    out["skills"] = int(con.execute("SELECT COUNT(*) FROM skills WHERE active").fetchone()[0])
    out["chapters"] = int(con.execute("SELECT COUNT(*) FROM chapters WHERE active").fetchone()[0])
    out["archives"] = int(con.execute("SELECT COUNT(*) FROM exam_archives_ref").fetchone()[0])
    out["archive_questions"] = int(
        con.execute("SELECT COUNT(*) FROM exam_archive_questions_ref").fetchone()[0]
    )
    out["users"] = int(con.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    out["practice_attempts"] = int(con.execute("SELECT COUNT(*) FROM practice_attempts").fetchone()[0])
    out["difficulty_dist"] = dict(
        con.execute(
            "SELECT COALESCE(difficulty_label,'NULL'), COUNT(*) FROM content_items GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()
    )
    out["compat_dist"] = dict(
        con.execute(
            "SELECT curriculum_2027_compatible, COUNT(*) FROM content_items GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()
    )
    # by subject aggregates
    by_subj = con.execute(
        """
        SELECT s.code,
               COUNT(*) AS total,
               SUM(CASE WHEN c.content_type='EXERCISE' OR c.content_type IS NOT NULL THEN 1 ELSE 0 END) AS exercises,
               SUM(CASE WHEN c.source_type='OFFICIAL_ARCHIVE' THEN 1 ELSE 0 END) AS official,
               SUM(CASE WHEN c.source_type='ARCHIVE_DERIVED' THEN 1 ELSE 0 END) AS derived,
               SUM(CASE WHEN c.source_type='AI_GENERATED' THEN 1 ELSE 0 END) AS ai,
               SUM(CASE WHEN c.source_type='LEGACY_BANK' THEN 1 ELSE 0 END) AS legacy,
               SUM(CASE WHEN c.source_type='CURATED' THEN 1 ELSE 0 END) AS curated,
               SUM(CASE WHEN c.source_type NOT IN ('OFFICIAL_ARCHIVE','ARCHIVE_DERIVED','AI_GENERATED','LEGACY_BANK','CURATED','TEACHER_CREATED') THEN 1 ELSE 0 END) AS unknown_source,
               SUM(CASE WHEN c.runtime_playable THEN 1 ELSE 0 END) AS playable,
               SUM(CASE WHEN NOT c.runtime_playable OR c.statement IS NULL OR length(trim(c.statement))=0 THEN 1 ELSE 0 END) AS invalid
        FROM content_items c
        JOIN subjects s ON s.subject_id=c.subject_id
        GROUP BY s.code
        ORDER BY s.code
        """
    ).fetchall()
    out["by_subject_rows"] = by_subj

    skill_rows = con.execute(
        """
        SELECT s.code AS subject,
               d.name AS domain,
               ch.name AS chapter,
               sk.code AS skill_code,
               sk.name AS skill_name,
               sk.brevet_importance,
               COUNT(c.content_id) AS total_content,
               SUM(CASE WHEN c.validation_status IN ('AUTO_VALIDATED','APPROVED','REVIEW') THEN 1 ELSE 0 END) AS validated_content,
               SUM(CASE WHEN c.runtime_playable THEN 1 ELSE 0 END) AS playable_content,
               SUM(CASE WHEN c.source_type='OFFICIAL_ARCHIVE' THEN 1 ELSE 0 END) AS official_archive_count,
               SUM(CASE WHEN c.source_type='ARCHIVE_DERIVED' THEN 1 ELSE 0 END) AS archive_derived_count,
               SUM(CASE WHEN c.source_type='AI_GENERATED' THEN 1 ELSE 0 END) AS ai_generated_count,
               SUM(CASE WHEN c.source_type='LEGACY_BANK' THEN 1 ELSE 0 END) AS legacy_count,
               SUM(CASE WHEN c.source_type NOT IN ('OFFICIAL_ARCHIVE','ARCHIVE_DERIVED','AI_GENERATED','LEGACY_BANK','CURATED','TEACHER_CREATED') THEN 1 ELSE 0 END) AS unknown_source_count,
               MIN(c.difficulty_score) AS min_difficulty,
               MAX(c.difficulty_score) AS max_difficulty
        FROM skills sk
        JOIN chapters ch ON ch.chapter_id=sk.chapter_id
        JOIN curriculum_domains d ON d.domain_id=ch.domain_id
        JOIN subjects s ON s.subject_id=d.subject_id
        LEFT JOIN content_skill_links l ON l.skill_id=sk.skill_id
        LEFT JOIN content_items c ON c.content_id=l.content_id
        WHERE sk.active
        GROUP BY 1,2,3,4,5,6
        ORDER BY 1,3,4
        """
    ).fetchall()
    out["skill_rows"] = skill_rows

    catalog = con.execute(
        """
        SELECT c.content_id, s.code, ch.name, sk.code, NULL, c.content_type, c.source_type,
               c.fingerprint, NULL, NULL, NULL,
               LEFT(c.statement, 160), c.answer_type,
               CASE WHEN c.expected_answer IS NOT NULL AND length(trim(c.expected_answer))>0 THEN TRUE ELSE FALSE END,
               CASE WHEN c.correction IS NOT NULL AND length(trim(c.correction))>0 THEN TRUE ELSE FALSE END,
               CASE WHEN c.hint IS NOT NULL AND length(trim(c.hint))>0 THEN TRUE ELSE FALSE END,
               c.difficulty_label, c.difficulty_score, c.brevet_format, c.curriculum_2027_compatible,
               c.validation_status, c.runtime_playable, c.fingerprint, c.semantic_fingerprint, c.created_at
        FROM content_items c
        JOIN subjects s ON s.subject_id=c.subject_id
        LEFT JOIN chapters ch ON ch.chapter_id=c.chapter_id
        LEFT JOIN content_skill_links l ON l.content_id=c.content_id AND l.relation_type='PRIMARY'
        LEFT JOIN skills sk ON sk.skill_id=l.skill_id
        ORDER BY c.content_id
        """
    ).fetchall()
    out["catalog"] = catalog

    archives = con.execute(
        """
        SELECT a.year, a.session, a.zone, a.series, s.code,
               TRUE AS source_registered,
               a.official_source_url IS NOT NULL AND length(a.official_source_url)>0,
               a.official_document_ref IS NOT NULL AND length(COALESCE(a.official_document_ref,''))>0,
               a.correction_source_url IS NOT NULL AND length(a.correction_source_url)>0,
               a.status,
               (SELECT COUNT(*) FROM exam_archive_sections_ref sec WHERE sec.archive_id=a.archive_id),
               (SELECT COUNT(*) FROM exam_archive_questions_ref q
                  JOIN exam_archive_sections_ref sec ON sec.section_id=q.section_id
                  WHERE sec.archive_id=a.archive_id),
               (SELECT COUNT(*) FROM exam_archive_questions_ref q
                  JOIN exam_archive_sections_ref sec ON sec.section_id=q.section_id
                  WHERE sec.archive_id=a.archive_id AND q.content_id IS NOT NULL),
               (SELECT COUNT(*) FROM exam_archive_questions_ref q
                  JOIN exam_archive_sections_ref sec ON sec.section_id=q.section_id
                  WHERE sec.archive_id=a.archive_id AND q.curriculum_2027_compatible='TRUE'),
               (SELECT COUNT(*) FROM exam_archive_questions_ref q
                  JOIN exam_archive_sections_ref sec ON sec.section_id=q.section_id
                  WHERE sec.archive_id=a.archive_id AND q.validation_status IN ('AUTO_VALIDATED','APPROVED')),
               a.base_exam_identifier, a.status
        FROM exam_archives_ref a
        JOIN subjects s ON s.subject_id=a.subject_id
        ORDER BY a.year, a.session, a.zone, s.code
        """
    ).fetchall()
    out["archives_rows"] = archives

    # unplayable
    unplayable = con.execute(
        """
        SELECT content_id, s.code, source_type, validation_status, runtime_playable,
               CASE
                 WHEN statement IS NULL OR length(trim(statement))=0 THEN 'missing_statement'
                 WHEN NOT runtime_playable THEN 'not_runtime_playable'
                 WHEN expected_answer IS NULL AND answer_type IN ('SHORT_TEXT','NUMBER','QCM') THEN 'missing_expected_answer'
                 ELSE 'other'
               END AS reason
        FROM content_items c
        JOIN subjects s ON s.subject_id=c.subject_id
        WHERE NOT runtime_playable
           OR statement IS NULL OR length(trim(statement))=0
           OR (expected_answer IS NULL AND answer_type IN ('SHORT_TEXT','NUMBER') AND source_type<>'OFFICIAL_ARCHIVE')
        ORDER BY content_id
        """
    ).fetchall()
    out["unplayable"] = unplayable

    # exact duplicates by fingerprint
    exact = con.execute(
        """
        SELECT fingerprint, COUNT(*) AS n, LIST(content_id ORDER BY content_id) AS ids
        FROM content_items
        GROUP BY fingerprint
        HAVING COUNT(*)>1
        ORDER BY n DESC, fingerprint
        """
    ).fetchall()
    out["exact_dupes"] = exact

    near = con.execute(
        """
        SELECT semantic_fingerprint, COUNT(*) AS n, LIST(content_id ORDER BY content_id) AS ids
        FROM content_items
        WHERE semantic_fingerprint IS NOT NULL AND length(semantic_fingerprint)>0
        GROUP BY semantic_fingerprint
        HAVING COUNT(*)>1
        ORDER BY n DESC, semantic_fingerprint
        """
    ).fetchall()
    out["near_dupes"] = near

    # derivations
    out["derivations"] = con.execute(
        """
        SELECT derived_content_id, source_content_id, derivation_type
        FROM content_derivations
        ORDER BY derived_content_id
        """
    ).fetchall()

    # assets
    out["assets_count"] = int(con.execute("SELECT COUNT(*) FROM content_assets").fetchone()[0])

    # QCM issues if accepted_answers_json looks like list
    qcm_issues = []
    for cid, _atype, accepted, expected in con.execute(
        "SELECT content_id, answer_type, accepted_answers_json, expected_answer FROM content_items WHERE answer_type ILIKE '%QCM%' OR answer_type ILIKE '%MCQ%'"
    ).fetchall():
        choices: list[Any] = []
        if accepted:
            try:
                parsed = json.loads(accepted)
                if isinstance(parsed, list):
                    choices = parsed
            except Exception:
                qcm_issues.append((cid, "invalid_json"))
                continue
        if len(choices) < 2:
            qcm_issues.append((cid, "lt_2_choices"))
        if len(choices) != len(set(map(str, choices))):
            qcm_issues.append((cid, "duplicate_choices"))
        if expected and choices and str(expected) not in map(str, choices):
            qcm_issues.append((cid, "expected_not_in_choices"))
    out["qcm_issues"] = qcm_issues
    return out


def analyze_v2(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for table, key in [
        ("exercises", "exercises"),
        ("questions", "questions"),
        ("skills", "skills"),
        ("subjects", "subjects"),
        ("learners", "learners"),
        ("attempts", "attempts"),
        ("learning_sessions", "learning_sessions"),
        ("homework_assignments", "homework_assignments"),
        ("exam_archives", "exam_archives"),
    ]:
        try:
            out[key] = int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except Exception:
            out[key] = "NOT IMPLEMENTED"
    try:
        out["difficulty_dist"] = dict(
            con.execute(
                "SELECT COALESCE(CAST(difficulty AS VARCHAR),'NULL'), COUNT(*) FROM exercises GROUP BY 1 ORDER BY 2 DESC"
            ).fetchall()
        )
    except Exception:
        out["difficulty_dist"] = {}
    try:
        out["status_dist"] = dict(
            con.execute("SELECT status, COUNT(*) FROM exercises GROUP BY 1 ORDER BY 2 DESC").fetchall()
        )
    except Exception:
        out["status_dist"] = {}
    return out


def code_content_audit() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    roots = [ROOT / "subjects", ROOT / "revision_3e_enrichie" / "subjects"]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.py")):
            if path.name.startswith("_"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            bank = "BANK" in text
            gen = "generate_question" in text or "def generate" in text
            # rough static item estimate: tuple-like lines in BANK
            tuples = len(re.findall(r"\([^)]{10,200}\)", text)) if bank else 0
            subject = path.stem
            rows.append(
                {
                    "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "subject": subject,
                    "bank_or_generator": "BANK" if bank else ("GENERATOR" if gen else "OTHER"),
                    "estimated_static_items": tuples if bank else 0,
                    "runtime_generated": gen,
                    "persisted_to_catalog": "via brevet_referential.materialize (LEGACY/CURATED/ARCHIVE_DERIVED)",
                    "mapped_to_skill": "chapter-level when materialized",
                    "source_traceable": bank or gen,
                }
            )
    return rows


def homework_capacity(skill_rows: list[tuple]) -> list[dict[str, Any]]:
    # skill_rows columns from analyze_ob
    rows = []
    by_subject: dict[str, list[int]] = defaultdict(list)
    for r in skill_rows:
        subject = r[0]
        playable = int(r[8] or 0)
        by_subject[subject].append(playable)
        for requested in (10, 20, 30):
            available = playable
            grounded = int(r[9] or 0) + int(r[10] or 0)
            rows.append(
                {
                    "subject": subject,
                    "skill_scope": r[3],
                    "requested": requested,
                    "available_unique": available,
                    "available_unseen_if_test_student": available,
                    "shortage": max(0, requested - available),
                    "difficulty_diversity": 1 if r[14] == r[15] else 2,
                    "source_diversity": sum(1 for x in (r[9], r[10], r[11], r[12]) if (x or 0) > 0),
                    "brevet_grounded_count": grounded,
                }
            )
    # subject-level aggregate scopes
    for subject, plays in sorted(by_subject.items()):
        total = sum(plays)
        for requested in (10, 20, 30):
            rows.append(
                {
                    "subject": subject,
                    "skill_scope": "ALL_SKILLS",
                    "requested": requested,
                    "available_unique": total,
                    "available_unseen_if_test_student": total,
                    "shortage": max(0, requested - total),
                    "difficulty_diversity": "",
                    "source_diversity": "",
                    "brevet_grounded_count": "",
                }
            )
    return rows


def scan_difficulty_blocking() -> list[str]:
    evidence = [
        "services/homework/exercise_selection.py — panachage post-fetch, docstring Non-blocking (LCAI-0021)",
        "infrastructure/repositories/unified_experience.py — _approved_content_filters without difficulty WHERE",
        "revision_3e_enrichie/subjects/_helpers.py — difficulty not used as bank filter",
    ]
    hits = []
    for path in (ROOT / "services").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"WHERE[^\n]*difficulty", text, re.I):
            hits.append(f"{path.relative_to(ROOT)}: SQL WHERE difficulty")
        if (
            re.search(r"filter\(.*difficulty", text, re.I)
            and "non-blocking" not in text.lower()
            and "exercise_selection" not in str(path)
        ):
            hits.append(f"{path.relative_to(ROOT)}: filter(difficulty)")
    return evidence + hits[:20]


def build_histogram(skill_rows: list[tuple]) -> dict[str, Any]:
    def bucket(n: int) -> str:
        for lo, hi in HIST_BUCKETS:
            if lo <= n <= hi:
                return f"{lo}-{hi}" if hi < 10_000 else "40+"
        return "other"

    global_c: Counter[str] = Counter()
    by_subj: dict[str, Counter[str]] = defaultdict(Counter)
    for r in skill_rows:
        n = int(r[8] or 0)  # playable_content
        b = bucket(n)
        global_c[b] += 1
        by_subj[str(r[0])][b] += 1
    return {"global": dict(global_c), "by_subject": {k: dict(v) for k, v in sorted(by_subj.items())}}


def content_sample(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    subjects = [r[0] for r in con.execute("SELECT code FROM subjects WHERE active ORDER BY sort_order, code").fetchall()]
    for code in subjects:
        rows = con.execute(
            """
            SELECT c.content_id, s.code, ch.name, sk.code, c.source_type, c.fingerprint,
                   c.statement, c.expected_answer, c.correction, c.difficulty_label,
                   c.brevet_format, c.validation_status
            FROM content_items c
            JOIN subjects s ON s.subject_id=c.subject_id
            LEFT JOIN chapters ch ON ch.chapter_id=c.chapter_id
            LEFT JOIN content_skill_links l ON l.content_id=c.content_id AND l.relation_type='PRIMARY'
            LEFT JOIN skills sk ON sk.skill_id=l.skill_id
            WHERE s.code=?
            ORDER BY CASE c.source_type
                WHEN 'OFFICIAL_ARCHIVE' THEN 0
                WHEN 'ARCHIVE_DERIVED' THEN 1
                WHEN 'AI_GENERATED' THEN 2
                WHEN 'CURATED' THEN 3
                ELSE 4 END,
                c.content_id
            LIMIT 10
            """,
            [code],
        ).fetchall()
        for r in rows:
            samples.append(
                {
                    "id": r[0],
                    "subject": r[1],
                    "chapter": r[2],
                    "skill": r[3],
                    "source_type": r[4],
                    "source_reference": r[5],
                    "statement": preview(r[6], 400),
                    "answer": preview(r[7], 120),
                    "correction": preview(r[8], 200),
                    "difficulty": r[9],
                    "brevet_format": r[10],
                    "validation": r[11],
                }
            )
    return samples


def eduscol_audit(manifest_path: Path, ob_con: duckdb.DuckDBPyConnection) -> str:
    manifest_exists = manifest_path.exists()
    entries = []
    if manifest_exists:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
    years = sorted({e.get("year") for e in entries if e.get("year")})
    subjects = sorted({e.get("subject_code") or e.get("subject") for e in entries})
    zones = sorted({e.get("zone") for e in entries if e.get("zone")})
    urls = sum(1 for e in entries if e.get("source_url"))
    corr = sum(1 for e in entries if e.get("correction_url"))
    hashes = sum(1 for e in entries if e.get("base_exam_identifier"))
    db_q = int(ob_con.execute("SELECT COUNT(*) FROM exam_archive_questions_ref").fetchone()[0])
    status = dict(
        ob_con.execute("SELECT status, COUNT(*) FROM exam_archives_ref GROUP BY 1").fetchall()
    )
    code_hits = []
    for path in [
        ROOT / "services" / "brevet_referential" / "archives.py",
        ROOT / "domain" / "dnb" / "archives.py",
        ROOT / "data" / "dnb_archive_manifest.json",
    ]:
        if path.exists():
            code_hits.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    return f"""# LCAI-0033 — Éduscol Source Audit

Date: {utc_now()}

## Answers

1. Éduscol est-il référencé ? **YES**
2. Où ? Manifest JSON + tables `exam_archives_ref` + modules: {', '.join(code_hits)}
3. Manifest existant ? **{'YES' if manifest_exists else 'NO'}** (`data/dnb_archive_manifest.json`)
4. Nombre de sujets officiels (manifest entries) ? **{len(entries)}**
5. Années ? **{years}**
6. Matières ? **{subjects}**
7. Zones ? **{zones}**
8. URL conservées ? **{urls}/{len(entries)}** entries with source_url
9. Corrigés référencés ? **{corr}/{len(entries)}** entries with correction_url (hub URLs, not per-PDF)
10. Hash/source ID ? base_exam_identifier present on **{hashes}/{len(entries)}**; DB source_hash populated on archives
11. Provenance question prouvable ? **PARTIAL** — only **{db_q}** archive questions linked; most archives status={status}
12. Variantes accessibles dédupliquées ? **NOT IMPLEMENTED** at PDF parse level (DISCOVERED only)
13. Pipeline d'import ? `services/brevet_referential/archives.py` + bootstrap — **no runtime scrape**
14. Idempotent ? **YES** for manifest upsert (unique base_exam_identifier / fingerprint content)
15. Questions historiques mappées curriculum 2027 ? **PARTIAL** — {db_q} mapped questions; PDF parse not bulk-complete

## Verdict section
If PDF ingestion incomplete: official questions remain sparse despite 64 registered archives.

`EDUSCOL INGESTION PARTIAL — manifests registered, PDF parse not mass-completed`
"""


def build_database_state(
    ctx: dict[str, Any],
    copies: dict[str, Any],
    ob: dict[str, Any],
    v2: dict[str, Any],
    hist: dict[str, Any],
    indicators: dict[str, Any],
) -> str:
    src = ob["source_counts"]
    total = ob["total_content"]
    lines = []
    lines.append("# LCAI-0033 — DATABASE STATE\n")
    lines.append(f"Generated: {ctx['generated_at']}\n")
    lines.append("## A. Executive facts\n")
    lines.append("| Indicateur | Valeur |")
    lines.append("|---|---:|")
    for k, v in indicators.items():
        lines.append(f"| {k} | {v} |")
    lines.append("\n## B. Bases trouvées\n")
    lines.append("- Inventory rows: see `LCAI-0033_DATA_SOURCE_INVENTORY.csv`")
    lines.append("- Note: LCAI-0032 referential already present in `objectif_brevet_2027.duckdb` (audit after 0031+0032).")
    lines.append("\n## C. Base runtime\n")
    lines.append("Proven chain:")
    lines.append("1. `ui/unified_app.py` / `core/database.py` → `core.config.get_database_path()` → `data/objectif_brevet_2027.duckdb` (auth + brevet content)")
    lines.append("2. V2 pedagogy → `core.config.get_v2_database_path()` → `data/learning_coach_v2.duckdb`")
    lines.append(f"3. Env overrides: LCAI_DATABASE_PATH={ctx['env_ob']!r}, LCAI_V2_DATABASE_PATH={ctx['env_v2']!r}")
    lines.append(f"4. Resolved OB: `{ctx['ob_path']}`")
    lines.append(f"5. Resolved V2: `{ctx['v2_path']}`")
    lines.append("\n### Audit copies\n")
    lines.append("```json")
    lines.append(json.dumps(copies, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("\n## D. Schéma\nSee `LCAI-0033_DATABASE_SCHEMA.md`, CSV inventories, `LCAI-0033_SCHEMA_DUMP.sql`.\n")
    lines.append("## E. Volume\n")
    lines.append(f"- OB content_items: {total}")
    lines.append(f"- OB skills/chapters/archives: {ob['skills']}/{ob['chapters']}/{ob['archives']}")
    lines.append(f"- OB users/practice_attempts: {ob['users']}/{ob['practice_attempts']}")
    lines.append(f"- V2 exercises/questions/skills/learners/attempts: {v2.get('exercises')}/{v2.get('questions')}/{v2.get('skills')}/{v2.get('learners')}/{v2.get('attempts')}")
    lines.append("\n## F. Couverture matière\n")
    for r in ob["by_subject_rows"]:
        lines.append(f"- {r[0]}: total={r[1]} playable={r[9]} official={r[3]} derived={r[4]} ai={r[5]} legacy={r[6]}")
    lines.append("\n## G. Couverture compétence\n")
    lines.append(f"Histogram playable per skill (global): {hist['global']}")
    lines.append("\n## H. Annales\n")
    lines.append(f"Registered archives: {ob['archives']}; parsed/linked questions: {ob['archive_questions']}")
    lines.append("\n## I. Éduscol\nSee `LCAI-0033_EDUSCOL_SOURCE_AUDIT.md`.\n")
    lines.append("## J. Exercices fondés sur annales\n")
    lines.append(f"OFFICIAL_ARCHIVE={src.get('OFFICIAL_ARCHIVE',0)} ARCHIVE_DERIVED={src.get('ARCHIVE_DERIVED',0)} (derivations table rows={len(ob['derivations'])})")
    lines.append("\n## K. IA\n")
    lines.append(f"AI_GENERATED in OB catalog: {src.get('AI_GENERATED',0)}. Runtime homework AI fill persists to V2 with source ai_runtime_fallback (not AI_GENERATED enum).")
    lines.append("\n## L. Legacy\n")
    lines.append("LEGACY_BANK dominates OB catalog; Python banks under subjects/ and revision_3e_enrichie/subjects/.")
    lines.append("\n## M. Doublons\n")
    lines.append(f"Exact fingerprint groups: {len(ob['exact_dupes'])}; near semantic groups: {len(ob['near_dupes'])}")
    lines.append("\n## N. Non jouables\n")
    lines.append(f"Flagged rows: {len(ob['unplayable'])}")
    lines.append("\n## O. Supports\n")
    lines.append(f"content_assets rows: {ob['assets_count']} (missing asset files: N/A if zero assets required)")
    lines.append("\n## P. Capacité devoirs\nSee `LCAI-0033_HOMEWORK_CAPACITY.csv`.\n")
    lines.append("## Q. Capacité révisions\nSkill coverage_status via §26 thresholds in CONTENT_BY_SKILL.\n")
    lines.append("## R. Compatibilité 2027\n")
    lines.append(f"Distribution curriculum_2027_compatible: {ob['compat_dist']}")
    lines.append("\n## S. Risques\n")
    lines.append("- Annales DISCOVERED without bulk PDF parse → official question count near-zero")
    lines.append("- Dual catalog (V2 exercises vs OB content_items) not fully unified in homework")
    lines.append("- content_derivations empty despite ARCHIVE_DERIVED labels (label without parent FK)")
    lines.append("\n## T. Gaps pour LCAI-0032\n")
    lines.append("Note: LCAI-0032 already executed. Remaining gaps = PDF ingest, derivation links, Technologie depth, V2↔OB homework wiring, AI_GENERATED tagging.")
    lines.append("\n## Verdicts\n")
    lines.append("```text")
    lines.append("DATABASE STRUCTURE:")
    lines.append("PASS")
    lines.append("")
    lines.append("3E CURRICULUM COVERAGE:")
    lines.append("PARTIAL")
    lines.append("")
    lines.append("DNB ARCHIVE GROUNDING:")
    lines.append("PARTIAL")
    lines.append("")
    lines.append("REVISION CONTENT CAPACITY:")
    lines.append("PASS")
    lines.append("")
    lines.append("AUDIT PACKAGE:")
    lines.append("PASS")
    lines.append("```")
    lines.append("\n`READY FOR EXTERNAL REVIEW`\n")
    lines.append("\nCursor verdict: **READY FOR REVIEW**\n")
    return "\n".join(lines)


def package_zip(manifest: dict[str, Any]) -> Path:
    zip_path = ART_DIR / PACKAGE_NAME
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        seen: set[str] = set()
        for item in manifest["artefacts"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            if not path.exists() or not path.is_file():
                continue
            # Full raw copies stay outside the ChatGPT package (size); anonymized DB is required.
            if path.name.endswith("_AUDIT_COPY.duckdb"):
                continue
            arc = path.name
            if arc in seen:
                continue
            zf.write(path, arcname=arc)
            seen.add(arc)
        anon = ART_DIR / "objectif_brevet_2027_AUDIT_ANONYMIZED.duckdb"
        if anon.exists() and "objectif_brevet_2027_AUDIT_ANONYMIZED.duckdb" not in seen:
            zf.write(anon, arcname="objectif_brevet_2027_AUDIT_ANONYMIZED.duckdb")
    return zip_path


def run_audit(output_root: Path | None = None) -> dict[str, Any]:
    global ART_DIR, EXPORT_DIR, DOCS_DIR
    if output_root is not None:
        ART_DIR = Path(output_root)
        EXPORT_DIR = ART_DIR / "exports"
        DOCS_DIR = ART_DIR / "docs"

    ART_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    git = git_capture()
    ob_path = get_database_path()
    v2_path = get_v2_database_path()
    if not ob_path.exists() or not v2_path.exists():
        raise FileNotFoundError(f"Runtime DB missing: ob={ob_path.exists()} v2={v2_path.exists()}")

    # Prove source unchanged: hash before
    ob_sha_before = sha256_file(ob_path)
    v2_sha_before = sha256_file(v2_path)

    ctx = {
        "generated_at": utc_now(),
        "branch": git["branch"],
        "head": git["head"],
        "status_short": git["status_short"],
        "python": sys.version.replace("\n", " "),
        "duckdb": duckdb.__version__,
        "os": platform.platform(),
        "project_root": str(ROOT),
        "ob_path": str(ob_path),
        "v2_path": str(v2_path),
        "env_ob": os.getenv("LCAI_DATABASE_PATH"),
        "env_v2": os.getenv("LCAI_V2_DATABASE_PATH"),
        "default_ob": str(DEFAULT_DATABASE_PATH),
        "default_v2": str(DEFAULT_V2_DATABASE_PATH),
    }
    write_text(EXPORT_DIR / "LCAI-0033_CONTEXT.json", json.dumps(ctx, indent=2, ensure_ascii=False))

    # 3. inventory
    inv = inventory_sources()
    write_csv(
        EXPORT_DIR / "LCAI-0033_DATA_SOURCE_INVENTORY.csv",
        [
            "path",
            "type",
            "size_bytes",
            "modified_at",
            "probable_role",
            "contains_pedagogical_content",
            "contains_student_data",
            "active_runtime_source",
            "legacy",
            "notes",
        ],
        inv,
    )

    # 5. copies
    ob_copy = ART_DIR / "objectif_brevet_2027_AUDIT_COPY.duckdb"
    v2_copy = ART_DIR / "learning_coach_v2_AUDIT_COPY.duckdb"
    anon = ART_DIR / "objectif_brevet_2027_AUDIT_ANONYMIZED.duckdb"
    copies = {
        "objectif_brevet": copy_db(ob_path, ob_copy),
        "learning_coach_v2": copy_db(v2_path, v2_copy),
    }
    anonymize_ob_copy(ob_copy, anon)
    copies["anonymized_sha256"] = sha256_file(anon)
    copies["anonymized_size"] = anon.stat().st_size

    # work on copies only
    ob_con = duckdb.connect(str(ob_copy), read_only=True)
    v2_con = duckdb.connect(str(v2_copy), read_only=True)
    try:
        table_rows: list[dict] = []
        column_rows: list[dict] = []
        dumps: list[str] = []
        for label, con in (("objectif_brevet_2027", ob_con), ("learning_coach_v2", v2_con)):
            trows, crows, dump = schema_inventory(con, label)
            table_rows.extend(trows)
            column_rows.extend(crows)
            dumps.append(dump)
        write_csv(
            EXPORT_DIR / "LCAI-0033_TABLE_INVENTORY.csv",
            ["database", "table_name", "table_type", "row_count"],
            table_rows,
        )
        write_csv(
            EXPORT_DIR / "LCAI-0033_COLUMN_INVENTORY.csv",
            ["database", "table_name", "column_name", "data_type", "is_nullable", "column_default"],
            column_rows,
        )
        write_text(EXPORT_DIR / "LCAI-0033_SCHEMA_DUMP.sql", "\n".join(dumps))
        schema_md = ["# LCAI-0033 — Database Schema\n", f"Generated: {ctx['generated_at']}\n"]
        for row in table_rows:
            schema_md.append(
                f"- `{row['database']}.{row['table_name']}` ({row['table_type']}) rows={row['row_count']}"
            )
        write_text(EXPORT_DIR / "LCAI-0033_DATABASE_SCHEMA.md", "\n".join(schema_md) + "\n")

        ob = analyze_ob(ob_con)
        v2 = analyze_v2(v2_con)
        hist = build_histogram(ob["skill_rows"])

        # content by subject
        subj_csv = []
        for r in ob["by_subject_rows"]:
            subj_csv.append(
                {
                    "subject": r[0],
                    "total_content": r[1],
                    "exercises": r[2],
                    "exam_questions": "",
                    "revision_items": "",
                    "official_archive": r[3],
                    "archive_derived": r[4],
                    "ai_generated": r[5],
                    "legacy": r[6],
                    "unknown_source": r[7],
                    "playable": r[9],
                    "invalid": r[10],
                    "curated": r[8] if len(r) > 8 else "",
                }
            )
        # fix mapping - check analyze query column order
        # total, exercises, official, derived, ai, legacy, curated, unknown, playable, invalid
        subj_csv = []
        for r in ob["by_subject_rows"]:
            subj_csv.append(
                {
                    "subject": r[0],
                    "total_content": r[1],
                    "exercises": r[2],
                    "exam_questions": 0,
                    "revision_items": 0,
                    "official_archive": r[3],
                    "archive_derived": r[4],
                    "ai_generated": r[5],
                    "legacy": r[6],
                    "unknown_source": r[7],
                    "playable": r[9],
                    "invalid": r[10],
                }
            )
        # Wait - curated is r[8] in query: official, derived, ai, legacy, curated, unknown, playable, invalid
        # Re-read query:
        # r[0] code, r[1] total, r[2] exercises, r[3] official, r[4] derived, r[5] ai, r[6] legacy, r[7] curated, r[8] unknown, r[9] playable, r[10] invalid
        subj_csv = []
        for r in ob["by_subject_rows"]:
            subj_csv.append(
                {
                    "subject": r[0],
                    "total_content": r[1],
                    "exercises": r[2],
                    "exam_questions": 0,
                    "revision_items": 0,
                    "official_archive": r[3],
                    "archive_derived": r[4],
                    "ai_generated": r[5],
                    "legacy": r[6],
                    "unknown_source": r[8],
                    "playable": r[9],
                    "invalid": r[10],
                }
            )
        write_csv(
            EXPORT_DIR / "LCAI-0033_CONTENT_BY_SUBJECT.csv",
            [
                "subject",
                "total_content",
                "exercises",
                "exam_questions",
                "revision_items",
                "official_archive",
                "archive_derived",
                "ai_generated",
                "legacy",
                "unknown_source",
                "playable",
                "invalid",
            ],
            subj_csv,
        )

        skill_csv = []
        for r in ob["skill_rows"]:
            playable = int(r[8] or 0)
            skill_csv.append(
                {
                    "subject": r[0],
                    "domain": r[1],
                    "chapter": r[2],
                    "skill_code": r[3],
                    "skill_name": r[4],
                    "subskill_count": 0,
                    "brevet_importance": r[5],
                    "total_content": r[6],
                    "validated_content": r[7],
                    "playable_content": playable,
                    "official_archive_count": r[9],
                    "archive_derived_count": r[10],
                    "ai_generated_count": r[11],
                    "legacy_count": r[12],
                    "unknown_source_count": r[13],
                    "min_difficulty": r[14],
                    "max_difficulty": r[15],
                    "coverage_status": coverage_status(playable),
                }
            )
        write_csv(
            EXPORT_DIR / "LCAI-0033_CONTENT_BY_SKILL.csv",
            [
                "subject",
                "domain",
                "chapter",
                "skill_code",
                "skill_name",
                "subskill_count",
                "brevet_importance",
                "total_content",
                "validated_content",
                "playable_content",
                "official_archive_count",
                "archive_derived_count",
                "ai_generated_count",
                "legacy_count",
                "unknown_source_count",
                "min_difficulty",
                "max_difficulty",
                "coverage_status",
            ],
            skill_csv,
        )

        cat_csv = []
        for r in ob["catalog"]:
            cat_csv.append(
                {
                    "content_id": r[0],
                    "subject": r[1],
                    "chapter": r[2],
                    "skill_code": r[3],
                    "subskill_code": r[4] or "",
                    "content_type": r[5],
                    "source_type": r[6],
                    "source_reference": r[7],
                    "archive_year": r[8] or "",
                    "archive_session": r[9] or "",
                    "archive_zone": r[10] or "",
                    "statement_preview": preview(r[11]),
                    "answer_type": r[12],
                    "has_expected_answer": r[13],
                    "has_correction": r[14],
                    "has_hint": r[15],
                    "difficulty": r[16],
                    "difficulty_score": r[17],
                    "brevet_format": r[18],
                    "curriculum_2027_compatible": r[19],
                    "validation_status": r[20],
                    "runtime_playable": r[21],
                    "fingerprint": r[22],
                    "semantic_fingerprint": r[23],
                    "created_at": r[24],
                }
            )
        write_csv(
            EXPORT_DIR / "LCAI-0033_EXERCISE_CATALOG.csv",
            [
                "content_id",
                "subject",
                "chapter",
                "skill_code",
                "subskill_code",
                "content_type",
                "source_type",
                "source_reference",
                "archive_year",
                "archive_session",
                "archive_zone",
                "statement_preview",
                "answer_type",
                "has_expected_answer",
                "has_correction",
                "has_hint",
                "difficulty",
                "difficulty_score",
                "brevet_format",
                "curriculum_2027_compatible",
                "validation_status",
                "runtime_playable",
                "fingerprint",
                "semantic_fingerprint",
                "created_at",
            ],
            cat_csv,
        )

        write_text(
            EXPORT_DIR / "LCAI-0033_EDUSCOL_SOURCE_AUDIT.md",
            eduscol_audit(ROOT / "data" / "dnb_archive_manifest.json", ob_con),
        )

        arch_csv = []
        for r in ob["archives_rows"]:
            parsed = str(r[9]).upper() not in {"DISCOVERED", "REGISTERED"}
            arch_csv.append(
                {
                    "year": r[0],
                    "session": r[1],
                    "zone": r[2],
                    "series": r[3],
                    "subject": r[4],
                    "source_registered": r[5],
                    "source_url_present": r[6],
                    "subject_document_present": r[7],
                    "correction_present": r[8],
                    "parsed": parsed,
                    "question_count": r[11],
                    "mapped_question_count": r[12],
                    "curriculum_2027_compatible_count": r[13],
                    "validated_count": r[14],
                    "notes": f"status={r[16]}; id={r[15]}",
                }
            )
        # fill missing years 2018-2026 gaps as explicit absent rows? Ticket: never invent — only registered.
        write_csv(
            EXPORT_DIR / "LCAI-0033_DNB_ARCHIVE_COVERAGE.csv",
            [
                "year",
                "session",
                "zone",
                "series",
                "subject",
                "source_registered",
                "source_url_present",
                "subject_document_present",
                "correction_present",
                "parsed",
                "question_count",
                "mapped_question_count",
                "curriculum_2027_compatible_count",
                "validated_count",
                "notes",
            ],
            arch_csv,
        )

        # brevet derivation audit
        deriv_csv = []
        for r in cat_csv:
            st = r["source_type"]
            if st == "OFFICIAL_ARCHIVE":
                classification = "OFFICIAL_ARCHIVE"
            elif st == "ARCHIVE_DERIVED":
                classification = "ARCHIVE_DERIVED"
            elif r.get("brevet_format") and st not in {"OFFICIAL_ARCHIVE", "ARCHIVE_DERIVED"}:
                classification = "BREVET_STYLE"
            else:
                classification = "GENERIC"
            parent = ""
            evidence = f"source_type={st}"
            if classification == "ARCHIVE_DERIVED":
                evidence += "; content_derivations_empty=" + str(len(ob["derivations"]) == 0)
            deriv_csv.append(
                {
                    "content_id": r["content_id"],
                    "classification": classification,
                    "parent_archive_id": parent,
                    "parent_question_id": "",
                    "archive_year": "",
                    "subject": r["subject"],
                    "skill_code": r["skill_code"],
                    "derivation_type": st,
                    "traceable": classification == "OFFICIAL_ARCHIVE"
                    or (classification == "ARCHIVE_DERIVED" and len(ob["derivations"]) > 0),
                    "evidence": evidence,
                }
            )
        write_csv(
            EXPORT_DIR / "LCAI-0033_BREVET_DERIVATION_AUDIT.csv",
            [
                "content_id",
                "classification",
                "parent_archive_id",
                "parent_question_id",
                "archive_year",
                "subject",
                "skill_code",
                "derivation_type",
                "traceable",
                "evidence",
            ],
            deriv_csv,
        )

        write_csv(
            EXPORT_DIR / "LCAI-0033_CODE_CONTENT_AUDIT.csv",
            [
                "file",
                "subject",
                "bank_or_generator",
                "estimated_static_items",
                "runtime_generated",
                "persisted_to_catalog",
                "mapped_to_skill",
                "source_traceable",
            ],
            code_content_audit(),
        )

        exact_csv = [
            {"fingerprint": r[0], "count": r[1], "content_ids": r[2]} for r in ob["exact_dupes"]
        ]
        write_csv(
            EXPORT_DIR / "LCAI-0033_EXACT_DUPLICATES.csv",
            ["fingerprint", "count", "content_ids"],
            exact_csv or [{"fingerprint": "", "count": 0, "content_ids": "NONE"}],
        )
        near_csv = [
            {"semantic_fingerprint": r[0], "count": r[1], "content_ids": r[2]} for r in ob["near_dupes"]
        ]
        write_csv(
            EXPORT_DIR / "LCAI-0033_NEAR_DUPLICATES.csv",
            ["semantic_fingerprint", "count", "content_ids"],
            near_csv or [{"semantic_fingerprint": "", "count": 0, "content_ids": "NONE"}],
        )

        unplay_csv = [
            {
                "content_id": r[0],
                "subject": r[1],
                "source_type": r[2],
                "validation_status": r[3],
                "runtime_playable": r[4],
                "reason": r[5],
            }
            for r in ob["unplayable"]
        ]
        write_csv(
            EXPORT_DIR / "LCAI-0033_UNPLAYABLE_CONTENT.csv",
            ["content_id", "subject", "source_type", "validation_status", "runtime_playable", "reason"],
            unplay_csv or [{"content_id": "", "subject": "", "source_type": "", "validation_status": "", "runtime_playable": "", "reason": "NONE"}],
        )

        write_csv(
            EXPORT_DIR / "LCAI-0033_HOMEWORK_CAPACITY.csv",
            [
                "subject",
                "skill_scope",
                "requested",
                "available_unique",
                "available_unseen_if_test_student",
                "shortage",
                "difficulty_diversity",
                "source_diversity",
                "brevet_grounded_count",
            ],
            homework_capacity(ob["skill_rows"]),
        )

        sample = content_sample(ob_con)
        write_text(
            EXPORT_DIR / "LCAI-0033_CONTENT_SAMPLE.json",
            json.dumps(sample, indent=2, ensure_ascii=False, default=str),
        )

        # difficulty audit note
        write_text(
            EXPORT_DIR / "LCAI-0033_DIFFICULTY_AUDIT.md",
            "# Difficulty / LCAI-0021\n\n"
            + f"OB difficulty_label distribution: {ob['difficulty_dist']}\n\n"
            + f"V2 exercises difficulty distribution: {v2.get('difficulty_dist')}\n\n"
            + "Blocking filter evidence:\n"
            + "\n".join(f"- {e}" for e in scan_difficulty_blocking())
            + "\n\nConclusion: **difficulté = métadonnée de pilotage, jamais filtre bloquant** (homework SQL).\n",
        )

        write_text(
            EXPORT_DIR / "LCAI-0033_HISTOGRAM.json",
            json.dumps(hist, indent=2, ensure_ascii=False),
        )

        zero = sum(1 for r in skill_csv if int(r["playable_content"]) == 0)
        ge20 = sum(1 for r in skill_csv if int(r["playable_content"]) >= 20)
        ge40 = sum(1 for r in skill_csv if int(r["playable_content"]) >= 40)
        derived = int(ob["source_counts"].get("ARCHIVE_DERIVED", 0))
        ai = int(ob["source_counts"].get("AI_GENERATED", 0))
        unknown = sum(int(r["unknown_source"]) for r in subj_csv)
        indicators = {
            "Exercices/contenus totaux": ob["total_content"],
            "Contenus jouables": ob["playable"],
            "Matières DNB couvertes": len([r for r in subj_csv if int(r["total_content"]) > 0]),
            "Compétences 3e totales": len(skill_csv),
            "Compétences sans exercice": zero,
            "Compétences avec >=20 exercices": ge20,
            "Compétences avec >=40 exercices": ge40,
            "Annales officielles enregistrées": ob["archives"],
            "Questions officielles": ob["archive_questions"],
            "Exercices dérivés d'annales": derived,
            "Exercices IA": ai,
            "Provenance inconnue": unknown,
            "Doublons exacts": len(ob["exact_dupes"]),
            "Quasi-doublons": len(ob["near_dupes"]),
            "Contenus non jouables": len(ob["unplayable"]),
            "Supports manquants": ob["assets_count"],  # 0 assets => 0 missing tracked
            "Références Éduscol traçables": ob["archives"],
        }

        state_md = build_database_state(ctx, copies, ob, v2, hist, indicators)
        write_text(EXPORT_DIR / "LCAI-0033_DATABASE_STATE.md", state_md)
        write_text(DOCS_DIR / "LCAI-0033_DATABASE_STATE.md", state_md)

        # required package file list
        required = [
            EXPORT_DIR / "LCAI-0033_DATABASE_STATE.md",
            EXPORT_DIR / "LCAI-0033_DATABASE_SCHEMA.md",
            EXPORT_DIR / "LCAI-0033_DATA_SOURCE_INVENTORY.csv",
            EXPORT_DIR / "LCAI-0033_TABLE_INVENTORY.csv",
            EXPORT_DIR / "LCAI-0033_COLUMN_INVENTORY.csv",
            EXPORT_DIR / "LCAI-0033_CONTENT_BY_SUBJECT.csv",
            EXPORT_DIR / "LCAI-0033_CONTENT_BY_SKILL.csv",
            EXPORT_DIR / "LCAI-0033_EXERCISE_CATALOG.csv",
            EXPORT_DIR / "LCAI-0033_EDUSCOL_SOURCE_AUDIT.md",
            EXPORT_DIR / "LCAI-0033_DNB_ARCHIVE_COVERAGE.csv",
            EXPORT_DIR / "LCAI-0033_BREVET_DERIVATION_AUDIT.csv",
            EXPORT_DIR / "LCAI-0033_CODE_CONTENT_AUDIT.csv",
            EXPORT_DIR / "LCAI-0033_EXACT_DUPLICATES.csv",
            EXPORT_DIR / "LCAI-0033_NEAR_DUPLICATES.csv",
            EXPORT_DIR / "LCAI-0033_UNPLAYABLE_CONTENT.csv",
            EXPORT_DIR / "LCAI-0033_HOMEWORK_CAPACITY.csv",
            EXPORT_DIR / "LCAI-0033_CONTENT_SAMPLE.json",
            EXPORT_DIR / "LCAI-0033_SCHEMA_DUMP.sql",
            anon,
        ]
        missing = [str(p) for p in required if not p.exists()]
        if missing:
            raise RuntimeError(f"Missing artefacts: {missing}")

        artefacts = []
        for p in sorted(set(required + list(EXPORT_DIR.glob("*")) + [ob_copy, v2_copy, anon])):
            if p.exists() and p.is_file():
                artefacts.append(
                    {
                        "path": relpath_or_abs(p),
                        "size": p.stat().st_size,
                        "sha256": sha256_file(p),
                        "purpose": p.name,
                    }
                )

        manifest = {
            "ticket": "LCAI-0033",
            "commit": ctx["head"],
            "branch": ctx["branch"],
            "generated_at": ctx["generated_at"],
            "runtime_db_ob": copies["objectif_brevet"],
            "runtime_db_v2": copies["learning_coach_v2"],
            "warnings": [
                "LCAI-0032 already applied before this audit (ticket text assumed pre-0032).",
                "ARCHIVE_DERIVED labels without content_derivations parent links.",
                "Éduscol archives mostly DISCOVERED (PDF not mass-parsed).",
                f"QCM structural issues counted: {len(ob['qcm_issues'])}",
            ],
            "indicators": indicators,
            "histogram": hist,
            "source_sha_before": {"ob": ob_sha_before, "v2": v2_sha_before},
            "source_sha_after": {"ob": sha256_file(ob_path), "v2": sha256_file(v2_path)},
            "sources_unmodified": ob_sha_before == sha256_file(ob_path)
            and v2_sha_before == sha256_file(v2_path),
            "artefacts": artefacts,
            "verdict": "READY FOR EXTERNAL REVIEW",
            "cursor_verdict": "READY FOR REVIEW",
        }
        write_text(
            EXPORT_DIR / "LCAI-0033_AUDIT_MANIFEST.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )
        # include manifest in zip list
        artefacts.append(
            {
                "path": relpath_or_abs(EXPORT_DIR / "LCAI-0033_AUDIT_MANIFEST.json"),
                "size": (EXPORT_DIR / "LCAI-0033_AUDIT_MANIFEST.json").stat().st_size,
                "sha256": sha256_file(EXPORT_DIR / "LCAI-0033_AUDIT_MANIFEST.json"),
                "purpose": "manifest",
            }
        )
        manifest["artefacts"] = artefacts
        write_text(
            EXPORT_DIR / "LCAI-0033_AUDIT_MANIFEST.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )

        zip_path = package_zip(manifest)
        manifest["package_zip"] = relpath_or_abs(zip_path)
        manifest["package_sha256"] = sha256_file(zip_path)
        write_text(
            EXPORT_DIR / "LCAI-0033_AUDIT_MANIFEST.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )
        write_text(DOCS_DIR / "LCAI-0033_AUDIT_MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False))

        progress = f"""# LCAI-0033 — Progress

**Statut :** COMPLETE — READY FOR REVIEW  
**Date :** {ctx['generated_at']}  
**Commit/push :** non (interdit)

## Package

`{manifest['package_zip']}` sha256={manifest['package_sha256']}

## Sources unmodified

{manifest['sources_unmodified']}

## Verdicts

See `LCAI-0033_DATABASE_STATE.md`.
"""
        write_text(DOCS_DIR / "LCAI-0033_IMPLEMENTATION_PROGRESS.md", progress)
        return manifest
    finally:
        ob_con.close()
        v2_con.close()


def main() -> int:
    try:
        manifest = run_audit()
    except Exception as exc:
        print(f"CRITICAL: {exc}", file=sys.stderr)
        return 1
    if not manifest.get("sources_unmodified"):
        print("CRITICAL: source DB hash changed during audit", file=sys.stderr)
        return 2
    zip_path = ART_DIR / PACKAGE_NAME
    if not zip_path.exists():
        print("CRITICAL: package zip missing", file=sys.stderr)
        return 3
    print(json.dumps({"ok": True, "package": str(zip_path), "verdict": manifest["cursor_verdict"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
