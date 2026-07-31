"""Professor AI invariants — Master Book non-negotiables (LCAI-0022D)."""

from __future__ import annotations

FORBIDDEN_DIRECT_SCORE_ACTIONS = frozenset(
    {
        "write_mastery_score",
        "set_mastery_level",
        "mutate_assessment_score",
        "overwrite_skill_score",
        "direct_grade_write",
    }
)


class ProfessorAIInvariantError(RuntimeError):
    """Raised when a Professor AI invariant would be violated."""


def forbid_direct_score_mutation(action: str) -> None:
    """Explicit guard: Professor AI never invents or writes scores itself."""
    token = (action or "").strip().casefold()
    raise ProfessorAIInvariantError(
        "Invariant IA violé : mutation directe de score interdite "
        f"({token or 'action inconnue'}). "
        "Les notes et la maîtrise passent uniquement par Learning Engine / Assessment."
    )


def assert_score_mutation_forbidden(action: str) -> None:
    """Raise if the action is in the forbidden direct-score catalogue."""
    token = (action or "").strip().casefold()
    if token in FORBIDDEN_DIRECT_SCORE_ACTIONS:
        forbid_direct_score_mutation(token)


def assert_no_score_fields_in_payload(payload: dict[str, object] | None) -> None:
    """Refuse payloads that attempt to smuggle score writes through the journal."""
    if not payload:
        return
    forbidden_keys = {
        "mastery_score",
        "skill_score",
        "assessment_score",
        "grade_score",
        "score_write",
        "new_mastery",
    }
    found = forbidden_keys.intersection({str(key).casefold() for key in payload})
    if found:
        forbid_direct_score_mutation(",".join(sorted(found)))
