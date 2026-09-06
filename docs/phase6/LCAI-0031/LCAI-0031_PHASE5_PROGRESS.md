# LCAI-0031 — Phase 5 Progress Report (Coach Brevet / Professeur IA)

**Statut :** PHASE 5 COMPLETE (coach unique + contexte complet + décisions)  
**Date :** 2026-09-06  
**Commit/push :** non (interdit ticket)

---

## Objectif phase

Le Professeur IA devient le **Coach Brevet** unique (qualité conversationnelle type ChatGPT), avec **tous les éléments utiles injectés à chaque échange**.

---

## Livré

| Brique | Détail |
|--------|--------|
| Pack contexte | `services/dnb/coach.py` — profil, countdown DNB, readiness, priorités, fragiles/forts, exercice, plan |
| Décisions | `services/dnb/coach_decisions.py` — `decide_next_work` + payload audit |
| Prompt système | `prompts/brevet_coach_system.md` — identité coach unique |
| ChatGPT Voice | `services/chatgpt_voice/link.py` + `ui/chatgpt_voice.py` — briefing complet dans `q=` |
| Guidance in-app | `StudentGuidanceService` utilise le prompt Brevet + `session_summary` = briefing + décision |
| Shell élève | Sidebar + Accueil = Coach Brevet ; pas de bandeau Professor AI concurrent |
| Labels FR | Aide séance / révision = « Coach Brevet » |

---

## Contrat « chaque tour »

À chaque génération (accueil, aide exercice, follow-up, révision, feedback devoir) :

1. Briefing Coach (calendrier, readiness, priorités, …)  
2. Décision justifiée (`PRIORITY_WORK` / `EXERCISE_HELP` / …)  
3. Prompt `brevet_coach_system.md`  
4. Identité affichée / préférences = **Coach Brevet**

Canal ChatGPT (voix/texte) : même pack prérempli dans l’URL.

---

## Non livré (Phase 6+)

- Navigation / dashboards Brevet complets (Phase 6)  
- Persistance systématique de chaque décision coach dans `ai_decision_log` (payload prêt, écriture UI/orchestration à brancher si besoin)  
- Simulation orale jury bout-en-bout dans Streamlit  
- Contenu Technologie 3e toujours manquant (dette curriculum)

---

## Tests

```text
pytest tests/test_lcai_0031_phase5_coach.py tests/test_lcai_0030e_chatgpt_voice.py tests/test_student_guidance_0020.py -q
```

---

## Verdict Phase 5

```text
PHASE 5 READY — enchaîner Phase 6 (UX navigation / dashboards)
```
