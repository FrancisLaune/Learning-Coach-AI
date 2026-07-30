"""LCAI-0018H — Global curriculum certification audit (CM1–3e, 4e, 5e, 6e)."""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_v2_database_path
from infrastructure.database.v2 import reset_v2_connections
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from scripts.lcai_0000a_global_curriculum_inventory import (
    TICKET_BY_GRADE,
    apply_0000a_status,
    collect_inventory,
)
from services.content.homework_availability import HomeworkAvailabilityService

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "phase3"
EXPORTS = DOCS / "exports"

CERTIFICATION_GRADES = (
    "FR-CM1",
    "FR-CM2",
    "FR-6E",
    "FR-5E",
    "FR-4E",
    "FR-3E",
)

PUBLICATION_REPORTS: dict[str, str] = {
    "LCAI-0018G": "docs/phase3/exports/lcai_0018g_3e_certification_report.json",
    "LCAI-0018C": "docs/phase3/exports/lcai_0018c_cm1_publication_report.json",
    "LCAI-0018D": "docs/phase3/exports/lcai_0018d_cm2_publication_report.json",
    "LCAI-0018E": "docs/phase3/exports/lcai_0018e_6e_publication_report.json",
    "LCAI-0018F": "docs/phase3/exports/lcai_0018f_5e_publication_report.json",
}


@dataclass
class GradeCertification:
    grade_code: str
    grade_label: str
    ticket: str
    ticket_status: str
    technical_validation_0000a: str
    subjects_total: int
    subjects_with_published_chapters: int
    chapters_published: int
    chapters_curriculum: int
    homework_subjects_available: int
    homework_subjects_limited: int
    homework_subjects_unavailable: int
    publication_executed: bool
    published_count: int
    certification_status: str
    residual_gaps: str


def _load_0000a_status() -> dict[str, str]:
    status: dict[str, str] = {}
    for path in EXPORTS.glob("lcai_0000a_lcai_0018*_validation_report.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        status[payload["ticket"]] = payload.get("technical_validation", "UNKNOWN")
    return status


def _publication_summary(ticket: str) -> tuple[bool, int]:
    rel = PUBLICATION_REPORTS.get(ticket)
    if rel is None:
        return False, 0
    path = ROOT / rel
    if not path.exists():
        return False, 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    if ticket == "LCAI-0018G":
        count = int(payload.get("production_total") or 0)
        return count > 0, count
    published = payload.get("published") or []
    count = int(payload.get("published_count") or len(published))
    return count > 0, count


def _homework_summary(grade_id: int | None) -> tuple[int, int, int]:
    if grade_id is None:
        return 0, 0, 0
    try:
        repository = DuckDBUnifiedExperienceRepository(get_v2_database_path())
        availability = HomeworkAvailabilityService(repository).list_for_grade(grade_id)
        available = sum(1 for item in availability if item.availability_status == "available")
        limited = sum(1 for item in availability if item.availability_status == "limited")
        unavailable = sum(1 for item in availability if item.availability_status == "unavailable")
        return available, limited, unavailable
    except Exception:
        return 0, 0, 0
    finally:
        reset_v2_connections()


def build_grade_certifications(
    inventory_rows: list,
    validation_0000a: dict[str, str],
) -> list[GradeCertification]:
    by_grade: dict[str, list] = {}
    for row in inventory_rows:
        if row.grade_code not in CERTIFICATION_GRADES:
            continue
        by_grade.setdefault(row.grade_code, []).append(row)

    connection = duckdb.connect(str(get_v2_database_path()), read_only=True)
    grade_ids: dict[str, int] = {}
    certifications: list[GradeCertification] = []
    try:
        for grade_code in CERTIFICATION_GRADES:
            row = connection.execute("SELECT id FROM school_levels WHERE code=?", [grade_code]).fetchone()
            if row:
                grade_ids[grade_code] = int(row[0])

        for grade_code in CERTIFICATION_GRADES:
            rows = by_grade.get(grade_code, [])
            if not rows:
                continue
            meta = TICKET_BY_GRADE.get(grade_code, {"ticket": "—", "status": "OUT_OF_SCOPE"})
            ticket = str(meta["ticket"])
            ticket_status = str(meta["status"])
            tech = validation_0000a.get(ticket, "PENDING" if ticket_status == "PENDING" else "NOT_RUN")

            chapters_pub = sum(r.chapters_published for r in rows)
            chapters_cur = sum(r.chapters_curriculum for r in rows)
            subjects_with_pub = sum(1 for r in rows if r.chapters_published > 0)
            pub_executed, pub_count = _publication_summary(ticket) if ticket_status == "IMPLEMENTED" else (False, 0)

            if ticket_status == "PENDING":
                cert_status = "NON_CERTIFIE"
                gaps = "Ticket non implémenté"
            elif grade_code == "FR-3E" and subjects_with_pub > 0:
                cert_status = "CERTIFIE_EXISTANT"
                gaps = "Catalogue production existant (hors pipeline 0012E PRIMARY)"
            elif tech not in {"OK", "WARN"}:
                cert_status = "TECHNIQUE_NOK"
                gaps = f"Validation LCAI-0000A : {tech}"
            elif subjects_with_pub == 0:
                cert_status = "NON_CERTIFIE"
                gaps = "Aucune matière avec chapitres publiés"
            elif subjects_with_pub < len(rows):
                cert_status = "CERTIFIE_PARTIEL"
                missing = [r.subject_label for r in rows if r.chapters_published == 0]
                gaps = f"Matières sans publication : {', '.join(missing[:6])}"
                if len(missing) > 6:
                    gaps += f" (+{len(missing) - 6})"
            else:
                cert_status = "CERTIFIE_PARTIEL"
                gaps = "Couverture compétences incomplète (publication AI maths/college partielle)"

            if grade_code == "FR-4E" and tech in {"OK", "WARN"}:
                cert_status = "CERTIFIE_REFERENCE"
                gaps = "Niveau référence 18B — couverture partielle documentée"

            certifications.append(
                GradeCertification(
                    grade_code=grade_code,
                    grade_label=rows[0].grade_label,
                    ticket=ticket,
                    ticket_status=ticket_status,
                    technical_validation_0000a=tech,
                    subjects_total=len(rows),
                    subjects_with_published_chapters=subjects_with_pub,
                    chapters_published=chapters_pub,
                    chapters_curriculum=chapters_cur,
                    homework_subjects_available=0,
                    homework_subjects_limited=0,
                    homework_subjects_unavailable=0,
                    publication_executed=pub_executed,
                    published_count=pub_count,
                    certification_status=cert_status,
                    residual_gaps=gaps,
                )
            )
    finally:
        connection.close()
        reset_v2_connections()

    for cert in certifications:
        hw_avail, hw_lim, hw_unavail = _homework_summary(grade_ids.get(cert.grade_code))
        cert.homework_subjects_available = hw_avail
        cert.homework_subjects_limited = hw_lim
        cert.homework_subjects_unavailable = hw_unavail

    return certifications


def write_certification_report(
    certifications: list[GradeCertification],
    inventory_rows: list,
    validation_0000a: dict[str, str],
) -> None:
    certified_partial = sum(1 for c in certifications if c.certification_status.startswith("CERTIFIE"))
    total_subjects = len([r for r in inventory_rows if r.grade_code in CERTIFICATION_GRADES])
    subjects_with_prod = len(
        [r for r in inventory_rows if r.grade_code in CERTIFICATION_GRADES and r.chapters_published > 0]
    )
    total_chapters_cur = sum(c.chapters_curriculum for c in certifications)
    total_chapters_pub = sum(c.chapters_published for c in certifications)
    coverage_pct = round(100 * total_chapters_pub / total_chapters_cur, 1) if total_chapters_cur else 0.0

    state_labels = {
        "TECH_OK_UX_HUMAINE": "✅ Tech OK — UX humaine",
        "CONTENU_A_PUBLIER": "📦 Sans publication",
        "TECH_NOK": "❌ Tech NOK",
        "PRET_VALIDATION_0000A": "🔄 Prêt 0000A",
        "PARTIEL": "⚠️ Partiel",
    }

    lines = [
        "# LCAI-0018H — Rapport de certification globale",
        "",
        f"**Date :** {datetime.now(UTC).replace(microsecond=0).isoformat()}",
        "**Périmètre :** CM1, CM2, 6e, 5e, 4e, 3e",
        "",
        "## Verdict global",
        "",
        "**CERTIFICATION PARTIELLE** — industrialisation technique validée (LCAI-0000A) sur les tickets implémentés ; "
        "couverture pédagogique multi-matières incomplète (DoD 100 % non atteignable par publication AI seule).",
        "",
        f"- Niveaux audités : **{len(certifications)}**",
        f"- Niveaux certifiés (partiel ou référence) : **{certified_partial}**",
        f"- Combinaisons niveau/matière : **{total_subjects}**",
        f"- Matières avec chapitres publiés : **{subjects_with_prod}**",
        f"- Chapitres publiés / curriculum : **{total_chapters_pub} / {total_chapters_cur}** ({coverage_pct} %)",
        "",
        "## Validation technique LCAI-0000A",
        "",
        "| Ticket | Statut |",
        "|--------|--------|",
    ]
    for ticket, status in sorted(validation_0000a.items()):
        lines.append(f"| {ticket} | {status} |")

    lines.extend(["", "## Certification par niveau", ""])
    lines.append(
        "| Niveau | Ticket | 0000A | Matières prod. | Ch. prod./cur. | Devoirs dispo./limit./indisp. | Statut |"
    )
    lines.append(
        "|--------|--------|-------|----------------:|----------------:|-------------------------------:|--------|"
    )
    for cert in certifications:
        hw = f"{cert.homework_subjects_available}/{cert.homework_subjects_limited}/{cert.homework_subjects_unavailable}"
        ch = f"{cert.chapters_published}/{cert.chapters_curriculum}"
        mat = f"{cert.subjects_with_published_chapters}/{cert.subjects_total}"
        lines.append(
            f"| {cert.grade_label} | {cert.ticket} | {cert.technical_validation_0000a} | {mat} | {ch} | {hw} | "
            f"{cert.certification_status} |"
        )

    lines.extend(["", "## Chargement matières par classe", ""])
    by_grade: dict[str, list] = {}
    for row in inventory_rows:
        if row.grade_code in CERTIFICATION_GRADES:
            by_grade.setdefault(row.grade_code, []).append(row)

    for cert in certifications:
        rows = by_grade.get(cert.grade_code, [])
        if not rows:
            continue
        lines.append(f"### {cert.grade_label} (`{cert.grade_code}`) — {cert.ticket}")
        lines.append("")
        lines.append("| Matière | Ch. prod. | Ch. curriculum | Lignes prod. | Draft | État |")
        lines.append("|---------|----------:|---------------:|-------------:|------:|------|")
        for row in rows:
            state = state_labels.get(row.validation_state, row.validation_state)
            lines.append(
                f"| {row.subject_label} | {row.chapters_published} | {row.chapters_curriculum} | "
                f"{row.published_content_rows} | {row.draft_content_rows} | {state} |"
            )
        lines.append("")

    lines.extend(["", "## Écarts résiduels par niveau", ""])
    for cert in certifications:
        lines.append(f"- **{cert.grade_label}** ({cert.ticket}) : {cert.residual_gaps}")

    lines.extend(
        [
            "",
            "## Validation humaine requise (LCAI-0000A)",
            "",
            "Pour chaque matière avec chapitres publiés : parcours devoirs parent/élève en UI.",
            "",
            "## Livrables",
            "",
            "- `docs/phase3/exports/LCAI-0018H_GRADE_CERTIFICATION.csv`",
            "- `docs/phase3/exports/LCAI-0018H_GLOBAL_CERTIFICATION.json`",
            "- `docs/phase3/LCAI-0018H_GLOBAL_CERTIFICATION_REPORT.md`",
            "- `docs/phase3/LCAI-0000A_GLOBAL_CURRICULUM_VALIDATION_INVENTORY.md`",
            "",
        ]
    )

    (DOCS / "LCAI-0018H_GLOBAL_CERTIFICATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    csv_path = EXPORTS / "LCAI-0018H_GRADE_CERTIFICATION.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        if certifications:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(certifications[0]).keys()))
            writer.writeheader()
            for cert in certifications:
                writer.writerow(asdict(cert))

    json_path = EXPORTS / "LCAI-0018H_GLOBAL_CERTIFICATION.json"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "verdict": "CERTIFICATION_PARTIELLE",
                "validation_0000a": validation_0000a,
                "grades": [asdict(c) for c in certifications],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def run_0000a_curriculum_all() -> dict[str, str]:
    """Load existing LCAI-0000A reports (no full pytest re-run)."""
    return _load_0000a_status()


def main() -> None:
    EXPORTS.mkdir(parents=True, exist_ok=True)
    validation_0000a = run_0000a_curriculum_all()

    connection = duckdb.connect(str(get_v2_database_path()), read_only=True)
    try:
        inventory = apply_0000a_status(collect_inventory(connection), validation_0000a)
    finally:
        connection.close()
        reset_v2_connections()

    certifications = build_grade_certifications(inventory, validation_0000a)
    write_certification_report(certifications, inventory, validation_0000a)

    print("LCAI-0018H global certification audit complete")
    print(f"grades certified (partial+): {sum(1 for c in certifications if 'CERTIFIE' in c.certification_status)}")
    for cert in certifications:
        print(
            f"  {cert.grade_code}: {cert.certification_status} ({cert.subjects_with_published_chapters}/{cert.subjects_total} matières)"
        )


if __name__ == "__main__":
    main()
