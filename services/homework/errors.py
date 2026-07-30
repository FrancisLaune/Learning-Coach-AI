"""Homework AI completion errors (LCAI-0018B7)."""

from __future__ import annotations


class HomeworkCompletionError(Exception):
    """Raised when homework cannot reach the exact requested exercise count."""

    def __init__(
        self,
        *,
        requested: int,
        actual: int = 0,
        reason: str = "INCOMPLETE",
    ) -> None:
        self.requested = requested
        self.actual = actual
        self.reason = reason
        super().__init__(self.user_message)

    @property
    def user_message(self) -> str:
        if self.reason == "AI_UNAVAILABLE":
            return "La génération IA est temporairement indisponible. Le devoir n'a pas été créé."
        if self.reason == "GENERATION_CAP_EXCEEDED":
            return (
                "Le nombre d'exercices demandé dépasse la limite de génération IA configurée. "
                "Le devoir n'a pas été créé."
            )
        if self.reason == "VALIDATION_EXHAUSTED":
            return (
                "La génération IA n'a pas pu produire tous les exercices validés demandés. "
                "Le devoir n'a pas été créé."
            )
        return (
            f"Impossible de créer le devoir de {self.requested} question(s) "
            f"({self.actual} obtenue(s)). Le devoir n'a pas été créé."
        )
