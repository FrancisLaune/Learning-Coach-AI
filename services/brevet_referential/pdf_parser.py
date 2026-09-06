"""LCAI-0035 — PDF text extraction and DNB exercise segmentation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PARSER_VERSION = "lcai-0035-pdf-v1"

EXERCISE_RE = re.compile(r"(?mi)^(?:\s*)(?:exercice|partie)\s+(\d+|[IVXLC]+)(?:\s*[:.\-–—)]|\s*\(|\s*$)")
QUESTION_RE = re.compile(r"(?mi)^(?:\s*)(?:question\s+)?(\d+)\s*[.)]\s+|^(?:\s*)([a-e])\s*[.)]\s+")
POINTS_RE = re.compile(r"(?i)(\d+(?:[.,]\d+)?)\s*points?")
CODE_RE = re.compile(r"\b(2[0-9]GEN[A-Z0-9]{3,14})\b")
SESSION_YEAR_RE = re.compile(r"(?i)session\s+(20\d{2})")


@dataclass(slots=True)
class ParsedQuestion:
    reference: str
    statement: str
    question_number: str
    subquestion_number: str | None = None
    points: float | None = None
    source_page_start: int | None = None
    source_page_end: int | None = None
    source_locator: str | None = None
    question_kind: str = "QUESTION"
    shared_context_ref: str | None = None
    parser_confidence: float = 0.7


@dataclass(slots=True)
class ParsedSection:
    title: str
    section_type: str
    position: int
    points: float | None = None
    questions: list[ParsedQuestion] = field(default_factory=list)
    raw_text: str = ""


@dataclass(slots=True)
class ParsedDocument:
    full_text: str
    pages: list[str]
    page_count: int
    official_exam_code: str | None
    year: int | None
    subject_guess: str | None
    zone_guess: str | None
    variant: str
    sections: list[ParsedSection]
    extraction_method: str = "PYPDF_TEXT"
    parser_version: str = PARSER_VERSION
    parser_confidence: float = 0.7
    metadata: dict[str, Any] = field(default_factory=dict)


def detect_variant(text: str) -> str:
    lowered = (text or "").casefold()
    if "arial 16" in lowered:
        return "ARIAL_16"
    if "arial 20" in lowered:
        return "ARIAL_20"
    if "arial 24" in lowered:
        return "ARIAL_24"
    if "braille" in lowered:
        return "BRAILLE"
    if "caractères agrandis" in lowered or "caracteres agrandis" in lowered:
        return "LARGE_PRINT"
    return "STANDARD"


def guess_subject(text: str, code: str | None = None) -> str | None:
    code_u = (code or "").upper()
    if "MAT" in code_u:
        return "MATHEMATICS"
    if "FR" in code_u:
        return "FRENCH"
    if "HGEMC" in code_u or "HG" in code_u:
        return "HISTORY_GEOGRAPHY_EMC"
    if "SC" in code_u:
        return "SCIENCES"
    lowered = (text or "").casefold()
    if "mathématique" in lowered or "mathematique" in lowered:
        return "MATHEMATICS"
    if "français" in lowered or "francais" in lowered or "dictée" in lowered:
        return "FRENCH"
    if "histoire" in lowered or "géographie" in lowered or "geographie" in lowered:
        return "HISTORY_GEOGRAPHY_EMC"
    if "sciences" in lowered or "physique" in lowered:
        return "SCIENCES"
    return None


def guess_zone(text: str, code: str | None = None) -> str:
    code_u = (code or "").upper()
    for marker, zone in (
        ("AS", "asie"),
        ("AN", "amerique_nord"),
        ("PO", "polynesie"),
        ("ME", "metropole"),
        ("NC", "nouvelle_caledonie"),
        ("AA", "centres_etrangers"),
        ("AG", "metropole"),
        ("G1", "metropole"),
    ):
        if (code_u.endswith(marker + "1") or marker in code_u[-4:]) and (
            code_u[-4:-1] == marker or code_u[-3:-1] == marker[:2]
        ):
            return zone
    lowered = (text or "").casefold()
    if "asie" in lowered:
        return "asie"
    if "amérique" in lowered or "amerique" in lowered:
        return "amerique_nord"
    if "polyn" in lowered:
        return "polynesie"
    if "métropole" in lowered or "metropole" in lowered:
        return "metropole"
    if "centres" in lowered:
        return "centres_etrangers"
    return "unknown"


def _roman_or_int(token: str) -> int:
    token = token.strip().upper()
    if token.isdigit():
        return int(token)
    romans = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
    return romans.get(token, 0)


def extract_pdf_text(path: Path) -> tuple[list[str], str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return pages, "\n".join(pages)


def _split_exercises(text: str) -> list[tuple[str, str]]:
    matches = list(EXERCISE_RE.finditer(text))
    if not matches:
        return [("Sujet", text.strip())]
    chunks: list[tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble and len(preamble) > 80:
        chunks.append(("Preamble", preamble))
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        label = match.group(0).strip().split("\n")[0][:80]
        chunks.append((label, text[start:end].strip()))
    return chunks


def _extract_points(text: str) -> float | None:
    match = POINTS_RE.search(text[:200])
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _segment_questions(section_label: str, body: str, page_hint: int | None) -> list[ParsedQuestion]:
    lines = body.splitlines()
    blocks: list[tuple[str, list[str]]] = []
    current_ref = "1"
    current_lines: list[str] = []
    saw_marker = False
    for line in lines:
        qmatch = re.match(r"^\s*(?:Question\s+)?(\d+)\s*[.)]\s+(.*)$", line, re.I)
        amatch = re.match(r"^\s*([a-e])\s*[.)]\s+(.*)$", line, re.I)
        if qmatch:
            if current_lines and saw_marker:
                blocks.append((current_ref, current_lines))
            current_ref = qmatch.group(1)
            current_lines = [qmatch.group(2)]
            saw_marker = True
        elif amatch and saw_marker:
            if current_lines:
                blocks.append((current_ref, current_lines))
            current_ref = f"{current_ref}.{amatch.group(1)}"
            current_lines = [amatch.group(2)]
        else:
            current_lines.append(line)
    if current_lines:
        blocks.append((current_ref if saw_marker else "1", current_lines))

    # Fallback: whole exercise as one playable unit when no question markers.
    if not saw_marker:
        statement = body.strip()
        if len(statement) < 40:
            return []
        return [
            ParsedQuestion(
                reference=section_label[:40],
                statement=statement[:8000],
                question_number="1",
                points=_extract_points(statement),
                source_page_start=page_hint,
                source_page_end=page_hint,
                source_locator=f"section:{section_label}|q:1",
                question_kind="EXERCISE",
                parser_confidence=0.55,
            )
        ]

    questions: list[ParsedQuestion] = []
    context = ""
    # Shared context = text before first numbered question inside exercise.
    first_q = re.search(r"(?mi)^(?:\s*)(?:Question\s+)?\d+\s*[.)]", body)
    if first_q and first_q.start() > 40:
        context = body[: first_q.start()].strip()

    for ref, ref_lines in blocks:
        statement = "\n".join(ref_lines).strip()
        if len(statement) < 15:
            continue
        full = f"{context}\n\n{statement}" if context and not statement.startswith(context[:40]) else statement
        parts = ref.split(".")
        qnum = parts[0]
        sub = parts[1] if len(parts) > 1 else None
        questions.append(
            ParsedQuestion(
                reference=f"{section_label} Q{ref}",
                statement=full[:8000],
                question_number=qnum,
                subquestion_number=sub,
                points=_extract_points(statement),
                source_page_start=page_hint,
                source_page_end=page_hint,
                source_locator=f"section:{section_label}|q:{ref}",
                question_kind="SUBQUESTION" if sub else "QUESTION",
                shared_context_ref=section_label if context else None,
                parser_confidence=0.75 if sub or qnum else 0.6,
            )
        )
    return questions


def _page_for_snippet(pages: list[str], snippet: str) -> int | None:
    needle = (snippet or "")[:80]
    if not needle:
        return None
    for index, page in enumerate(pages, start=1):
        if needle in page:
            return index
    return None


def parse_dnb_pdf(path: Path) -> ParsedDocument:
    pages, full_text = extract_pdf_text(path)
    code_match = CODE_RE.search(full_text)
    code = code_match.group(1) if code_match else None
    year_match = SESSION_YEAR_RE.search(full_text)
    year = int(year_match.group(1)) if year_match else None
    if year is None and code and code[:2].isdigit():
        year = 2000 + int(code[:2])
    subject = guess_subject(full_text, code)
    zone = guess_zone(full_text, code)
    variant = detect_variant(full_text)

    sections: list[ParsedSection] = []
    chunks = _split_exercises(full_text)
    position = 0
    for label, body in chunks:
        if label == "Preamble":
            continue
        position += 1
        page_hint = _page_for_snippet(pages, body[:120])
        questions = _segment_questions(label, body, page_hint)
        sections.append(
            ParsedSection(
                title=label[:120],
                section_type="EXERCISE",
                position=position,
                points=_extract_points(body),
                questions=questions,
                raw_text=body[:20000],
            )
        )

    # French single-document parts (dictée / rédaction) may have no "Exercice".
    if not sections and full_text.strip():
        sections.append(
            ParsedSection(
                title="Document",
                section_type="MAIN",
                position=1,
                points=_extract_points(full_text),
                questions=_segment_questions("Document", full_text, 1),
                raw_text=full_text[:20000],
            )
        )

    confidence = 0.8 if sections and any(s.questions for s in sections) else 0.4
    return ParsedDocument(
        full_text=full_text,
        pages=pages,
        page_count=len(pages),
        official_exam_code=code,
        year=year,
        subject_guess=subject,
        zone_guess=zone,
        variant=variant,
        sections=sections,
        parser_confidence=confidence,
        metadata={"path": str(path)},
    )


def is_dnb_document(text: str) -> bool:
    lowered = (text or "").casefold()
    return (
        "diplôme national du brevet" in lowered
        or "diplome national du brevet" in lowered
        or "dnb –" in lowered
        or "dnb -" in lowered
        or bool(CODE_RE.search(text or ""))
    )
