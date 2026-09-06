"""LCAI-0035 — curated offline catalog of official DNB documents."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.config import PROJECT_ROOT
from services.brevet_referential.eduscol_ingest import detect_document_variant

CATALOG_PATH = PROJECT_ROOT / "data" / "dnb_eduscol_document_catalog.json"
MANIFEST_PATH = PROJECT_ROOT / "data" / "dnb_archive_manifest.json"
ARTIFACT_PROBE = PROJECT_ROOT / "artifacts" / "LCAI-0035" / "catalog_dnb.json"

EDUSCOL_HUB = "https://eduscol.education.fr/cid133202/diplome-national-du-brevet.html"
EDUSCOL_GOUV_HUB = (
    "https://eduscol.education.gouv.fr/5202/preparer-le-diplome-national-du-brevet-dnb-avec-les-sujets-des-annales"
)

SUBJECT_CODE_MAP = {
    "MATHEMATICS": ("MATHEMATICS", "mathematics", "MATHEMATICS"),
    "FRENCH": ("FRENCH", "french", "FRENCH"),
    "HISTORY_GEOGRAPHY_EMC": ("HISTORY", "history_geography_emc", "HISTORY_GEOGRAPHY_EMC"),
    "SCIENCES": ("PHYSICS_CHEMISTRY", "sciences", "SCIENCES"),
    "TECHNOLOGY": ("TECHNOLOGY", "technology", "TECHNOLOGY"),
}


def _zone_from_code(code: str | None) -> str:
    if not code:
        return "unknown"
    code_u = code.upper()
    mapping = {
        "AS": "asie",
        "AN": "amerique_nord",
        "PO": "polynesie",
        "ME": "metropole",
        "NC": "nouvelle_caledonie",
        "AA": "centres_etrangers",
        "AG": "metropole",
        "G1": "metropole",
        "S1": "metropole",
    }
    for token, zone in mapping.items():
        if token in code_u:
            return zone
    return "unknown"


def exam_identity_key(
    *,
    year: int | None,
    session: str,
    zone: str,
    series: str,
    subject_group: str,
    exam_code: str | None,
) -> str:
    code = (exam_code or "NOCODE").upper()
    # Collapse French part codes: FRD/FRQGC/FRR (+ AA1 zone) → FR + zone.
    stem = re.sub(r"FR(?:QGC|QG|D|R)", "FR", code)
    stem = re.sub(r"(ARIAL|BRAILLE|LP).*$", "", stem)
    return f"{year or 'NA'}-{session}-{zone}-{series}-{subject_group}-{stem}"


def _entry_from_probe(row: dict[str, Any]) -> dict[str, Any] | None:
    if not row.get("is_dnb"):
        return None
    code = str(row.get("code") or "").upper()
    subject = str(row.get("subject") or "UNKNOWN")
    # Prefer official exam code tokens over noisy PDF header heuristics.
    if "MAT" in code:
        subject = "MATHEMATICS"
    elif "HGEMC" in code or re.search(r"HG(?!E)", code):
        subject = "HISTORY_GEOGRAPHY_EMC"
    elif re.search(r"FR(DA|QG|QGC|R)?", code):
        subject = "FRENCH"
    elif "SC" in code:
        subject = "SCIENCES"
    elif subject == "UNKNOWN":
        return None
    if subject not in SUBJECT_CODE_MAP:
        return None
    subject_code, subject_key, subject_group = SUBJECT_CODE_MAP[subject]
    year = row.get("year")
    code = row.get("code")
    zone = row.get("zone") if row.get("zone") not in (None, "unknown") else _zone_from_code(code)
    variant = row.get("variant") or detect_document_variant(str(row.get("header_sample") or ""))
    session = "normale"
    series = "generale"
    identity = exam_identity_key(
        year=year,
        session=session,
        zone=zone or "unknown",
        series=series,
        subject_group=subject_group,
        exam_code=code,
    )
    doc_id = row.get("document_id")
    url = row.get("url") or (f"https://eduscol.education.fr/document/{doc_id}/download" if doc_id else None)
    if not url:
        return None
    return {
        "exam_identity_key": identity,
        "source_provider": "EDUSCOL",
        "landing_page_url": EDUSCOL_GOUV_HUB,
        "document_url": url,
        "document_type": "SUBJECT",
        "document_variant": variant,
        "year": year,
        "session": session,
        "zone": zone or "unknown",
        "series": series,
        "subject": subject_key,
        "subject_code": subject_code,
        "subject_group": subject_group,
        "official_exam_code": code,
        "eduscol_document_id": str(doc_id) if doc_id else None,
        "local_path": row.get("path"),
        "source_hash": row.get("sha256"),
        "page_count": row.get("pages"),
        "download_status": "DOWNLOADED" if row.get("path") else "PENDING",
        "parse_status": "PENDING",
        "mapping_status": "PENDING",
        "validation_status": "REVIEW",
        "parser_version": None,
        "last_checked_at": None,
        "base_exam_identifier": identity,
        "notes": "Catalogued from offline EduScol PDF probe (LCAI-0035).",
    }


def _static_extra_urls() -> list[dict[str, Any]]:
    """Known official URLs outside the EduScol /document/ID pattern."""
    extras = [
        {
            "year": 2019,
            "subject": "mathematics",
            "subject_code": "MATHEMATICS",
            "subject_group": "MATHEMATICS",
            "zone": "metropole",
            "official_exam_code": "19GENMATMEAG1",
            "document_url": (
                "https://cache.media.eduscol.education.fr/file/sujets_DNB_2019/91/6/"
                "DNB2019_MATHEMATIQUES_SERIE_GENERALE_METROPOLE_1162916.pdf"
            ),
            "source_provider": "EDUSCOL_CACHE",
        },
        {
            "year": 2018,
            "subject": "mathematics",
            "subject_code": "MATHEMATICS",
            "subject_group": "MATHEMATICS",
            "zone": "metropole",
            "official_exam_code": "18GENMATZERO",
            "document_url": (
                "https://cache.media.eduscol.education.fr/file/DNB_2018/63/0/Sujet0_DNB2018_MATH_Serie_GEN_862630.pdf"
            ),
            "document_type": "ZERO_SUBJECT",
            "source_provider": "EDUSCOL_CACHE",
        },
        {
            "year": 2026,
            "subject": "mathematics",
            "subject_code": "MATHEMATICS",
            "subject_group": "MATHEMATICS",
            "zone": "metropole",
            "official_exam_code": "26GENMATME1",
            "document_url": (
                "https://www.education.gouv.fr/sites/default/files/document/"
                "diplome-national-du-brevet-2026-mathematiques-serie-generale-516986.pdf"
            ),
            "source_provider": "EDUCATION_GOUV",
        },
        {
            "year": 2026,
            "subject": "french",
            "subject_code": "FRENCH",
            "subject_group": "FRENCH",
            "zone": "metropole",
            "official_exam_code": "26GENFRME1",
            "document_url": (
                "https://www.education.gouv.fr/sites/default/files/document/"
                "diplome-national-du-brevet-2026-francais-grammaire-et-competences-"
                "linguistiques-comprehension-et_3.pdf"
            ),
            "source_provider": "EDUCATION_GOUV",
        },
        {
            "year": 2026,
            "subject": "history_geography_emc",
            "subject_code": "HISTORY",
            "subject_group": "HISTORY_GEOGRAPHY_EMC",
            "zone": "metropole",
            "official_exam_code": "26GENHGEMCME1",
            "document_url": (
                "https://www.education.gouv.fr/sites/default/files/document/"
                "diplome-national-du-brevet-2026-histoire-geographie-enseignement-"
                "moral-et-civique-serie-generale_2.pdf"
            ),
            "source_provider": "EDUCATION_GOUV",
        },
        {
            "year": 2026,
            "subject": "sciences",
            "subject_code": "PHYSICS_CHEMISTRY",
            "subject_group": "SCIENCES",
            "zone": "metropole",
            "official_exam_code": "26GENSCME1",
            "document_url": (
                "https://www.education.gouv.fr/sites/default/files/document/"
                "diplome-national-du-brevet-2026-sciences-serie-generale-518603.pdf"
            ),
            "source_provider": "EDUCATION_GOUV",
        },
    ]
    out: list[dict[str, Any]] = []
    for item in extras:
        year = int(item["year"])
        zone = str(item["zone"])
        session = "normale"
        series = "generale"
        subject_group = str(item["subject_group"])
        code = str(item.get("official_exam_code"))
        identity = exam_identity_key(
            year=year,
            session=session,
            zone=zone,
            series=series,
            subject_group=subject_group,
            exam_code=code,
        )
        out.append(
            {
                "exam_identity_key": identity,
                "source_provider": item.get("source_provider", "EDUSCOL"),
                "landing_page_url": EDUSCOL_HUB,
                "document_url": item["document_url"],
                "document_type": item.get("document_type", "SUBJECT"),
                "document_variant": "STANDARD",
                "year": year,
                "session": session,
                "zone": zone,
                "series": series,
                "subject": item["subject"],
                "subject_code": item["subject_code"],
                "subject_group": subject_group,
                "official_exam_code": code,
                "eduscol_document_id": None,
                "local_path": None,
                "source_hash": None,
                "page_count": None,
                "download_status": "PENDING",
                "parse_status": "PENDING",
                "mapping_status": "PENDING",
                "validation_status": "REVIEW",
                "parser_version": None,
                "last_checked_at": None,
                "base_exam_identifier": identity,
                "notes": "Static official URL from prior inventory / education.gouv.",
            }
        )
    return out


def build_catalog(include_accessibility: bool = False) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    if ARTIFACT_PROBE.exists():
        for row in json.loads(ARTIFACT_PROBE.read_text(encoding="utf-8")):
            entry = _entry_from_probe(row)
            if not entry:
                continue
            if not include_accessibility and entry["document_variant"] != "STANDARD":
                continue
            url = entry["document_url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            entries.append(entry)
    for entry in _static_extra_urls():
        if entry["document_url"] in seen_urls:
            continue
        seen_urls.add(entry["document_url"])
        entries.append(entry)
    payload = {
        "version": "DNB-EDUSCOL-CATALOG-V1",
        "ticket": "LCAI-0035",
        "source_authority": "Éduscol / Ministère de l'Éducation nationale",
        "include_accessibility_variants": include_accessibility,
        "entries": entries,
    }
    return payload


def write_catalog(path: Path | None = None, include_accessibility: bool = False) -> Path:
    target = path or CATALOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_catalog(include_accessibility=include_accessibility)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    target = path or CATALOG_PATH
    if not target.exists():
        write_catalog(target)
    return json.loads(target.read_text(encoding="utf-8"))


def sync_manifest_from_catalog(catalog: dict[str, Any] | None = None) -> Path:
    """Rewrite data/dnb_archive_manifest.json from the curated catalog (dedup by identity)."""
    catalog = catalog or load_catalog()
    by_identity: dict[str, dict[str, Any]] = {}
    for entry in catalog.get("entries", []):
        if entry.get("document_variant") != "STANDARD":
            continue
        key = entry["exam_identity_key"]
        # Prefer keeping first STANDARD subject document for each identity.
        if key not in by_identity:
            by_identity[key] = {
                "year": entry["year"],
                "session": entry["session"],
                "zone": entry["zone"],
                "series": entry["series"],
                "subject": entry["subject"],
                "subject_code": entry["subject_code"],
                "subject_group": entry["subject_group"],
                "label": entry["subject_group"],
                "source_url": entry["document_url"],
                "correction_url": entry.get("landing_page_url") or EDUSCOL_HUB,
                "status": entry.get("download_status") or "DISCOVERED",
                "base_exam_identifier": entry["exam_identity_key"],
                "exam_identity_key": entry["exam_identity_key"],
                "document_variant": entry["document_variant"],
                "source_provider": entry["source_provider"],
                "official_exam_code": entry.get("official_exam_code"),
                "notes": entry.get("notes"),
            }
    payload = {
        "version": "DNB-ARCHIVE-MANIFEST-V2",
        "source_authority": "Éduscol — Ministère de l'Éducation nationale",
        "ticket": "LCAI-0035",
        "entries": list(by_identity.values()),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return MANIFEST_PATH
