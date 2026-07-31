# LCAI-0023 — Lot 6 : Mode vocal scolaire sécurisé

## Statut

**READY FOR REVIEW**

## Objectif

Brancher le pipeline Master Book **STT → filtre scolaire → Professeur IA → TTS**, avec UX bandeau (présence + Parler) et stubs CI / providers OpenAI optionnels.

## Décisions

1. **Pipeline** `SchoolVoicePipeline` : transcription → `SafetyChannel.STT` → `AITeacherService.answer` (ou message de sécurité) → TTS si `audio_enabled`.
2. **STT** : `ConsoleSTTService` (fixtures UTF-8 / CI) + `OpenAISTTService` (Whisper) si `OPENAI_API_KEY`.
3. **TTS** : `build_tts_service()` → OpenAI `tts-1` si clé, sinon `ConsoleTTSService`.
4. **UI** : section « Mode vocal scolaire » (`st.audio_input` + upload) ; bandeau lit `professor_ai_presence` (LISTENING / THINKING / SPEAKING) ; bouton **Parler**.
5. **Pas de micro continu** : tour par tour Streamlit uniquement.
6. **Sécurité** : réutilise le filtre Lot 5 ; aucun contournement LLM sur transcript bloqué.

## Variables d'environnement (optionnelles)

| Variable | Rôle |
|----------|------|
| `OPENAI_API_KEY` | Active Whisper STT + TTS productifs |
| `OPENAI_STT_MODEL` | défaut `whisper-1` |
| `OPENAI_TTS_MODEL` | défaut `tts-1` |

## Fichiers

| Fichier | Action |
|---------|--------|
| `services/virtual_teacher/stt_service.py` | Créé |
| `services/virtual_teacher/voice_pipeline.py` | Créé |
| `services/virtual_teacher/openai_tts.py` | Créé |
| `ui/virtual_teacher.py` | Mode vocal + stack 3-tuple |
| `ui/professor_ai_banner.py` | Présence + Parler |
| `ui/unified_app.py` | Branchement pipeline |
| `tests/test_voice_mode_0023.py` | Créé |
| `docs/phase4/LCAI-0023_LOT6_IMPLEMENTATION_REPORT.md` | Créé |
| `docs/phase4/README.md` | Lot 6 terminé |

## Tests

```text
pytest tests/test_voice_mode_0023.py tests/test_school_safety_0022e.py tests/test_virtual_teacher_0017.py -q
```

## Limites résiduelles

- Sans `OPENAI_API_KEY`, la transcription d'un vrai fichier audio binaire reste vide (utiliser le chat texte ou fournir une clé).
- Pas de WebRTC / écoute continue.
- Voix OpenAI mappées grossièrement (`warm_female`→`nova`, `warm_male`→`onyx`).

## Verdict

**READY FOR REVIEW**
