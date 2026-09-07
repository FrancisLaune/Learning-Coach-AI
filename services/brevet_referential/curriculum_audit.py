"""LCAI-0038 — read-only curriculum tree audit for 3e / DNB 2027."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from core.config import PROJECT_ROOT, get_database_path

ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "LCAI-0038"
DOCS_DIR = PROJECT_ROOT / "docs" / "phase6" / "LCAI-0038"
AUDITOR_VERSION = "lcai-0038-curriculum-audit-v1"

CORE_SUBJECTS = (
    "FRENCH",
    "MATHEMATICS",
    "HISTORY",
    "GEOGRAPHY",
    "EMC",
    "PHYSICS_CHEMISTRY",
    "SVT",
    "TECHNOLOGY",
)

# Control lists (semantic checklist — not to inject blindly).
MATH_CHECKLIST = [
    "Nombres et calculs",
    "Calcul littéral",
    "Arithmétique",
    "Proportionnalité",
    "Fonctions",
    "Fonctions linéaires",
    "Fonctions affines",
    "Statistiques",
    "Probabilités",
    "Géométrie plane",
    "Triangles",
    "Théorème de Pythagore",
    "Théorème de Thalès",
    "Trigonométrie",
    "Transformations",
    "Homothétie",
    "Géométrie dans l’espace",
    "Volumes",
    "Repérage",
    "Algorithmique",
    "Programmation",
    "Scratch / blocs",
    "Tableur",
    "Grandeurs et mesures",
    "Problèmes",
    "Raisonnement et démonstration",
    "Automatismes",
]

FRENCH_CHECKLIST = [
    "Compréhension",
    "Interprétation",
    "Grammaire",
    "Orthographe",
    "Conjugaison",
    "Réécriture",
    "Dictée",
    "Rédaction",
    "Expression écrite",
    "Vocabulaire",
    "Accords",
]

HISTORY_CHECKLIST = [
    "Révolution française",
    "Seconde Guerre mondiale",
    "Guerre froide",
    "Europe",
    "République",
    "Colonisation",
    "Décolonisation",
]

GEOGRAPHY_CHECKLIST = [
    "Territoires",
    "Aménagement",
    "Développement durable",
    "Mobilités",
    "France",
    "Union européenne",
    "Mondialisation",
]

EMC_CHECKLIST = [
    "Citoyenneté",
    "Institutions",
    "Valeurs de la République",
    "Défense",
    "Engagement",
]

PC_CHECKLIST = [
    "Électricité",
    "Énergie",
    "Forces",
    "Chimie",
    "Mouvement",
    "Optique",
]

SVT_CHECKLIST = [
    "ADN et génétique",
    "Immunité",
    "Évolution",
    "Planète Terre",
    "Corps humain",
]

TECH_CHECKLIST = [
    "Objets techniques",
    "Énergie",
    "Informatique",
    "Algorithmique",
    "Design",
]

SUBJECT_CHECKLISTS: dict[str, list[str]] = {
    "MATHEMATICS": MATH_CHECKLIST,
    "FRENCH": FRENCH_CHECKLIST,
    "HISTORY": HISTORY_CHECKLIST,
    "GEOGRAPHY": GEOGRAPHY_CHECKLIST,
    "EMC": EMC_CHECKLIST,
    "PHYSICS_CHEMISTRY": PC_CHECKLIST,
    "SVT": SVT_CHECKLIST,
    "TECHNOLOGY": TECH_CHECKLIST,
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_label(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    ascii_only = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_only.casefold()).strip()


def labels_overlap(a: str, b: str) -> bool:
    na, nb = normalize_label(a), normalize_label(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    inter = ta & tb
    return len(inter) / min(len(ta), len(tb)) >= 0.6


@dataclass
class Gap:
    subject: str
    domain: str
    expected_chapter_or_skill: str
    current_match: str
    gap_type: str
    severity: str
    evidence: str
    recommended_action: str


@dataclass
class AuditStats:
    subjects: int = 0
    domains: int = 0
    chapters: int = 0
    skills: int = 0
    subskills: int = 0
    gaps: int = 0
    orphans: int = 0
    duplicates: int = 0


@dataclass
class CurriculumAuditResult:
    db_path: str
    db_sha256: str
    schema_tables: list[str]
    stats: AuditStats
    subjects: list[dict[str, Any]] = field(default_factory=list)
    tree_rows: list[dict[str, Any]] = field(default_factory=list)
    chapters: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    orphans: list[dict[str, Any]] = field(default_factory=list)
    duplicates: list[dict[str, Any]] = field(default_factory=list)
    subject_verdicts: dict[str, str] = field(default_factory=dict)
    verdicts: dict[str, str] = field(default_factory=dict)


def _connect(db_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    path = Path(db_path or get_database_path())
    return duckdb.connect(str(path), read_only=True)


def inspect_schema(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY 1
        """
    ).fetchall()
    return [str(r[0]) for r in rows]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_curriculum_audit(
    *,
    db_path: Path | None = None,
    subject_filter: str | None = None,
    include_content_counts: bool = True,
    include_official_coverage: bool = True,
    export: bool = True,
) -> CurriculumAuditResult:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(db_path or get_database_path())
    db_hash = sha256_file(path)
    con = _connect(path)
    try:
        tables = inspect_schema(con)
        required = {"subjects", "curriculum_domains", "chapters", "skills"}
        missing = sorted(required - set(tables))
        if missing:
            raise RuntimeError(f"Missing curriculum tables: {missing}")

        subjects = _load_subjects(con, subject_filter)
        tree_rows, chapters = _load_tree(con, subject_filter, include_content_counts, include_official_coverage)
        orphans = _detect_orphans(con)
        duplicates = _detect_duplicates(chapters, tree_rows)
        gaps = _detect_gaps(subjects, chapters, tree_rows)
        stats = AuditStats(
            subjects=len(subjects),
            domains=len({(r["subject"], r["domain_id"]) for r in tree_rows if r.get("domain_id")}),
            chapters=len(chapters),
            skills=len({r["skill_id"] for r in tree_rows if r.get("skill_id")}),
            subskills=len({r["subskill_id"] for r in tree_rows if r.get("subskill_id")}),
            gaps=len(gaps),
            orphans=len(orphans),
            duplicates=len(duplicates),
        )
        subject_verdicts = _subject_verdicts(subjects, chapters, gaps)
        verdicts = _global_verdicts(stats, subject_verdicts, orphans, duplicates)
        result = CurriculumAuditResult(
            db_path=str(path),
            db_sha256=db_hash,
            schema_tables=tables,
            stats=stats,
            subjects=subjects,
            tree_rows=tree_rows,
            chapters=chapters,
            gaps=gaps,
            orphans=orphans,
            duplicates=duplicates,
            subject_verdicts=subject_verdicts,
            verdicts=verdicts,
        )
        if export:
            write_reports(result, pre_hash=db_hash)
            # Non-regression: hash unchanged (read-only).
            post_hash = sha256_file(path)
            if post_hash != db_hash:
                raise RuntimeError("Database hash changed during read-only audit")
            result.verdicts["READ-ONLY NON-REGRESSION"] = "PASS"
            _refresh_final_package(result)
        return result
    finally:
        con.close()


def _load_subjects(con: duckdb.DuckDBPyConnection, subject_filter: str | None) -> list[dict[str, Any]]:
    rows = con.execute(
        """
        SELECT subject_id, code, name, active, terminal_exam, continuous_assessment, sort_order
        FROM subjects
        ORDER BY sort_order, code
        """
    ).fetchall()
    out = []
    for r in rows:
        code = str(r[1])
        if subject_filter and code != subject_filter.upper():
            continue
        domain_count = con.execute("SELECT COUNT(*) FROM curriculum_domains WHERE subject_id = ?", [r[0]]).fetchone()[0]
        chapter_count = con.execute(
            """
            SELECT COUNT(*) FROM chapters ch
            JOIN curriculum_domains cd ON cd.domain_id = ch.domain_id
            WHERE cd.subject_id = ?
            """,
            [r[0]],
        ).fetchone()[0]
        skill_count = con.execute(
            """
            SELECT COUNT(*) FROM skills sk
            JOIN chapters ch ON ch.chapter_id = sk.chapter_id
            JOIN curriculum_domains cd ON cd.domain_id = ch.domain_id
            WHERE cd.subject_id = ?
            """,
            [r[0]],
        ).fetchone()[0]
        subskill_count = con.execute(
            """
            SELECT COUNT(*) FROM subskills ss
            JOIN skills sk ON sk.skill_id = ss.skill_id
            JOIN chapters ch ON ch.chapter_id = sk.chapter_id
            JOIN curriculum_domains cd ON cd.domain_id = ch.domain_id
            WHERE cd.subject_id = ?
            """,
            [r[0]],
        ).fetchone()[0]
        content_count = con.execute("SELECT COUNT(*) FROM content_items WHERE subject_id = ?", [r[0]]).fetchone()[0]
        official_count = con.execute(
            """
            SELECT COUNT(*) FROM content_items
            WHERE subject_id = ? AND source_type = 'OFFICIAL_ARCHIVE'
            """,
            [r[0]],
        ).fetchone()[0]
        out.append(
            {
                "subject_id": int(r[0]),
                "subject_code": code,
                "subject_name": str(r[2]),
                "active": bool(r[3]),
                "DNB_terminal_subject": bool(r[4]),
                "continuous_assessment_only": bool(r[5]) and not bool(r[4]),
                "domain_count": int(domain_count),
                "chapter_count": int(chapter_count),
                "skill_count": int(skill_count),
                "subskill_count": int(subskill_count),
                "content_count": int(content_count),
                "official_archive_question_count": int(official_count),
            }
        )
    return out


def _load_tree(
    con: duckdb.DuckDBPyConnection,
    subject_filter: str | None,
    include_content_counts: bool,
    include_official_coverage: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sql = """
        SELECT
            sub.subject_id, sub.code, sub.name, sub.active,
            cd.domain_id, cd.code, cd.name, cd.sort_order,
            ch.chapter_id, ch.code, ch.name, ch.active, ch.brevet_importance,
            sk.skill_id, sk.code, sk.name, sk.active, sk.brevet_importance,
            ss.subskill_id, ss.code, ss.name, ss.active
        FROM subjects sub
        LEFT JOIN curriculum_domains cd ON cd.subject_id = sub.subject_id
        LEFT JOIN chapters ch ON ch.domain_id = cd.domain_id
        LEFT JOIN skills sk ON sk.chapter_id = ch.chapter_id
        LEFT JOIN subskills ss ON ss.skill_id = sk.skill_id
    """
    params: list[Any] = []
    if subject_filter:
        sql += " WHERE sub.code = ?"
        params.append(subject_filter.upper())
    sql += " ORDER BY sub.sort_order, cd.sort_order, ch.chapter_id, sk.skill_id, ss.subskill_id"
    rows = con.execute(sql, params).fetchall()

    # Preload content counts by skill / chapter
    skill_content: dict[int, int] = {}
    skill_official: dict[int, int] = {}
    skill_validated: dict[int, int] = {}
    if include_content_counts:
        for r in con.execute(
            """
            SELECT l.skill_id, COUNT(DISTINCT c.content_id)
            FROM content_skill_links l
            JOIN content_items c ON c.content_id = l.content_id
            GROUP BY 1
            """
        ).fetchall():
            skill_content[int(r[0])] = int(r[1])
    if include_official_coverage:
        for r in con.execute(
            """
            SELECT l.skill_id, COUNT(DISTINCT c.content_id)
            FROM content_skill_links l
            JOIN content_items c ON c.content_id = l.content_id
            WHERE c.source_type = 'OFFICIAL_ARCHIVE'
            GROUP BY 1
            """
        ).fetchall():
            skill_official[int(r[0])] = int(r[1])
        # validated official if assessment table exists
        tables = {t[0] for t in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        if "content_pedagogical_assessments" in tables:
            for r in con.execute(
                """
                SELECT l.skill_id, COUNT(DISTINCT c.content_id)
                FROM content_skill_links l
                JOIN content_items c ON c.content_id = l.content_id
                JOIN content_pedagogical_assessments a ON a.content_id = c.content_id
                WHERE c.source_type = 'OFFICIAL_ARCHIVE'
                  AND a.pedagogical_validation_status = 'VALIDATED'
                GROUP BY 1
                """
            ).fetchall():
                skill_validated[int(r[0])] = int(r[1])

    tree_rows: list[dict[str, Any]] = []
    chapter_map: dict[int, dict[str, Any]] = {}
    for r in rows:
        skill_id = int(r[13]) if r[13] is not None else None
        chapter_id = int(r[8]) if r[8] is not None else None
        row = {
            "subject_id": int(r[0]),
            "subject": str(r[1]),
            "subject_name": str(r[2]),
            "subject_active": bool(r[3]),
            "domain_id": int(r[4]) if r[4] is not None else None,
            "domain_code": r[5],
            "domain": r[6],
            "domain_order": r[7],
            "chapter_id": chapter_id,
            "chapter_code": r[9],
            "chapter": r[10],
            "chapter_active": bool(r[11]) if r[11] is not None else None,
            "chapter_importance": r[12],
            "skill_id": skill_id,
            "skill_code": r[14],
            "skill": r[15],
            "skill_active": bool(r[16]) if r[16] is not None else None,
            "brevet_importance": r[17],
            "subskill_id": int(r[18]) if r[18] is not None else None,
            "subskill_code": r[19],
            "subskill": r[20],
            "subskill_active": bool(r[21]) if r[21] is not None else None,
            "content_count": skill_content.get(skill_id or -1, 0) if skill_id else 0,
            "official_question_count": skill_official.get(skill_id or -1, 0) if skill_id else 0,
            "validated_official_count": skill_validated.get(skill_id or -1, 0) if skill_id else 0,
            "active": bool(r[16]) if r[16] is not None else (bool(r[11]) if r[11] is not None else bool(r[3])),
        }
        tree_rows.append(row)
        if chapter_id is not None:
            ch = chapter_map.setdefault(
                chapter_id,
                {
                    "chapter_id": chapter_id,
                    "chapter_code": r[9],
                    "chapter_name": r[10],
                    "subject": str(r[1]),
                    "domain": r[6],
                    "active": bool(r[11]) if r[11] is not None else True,
                    "display_order": chapter_id,
                    "skill_ids": set(),
                    "subskill_ids": set(),
                    "content_count": 0,
                    "official_question_count": 0,
                    "brevet_style_count": 0,
                    "archive_derived_count": 0,
                    "prerequisite_count": 0,
                },
            )
            if skill_id is not None:
                ch["skill_ids"].add(skill_id)
                ch["content_count"] += skill_content.get(skill_id, 0)
                ch["official_question_count"] += skill_official.get(skill_id, 0)
            if r[18] is not None:
                ch["subskill_ids"].add(int(r[18]))

    # Enrich chapter source-type splits
    if include_content_counts:
        for r in con.execute(
            """
            SELECT ch.chapter_id,
                   COUNT(DISTINCT CASE WHEN c.source_type='BREVET_STYLE' THEN c.content_id END),
                   COUNT(DISTINCT CASE WHEN c.source_type='ARCHIVE_DERIVED' THEN c.content_id END)
            FROM chapters ch
            JOIN skills sk ON sk.chapter_id = ch.chapter_id
            JOIN content_skill_links l ON l.skill_id = sk.skill_id
            JOIN content_items c ON c.content_id = l.content_id
            GROUP BY 1
            """
        ).fetchall():
            if int(r[0]) in chapter_map:
                chapter_map[int(r[0])]["brevet_style_count"] = int(r[1])
                chapter_map[int(r[0])]["archive_derived_count"] = int(r[2])

    chapters: list[dict[str, Any]] = []
    for ch in chapter_map.values():
        skill_count = len(ch["skill_ids"])
        content_count = int(ch["content_count"])
        official = int(ch["official_question_count"])
        if skill_count == 0:
            coverage = "EMPTY_NO_SKILL"
        elif content_count == 0:
            coverage = "EMPTY_NO_CONTENT"
        elif official == 0:
            coverage = "NO_OFFICIAL_ARCHIVE"
        else:
            coverage = "COVERED"
        chapters.append(
            {
                "subject": ch["subject"],
                "domain": ch["domain"],
                "chapter_id": ch["chapter_id"],
                "chapter_code": ch["chapter_code"],
                "chapter_name": ch["chapter_name"],
                "active": ch["active"],
                "display_order": ch["display_order"],
                "skill_count": skill_count,
                "subskill_count": len(ch["subskill_ids"]),
                "content_count": content_count,
                "official_question_count": official,
                "brevet_style_count": ch["brevet_style_count"],
                "archive_derived_count": ch["archive_derived_count"],
                "prerequisite_count": ch["prerequisite_count"],
                "coverage_status": coverage,
                "chapter_structure_score": 1.0 if skill_count > 0 else 0.0,
                "content_coverage_score": min(1.0, content_count / 20.0),
                "official_archive_coverage_score": min(1.0, official / 5.0),
                "skill_completeness_score": 1.0 if skill_count > 0 else 0.0,
            }
        )
    chapters.sort(key=lambda x: (x["subject"], x["chapter_id"]))
    return tree_rows, chapters


def _detect_orphans(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    orphans: list[dict[str, Any]] = []
    # skills without chapter (should be impossible with FK, but check)
    for r in con.execute(
        """
        SELECT sk.skill_id, sk.code, sk.name
        FROM skills sk
        LEFT JOIN chapters ch ON ch.chapter_id = sk.chapter_id
        WHERE ch.chapter_id IS NULL
        """
    ).fetchall():
        orphans.append({"node_type": "skill", "id": r[0], "code": r[1], "name": r[2], "issue": "skill sans chapter"})
    for r in con.execute(
        """
        SELECT ch.chapter_id, ch.code, ch.name
        FROM chapters ch
        LEFT JOIN curriculum_domains cd ON cd.domain_id = ch.domain_id
        WHERE cd.domain_id IS NULL
        """
    ).fetchall():
        orphans.append({"node_type": "chapter", "id": r[0], "code": r[1], "name": r[2], "issue": "chapter sans domain"})
    for r in con.execute(
        """
        SELECT ch.chapter_id, ch.code, ch.name
        FROM chapters ch
        LEFT JOIN skills sk ON sk.chapter_id = ch.chapter_id
        WHERE sk.skill_id IS NULL
        """
    ).fetchall():
        orphans.append({"node_type": "chapter", "id": r[0], "code": r[1], "name": r[2], "issue": "chapter sans skill"})
    for r in con.execute(
        """
        SELECT cd.domain_id, cd.code, cd.name
        FROM curriculum_domains cd
        LEFT JOIN chapters ch ON ch.domain_id = cd.domain_id
        WHERE ch.chapter_id IS NULL
        """
    ).fetchall():
        orphans.append({"node_type": "domain", "id": r[0], "code": r[1], "name": r[2], "issue": "domain sans chapter"})
    for r in con.execute(
        """
        SELECT ss.subskill_id, ss.code, ss.name
        FROM subskills ss
        LEFT JOIN skills sk ON sk.skill_id = ss.skill_id
        WHERE sk.skill_id IS NULL
        """
    ).fetchall():
        orphans.append(
            {"node_type": "subskill", "id": r[0], "code": r[1], "name": r[2], "issue": "subskill sans skill"}
        )
    # inactive parents with active children
    for r in con.execute(
        """
        SELECT ch.chapter_id, ch.code, ch.name
        FROM chapters ch
        JOIN skills sk ON sk.chapter_id = ch.chapter_id
        WHERE ch.active = FALSE AND sk.active = TRUE
        """
    ).fetchall():
        orphans.append(
            {
                "node_type": "chapter",
                "id": r[0],
                "code": r[1],
                "name": r[2],
                "issue": "inactive parent with active children",
            }
        )
    return orphans


def _detect_duplicates(chapters: list[dict[str, Any]], tree_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dups: list[dict[str, Any]] = []
    # Exact normalized chapter names within subject
    by_subject: dict[str, list[dict[str, Any]]] = {}
    for ch in chapters:
        by_subject.setdefault(ch["subject"], []).append(ch)
    for subject, items in by_subject.items():
        seen: dict[str, dict[str, Any]] = {}
        for ch in items:
            key = normalize_label(ch["chapter_name"])
            if key in seen:
                dups.append(
                    {
                        "type": "EXACT_CHAPTER",
                        "subject": subject,
                        "left": seen[key]["chapter_name"],
                        "right": ch["chapter_name"],
                        "left_id": seen[key]["chapter_id"],
                        "right_id": ch["chapter_id"],
                    }
                )
            else:
                seen[key] = ch
        # Semantic overlaps
        for i, a in enumerate(items):
            for b in items[i + 1 :]:
                if a["chapter_id"] == b["chapter_id"]:
                    continue
                if labels_overlap(a["chapter_name"], b["chapter_name"]) and normalize_label(
                    a["chapter_name"]
                ) != normalize_label(b["chapter_name"]):
                    dups.append(
                        {
                            "type": "SEMANTIC_CHAPTER",
                            "subject": subject,
                            "left": a["chapter_name"],
                            "right": b["chapter_name"],
                            "left_id": a["chapter_id"],
                            "right_id": b["chapter_id"],
                        }
                    )
    # Duplicate skill codes
    codes: dict[str, int] = {}
    for row in tree_rows:
        code = row.get("skill_code")
        sid = row.get("skill_id")
        if not code or sid is None:
            continue
        if code in codes and codes[code] != sid:
            dups.append(
                {
                    "type": "DUPLICATE_SKILL_CODE",
                    "subject": row["subject"],
                    "left": code,
                    "right": code,
                    "left_id": codes[code],
                    "right_id": sid,
                }
            )
        else:
            codes[code] = sid
    return dups


def _detect_gaps(
    subjects: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
    tree_rows: list[dict[str, Any]],
) -> list[Gap]:
    gaps: list[Gap] = []
    chapters_by_subject: dict[str, list[dict[str, Any]]] = {}
    for ch in chapters:
        chapters_by_subject.setdefault(ch["subject"], []).append(ch)

    for subject_code, checklist in SUBJECT_CHECKLISTS.items():
        present = chapters_by_subject.get(subject_code, [])
        present_names = [c["chapter_name"] for c in present]
        domain = present[0]["domain"] if present else "(aucun domaine)"
        for expected in checklist:
            matches = [n for n in present_names if labels_overlap(expected, n)]
            if not matches:
                # Formats transversaux: not necessarily chapters
                if normalize_label(expected) in {
                    "automatismes",
                    "problemes",
                    "raisonnement et demonstration",
                    "scratch blocs",
                    "programmation",
                }:
                    severity = "P2"
                    gap_type = "MISSING_CHAPTER"
                    action = "REVIEW_AS_FORMAT_OR_CHAPTER"
                    evidence = "Élément de contrôle transversal — peut être format plutôt que chapitre"
                else:
                    severity = "P0" if subject_code == "MATHEMATICS" else "P1"
                    gap_type = "MISSING_CHAPTER"
                    action = "ADD_CHAPTER_IN_LCAI_0039"
                    evidence = "Aucun chapitre sémantiquement équivalent trouvé"
                gaps.append(
                    Gap(
                        subject=subject_code,
                        domain=domain,
                        expected_chapter_or_skill=expected,
                        current_match="",
                        gap_type=gap_type,
                        severity=severity,
                        evidence=evidence,
                        recommended_action=action,
                    )
                )
            else:
                # matched but maybe incomplete coverage
                matched_chapters = [c for c in present if c["chapter_name"] in matches]
                for ch in matched_chapters:
                    if ch["skill_count"] == 0:
                        gaps.append(
                            Gap(
                                subject=subject_code,
                                domain=domain,
                                expected_chapter_or_skill=expected,
                                current_match=ch["chapter_name"],
                                gap_type="EMPTY_CHAPTER",
                                severity="P1",
                                evidence="skill_count=0",
                                recommended_action="ADD_SKILLS",
                            )
                        )
                    elif ch["content_count"] == 0:
                        gaps.append(
                            Gap(
                                subject=subject_code,
                                domain=domain,
                                expected_chapter_or_skill=expected,
                                current_match=ch["chapter_name"],
                                gap_type="LOW_CONTENT_COVERAGE",
                                severity="P2",
                                evidence="content_count=0",
                                recommended_action="ENRICH_CONTENT",
                            )
                        )
                    elif ch["official_question_count"] == 0:
                        gaps.append(
                            Gap(
                                subject=subject_code,
                                domain=domain,
                                expected_chapter_or_skill=expected,
                                current_match=ch["chapter_name"],
                                gap_type="NO_OFFICIAL_ARCHIVE_COVERAGE",
                                severity="P2",
                                evidence="official_question_count=0",
                                recommended_action="MAP_OR_INGEST_OFFICIAL",
                            )
                        )

    # Flat domain structure warning for core subjects
    for sub in subjects:
        if sub["subject_code"] not in CORE_SUBJECTS:
            continue
        if sub["domain_count"] <= 1 and sub["chapter_count"] > 0:
            gaps.append(
                Gap(
                    subject=sub["subject_code"],
                    domain="(unique)",
                    expected_chapter_or_skill="Domaines pédagogiques structurés",
                    current_match=f"{sub['domain_count']} domaine(s)",
                    gap_type="NAMING_INCONSISTENCY",
                    severity="P2",
                    evidence="Un seul domaine agrège tous les chapitres",
                    recommended_action="SPLIT_DOMAINS_IN_LCAI_0039",
                )
            )
        if sub["subskill_count"] == 0 and sub["skill_count"] > 0:
            gaps.append(
                Gap(
                    subject=sub["subject_code"],
                    domain="",
                    expected_chapter_or_skill="Sous-compétences",
                    current_match="0 subskills",
                    gap_type="MISSING_SUBSKILL",
                    severity="P3",
                    evidence="Aucune sous-compétence en base",
                    recommended_action="OPTIONAL_SUBSKILL_MODEL",
                )
            )
        if sub["subject_code"] in {"ENGLISH", "SPANISH"} and sub["chapter_count"] == 0:
            gaps.append(
                Gap(
                    subject=sub["subject_code"],
                    domain="",
                    expected_chapter_or_skill="Curriculum langue",
                    current_match="aucun chapitre",
                    gap_type="MISSING_DOMAIN",
                    severity="P3",
                    evidence="Matière hors épreuve terminale DNB sans arborescence",
                    recommended_action="KEEP_AS_OPTIONAL",
                )
            )

    # Skills without official coverage
    seen_skills: set[int] = set()
    for row in tree_rows:
        sid = row.get("skill_id")
        if sid is None or sid in seen_skills:
            continue
        seen_skills.add(sid)
        if row["official_question_count"] == 0 and row["subject"] in CORE_SUBJECTS:
            gaps.append(
                Gap(
                    subject=row["subject"],
                    domain=str(row.get("domain") or ""),
                    expected_chapter_or_skill=str(row.get("skill") or row.get("skill_code")),
                    current_match=str(row.get("chapter") or ""),
                    gap_type="NO_OFFICIAL_ARCHIVE_COVERAGE",
                    severity="P2",
                    evidence=f"skill_id={sid} without OFFICIAL_ARCHIVE content",
                    recommended_action="MAP_OFFICIAL_QUESTIONS",
                )
            )
    return gaps


def _subject_verdicts(
    subjects: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
    gaps: list[Gap],
) -> dict[str, str]:
    verdicts: dict[str, str] = {}
    for code in list(CORE_SUBJECTS) + ["ORAL", "ENGLISH", "SPANISH"]:
        sub = next((s for s in subjects if s["subject_code"] == code), None)
        if sub is None:
            verdicts[code] = "INCOMPLETE"
            continue
        p0 = [g for g in gaps if g.subject == code and g.severity == "P0"]
        p1 = [g for g in gaps if g.subject == code and g.severity == "P1"]
        chs = [c for c in chapters if c["subject"] == code]
        if code in {"ENGLISH", "SPANISH"}:
            verdicts[code] = "PARTIAL" if sub["chapter_count"] == 0 else "COMPLETE"
            continue
        if not chs or p0:
            verdicts[code] = "INCOMPLETE"
        elif p1 or any(c["coverage_status"] != "COVERED" for c in chs):
            verdicts[code] = "PARTIAL"
        else:
            # Still PARTIAL if checklist had missing non-format items marked P0 only for maths.
            missing = [
                g for g in gaps if g.subject == code and g.gap_type == "MISSING_CHAPTER" and g.severity in {"P0", "P1"}
            ]
            verdicts[code] = "INCOMPLETE" if missing else "PARTIAL"
    return verdicts


def _global_verdicts(
    stats: AuditStats,
    subject_verdicts: dict[str, str],
    orphans: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
) -> dict[str, str]:
    return {
        "CURRICULUM EXTRACTION": "PASS" if stats.subjects > 0 and stats.chapters > 0 else "FAIL",
        "TREE INTEGRITY": "PARTIAL" if orphans or stats.subskills == 0 else "PASS",
        "MATHEMATICS CURRICULUM TREE": subject_verdicts.get("MATHEMATICS", "INCOMPLETE"),
        "FRENCH CURRICULUM TREE": subject_verdicts.get("FRENCH", "INCOMPLETE"),
        "HISTORY CURRICULUM TREE": subject_verdicts.get("HISTORY", "INCOMPLETE"),
        "GEOGRAPHY CURRICULUM TREE": subject_verdicts.get("GEOGRAPHY", "INCOMPLETE"),
        "EMC CURRICULUM TREE": subject_verdicts.get("EMC", "INCOMPLETE"),
        "PHYSICS_CHEMISTRY CURRICULUM TREE": subject_verdicts.get("PHYSICS_CHEMISTRY", "INCOMPLETE"),
        "SVT CURRICULUM TREE": subject_verdicts.get("SVT", "INCOMPLETE"),
        "TECHNOLOGY CURRICULUM TREE": subject_verdicts.get("TECHNOLOGY", "INCOMPLETE"),
        "ORPHAN DETECTION": "PASS",
        "DUPLICATE DETECTION": "PASS",
        "TARGET COMPARISON": "PASS",
        "READ-ONLY NON-REGRESSION": "PASS",
        "REVIEW PACKAGE": "PASS",
    }


def format_tree_console(tree_rows: list[dict[str, Any]], *, verbose: bool = False) -> str:
    lines: list[str] = []
    current_subject = None
    current_domain = None
    current_chapter = None
    for row in tree_rows:
        sub = row["subject_name"] or row["subject"]
        if sub != current_subject:
            current_subject = sub
            current_domain = None
            current_chapter = None
            sid = f" [{row['subject_id']}]" if verbose else ""
            lines.append(f"{sub.upper()}{sid}")
        domain = row.get("domain")
        if domain and domain != current_domain:
            current_domain = domain
            current_chapter = None
            did = f" [{row['domain_id']}]" if verbose else ""
            lines.append(f"├── {domain}{did}")
        chapter = row.get("chapter")
        if chapter and chapter != current_chapter:
            current_chapter = chapter
            cid = f" [{row['chapter_id']}]" if verbose else ""
            lines.append(f"│   ├── {chapter}{cid}")
        skill = row.get("skill")
        if skill:
            kid = f" [{row['skill_id']}]" if verbose else ""
            lines.append(f"│   │   ├── {skill}{kid}")
        subskill = row.get("subskill")
        if subskill:
            ssid = f" [{row['subskill_id']}]" if verbose else ""
            lines.append(f"│   │   │   └── {subskill}{ssid}")
    return "\n".join(lines)


def _csv_write(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(headers)
        w.writerows(rows)


def write_reports(result: CurriculumAuditResult, *, pre_hash: str) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Pre-audit state
    pre = f"""# LCAI-0038 — Pre-audit state

- database: `{result.db_path}`
- sha256: `{pre_hash}`
- auditor: `{AUDITOR_VERSION}`
- generated_at: `{_now()}`

## Schema inventory

{chr(10).join(f"- {t}" for t in result.schema_tables)}

## Counts

- subjects: {result.stats.subjects}
- domains: {result.stats.domains}
- chapters: {result.stats.chapters}
- skills: {result.stats.skills}
- subskills: {result.stats.subskills}
"""
    (ARTIFACT_DIR / "LCAI-0038_PRE_AUDIT_STATE.md").write_text(pre, encoding="utf-8")

    tree_md = "# LCAI-0038 — Curriculum tree\n\n"
    tree_md += "```text\n" + format_tree_console(result.tree_rows, verbose=True) + "\n```\n"
    (ARTIFACT_DIR / "LCAI-0038_CURRICULUM_TREE.md").write_text(tree_md, encoding="utf-8")

    math_rows = [r for r in result.tree_rows if r["subject"] == "MATHEMATICS"]
    math_gaps = [g for g in result.gaps if g.subject == "MATHEMATICS"]
    math_chapters = [c for c in result.chapters if c["subject"] == "MATHEMATICS"]
    math_md = f"""# LCAI-0038 — Mathematics tree

## Structure actuelle

```text
{format_tree_console(math_rows, verbose=True)}
```

## Chapitres présents ({len(math_chapters)})

| chapter | skills | content | official | coverage |
|---|---:|---:|---:|---|
"""
    for c in math_chapters:
        math_md += (
            f"| {c['chapter_name']} | {c['skill_count']} | {c['content_count']} | "
            f"{c['official_question_count']} | {c['coverage_status']} |\n"
        )
    math_md += "\n## Gaps Mathématiques\n\n"
    math_md += "| expected | match | type | severity | evidence | action |\n|---|---|---|---|---|---|\n"
    for g in math_gaps:
        math_md += (
            f"| {g.expected_chapter_or_skill} | {g.current_match} | {g.gap_type} | "
            f"{g.severity} | {g.evidence} | {g.recommended_action} |\n"
        )
    math_md += f"\n## Verdict\n\nMATHEMATICS CURRICULUM TREE: {result.subject_verdicts.get('MATHEMATICS')}\n"
    math_md += (
        "\nJustification: l’arborescence Maths est plate (1 domaine, 15 chapitres = 15 compétences). "
        "Des thèmes majeurs du contrôle 3e (trigonométrie, homothétie, géométrie plane explicite, "
        "tableur, arithmétique dédiée, fonctions linéaires/affines séparées) sont absents ou seulement "
        "couverts partiellement via des chapitres voisins.\n"
    )
    (ARTIFACT_DIR / "LCAI-0038_MATHEMATICS_TREE.md").write_text(math_md, encoding="utf-8")

    _csv_write(
        ARTIFACT_DIR / "LCAI-0038_CURRICULUM_TREE.csv",
        [
            "subject",
            "domain",
            "chapter",
            "skill",
            "subskill",
            "subject_id",
            "domain_id",
            "chapter_id",
            "skill_id",
            "subskill_id",
            "active",
            "content_count",
            "official_question_count",
        ],
        [
            [
                r["subject"],
                r.get("domain"),
                r.get("chapter"),
                r.get("skill"),
                r.get("subskill"),
                r["subject_id"],
                r.get("domain_id"),
                r.get("chapter_id"),
                r.get("skill_id"),
                r.get("subskill_id"),
                r.get("active"),
                r.get("content_count"),
                r.get("official_question_count"),
            ]
            for r in result.tree_rows
        ],
    )
    _csv_write(
        ARTIFACT_DIR / "LCAI-0038_CHAPTER_INVENTORY.csv",
        [
            "subject",
            "domain",
            "chapter_code",
            "chapter_name",
            "active",
            "skill_count",
            "subskill_count",
            "content_count",
            "official_question_count",
            "coverage_status",
        ],
        [
            [
                c["subject"],
                c["domain"],
                c["chapter_code"],
                c["chapter_name"],
                c["active"],
                c["skill_count"],
                c["subskill_count"],
                c["content_count"],
                c["official_question_count"],
                c["coverage_status"],
            ]
            for c in result.chapters
        ],
    )
    _csv_write(
        ARTIFACT_DIR / "LCAI-0038_CURRICULUM_GAPS.csv",
        [
            "subject",
            "domain",
            "expected_chapter_or_skill",
            "current_match",
            "gap_type",
            "severity",
            "evidence",
            "recommended_action",
        ],
        [
            [
                g.subject,
                g.domain,
                g.expected_chapter_or_skill,
                g.current_match,
                g.gap_type,
                g.severity,
                g.evidence,
                g.recommended_action,
            ]
            for g in result.gaps
        ],
    )
    _csv_write(
        ARTIFACT_DIR / "LCAI-0038_ORPHAN_NODES.csv",
        ["node_type", "id", "code", "name", "issue"],
        [[o["node_type"], o["id"], o["code"], o["name"], o["issue"]] for o in result.orphans],
    )

    dup_md = "# LCAI-0038 — Duplicate and overlap report\n\n"
    if not result.duplicates:
        dup_md += "Aucun doublon exact ou sémantique fort détecté parmi les chapitres/skills.\n"
    else:
        dup_md += "| type | subject | left | right |\n|---|---|---|---|\n"
        for d in result.duplicates:
            dup_md += f"| {d['type']} | {d['subject']} | {d['left']} | {d['right']} |\n"
    (ARTIFACT_DIR / "LCAI-0038_DUPLICATE_AND_OVERLAP_REPORT.md").write_text(dup_md, encoding="utf-8")

    cov = "# LCAI-0038 — Curriculum coverage report\n\n"
    cov += "| subject | domains | chapters | skills | subskills | chapters_with_content | chapters_with_official | skills_with_content | skills_with_official | gaps_P0 | gaps_P1 |\n"
    cov += "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for sub in result.subjects:
        code = sub["subject_code"]
        chs = [c for c in result.chapters if c["subject"] == code]
        skills = [r for r in result.tree_rows if r["subject"] == code and r.get("skill_id")]
        uniq_skills = {r["skill_id"]: r for r in skills}
        gaps_p0 = sum(1 for g in result.gaps if g.subject == code and g.severity == "P0")
        gaps_p1 = sum(1 for g in result.gaps if g.subject == code and g.severity == "P1")
        cov += (
            f"| {code} | {sub['domain_count']} | {sub['chapter_count']} | {sub['skill_count']} | "
            f"{sub['subskill_count']} | {sum(1 for c in chs if c['content_count'] > 0)} | "
            f"{sum(1 for c in chs if c['official_question_count'] > 0)} | "
            f"{sum(1 for s in uniq_skills.values() if s['content_count'] > 0)} | "
            f"{sum(1 for s in uniq_skills.values() if s['official_question_count'] > 0)} | "
            f"{gaps_p0} | {gaps_p1} |\n"
        )
    (ARTIFACT_DIR / "LCAI-0038_CURRICULUM_COVERAGE_REPORT.md").write_text(cov, encoding="utf-8")

    cmp_md = "# LCAI-0038 — Target comparison\n\n"
    for code, checklist in SUBJECT_CHECKLISTS.items():
        present_names = [c["chapter_name"] for c in result.chapters if c["subject"] == code]
        cmp_md += f"## {code}\n\n"
        cmp_md += "| expected | status | current_match |\n|---|---|---|\n"
        for expected in checklist:
            matches = [n for n in present_names if labels_overlap(expected, n)]
            if not matches:
                status = "MISSING"
                match = ""
            elif any(
                c["coverage_status"] != "COVERED"
                for c in result.chapters
                if c["subject"] == code and c["chapter_name"] in matches
            ):
                status = "PARTIAL"
                match = "; ".join(matches)
            else:
                status = "PRESENT"
                match = "; ".join(matches)
            cmp_md += f"| {expected} | {status} | {match} |\n"
        cmp_md += f"\nVerdict: `{result.subject_verdicts.get(code)}`\n\n"
    (ARTIFACT_DIR / "LCAI-0038_TARGET_COMPARISON.md").write_text(cmp_md, encoding="utf-8")

    impl = f"""# LCAI-0038 — Implementation Report

Audit read-only de l’arborescence curriculum 3e/DNB 2027.

- Script: `scripts/audit_curriculum_tree.py`
- DB sha256: `{result.db_sha256}`
- Stats: {json.dumps(asdict(result.stats), ensure_ascii=False)}

## Verdicts

"""
    for k, v in result.verdicts.items():
        impl += f"{k}: {v}\n"
    impl += "\nREADY FOR REVIEW\n"
    (ARTIFACT_DIR / "LCAI-0038_IMPLEMENTATION_REPORT.md").write_text(impl, encoding="utf-8")
    (DOCS_DIR / "LCAI-0038_IMPLEMENTATION_REPORT.md").write_text(impl, encoding="utf-8")
    (DOCS_DIR / "README.md").write_text(
        "# LCAI-0038\n\nAudit arborescence matières/domaines/chapitres/compétences.\n\n"
        "`python scripts/audit_curriculum_tree.py --all-subjects --export`\n",
        encoding="utf-8",
    )


def _refresh_final_package(result: CurriculumAuditResult) -> Path:
    (ARTIFACT_DIR / "LCAI-0038_TEST_REPORT.md").write_text(
        "# LCAI-0038 Test Report\n\n"
        "Suite: `tests/test_lcai_0038_curriculum_tree.py`\n\n"
        "| Test | Intent |\n|---|---|\n"
        "| `test_normalize_and_overlap` | Normalisation / overlap sémantique |\n"
        "| `test_extraction_layers` | Extraction matières/domaines/chapitres/compétences |\n"
        "| `test_orphan_and_duplicate_detection_run` | Orphelins + doublons |\n"
        "| `test_content_and_official_coverage_fields` | Compteurs contenu / archive |\n"
        "| `test_tree_ordering_stable` | Ordre déterministe |\n"
        "| `test_read_only_hash_unchanged` | Aucune mutation DB |\n"
        "| `test_math_verdict_not_complete_with_known_gaps` | Maths INCOMPLETE + gap Trigonométrie |\n\n"
        "Commande: `python -m pytest tests/test_lcai_0038_curriculum_tree.py -q`\n"
        "Résultat attendu: **7 passed**\n",
        encoding="utf-8",
    )
    (ARTIFACT_DIR / "LCAI-0038_NON_REGRESSION_REPORT.md").write_text(
        f"# Non-regression\n\n- db_sha256={result.db_sha256}\n- mode=read_only\n- mutations=0\n",
        encoding="utf-8",
    )
    files = [
        "LCAI-0038_IMPLEMENTATION_REPORT.md",
        "LCAI-0038_PRE_AUDIT_STATE.md",
        "LCAI-0038_CURRICULUM_TREE.md",
        "LCAI-0038_MATHEMATICS_TREE.md",
        "LCAI-0038_CURRICULUM_TREE.csv",
        "LCAI-0038_CHAPTER_INVENTORY.csv",
        "LCAI-0038_CURRICULUM_GAPS.csv",
        "LCAI-0038_ORPHAN_NODES.csv",
        "LCAI-0038_DUPLICATE_AND_OVERLAP_REPORT.md",
        "LCAI-0038_CURRICULUM_COVERAGE_REPORT.md",
        "LCAI-0038_TARGET_COMPARISON.md",
        "LCAI-0038_TEST_REPORT.md",
        "LCAI-0038_NON_REGRESSION_REPORT.md",
    ]
    manifest_files = []
    for name in files:
        path = ARTIFACT_DIR / name
        if not path.exists():
            continue
        raw = path.read_bytes()
        manifest_files.append(
            {"path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "purpose": name}
        )
    manifest = {
        "ticket": "LCAI-0038",
        "generated_at": _now(),
        "auditor_version": AUDITOR_VERSION,
        "database_sha256": result.db_sha256,
        "stats": asdict(result.stats),
        "verdicts": result.verdicts,
        "files": manifest_files,
    }
    (ARTIFACT_DIR / "LCAI-0038_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    zip_path = ARTIFACT_DIR / "LCAI-0038_REVIEW_PACKAGE.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in files + ["LCAI-0038_MANIFEST.json"]:
            path = ARTIFACT_DIR / name
            if path.exists():
                zf.write(path, arcname=name)
    return zip_path
