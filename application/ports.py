"""Small repository ports needed by the first migration slice."""

from __future__ import annotations

from typing import Any, Protocol

import pandas as pd


class UserReader(Protocol):
    """Read operations required by authentication and parent navigation."""

    def authenticate(self, name: str, pin: str) -> dict[str, Any] | None: ...

    def student_list(self) -> list[dict[str, Any]]: ...


class ProgressReader(Protocol):
    """Read operations required by the current dashboard."""

    def dashboard_metrics(self, user_id: int) -> dict[str, Any]: ...

    def subject_averages(self, user_id: int) -> pd.DataFrame: ...
