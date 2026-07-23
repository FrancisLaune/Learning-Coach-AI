"""Explicitly enabled, isolated Streamlit entry point for V2 onboarding."""

from datetime import date, time

import streamlit as st

from core.config import is_v2_ui_enabled
from domain.decision.enums import ObjectiveKind
from domain.learning.models import AcademicYear, GradeLevel
from domain.onboarding.enums import CreatorRole, DifficultyPreference
from domain.onboarding.models import (
    AvailabilitySlot,
    LearnerGoalConfiguration,
    LearnerProfile,
    OnboardingRequest,
    StudyPreferences,
)
from infrastructure.repositories.onboarding import DuckDBOnboardingRepository
from infrastructure.repositories.recommendation import DuckDBRecommendationRepository
from services.onboarding import OnboardingService, OnboardingValidationError
from services.recommendation import PersonalizedSessionService

if not is_v2_ui_enabled():
    st.error("Interface V2 désactivée. Définir LCAI_ENABLE_V2_UI=true pour l'activer explicitement.")
    st.stop()

st.title("Initialiser mon parcours d’apprentissage")
display_name = st.text_input("Prénom ou nom d’affichage")
grade_label = st.selectbox("Niveau actuel", ["4e", "3e", "Seconde", "Première", "Terminale"])
objective_label = st.selectbox(
    "Que souhaites-tu faire ?",
    [
        "Réviser mon programme",
        "Consolider mes bases",
        "Rattraper mes difficultés",
        "Préparer le niveau suivant",
        "Préparer le brevet",
        "Préparer le baccalauréat",
    ],
)
duration = st.slider("Temps disponible par jour", 10, 90, 30, 5)
days = st.multiselect("Jours disponibles", [("Lundi", 0), ("Mercredi", 2), ("Vendredi", 4)], format_func=lambda x: x[0])
confirm = st.checkbox("Je confirme le remplacement du parcours actif s’il existe")

grades = {
    "4e": GradeLevel("FR-4E", 4, "Quatrième"),
    "3e": GradeLevel("FR-3E", 3, "Troisième"),
    "Seconde": GradeLevel("FR-2NDE", 6, "Seconde"),
    "Première": GradeLevel("FR-1ERE", 7, "Première"),
    "Terminale": GradeLevel("FR-TERM", 8, "Terminale"),
}
objectives = {
    "Réviser mon programme": ObjectiveKind.REVISION,
    "Consolider mes bases": ObjectiveKind.CONSOLIDATION,
    "Rattraper mes difficultés": ObjectiveKind.CATCH_UP,
    "Préparer le niveau suivant": ObjectiveKind.PREPARATION_NEXT_GRADE,
    "Préparer le brevet": ObjectiveKind.PREPARATION_BREVET,
    "Préparer le baccalauréat": ObjectiveKind.PREPARATION_BAC,
}
targets = {"4e": grades["3e"], "3e": grades["Seconde"], "Seconde": grades["Première"], "Première": grades["Terminale"]}

if st.button("Créer le parcours et proposer une séance", disabled=not (display_name and confirm)):
    objective = objectives[objective_label]
    target = targets.get(grade_label) if objective is ObjectiveKind.PREPARATION_NEXT_GRADE else None
    exam = (
        "BREVET"
        if objective is ObjectiveKind.PREPARATION_BREVET
        else "BACCALAUREAT"
        if objective is ObjectiveKind.PREPARATION_BAC
        else None
    )
    request = OnboardingRequest(
        f"ui:{display_name}:{grade_label}:{objective.value}",
        LearnerProfile(f"ui:{display_name}", display_name, CreatorRole.STUDENT),
        AcademicYear(date.today().year, date.today().year + 1),
        grades[grade_label],
        LearnerGoalConfiguration(objective, target, exam, None),
        (),
        StudyPreferences(
            duration,
            tuple(AvailabilitySlot(day[1], duration, time(17)) for day in days),
            difficulty=DifficultyPreference.STANDARD,
        ),
        CreatorRole.STUDENT,
    )
    try:
        result = OnboardingService(DuckDBOnboardingRepository()).complete(request)
        recommendation_repository = DuckDBRecommendationRepository()
        contents = recommendation_repository.load_approved_contents()
        proposal = PersonalizedSessionService(session_repository=recommendation_repository).generate(
            result, contents, result.created_at
        )
        st.success("Parcours enregistré.")
        st.write(result.summary)
        if proposal.absence_code:
            st.warning(f"Aucun contenu inventé : {proposal.absence_code}")
    except OnboardingValidationError as exc:
        st.error(str(exc))
