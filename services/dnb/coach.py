"""LCAI-0031 Phase 5 — unique Coach Brevet context pack (ChatGPT-level briefing)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from domain.dnb.calendar import load_dnb_exam_calendar
from domain.dnb.planner import build_brevet_study_plan
from domain.dnb.prioritizer import SkillPriorityInput, default_importance_for_subject, prioritize_skills
from domain.dnb.readiness import compute_brevet_readiness

COACH_NAME = "Coach Brevet"
COACH_MISSION = (
    "Tu es le Coach Brevet unique de Learning Coach AI — professeur de 3e "
    "spécialisé dans la réussite annuelle et le DNB 2027. "
    "Tu parles comme un excellent professeur bienveillant (niveau conversation ChatGPT) : "
    "clair, précis, motivant, sans jargon inutile."
)


@dataclass(frozen=True, slots=True)
class BrevetCoachContext:
    """All elements the unique AI coach needs for a useful exchange."""

    display_name: str = ""
    grade_label: str = "3e"
    series: str = "générale"
    days_until_exam: int | None = None
    exam_dates_summary: str = ""
    readiness_score: float | None = None
    readiness_band: str = ""
    readiness_explanation: str = ""
    weekly_objective: str = ""
    mock_exam_hint: str = ""
    priorities: tuple[str, ...] = ()
    fragile_skills: tuple[str, ...] = ()
    strong_skills: tuple[str, ...] = ()
    subject_label: str = ""
    chapter_label: str = ""
    exercise_statement: str = ""
    notion_reminder: str = ""
    hint_text: str = ""
    student_question: str = ""
    recent_results_summary: str = ""
    continuous_assessment_note: str = (
        "Anglais/Espagnol : suivi contrôle continu uniquement, hors épreuves écrites terminales standard."
    )
    extra_notes: tuple[str, ...] = field(default_factory=tuple)

    def has_exercise(self) -> bool:
        return bool(self.exercise_statement.strip())


def _format_pct(value: float | None) -> str:
    if value is None:
        return "non calculé"
    return f"{value:.0%}"


def build_coach_system_briefing(context: BrevetCoachContext) -> str:
    """System-style briefing injected into every coach turn."""
    lines = [
        COACH_MISSION,
        "",
        "Règles d'échange :",
        "1. Réponds en français, de façon naturelle et pédagogique.",
        "2. Aide à la méthode ; ne donne pas la réponse finale d'un exercice noté sauf demande explicite de correction après coup.",
        "3. Adapte-toi à un élève de 3e préparant le DNB 2027.",
        "4. Utilise TOUT le contexte fourni (priorités, readiness, échéance, exercice).",
        "5. Propose une prochaine action concrète (réviser X, faire un devoir, oral, blanc).",
        "6. Ne confonds jamais annale officielle et contenu généré.",
        "7. Cadre scolaire uniquement — refuse le hors-sujet dangereux.",
        "",
        "Profil élève :",
        f"- Prénom : {context.display_name or 'Élève'}",
        f"- Classe : {context.grade_label} (série {context.series})",
    ]
    if context.days_until_exam is not None:
        lines.append(f"- Jours avant le premier écrit DNB : {context.days_until_exam}")
    if context.exam_dates_summary:
        lines.append(f"- Calendrier : {context.exam_dates_summary}")
    lines.append(f"- Readiness : {_format_pct(context.readiness_score)} ({context.readiness_band or 'n/a'})")
    if context.readiness_explanation:
        lines.append(f"- Lecture readiness : {context.readiness_explanation}")
    if context.weekly_objective:
        lines.append(f"- Objectif de la semaine : {context.weekly_objective}")
    if context.mock_exam_hint:
        lines.append(f"- Conseil blancs : {context.mock_exam_hint}")
    if context.priorities:
        lines.append("- Priorités Brevet :")
        lines.extend(f"  • {item}" for item in context.priorities[:6])
    if context.fragile_skills:
        lines.append("- Points faibles : " + " ; ".join(context.fragile_skills[:5]))
    if context.strong_skills:
        lines.append("- Points forts : " + " ; ".join(context.strong_skills[:5]))
    if context.recent_results_summary:
        lines.append(f"- Résultats récents : {context.recent_results_summary}")
    if context.subject_label:
        lines.append(f"- Matière en cours : {context.subject_label}")
    if context.chapter_label:
        lines.append(f"- Chapitre / compétence : {context.chapter_label}")
    if context.has_exercise():
        lines.append("- Exercice en cours :")
        lines.append(context.exercise_statement.strip()[:1500])
    if context.notion_reminder.strip():
        lines.append(f"- Consignes / notion : {context.notion_reminder.strip()[:500]}")
    if context.hint_text.strip():
        lines.append(f"- Indice catalogue (à reformuler) : {context.hint_text.strip()[:400]}")
    lines.append(f"- Note : {context.continuous_assessment_note}")
    for note in context.extra_notes:
        if note.strip():
            lines.append(f"- {note.strip()}")
    return "\n".join(lines)


def build_coach_user_turn(context: BrevetCoachContext, *, default_ask: str = "") -> str:
    """User-facing turn that still embeds the briefing for ChatGPT URL prefills."""
    briefing = build_coach_system_briefing(context)
    question = (context.student_question or default_ask or "").strip()
    if not question:
        if context.has_exercise():
            question = "Aide-moi à résoudre cet exercice sans me donner tout de suite la réponse finale."
        elif context.priorities:
            question = f"Que dois-je travailler en priorité cette semaine ? Commence par : {context.priorities[0]}"
        else:
            question = "Fais un point Coach Brevet : où j'en suis et que faire ensuite ?"
    return f"{briefing}\n\n---\nMessage de l'élève :\n{question}"


def coach_context_from_home(
    *,
    display_name: str,
    objective: str = "",
    fragile: tuple[Any, ...] = (),
    strong: tuple[Any, ...] = (),
    mastery: tuple[Any, ...] = (),
    revision_priorities: tuple[Any, ...] = (),
    recent_score: str | None = None,
    success_rate: str | None = None,
    subject_label: str = "",
    chapter_label: str = "",
    exercise_statement: str = "",
    notion_reminder: str = "",
    hint_text: str = "",
    student_question: str = "",
    today: date | None = None,
) -> BrevetCoachContext:
    """Assemble coach context from home/guidance signals + DNB engine."""
    as_of = today or date.today()
    calendar = load_dnb_exam_calendar()
    days = calendar.countdown_days(today=as_of)
    exam_dates = ", ".join(
        f"{item.label} ({item.exam_date.isoformat()})" for item in calendar.written_exams
    )

    mastery_rows: list[SkillPriorityInput] = []
    for item in mastery[:12]:
        mastery_rows.append(
            SkillPriorityInput(
                skill_id=int(getattr(item, "skill_id", 0) or 0),
                label=str(getattr(item, "label", "") or "Compétence"),
                mastery_score=float(getattr(item, "score", 0) or 0),
                importance=default_importance_for_subject(
                    str(getattr(item, "subject_label", "") or "")
                ),
            )
        )
    ranked = prioritize_skills(mastery_rows, days_until_exam=days, limit=5) if mastery_rows else ()
    plan = build_brevet_study_plan(priorities=ranked, weekly_minutes=180, today=as_of)

    fragile_labels = tuple(
        f"{getattr(item, 'subject_label', '')}: {getattr(item, 'label', '')}".strip(": ")
        for item in fragile[:5]
    )
    strong_labels = tuple(
        f"{getattr(item, 'subject_label', '')}: {getattr(item, 'label', '')}".strip(": ")
        for item in strong[:5]
    )
    priority_labels = tuple(
        f"{item.label} — {item.reason}" for item in ranked[:5]
    ) or tuple(
        f"{getattr(item, 'subject_label', '')}: {getattr(item, 'skill_label', '')} ({getattr(item, 'reason', '')})"
        for item in revision_priorities[:5]
    )

    avg_mastery = None
    if mastery:
        scores = [float(getattr(item, "score", 0) or 0) for item in mastery]
        avg_mastery = (sum(scores) / len(scores) / 100.0) if scores else None
    fragile_ratio = (len(fragile) / max(1, len(mastery))) if mastery else 0.3
    readiness = compute_brevet_readiness(
        mastery=avg_mastery if avg_mastery is not None else 0.45,
        coverage=min(1.0, len(mastery) / 20.0) if mastery else 0.2,
        stability=0.55,
        exam_performance=0.0,
        critical_gap_ratio=min(1.0, fragile_ratio),
    )
    plan_with_ready = build_brevet_study_plan(
        priorities=ranked,
        weekly_minutes=180,
        today=as_of,
        readiness_score=readiness.score,
    )

    subject = subject_label
    chapter = chapter_label
    if not subject and revision_priorities:
        subject = str(getattr(revision_priorities[0], "subject_label", "") or "")
        chapter = str(getattr(revision_priorities[0], "skill_label", "") or "")
    elif not subject and fragile:
        subject = str(getattr(fragile[0], "subject_label", "") or "")
        chapter = str(getattr(fragile[0], "label", "") or "")

    results_parts: list[str] = []
    for value in (recent_score, success_rate):
        if value is None:
            continue
        text = str(value).strip()
        if text and text != "None" and "MagicMock" not in text:
            results_parts.append(text)
    results = " / ".join(results_parts)

    return BrevetCoachContext(
        display_name=display_name,
        days_until_exam=days,
        exam_dates_summary=exam_dates,
        readiness_score=readiness.score,
        readiness_band=readiness.band,
        readiness_explanation=readiness.explanation,
        weekly_objective=plan_with_ready.objective or objective,
        mock_exam_hint=plan_with_ready.mock_exam_hint,
        priorities=priority_labels,
        fragile_skills=fragile_labels,
        strong_skills=strong_labels,
        subject_label=subject,
        chapter_label=chapter,
        exercise_statement=exercise_statement,
        notion_reminder=notion_reminder,
        hint_text=hint_text,
        student_question=student_question,
        recent_results_summary=results,
        extra_notes=tuple(
            f"{item.label} (~{item.suggested_minutes} min)" for item in plan.focuses[:3]
        ),
    )
