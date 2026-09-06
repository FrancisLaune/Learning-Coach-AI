"""Seed curriculum domains / chapters / skills from Python subject banks."""

from __future__ import annotations

import importlib
import sys

from core.config import PROJECT_ROOT
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.models import SUBJECT_MODULE_MAP, importance_for, slugify


def _ensure_path() -> None:
    enrichie = PROJECT_ROOT / "revision_3e_enrichie"
    if str(enrichie) not in sys.path:
        sys.path.insert(0, str(enrichie))


def seed_curriculum_from_banks(store: BrevetContentStore | None = None) -> dict[str, int]:
    _ensure_path()
    store = store or BrevetContentStore()
    con = store.connect()
    stats = {"domains": 0, "chapters": 0, "skills": 0}
    version = con.execute(
        "SELECT curriculum_version_id FROM curriculum_versions WHERE code = 'FR_3E_DNB_2027_V1'"
    ).fetchone()
    if version is None:
        raise RuntimeError("curriculum_versions FR_3E_DNB_2027_V1 missing — apply migrations first")
    version_id = int(version[0])

    for module_name, (subject_code, label) in SUBJECT_MODULE_MAP.items():
        subject = con.execute("SELECT subject_id FROM subjects WHERE code = ?", [subject_code]).fetchone()
        if subject is None:
            continue
        subject_id = int(subject[0])
        mod = importlib.import_module(f"subjects.{module_name}")
        chapters = getattr(mod, "CHAPTERS", {}) or {}
        domain_code = f"{subject_code}_CORE"
        existing_domain = con.execute(
            """
            SELECT domain_id FROM curriculum_domains
            WHERE curriculum_version_id = ? AND subject_id = ? AND code = ?
            """,
            [version_id, subject_id, domain_code],
        ).fetchone()
        if existing_domain is None:
            con.execute(
                """
                INSERT INTO curriculum_domains(
                    curriculum_version_id, subject_id, code, name, description, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [version_id, subject_id, domain_code, f"{label} — programme 3e", "Domaine principal", 1],
            )
            stats["domains"] += 1
            domain_id = int(
                con.execute(
                    """
                    SELECT domain_id FROM curriculum_domains
                    WHERE curriculum_version_id = ? AND subject_id = ? AND code = ?
                    """,
                    [version_id, subject_id, domain_code],
                ).fetchone()[0]
            )
        else:
            domain_id = int(existing_domain[0])

        for chapter_name, meta in chapters.items():
            chapter_code = slugify(chapter_name)[:80]
            importance = importance_for(subject_code, chapter_name)
            description = str(meta.get("summary") or "") if isinstance(meta, dict) else ""
            existing_ch = con.execute(
                "SELECT chapter_id FROM chapters WHERE domain_id = ? AND code = ?",
                [domain_id, chapter_code],
            ).fetchone()
            if existing_ch is None:
                con.execute(
                    """
                    INSERT INTO chapters(domain_id, code, name, description, brevet_importance, active)
                    VALUES (?, ?, ?, ?, ?, TRUE)
                    """,
                    [domain_id, chapter_code, chapter_name, description, importance],
                )
                stats["chapters"] += 1
                chapter_id = int(
                    con.execute(
                        "SELECT chapter_id FROM chapters WHERE domain_id = ? AND code = ?",
                        [domain_id, chapter_code],
                    ).fetchone()[0]
                )
            else:
                chapter_id = int(existing_ch[0])
                con.execute(
                    "UPDATE chapters SET brevet_importance = ?, name = ? WHERE chapter_id = ?",
                    [importance, chapter_name, chapter_id],
                )

            skill_code = f"{chapter_code}_SKILL"
            existing_sk = con.execute(
                "SELECT skill_id FROM skills WHERE chapter_id = ? AND code = ?",
                [chapter_id, skill_code],
            ).fetchone()
            if existing_sk is None:
                con.execute(
                    """
                    INSERT INTO skills(
                        chapter_id, code, name, description, expected_level,
                        brevet_importance, auto_gradable, active
                    ) VALUES (?, ?, ?, ?, '3E', ?, TRUE, TRUE)
                    """,
                    [chapter_id, skill_code, chapter_name, description, importance],
                )
                stats["skills"] += 1
            else:
                con.execute(
                    "UPDATE skills SET brevet_importance = ?, name = ? WHERE skill_id = ?",
                    [importance, chapter_name, int(existing_sk[0])],
                )

    oral = con.execute("SELECT subject_id FROM subjects WHERE code = 'ORAL'").fetchone()
    if oral is not None:
        oral_id = int(oral[0])
        domain = con.execute(
            """
            SELECT domain_id FROM curriculum_domains
            WHERE curriculum_version_id = ? AND subject_id = ? AND code = 'ORAL_CORE'
            """,
            [version_id, oral_id],
        ).fetchone()
        if domain is None:
            con.execute(
                """
                INSERT INTO curriculum_domains(
                    curriculum_version_id, subject_id, code, name, description, sort_order
                ) VALUES (?, ?, 'ORAL_CORE', 'Oral du DNB', 'Projet et soutenance', 1)
                """,
                [version_id, oral_id],
            )
            stats["domains"] += 1
            domain_id = int(
                con.execute(
                    """
                    SELECT domain_id FROM curriculum_domains
                    WHERE curriculum_version_id = ? AND subject_id = ? AND code = 'ORAL_CORE'
                    """,
                    [version_id, oral_id],
                ).fetchone()[0]
            )
        else:
            domain_id = int(domain[0])
        ch = con.execute(
            "SELECT chapter_id FROM chapters WHERE domain_id = ? AND code = 'ORAL_PROJECT'",
            [domain_id],
        ).fetchone()
        if ch is None:
            con.execute(
                """
                INSERT INTO chapters(domain_id, code, name, description, brevet_importance, active)
                VALUES (?, 'ORAL_PROJECT', 'Projet oral', 'Préparation soutenance', 'HIGH', TRUE)
                """,
                [domain_id],
            )
            stats["chapters"] += 1
            chapter_id = int(
                con.execute(
                    "SELECT chapter_id FROM chapters WHERE domain_id = ? AND code = 'ORAL_PROJECT'",
                    [domain_id],
                ).fetchone()[0]
            )
        else:
            chapter_id = int(ch[0])
        sk = con.execute(
            "SELECT skill_id FROM skills WHERE chapter_id = ? AND code = 'ORAL_DEFENSE'",
            [chapter_id],
        ).fetchone()
        if sk is None:
            con.execute(
                """
                INSERT INTO skills(
                    chapter_id, code, name, description, expected_level,
                    brevet_importance, auto_gradable, active
                ) VALUES (?, 'ORAL_DEFENSE', 'Soutenance orale', 'Présenter et répondre au jury',
                          '3E', 'HIGH', FALSE, TRUE)
                """,
                [chapter_id],
            )
            stats["skills"] += 1
    return stats
