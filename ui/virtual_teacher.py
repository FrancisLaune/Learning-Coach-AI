"""Streamlit UI for the Virtual Teacher feature."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from domain.virtual_teacher.models import ConversationRequest, PedagogicalContext, PreferencesPatch
from infrastructure.repositories.virtual_teacher import DuckDBVirtualTeacherRepository
from services.professor_ai.banner import BannerPresenceState
from services.virtual_teacher.ai_conversation_orchestrator import AIConversationOrchestrator
from services.virtual_teacher.ai_teacher_preferences_service import AITeacherPreferencesService
from services.virtual_teacher.ai_teacher_service import AITeacherService
from services.virtual_teacher.authorization import VirtualTeacherAccessError
from services.virtual_teacher.llm_service import build_llm_service
from services.virtual_teacher.openai_tts import build_tts_service
from services.virtual_teacher.pedagogical_guardrails import PedagogicalGuardrails
from services.virtual_teacher.stt_service import build_stt_service
from services.virtual_teacher.voice_pipeline import PRESENCE_STATE_KEY, SchoolVoicePipeline


def build_virtual_teacher_stack(
    repository_factory: Callable[[], DuckDBVirtualTeacherRepository],
) -> tuple[AITeacherService, AITeacherPreferencesService, SchoolVoicePipeline]:
    repository = repository_factory()
    preferences = AITeacherPreferencesService(repository)
    orchestrator = AIConversationOrchestrator(
        llm=build_llm_service(),
        guardrails=PedagogicalGuardrails(),
    )
    teacher = AITeacherService(
        repository=repository,
        preferences_service=preferences,
        orchestrator=orchestrator,
        tts=build_tts_service(),
    )
    pipeline = SchoolVoicePipeline(teacher=teacher, stt=build_stt_service())
    return teacher, preferences, pipeline


def render_student_virtual_teacher(
    *,
    user: dict,
    learner_id: int,
    teacher_service: AITeacherService,
    preferences_service: AITeacherPreferencesService,
    learner_display_name: str,
    grade_label: str | None,
    voice_pipeline: SchoolVoicePipeline | None = None,
) -> None:
    st.title("Mon professeur virtuel")
    try:
        preferences = preferences_service.get_preferences_for_student(
            user=user,
            student_learner_id=learner_id,
            learner_id=learner_id,
        )
    except VirtualTeacherAccessError:
        st.error("Ton profil d'apprentissage n'est pas encore prêt pour le professeur virtuel.")
        return
    if not preferences.feature_enabled:
        st.info("Le professeur virtuel n'est pas encore activé. Demande à ton parent de l'activer.")
        return

    left, right = st.columns([1, 2])
    with left:
        st.subheader(preferences.teacher_name or "Professeur")
        avatar = "👩‍🏫" if preferences.teacher_profile.endswith("FEMALE_01") else "👨‍🏫"
        st.markdown(f"<div style='font-size:4rem;text-align:center'>{avatar}</div>", unsafe_allow_html=True)
        st.caption(f"Voix : {preferences.voice_id.replace('_', ' ')}")
        st.caption(f"Ton : {preferences.tone}")
        if not preferences.parent_locked:
            with st.form("student_teacher_preferences"):
                teacher_name = st.selectbox("Prénom affiché", ["Emma", "Léa", "Lucas", "Hugo"])
                voice_id = st.selectbox("Voix", ["warm_female", "warm_male"])
                tone = st.selectbox("Ton", ["calm", "encouraging", "academic"])
                if st.form_submit_button("Enregistrer"):
                    patch = PreferencesPatch(
                        teacher_name=teacher_name,
                        voice_id=voice_id,
                        tone=tone,
                        fields={"teacher_name", "voice_id", "tone"},
                    )
                    try:
                        preferences_service.save_for_student(
                            user=user,
                            student_learner_id=learner_id,
                            learner_id=learner_id,
                            patch=patch,
                        )
                        st.success("Préférences mises à jour.")
                        st.rerun()
                    except VirtualTeacherAccessError as exc:
                        st.error(_friendly_error(str(exc)))

    session_key = f"vt_session_{learner_id}"
    if session_key not in st.session_state:
        try:
            context = PedagogicalContext(
                learner_id=learner_id,
                learner_display_name=learner_display_name,
                grade_label=grade_label,
            )
            session = teacher_service.start_session(
                user=user,
                learner_id=learner_id,
                student_learner_id=learner_id,
                actor_type="STUDENT",
                actor_ref=str(user["id"]),
                context=context,
            )
            st.session_state[session_key] = session.id
        except VirtualTeacherAccessError as exc:
            st.error(_friendly_error(str(exc)))
            return

    with right:
        st.subheader("Conversation")
        last_audio = st.session_state.pop(f"vt_last_audio_{learner_id}", None)
        if last_audio is not None:
            st.caption("Réponse audio")
            _play_audio(last_audio)
        messages = teacher_service.list_session_messages(
            user=user,
            session_id=int(st.session_state[session_key]),
            learner_id=learner_id,
            student_learner_id=learner_id,
            actor_type="STUDENT",
            actor_ref=str(user["id"]),
        )
        for message in messages:
            role_label = "Élève" if message.message_role == "USER" else "Professeur"
            with st.chat_message("user" if message.message_role == "USER" else "assistant"):
                st.write(f"**{role_label}** — {message.content}")
                if (
                    message.message_role == "ASSISTANT"
                    and preferences.audio_enabled
                    and st.button("Écouter", key=f"listen_{message.id}")
                ):
                    try:
                        st.session_state[PRESENCE_STATE_KEY] = BannerPresenceState.SPEAKING.value
                        audio = teacher_service.synthesize_audio(
                            user=user,
                            learner_id=learner_id,
                            student_learner_id=learner_id,
                            actor_type="STUDENT",
                            actor_ref=str(user["id"]),
                            text=message.content,
                            voice_id=preferences.voice_id,
                        )
                        st.session_state[f"vt_last_audio_{learner_id}"] = audio
                        st.rerun()
                    except VirtualTeacherAccessError as exc:
                        st.warning(_friendly_error(str(exc)))

        quick_actions = st.columns(3)
        quick_message = None
        if quick_actions[0].button("Explique-moi"):
            quick_message = "Explique-moi cette notion."
        if quick_actions[1].button("Donne-moi un indice"):
            quick_message = "Donne-moi un indice."
        if quick_actions[2].button("Montre un exemple"):
            quick_message = "Montre-moi un exemple."

        if not preferences.audio_enabled:
            st.warning(
                "La lecture audio et le mode vocal sont désactivés. "
                "Un parent doit cocher « Autoriser la lecture audio » dans les réglages du professeur virtuel."
            )
        elif voice_pipeline is not None:
            if st.session_state.pop("professor_ai_voice_focus", None):
                st.info("Mode vocal : enregistre ta question ci-dessous.")
            st.subheader("Mode vocal scolaire")
            st.caption("Enregistre une question : transcription → filtre scolaire → réponse → lecture.")
            recorded = None
            if hasattr(st, "audio_input"):
                recorded = st.audio_input("Enregistre ta question", key=f"vt_audio_input_{learner_id}")
            uploaded = st.file_uploader(
                "Ou envoie un fichier audio",
                type=("wav", "mp3", "webm", "m4a", "ogg"),
                key=f"vt_audio_upload_{learner_id}",
            )
            audio_file = recorded or uploaded
            if audio_file is not None and st.button("Envoyer ma question vocale", key=f"vt_voice_send_{learner_id}"):
                st.session_state[PRESENCE_STATE_KEY] = BannerPresenceState.LISTENING.value
                payload = audio_file.getvalue() if hasattr(audio_file, "getvalue") else bytes(audio_file.read())
                mime = getattr(audio_file, "type", None) or "audio/wav"
                context = PedagogicalContext(
                    learner_id=learner_id,
                    learner_display_name=learner_display_name,
                    grade_label=grade_label,
                )
                request = ConversationRequest(
                    learner_id=learner_id,
                    actor_type="STUDENT",
                    actor_ref=str(user["id"]),
                    session_id=int(st.session_state[session_key]),
                    user_message="",
                    context=context,
                    quick_action="voice",
                )
                try:
                    st.session_state[PRESENCE_STATE_KEY] = BannerPresenceState.THINKING.value
                    turn = voice_pipeline.process_turn(
                        user=user,
                        request=request,
                        student_learner_id=learner_id,
                        audio=payload,
                        mime_type=str(mime),
                        voice_id=preferences.voice_id,
                        audio_enabled=preferences.audio_enabled,
                    )
                    st.session_state[PRESENCE_STATE_KEY] = turn.presence.value
                    st.session_state[f"vt_last_transcript_{learner_id}"] = turn.transcript
                    if turn.blocked:
                        st.session_state[f"vt_last_voice_warning_{learner_id}"] = (
                            turn.safety_message or "Question filtrée pour ta sécurité."
                        )
                    if turn.audio is not None:
                        st.session_state[f"vt_last_audio_{learner_id}"] = turn.audio
                    elif preferences.audio_enabled:
                        st.session_state[f"vt_last_voice_warning_{learner_id}"] = (
                            "La réponse texte est disponible, mais la synthèse vocale a échoué. "
                            "Vérifie la clé OpenAI ou utilise le bouton Écouter."
                        )
                    st.rerun()
                except VirtualTeacherAccessError as exc:
                    st.session_state[PRESENCE_STATE_KEY] = BannerPresenceState.IDLE.value
                    st.error(_friendly_error(str(exc)))

        transcript = st.session_state.pop(f"vt_last_transcript_{learner_id}", None)
        if transcript:
            st.info(f"Transcription : {transcript}")
        voice_warning = st.session_state.pop(f"vt_last_voice_warning_{learner_id}", None)
        if voice_warning:
            st.warning(voice_warning)

        user_message = st.chat_input("Pose ta question scolaire")
        prompt = quick_message or user_message
        if prompt:
            context = PedagogicalContext(
                learner_id=learner_id,
                learner_display_name=learner_display_name,
                grade_label=grade_label,
            )
            request = ConversationRequest(
                learner_id=learner_id,
                actor_type="STUDENT",
                actor_ref=str(user["id"]),
                session_id=int(st.session_state[session_key]),
                user_message=prompt,
                context=context,
                quick_action=quick_message,
            )
            try:
                st.session_state[PRESENCE_STATE_KEY] = BannerPresenceState.THINKING.value
                _, response = teacher_service.answer(
                    user=user,
                    request=request,
                    student_learner_id=learner_id,
                )
                st.session_state[PRESENCE_STATE_KEY] = BannerPresenceState.SPEAKING.value
                if preferences.audio_enabled and response.audio_allowed:
                    try:
                        st.session_state[f"vt_last_audio_{learner_id}"] = teacher_service.synthesize_audio(
                            user=user,
                            learner_id=learner_id,
                            student_learner_id=learner_id,
                            actor_type="STUDENT",
                            actor_ref=str(user["id"]),
                            text=response.message,
                            voice_id=preferences.voice_id,
                        )
                    except VirtualTeacherAccessError as exc:
                        st.session_state[f"vt_last_voice_warning_{learner_id}"] = _friendly_error(str(exc))
                st.rerun()
            except VirtualTeacherAccessError as exc:
                st.session_state[PRESENCE_STATE_KEY] = BannerPresenceState.IDLE.value
                st.error(_friendly_error(str(exc)))


def _play_audio(audio) -> None:
    mime = getattr(audio, "mime_type", "audio/wav") or "audio/wav"
    if str(mime).startswith("audio/"):
        st.audio(audio.content, format=str(mime), autoplay=True)
    else:
        st.caption("Synthèse vocale (mode console) — une vraie voix nécessite une clé OpenAI valide.")
        st.code(audio.content.decode("utf-8", errors="ignore")[:500])


def render_parent_virtual_teacher_settings(
    *,
    user: dict,
    parent_ref: str,
    learner_id: int,
    learner_label: str,
    preferences_service: AITeacherPreferencesService,
) -> None:
    st.subheader(f"Professeur virtuel — {learner_label}")
    try:
        preferences = preferences_service.get_preferences_for_parent(
            user=user,
            parent_ref=parent_ref,
            learner_id=learner_id,
        )
    except VirtualTeacherAccessError as exc:
        st.error(_friendly_error(str(exc)))
        return

    with st.form(f"parent_vt_settings_{learner_id}"):
        feature_enabled = st.checkbox("Activer le professeur virtuel", value=preferences.feature_enabled)
        parent_locked = st.checkbox("Verrouiller les préférences élève", value=preferences.parent_locked)
        teacher_profile = st.selectbox(
            "Profil",
            ["TEACHER_FEMALE_01", "TEACHER_MALE_01"],
            index=0 if preferences.teacher_profile == "TEACHER_FEMALE_01" else 1,
        )
        teacher_name = st.selectbox("Prénom affiché", ["Emma", "Léa", "Lucas", "Hugo"], index=0)
        voice_id = st.selectbox(
            "Voix", ["warm_female", "warm_male"], index=0 if preferences.voice_id == "warm_female" else 1
        )
        tone = st.selectbox("Ton", ["calm", "encouraging", "academic"])
        response_length = st.selectbox("Longueur des réponses", ["short", "normal", "detailed"])
        help_level = st.slider(
            "Niveau d'aide (1 = peu d'aide, 3 = plus d'indices)",
            1,
            3,
            preferences.help_level,
            help="Ce n'est pas le niveau scolaire (6e/5e…). Choisis 1, 2 ou 3.",
        )
        audio_enabled = st.checkbox("Autoriser la lecture audio", value=preferences.audio_enabled)
        mode_labels = {
            "PROFESSOR": "Professeur IA (guide le parcours)",
            "COMPANION": "Compagnon (aide sans modifier le planning)",
            "MANUAL": "Manuel (l'élève choisit)",
        }
        current_mode = preferences.operating_mode if preferences.operating_mode in mode_labels else "MANUAL"
        if feature_enabled and current_mode == "MANUAL":
            current_mode = "PROFESSOR"
        operating_mode = st.selectbox(
            "Mode d'accompagnement",
            list(mode_labels),
            index=list(mode_labels).index(current_mode),
            format_func=mode_labels.__getitem__,
            help="Le mode Compagnon ne peut pas créer ni modifier un devoir.",
        )
        submitted = st.form_submit_button("Enregistrer")
        if submitted:
            patch = PreferencesPatch(
                feature_enabled=feature_enabled,
                parent_locked=parent_locked,
                teacher_profile=teacher_profile,
                teacher_name=teacher_name,
                voice_id=voice_id,
                tone=tone,
                response_length=response_length,
                help_level=help_level,
                audio_enabled=audio_enabled,
                operating_mode=operating_mode if feature_enabled else "MANUAL",
                fields={
                    "feature_enabled",
                    "parent_locked",
                    "teacher_profile",
                    "teacher_name",
                    "voice_id",
                    "tone",
                    "response_length",
                    "help_level",
                    "audio_enabled",
                    "operating_mode",
                },
            )
            try:
                preferences_service.save_for_parent(
                    user=user,
                    parent_ref=parent_ref,
                    learner_id=learner_id,
                    patch=patch,
                )
                st.success("Configuration enregistrée.")
                st.rerun()
            except VirtualTeacherAccessError as exc:
                st.error(_friendly_error(str(exc)))

    cols = st.columns(2)
    confirm_reset = st.checkbox(
        "Je confirme la réinitialisation des préférences",
        key=f"confirm_reset_vt_{learner_id}",
    )
    if cols[0].button("Réinitialiser les préférences", key=f"reset_vt_{learner_id}", disabled=not confirm_reset):
        try:
            preferences_service.reset_preferences(user=user, parent_ref=parent_ref, learner_id=learner_id)
            st.success("Préférences réinitialisées.")
            st.rerun()
        except VirtualTeacherAccessError as exc:
            st.error(_friendly_error(str(exc)))
    confirm_delete = st.checkbox(
        "Je confirme la suppression de l'historique",
        key=f"confirm_delete_vt_{learner_id}",
    )
    if cols[1].button("Supprimer l'historique", key=f"delete_vt_{learner_id}", disabled=not confirm_delete):
        try:
            preferences_service.delete_history(user=user, parent_ref=parent_ref, learner_id=learner_id)
            st.success("Historique supprimé.")
            st.rerun()
        except VirtualTeacherAccessError as exc:
            st.error(_friendly_error(str(exc)))


def _friendly_error(code: str) -> str:
    mapping = {
        "LEARNER_ID_REQUIRED": "Profil apprenant requis.",
        "LEARNER_ID_UNRESOLVED": "Ton profil apprenant n'est pas encore disponible.",
        "FEATURE_DISABLED": "Le professeur virtuel est désactivé pour cet élève.",
        "PREFERENCES_LOCKED": "Ces réglages sont verrouillés par le parent.",
        "PARENT_ACCESS_DENIED": "Accès parent refusé.",
        "STUDENT_ACCESS_DENIED": "Accès élève refusé.",
        "CROSS_FAMILY_ACCESS_DENIED": "Cet apprenant n'appartient pas à ton espace familial.",
        "CROSS_LEARNER_ACCESS_DENIED": "Tu ne peux accéder qu'à ton propre profil.",
        "SESSION_ACCESS_DENIED": "Cette séance n'est pas accessible.",
        "MESSAGE_TOO_LONG": "Ton message est trop long. Reformule-le en restant concis.",
        "EMPTY_MESSAGE": "Écris une question avant d'envoyer.",
        "TTS_UNAVAILABLE": "Lecture audio momentanément indisponible.",
        "AUDIO_DISABLED": "La lecture audio est désactivée.",
        "SAFETY_BLOCKED": "Ce message ne peut pas être lu à voix haute.",
        "STT_UNAVAILABLE": "La reconnaissance vocale est momentanément indisponible.",
        "STT_EMPTY": "Je n'ai pas compris l'audio. Réessaie ou écris ta question.",
        "OPENAI_KEY_INVALID": (
            "La clé OpenAI est invalide ou expirée. "
            "Vérifie `.streamlit/secrets.toml` ([openai] api_key) puis redémarre l'application."
        ),
    }
    return mapping.get(code, "Action non disponible pour le moment.")
