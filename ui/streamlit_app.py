from __future__ import annotations

import logging
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from analytics.adaptive import coaching_message, recommend_level
from analytics.mastery import compute_mastery
from core.config import (
    get_demo_parent_credentials,
    is_demo_credentials_enabled,
    is_legacy_ui_enabled,
    is_v2_parent_dashboard_enabled,
    is_v2_ui_enabled,
)
from core.engine import LEVELS, build_exam, build_progressive_set, build_question_set, is_correct
from core.registry import SUBJECTS
from infrastructure.database.legacy_gateway import (
    activity_progression,
    advanced_learning_overview,
    authenticate,
    chapter_performance,
    create_exam,
    create_parent,
    dashboard_metrics,
    exam_chapter_analysis,
    finish_exam,
    get_exam,
    learning_overview,
    list_exams,
    note_history,
    practice_chapter_stats,
    practice_difficulty_stats,
    save_exam_answers,
    save_practice_attempt,
    student_list,
    subject_averages,
    time_progression,
    weakest_chapters,
)
from services.runtime import prepare_runtime
from ui.components.layout import configure_page, render_global_styles
from ui.session import initialize_state, logout

LOGGER = logging.getLogger(__name__)

configure_page()
render_global_styles()


def login_screen() -> None:
    st.markdown(
        """
    <div class="hero">
      <h1>🎓 Learning Coach AI</h1>
      <div class="small">Parcours personnalisé, devoirs, révisions et suivi familial.</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.subheader("Connexion")
    parent_tab, student_tab = st.tabs(["Parent", "Élève"])
    with parent_tab:
        with st.form("parent_login"):
            name = st.text_input("Identifiant ou e-mail", key="parent_login_name")
            pin = st.text_input("Mot de passe", type="password", key="parent_login_password")
            login_parent = st.form_submit_button("Se connecter", type="primary")
        if login_parent:
            user = authenticate(name, pin, "parent")
            if user:
                st.session_state.user = user
                st.rerun()
            st.error("Identifiant, e-mail ou mot de passe incorrect.")
        if is_demo_credentials_enabled():
            demo_name, demo_password = get_demo_parent_credentials()
            with st.popover("ℹ️ Compte de démonstration"):
                st.write(f"Identifiant : **{demo_name}**")
                st.write(f"Mot de passe : **{demo_password}**")
        st.caption("Pas encore de compte ?")
        with st.expander("Créer un compte Parent"):
            with st.form("create_parent_account"):
                names = st.columns(2)
                first_name = names[0].text_input("Prénom")
                last_name = names[1].text_input("Nom")
                email = st.text_input("Adresse e-mail")
                username = st.text_input("Identifiant")
                password = st.text_input("Mot de passe", type="password")
                confirmation = st.text_input("Confirmer le mot de passe", type="password")
                submitted = st.form_submit_button("Créer le compte", type="primary")
            if submitted:
                ok, message = create_parent(first_name, last_name, email, username, password, confirmation)
                if ok:
                    st.success(message)
                else:
                    st.error(message)
    with student_tab:
        with st.form("student_login"):
            student_name = st.text_input("Identifiant ou e-mail", key="student_login_name")
            student_password = st.text_input(
                "Mot de passe",
                type="password",
                key="student_login_password",
            )
            login_student = st.form_submit_button("Se connecter", type="primary")
        if login_student:
            user = authenticate(student_name, student_password, "student")
            if user:
                st.session_state.user = user
                st.rerun()
            st.error("Identifiant, e-mail ou mot de passe incorrect.")
        st.caption("Le compte Élève est créé et géré depuis l’espace Parent.")


def render_revision_sheet(subject: str, chapter: str) -> None:
    module = SUBJECTS[subject]
    sheet = module.CHAPTERS[chapter]
    st.markdown(f"## 📘 {subject} — {chapter}")
    st.info(sheet["summary"])
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Méthode")
        st.write(sheet["method"])
        st.subheader("Exemple")
        st.write(sheet["example"])
    with c2:
        st.subheader("À retenir")
        for item in sheet["key_points"]:
            st.write(f"• {item}")
        st.subheader("Piège fréquent")
        st.warning(sheet["pitfalls"])


def dashboard_view(user_id: int, title: str) -> None:
    st.title(title)
    metrics = dashboard_metrics(user_id)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Devoirs terminés", metrics["completed_exams"])
    c2.metric("Moyenne générale", f"{metrics['avg_score']:.2f}/20")
    c3.metric("Meilleure note", f"{metrics['best_score']:.2f}/20")
    c4.metric("Exercices libres", metrics["practice_total"])
    c5.metric("Réussite exercices", f"{metrics['practice_success']:.1f}%")

    averages = subject_averages(user_id)
    history = note_history(user_id)
    chapters = chapter_performance(user_id)

    st.subheader("Moyenne par matière")
    if averages.empty:
        st.info("Aucun devoir terminé pour le moment.")
    else:
        st.dataframe(averages, use_container_width=True, hide_index=True)
        fig = px.bar(
            averages, x="subject", y="moyenne", range_y=[0, 20], labels={"subject": "Matière", "moyenne": "Moyenne /20"}
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Évolution des notes")
    if history.empty:
        st.info("L'évolution apparaîtra après les premiers devoirs.")
    else:
        fig = px.line(
            history,
            x="started_at",
            y="score",
            color="subject",
            markers=True,
            range_y=[0, 20],
            labels={"started_at": "Date", "score": "Note /20", "subject": "Matière"},
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(history, use_container_width=True, hide_index=True)

    st.subheader("Maîtrise des chapitres")
    if chapters.empty:
        st.info("Aucune donnée de chapitre.")
    else:
        st.dataframe(chapters, use_container_width=True, hide_index=True)


def mastery_label(value: float) -> str:
    if value >= 80:
        return "Bien maîtrisé"
    if value >= 65:
        return "Satisfaisant"
    if value >= 50:
        return "Moyen — à consolider"
    return "Prioritaire — à revoir"


def analysis_view(user_id: int, student_name: str) -> None:
    st.title(f"🔎 Analyse et progression de {student_name}")
    overview = learning_overview(user_id)
    progression = activity_progression(user_id)
    completed = list_exams(user_id, "completed")
    advanced = advanced_learning_overview(user_id)
    timing = time_progression(user_id)

    tab_global, tab_chapters, tab_exams = st.tabs(["Bilan global", "Matières et chapitres", "Analyse par devoir"])

    with tab_global:
        if overview.empty:
            st.info("L’analyse apparaîtra après les premiers devoirs ou entraînements corrigés.")
        else:
            total_questions = int(overview["questions"].sum())
            global_rate = float((overview["reussite"] * overview["questions"]).sum() / total_questions)
            mastered = int((overview["reussite"] >= 80).sum())
            priority = int((overview["reussite"] < 50).sum())
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Questions analysées", total_questions)
            c2.metric("Réussite globale", f"{global_rate:.1f}%")
            c3.metric("Chapitres bien maîtrisés", mastered)
            c4.metric("Chapitres prioritaires", priority)

            ranked = overview.sort_values(["reussite", "questions"], ascending=[False, False])
            strengths = ranked[ranked["reussite"] >= 80].head(5)
            medium = ranked[(ranked["reussite"] >= 50) & (ranked["reussite"] < 80)].sort_values("reussite").head(5)
            weak = (
                ranked[ranked["reussite"] < 50].sort_values(["reussite", "questions"], ascending=[True, False]).head(5)
            )

            st.subheader("Synthèse pédagogique")
            if global_rate >= 80:
                st.success(
                    "Très bon niveau global. Il faut maintenir les acquis et privilégier les exercices de niveau Brevet ou expert."
                )
            elif global_rate >= 65:
                st.info(
                    "Niveau global satisfaisant. Quelques chapitres doivent encore être consolidés pour obtenir des résultats réguliers."
                )
            elif global_rate >= 50:
                st.warning(
                    "Niveau global moyen. Un travail régulier et ciblé sur les chapitres fragiles est recommandé."
                )
            else:
                st.error(
                    "Plusieurs bases restent fragiles. Il est conseillé de reprendre les fiches de cours puis de faire des séries ciblées de niveau moyen."
                )

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("#### ✅ Bien maîtrisé")
                if strengths.empty:
                    st.caption("Aucun chapitre n’atteint encore 80 %.")
                for r in strengths.to_dict("records"):
                    st.write(f"**{r['subject']} — {r['chapter']}** : {r['reussite']:.0f}%")
            with c2:
                st.markdown("#### 🟠 À consolider")
                if medium.empty:
                    st.caption("Aucun chapitre dans cette catégorie.")
                for r in medium.to_dict("records"):
                    st.write(f"**{r['subject']} — {r['chapter']}** : {r['reussite']:.0f}%")
            with c3:
                st.markdown("#### 🔴 À revoir en priorité")
                if weak.empty:
                    st.caption("Aucun chapitre sous 50 %.")
                for r in weak.to_dict("records"):
                    st.write(f"**{r['subject']} — {r['chapter']}** : {r['reussite']:.0f}%")

            st.subheader("Progression dans le temps")
            if progression.empty:
                st.info("Pas encore assez d’activités pour tracer la progression.")
            else:
                fig = px.line(
                    progression,
                    x="activity_date",
                    y="percentage",
                    color="activity_type",
                    symbol="subject",
                    markers=True,
                    range_y=[0, 100],
                    labels={
                        "activity_date": "Date",
                        "percentage": "Réussite (%)",
                        "activity_type": "Activité",
                        "subject": "Matière",
                    },
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab_chapters:
        if overview.empty:
            st.info("Aucune donnée disponible.")
        else:
            subjects = ["Toutes les matières"] + sorted(overview["subject"].unique().tolist())
            selected_subject = st.selectbox("Filtrer par matière", subjects, key=f"analysis_subject_{user_id}")
            data = (
                overview
                if selected_subject == "Toutes les matières"
                else overview[overview["subject"] == selected_subject]
            )
            data = data.copy()
            data["niveau"] = data["reussite"].apply(mastery_label)
            st.dataframe(
                data[
                    [
                        "subject",
                        "chapter",
                        "questions",
                        "questions_devoirs",
                        "questions_entrainements",
                        "reussite",
                        "niveau",
                        "derniere_activite",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
            fig = px.bar(
                data.sort_values("reussite"),
                x="reussite",
                y="chapter",
                color="subject",
                orientation="h",
                range_x=[0, 100],
                labels={"reussite": "Réussite (%)", "chapter": "Chapitre", "subject": "Matière"},
            )
            st.plotly_chart(fig, use_container_width=True)

            difficulty = practice_difficulty_stats(user_id)
            if not difficulty.empty:
                st.subheader("Résultats des entraînements par difficulté")
                st.dataframe(difficulty, use_container_width=True, hide_index=True)

    if not advanced.empty:
        st.subheader("⏱️ Maîtrise, temps et difficulté")
        rows = []
        for r in advanced.to_dict("records"):
            m = compute_mastery(
                float(r.get("accuracy") or 0),
                float(r.get("avg_seconds") or r.get("target_seconds") or 90),
                float(r.get("target_seconds") or 90),
                str(r.get("difficulty") or "Moyen"),
                int(r.get("attempts") or 0),
            )
            recommended = recommend_level(
                str(r.get("difficulty") or "Moyen"), m.accuracy, m.speed_index, int(r.get("attempts") or 0)
            )
            rows.append({**r, "maitrise": m.score, "niveau_conseille": recommended, "recommandation": m.recommendation})
        adv_df = pd.DataFrame(rows)
        st.dataframe(
            adv_df[
                [
                    "subject",
                    "chapter",
                    "difficulty",
                    "attempts",
                    "accuracy",
                    "avg_seconds",
                    "target_seconds",
                    "speed_index",
                    "maitrise",
                    "niveau_conseille",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
        weakest = adv_df.sort_values(["maitrise", "accuracy"]).head(5)
        for r in weakest.to_dict("records"):
            st.info(
                f"**{r['subject']} — {r['chapter']}** : {coaching_message(float(r['accuracy']), float(r['speed_index'] or 1), str(r['difficulty']), str(r['niveau_conseille']))}"
            )
    if not timing.empty:
        st.subheader("📈 Évolution de la vitesse")
        fig = px.line(
            timing,
            x="activity_date",
            y="seconds_per_question",
            color="subject",
            markers=True,
            labels={"activity_date": "Date", "seconds_per_question": "Secondes par question", "subject": "Matière"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab_exams:
        if completed.empty:
            st.info("Aucun devoir terminé à analyser.")
        else:
            records = completed.to_dict("records")
            options = [int(r["id"]) for r in records]
            labels = {int(r["id"]): f"{r['started_at']} — {r['title']} — {float(r['score']):.2f}/20" for r in records}
            preset = st.session_state.pop("selected_analysis_exam", None)
            default_index = options.index(int(preset)) if preset and int(preset) in options else 0
            exam_id = st.selectbox(
                "Choisir un devoir",
                options,
                index=default_index,
                format_func=lambda eid: labels[eid],
                key=f"analysis_exam_{user_id}",
            )
            exam, questions = get_exam(int(exam_id))
            if exam is None:
                st.error("Ce devoir n'est plus disponible.")
                return
            chapters = exam_chapter_analysis(int(exam_id))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Note", f"{float(exam['score']):.2f}/20")
            c2.metric("Réussite", f"{float(exam['percentage']):.1f}%")
            c3.metric("Bonnes réponses", f"{int(exam['correct_count'])}/{int(exam['question_count'])}")
            c4.metric("Appréciation", mastery_label(float(exam["percentage"])))

            st.subheader("Analyse par chapitre du devoir")
            display_chapters = chapters.copy()
            display_chapters["niveau"] = display_chapters["reussite"].apply(mastery_label)
            st.dataframe(display_chapters, use_container_width=True, hide_index=True)

            weak_exam = chapters[chapters["reussite"] < 65]
            strong_exam = chapters[chapters["reussite"] >= 80]
            if not strong_exam.empty:
                st.success("Points forts de ce devoir : " + ", ".join(strong_exam["chapter"].astype(str).tolist()))
            if not weak_exam.empty:
                st.warning("À retravailler après ce devoir : " + ", ".join(weak_exam["chapter"].astype(str).tolist()))
            elif float(exam["percentage"]) >= 80:
                st.success("Le devoir est bien maîtrisé. Passer à un niveau plus difficile est pertinent.")

            st.subheader("Détail des réponses")
            for q in questions:
                icon = "✅" if q["is_correct"] else "❌"
                with st.expander(f"{icon} Question {q['position']} — {q['chapter']}"):
                    st.write(q["question"])
                    st.caption(f"Réponse donnée : {q.get('student_answer') or '—'}")
                    st.caption(f"Réponse attendue : {q['expected_answer']} {q.get('unit') or ''}")
                    if not q["is_correct"]:
                        st.write("**Méthode / explication :**")
                        st.write(q["explanation"])


def practice_view(user: dict) -> None:
    st.title("✏️ Centre d’entraînement adaptatif V7.0")
    subject = st.selectbox("Matière", list(SUBJECTS.keys()), key="practice_subject")
    module = SUBJECTS[subject]
    all_chapters = list(module.CHAPTERS.keys())

    mode = st.radio(
        "Type d’entraînement",
        ["Rapide", "Intensif par chapitre", "Programme complet", "Progressif", "Adaptatif aux erreurs"],
        horizontal=True,
    )

    if mode == "Intensif par chapitre":
        selected_chapters = st.multiselect("Chapitres", all_chapters, default=all_chapters[:1])
    elif mode == "Adaptatif aux erreurs":
        selected_chapters = weakest_chapters(user["id"], subject, all_chapters, limit=5)
        st.info("Chapitres automatiquement prioritaires : " + ", ".join(selected_chapters))
    elif mode == "Rapide":
        selected_chapters = st.multiselect("Chapitres", all_chapters, default=all_chapters[: min(3, len(all_chapters))])
    else:
        selected_chapters = all_chapters
        st.caption(f"Les {len(all_chapters)} chapitres de {subject} seront utilisés.")

    if mode == "Progressif":
        difficulty = "Progressif : facile → expert"
    else:
        difficulty = st.select_slider("Niveau", options=LEVELS, value="Moyen")

    sizes_by_mode = {
        "Rapide": [5, 10, 20],
        "Intensif par chapitre": [20, 30, 50, 75, 100],
        "Programme complet": [20, 30, 50, 75, 100],
        "Progressif": [25, 50, 75, 100],
        "Adaptatif aux erreurs": [10, 20, 30, 50],
    }
    series_size = st.selectbox("Nombre total d’exercices", sizes_by_mode[mode], index=0)
    per_page = st.selectbox("Questions affichées par page", [5, 10, 20], index=1)

    if selected_chapters:
        with st.expander("Consulter une fiche avant de commencer"):
            sheet_chapter = st.selectbox("Fiche", selected_chapters, key="practice_sheet")
            render_revision_sheet(subject, sheet_chapter)

    signature = f"{subject}|{mode}|{difficulty}|{series_size}|{'/'.join(selected_chapters)}"
    if st.session_state.get("training_signature") != signature:
        st.session_state.training_signature = signature
        st.session_state.training_questions = []
        st.session_state.training_page = 0
        st.session_state.training_results = None

    c1, c2 = st.columns([1, 2])
    if c1.button("Générer la série", type="primary", use_container_width=True):
        if not selected_chapters:
            st.error("Sélectionne au moins un chapitre.")
            return
        if mode == "Progressif":
            questions = build_progressive_set(module, series_size, selected_chapters)
        else:
            questions = build_question_set(module, series_size, selected_chapters, difficulty)
        st.session_state.training_questions = questions
        st.session_state.training_started_at = time.time()
        st.session_state.training_page = 0
        st.session_state.training_results = None
        # purge old answer widgets
        for key in list(st.session_state.keys()):
            if key.startswith("v6_answer_"):
                del st.session_state[key]
        st.rerun()
    c2.caption("Les séries sont paginées : une série de 100 exercices reste confortable à utiliser.")

    questions = st.session_state.get("training_questions", [])
    if not questions:
        st.info("Choisis le parcours puis génère une série. Les entraînements vont de 5 à 100 exercices.")
        stats = practice_chapter_stats(user["id"], subject)
        if not stats.empty:
            st.subheader("Résultats précédents par chapitre")
            st.dataframe(stats, use_container_width=True, hide_index=True)
        return

    total_pages = (len(questions) + per_page - 1) // per_page
    page = min(st.session_state.get("training_page", 0), total_pages - 1)
    st.progress(
        (page + 1) / total_pages,
        text=f"Page {page + 1}/{total_pages} · exercices {page * per_page + 1} à {min(len(questions), (page + 1) * per_page)} sur {len(questions)}",
    )
    begin = page * per_page
    finish = min(len(questions), begin + per_page)
    for idx in range(begin, finish):
        q = questions[idx]
        st.markdown(f"### Exercice {idx + 1} · {q['chapter']} · {q.get('difficulty', 'Moyen')}")
        st.write(q["question"])
        st.text_input("Ta réponse", key=f"v6_answer_{idx}")
        st.divider()

    nav1, nav2, nav3 = st.columns([1, 1, 2])
    if nav1.button("⬅ Page précédente", disabled=page == 0, use_container_width=True):
        st.session_state.training_page = page - 1
        st.rerun()
    if nav2.button("Page suivante ➡", disabled=page >= total_pages - 1, use_container_width=True):
        st.session_state.training_page = page + 1
        st.rerun()
    if nav3.button("Corriger toute la série", type="primary", use_container_width=True):
        results = []
        for idx, q in enumerate(questions):
            answer = st.session_state.get(f"v6_answer_{idx}", "")
            correct = is_correct(q, answer)
            elapsed_total = max(1.0, time.time() - float(st.session_state.get("training_started_at") or time.time()))
            elapsed_each = elapsed_total / max(1, len(questions))
            save_practice_attempt(
                user["id"],
                subject,
                q["chapter"],
                q["question"],
                str(q["expected_answer"]),
                answer,
                correct,
                q.get("difficulty", difficulty),
                elapsed_each,
                int(q.get("target_seconds", 90)),
            )
            results.append((q, answer, correct))
        st.session_state.training_results = results

    results = st.session_state.get("training_results")
    if results is not None:
        good = sum(1 for _, _, ok in results if ok)
        pct = 100 * good / len(results)
        st.subheader("Bilan de la série")
        m1, m2, m3 = st.columns(3)
        m1.metric("Réponses correctes", f"{good}/{len(results)}")
        m2.metric("Réussite", f"{pct:.1f}%")
        m3.metric("Niveau validé", "Oui" if pct >= 80 else "À retravailler")
        if pct >= 80:
            st.success("Objectif de 80 % atteint. Tu peux passer au niveau suivant.")
        else:
            st.warning("Reprends les erreurs puis relance un entraînement adaptatif.")
        wrong = [x for x in results if not x[2]]
        st.markdown(f"### Correction des {len(wrong)} erreur(s)")
        for idx, (q, answer, correct) in enumerate(results, 1):
            if correct:
                continue
            with st.expander(f"❌ Exercice {idx} — {q['chapter']}"):
                st.write(q["question"])
                st.caption(f"Réponse donnée : {answer or '—'}")
                st.caption(f"Réponse attendue : {q['expected_answer']} {q.get('unit', '')}")
                st.write(q["explanation"])


def create_exam_view(user: dict) -> None:
    st.title("📝 Nouveau devoir")
    subject = st.selectbox("Matière", list(SUBJECTS.keys()), key="exam_subject")
    module = SUBJECTS[subject]

    exam_scope = st.radio(
        "Type de devoir",
        [
            "Examen complet — ensemble des chapitres",
            "Devoir ciblé — chapitres particuliers",
        ],
    )
    all_chapters = list(module.CHAPTERS.keys())
    if exam_scope.startswith("Examen complet"):
        selected_chapters = all_chapters
        st.info(f"Le devoir couvrira les {len(all_chapters)} chapitres de {subject}.")
    else:
        selected_chapters = st.multiselect("Chapitres à évaluer", all_chapters, default=all_chapters[:1])

    difficulty = st.select_slider("Difficulté", options=["Moyen", "Difficile"], value="Moyen")
    mode_label = st.radio("Organisation", ["Chronométré", "Sans limite de temps"])
    timed = mode_label == "Chronométré"
    duration = st.selectbox("Durée", [15, 30, 45, 60, 90, 120], index=2) if timed else None
    question_count = st.selectbox("Nombre de questions", [5, 10, 15, 20, 30, 40], index=2)

    if exam_scope.startswith("Examen complet") and question_count < len(all_chapters):
        st.warning("Pour couvrir tous les chapitres, choisis idéalement au moins autant de questions que de chapitres.")

    if st.button("Commencer le devoir", type="primary"):
        if not selected_chapters:
            st.error("Sélectionne au moins un chapitre.")
            return
        questions = build_exam(module, question_count, chapters=selected_chapters, difficulty=difficulty)
        scope_name = "examen complet" if exam_scope.startswith("Examen complet") else "devoir ciblé"
        timing = f"{duration} min" if timed else "sans limite"
        title = f"{subject} — {scope_name} — {difficulty.lower()} — {timing}"
        exam_id = create_exam(
            user_id=user["id"],
            subject=subject,
            title=title,
            mode="timed" if timed else "free",
            duration_minutes=duration,
            questions=questions,
            difficulty=difficulty,
        )
        st.session_state.active_exam_id = exam_id
        st.rerun()


def submit_exam(exam_id: int, questions: list[dict], answers: dict[int, str]) -> None:
    opened = st.session_state.get("exam_opened_at", {}).get(str(exam_id), time.time())
    elapsed_total = max(1.0, time.time() - opened)
    payload = {}
    for question in questions:
        answer = answers.get(int(question["id"]), "")
        payload[int(question["id"])] = (answer, is_correct(question, answer), elapsed_total / max(1, len(questions)))
    save_exam_answers(exam_id, payload)
    score, percentage, good, total = finish_exam(exam_id, elapsed_total)
    st.session_state.active_exam_id = None
    st.success(f"Devoir terminé : {score:.2f}/20 — {good}/{total} réponses correctes.")
    _, corrected = get_exam(exam_id)
    for question in corrected:
        icon = "✅" if question["is_correct"] else "❌"
        st.markdown(f"{icon} **{question['position']}. {question['question']}**")
        st.caption(
            f"Réponse donnée : {question['student_answer'] or '—'} | "
            f"Réponse attendue : {question['expected_answer']} {question['unit'] or ''}"
        )
        st.write(question["explanation"])
    st.stop()


def exam_view(user: dict, exam_id: int) -> None:
    exam, questions = get_exam(exam_id)
    if not exam or int(exam["user_id"]) != int(user["id"]):
        st.error("Devoir introuvable.")
        st.session_state.active_exam_id = None
        return

    st.title(exam["title"])
    st.session_state.exam_opened_at.setdefault(str(exam_id), time.time())
    remaining = None
    if exam["mode"] == "timed":
        started = pd.Timestamp(exam["started_at"]).to_pydatetime()
        elapsed = (datetime.now() - started).total_seconds()
        remaining = max(0, int(exam["duration_minutes"] * 60 - elapsed))
        st.metric("Temps restant", f"{remaining // 60:02d}:{remaining % 60:02d}")
        if remaining <= 0:
            existing = {int(q["id"]): q.get("student_answer") or "" for q in questions}
            submit_exam(exam_id, questions, existing)

    answers = {}
    for question in questions:
        st.markdown(f"### Question {question['position']}")
        st.write(question["question"])
        answers[int(question["id"])] = st.text_input(
            "Réponse",
            value=question.get("student_answer") or "",
            key=f"exam_q_{question['id']}",
        )
        st.divider()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Enregistrer et reprendre plus tard", use_container_width=True):
            payload = {
                int(q["id"]): (
                    answers[int(q["id"])],
                    is_correct(q, answers[int(q["id"])]),
                    max(1.0, time.time() - st.session_state.exam_opened_at.get(str(exam_id), time.time()))
                    / max(1, len(questions)),
                )
                for q in questions
            }
            save_exam_answers(exam_id, payload)
            st.session_state.active_exam_id = None
            st.session_state.next_student_page = "Mes devoirs et notes"
            st.session_state.exam_saved_message = (
                "Le devoir a été enregistré. Tu pourras le reprendre depuis la section « Mes devoirs et notes »."
            )
            st.rerun()
    with c2:
        if st.button("Terminer et obtenir la note", type="primary", use_container_width=True):
            submit_exam(exam_id, questions, answers)


def exam_history_view(user: dict) -> None:
    st.title("📚 Mes devoirs et mes notes")
    saved_message = st.session_state.pop("exam_saved_message", None)
    if saved_message:
        st.success(saved_message)
    exams = list_exams(user["id"])
    if exams.empty:
        st.info("Aucun devoir.")
        return
    display = exams[["started_at", "subject", "title", "status", "score", "percentage"]].copy()
    st.dataframe(display, use_container_width=True, hide_index=True)
    started = exams[exams["status"] == "started"]
    if not started.empty:
        st.subheader("Devoirs à reprendre")
        for row in started.to_dict("records"):
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{row['title']}** — commencé le {row['started_at']}")
            if c2.button("Reprendre", key=f"resume_{row['id']}"):
                st.session_state.active_exam_id = int(row["id"])
                st.rerun()
    completed = exams[exams["status"] == "completed"]
    if not completed.empty:
        st.subheader("Devoirs terminés — analyses détaillées")
        for row in completed.to_dict("records"):
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{row['title']}** — {float(row['score']):.2f}/20 — {float(row['percentage']):.1f}%")
            if c2.button("Analyser", key=f"analyse_{row['id']}", use_container_width=True):
                st.session_state.selected_analysis_exam = int(row["id"])
                st.session_state.next_student_page = "Analyse et progression"
                st.rerun()


def revision_library_view() -> None:
    st.title("📘 Bibliothèque de fiches de révision")
    subject = st.selectbox("Matière", list(SUBJECTS.keys()), key="sheet_subject")
    chapter = st.selectbox("Chapitre", list(SUBJECTS[subject].CHAPTERS.keys()), key="sheet_chapter")
    render_revision_sheet(subject, chapter)
    st.subheader("Tous les chapitres de la matière")
    for chapter_name, data in SUBJECTS[subject].CHAPTERS.items():
        with st.expander(chapter_name):
            st.write(data["summary"])


def student_app(user: dict) -> None:
    navigation_options = [
        "Tableau de bord",
        "Fiches de révision",
        "Entraînement libre",
        "Nouveau devoir",
        "Mes devoirs et notes",
        "Analyse et progression",
    ]

    next_page = st.session_state.pop("next_student_page", None)
    if next_page in navigation_options:
        st.session_state.student_navigation = next_page

    with st.sidebar:
        st.success(f"Élève : {user['name']}")
        page = st.radio(
            "Navigation",
            navigation_options,
            key="student_navigation",
        )
        st.button("Déconnexion", on_click=logout)

    if st.session_state.active_exam_id:
        exam_view(user, int(st.session_state.active_exam_id))
    elif page == "Tableau de bord":
        dashboard_view(user["id"], f"📊 Tableau de bord de {user['name']}")
    elif page == "Fiches de révision":
        revision_library_view()
    elif page == "Entraînement libre":
        practice_view(user)
    elif page == "Nouveau devoir":
        create_exam_view(user)
    elif page == "Mes devoirs et notes":
        exam_history_view(user)
    else:
        analysis_view(user["id"], user["name"])


def parent_app() -> None:
    with st.sidebar:
        st.success("Espace parent")
        parent_page = st.radio("Navigation", ["Tableau de bord", "Analyse et progression"], key="parent_navigation")
        st.button("Déconnexion", on_click=logout)

    students = student_list()
    if not students:
        st.info("Aucun compte enfant.")
        return
    ids = [s["id"] for s in students]
    names = {s["id"]: s["name"] for s in students}
    selected = st.selectbox("Élève", ids, format_func=lambda sid: names[sid])
    if parent_page == "Tableau de bord":
        dashboard_view(selected, f"👨‍👩‍👦 Suivi de {names[selected]}")
    else:
        analysis_view(selected, names[selected])


def run_app() -> None:
    """Start the unified product; legacy access requires explicit opt-in."""
    try:
        prepare_runtime()
    except Exception:
        LOGGER.exception("Application runtime initialization failed")
        st.error("Nous ne pouvons pas initialiser l'application pour le moment. Veuillez réessayer.")
        return
    initialize_state()

    if not is_legacy_ui_enabled():
        from ui.unified_app import run_unified_app

        run_unified_app(login_screen)
        return

    if not st.session_state.user:
        login_screen()
    elif is_v2_ui_enabled():
        from ui.v2_experience import run_parent_experience, run_student_experience

        if st.session_state.user["role"] == "parent":
            if is_v2_parent_dashboard_enabled():
                run_parent_experience(st.session_state.user)
            else:
                st.warning("Le tableau de bord parent V2 n'est pas activé.")
        else:
            run_student_experience(st.session_state.user)
    elif st.session_state.user["role"] == "parent":
        parent_app()
    else:
        student_app(st.session_state.user)
