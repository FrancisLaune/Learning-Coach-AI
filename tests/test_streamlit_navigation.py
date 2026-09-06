from __future__ import annotations

from ui.navigation import NAVIGATION_REQUEST_KEY, apply_navigation_request, request_navigation


def test_parent_navigation_is_deferred_until_next_render() -> None:
    state: dict[str, object] = {"parent_page": "Mes enfants"}

    request_navigation(state, "parent", "Tableau de bord", 42)

    assert state["parent_page"] == "Mes enfants"
    assert state[NAVIGATION_REQUEST_KEY] == {
        "scope": "parent",
        "page": "Vue générale",
        "learner_id": 42,
    }
    apply_navigation_request(
        state,
        "parent",
        "parent_page",
        ("Mes enfants", "Vue générale"),
    )
    assert state["parent_page"] == "Vue générale"
    assert state["parent_selected_learner"] == 42
    assert NAVIGATION_REQUEST_KEY not in state


def test_repeated_navigation_requests_do_not_leak_or_cross_roles() -> None:
    state: dict[str, object] = {"unified_student_page": "Accueil"}
    pages = ("Accueil", "S'entraîner")

    request_navigation(state, "student", "Ma séance IA")
    apply_navigation_request(state, "parent", "parent_page", ("Mes enfants",))
    assert state["unified_student_page"] == "Accueil"
    apply_navigation_request(state, "student", "unified_student_page", pages)
    assert state["unified_student_page"] == "S'entraîner"

    request_navigation(state, "student", "Accueil")
    apply_navigation_request(state, "student", "unified_student_page", pages)
    assert state["unified_student_page"] == "Accueil"
