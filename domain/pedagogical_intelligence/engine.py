"""Pure pedagogical intelligence policies (deterministic, explainable)."""

from __future__ import annotations

from domain.pedagogical_intelligence.models import ReadinessBand


def compute_readiness_score(
    *,
    mastery_score: float,
    coverage_score: float,
    confidence_score: float,
    critical_score: float,
    stability_score: float,
) -> float:
    """Weighted readiness score in 0..1 (Phase 2 formula)."""
    return max(
        0.0,
        min(
            1.0,
            mastery_score * 0.45
            + coverage_score * 0.20
            + confidence_score * 0.15
            + critical_score * 0.15
            + stability_score * 0.05,
        ),
    )


def classify_readiness_band(*, score: float, coverage: float, confidence: float) -> ReadinessBand:
    """Map readiness metrics to band (score may be 0-100 or 0-1)."""
    normalized = score / 100 if score > 1 else score
    if normalized >= 0.80 and coverage >= 0.50:
        return "READY"
    if normalized >= 0.60 and coverage >= 0.35:
        return "ALMOST_READY"
    return "NOT_READY"


def select_next_diagnostic_skill(
    target_skill_ids: tuple[int, ...],
    confidence_by_skill: dict[int, float],
    assessed_skill_ids: tuple[int, ...],
) -> int | None:
    """Pick the skill with the lowest diagnostic confidence not yet assessed."""
    assessed = set(assessed_skill_ids)
    remaining = [skill_id for skill_id in target_skill_ids if skill_id not in assessed]
    if not remaining:
        return None
    return min(remaining, key=lambda skill_id: confidence_by_skill.get(skill_id, 0.0))


def should_stop_diagnostic(
    *,
    questions_asked: int,
    confidence_by_skill: dict[int, float],
    target_skill_ids: tuple[int, ...],
    assessed_skill_ids: tuple[int, ...],
    min_questions: int = 5,
    max_questions: int = 20,
    confidence_threshold: float = 0.75,
) -> bool:
    if questions_asked >= max_questions:
        return True
    if questions_asked < min_questions:
        return False
    assessed = set(assessed_skill_ids)
    if not assessed:
        return False
    assessed_confidences = [confidence_by_skill.get(skill_id, 0.0) for skill_id in assessed]
    if assessed_confidences and min(assessed_confidences) >= confidence_threshold:
        return True
    return len(assessed) >= len(target_skill_ids)


def update_diagnostic_confidence(previous: float, correctness: float) -> float:
    """Blend prior diagnostic confidence with a new observed correctness signal."""
    observed = max(0.0, min(1.0, correctness))
    return max(0.0, min(1.0, previous * 0.35 + observed * 0.65))


def readiness_explanations(
    *,
    band: ReadinessBand,
    acquired_count: int,
    fragile_count: int,
    blocking_count: int,
    target_grade_label: str,
) -> tuple[str, ...]:
    lines = [
        f"Compétences solides : {acquired_count}.",
        f"Compétences fragiles : {fragile_count}.",
        f"Lacunes prioritaires : {blocking_count}.",
    ]
    if band == "READY":
        lines.append(f"L'élève présente un profil prêt pour {target_grade_label}.")
    elif band == "ALMOST_READY":
        lines.append(f"Renforcement recommandé avant {target_grade_label}.")
    else:
        lines.append(f"Un parcours de remédiation est nécessaire avant {target_grade_label}.")
    return tuple(lines)
