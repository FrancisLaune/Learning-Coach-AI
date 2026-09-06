"""Phase 7 smoke + DB audit helpers for LCAI-0031."""
from __future__ import annotations

import importlib
from pathlib import Path

from core.config import PROJECT_ROOT, get_database_path, get_v2_database_path


def smoke_imports() -> list[str]:
    modules = [
        "domain.dnb.config",
        "domain.dnb.calendar",
        "services.dnb",
        "services.brevet_referential",
        "services.chatgpt_voice",
        "ui.dnb_navigation",
        "ui.dnb_student_home",
        "ui.dnb_exam_pages",
        "ui.dnb_parent_dashboard",
        "ui.unified_app",
    ]
    ok: list[str] = []
    for name in modules:
        importlib.import_module(name)
        ok.append(name)
    return ok


def audit_dbs() -> dict[str, object]:
    import duckdb

    result: dict[str, object] = {}
    v2 = Path(get_v2_database_path())
    ob = Path(get_database_path())
    result["v2_path"] = str(v2)
    result["objectif_brevet_path"] = str(ob)
    if v2.exists():
        con = duckdb.connect(str(v2), read_only=True)
        tables = [
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY 1"
            ).fetchall()
        ]
        dnbish = [t for t in tables if "dnb" in t.lower() or "brevet" in t.lower() or "exam_archive" in t.lower()]
        result["v2_table_count"] = len(tables)
        result["v2_dnb_related"] = dnbish
        con.close()
    if ob.exists():
        con = duckdb.connect(str(ob), read_only=True)
        content = con.execute("SELECT COUNT(*) FROM content_items").fetchone()[0]
        skills = con.execute("SELECT COUNT(*) FROM skills WHERE active").fetchone()[0]
        archives = con.execute("SELECT COUNT(*) FROM exam_archives_ref").fetchone()[0]
        result["ob_content_items"] = int(content)
        result["ob_skills"] = int(skills)
        result["ob_archives"] = int(archives)
        con.close()
    # product facing grades
    from services.dnb import product_facing_grade_codes, product_config

    result["product_grades"] = sorted(product_facing_grade_codes())
    result["primary_grade"] = product_config().primary_grade_code
    result["docs"] = sorted(p.name for p in (PROJECT_ROOT / "docs" / "phase6" / "LCAI-0031").glob("*.md"))
    return result


if __name__ == "__main__":
    print("SMOKE", smoke_imports())
    print("AUDIT", audit_dbs())
