# LCAI-0020 — Rapport d'implémentation Professeur IA (parcours Élève)

**Date :** 2026-07-30  
**Statut :** READY FOR REVIEW  
**Verdict :** READY FOR REVIEW  
**Commit :** non effectué  
**Push :** non effectué  

---

## Résumé

Le Professeur IA est intégré comme accompagnateur permanent du parcours Élève via une façade `StudentGuidanceService`, avec fallback déterministe complet. Le Tableau de bord reste l'entrée principale ; les devoirs disposent d'un accompagnement avant, pendant et après séance.

---

## Audit de l'existant réutilisé

| Composant | Rôle |
|-----------|------|
| `AIConversationOrchestrator` | Appels IA via orchestrateur existant (LCAI-0017) |
| `LearnerExperienceService` | Dashboard, synthèse séance, maîtrise |
| `HomeworkService` | Devoirs, scoping `learner_id` |
| `DeterministicCoachService` | Recommandations sans IA |
| `PedagogicalRecommendationService` | Priorités de révision |
| `resolve_ai_availability()` | Modes ACTIVE / INACTIVE / UNAVAILABLE |
| `ui/unified_app.py` | Shell élève unifié |
| `ui/v2_experience.py` | Séances et historique |

Aucun appel LLM direct depuis Streamlit.

---

## Fichiers créés

| Fichier | Description |
|---------|-------------|
| `application/dto/student_guidance.py` | DTOs guidance |
| `services/student_guidance/service.py` | Façade `StudentGuidanceService` |
| `services/student_guidance/availability.py` | Résolution disponibilité IA |
| `services/student_guidance/mastery_bands.py` | Seuils centralisés |
| `services/student_guidance/deterministic.py` | Fallbacks déterministes |
| `services/student_guidance/__init__.py` | Exports |
| `ui/student_guidance.py` | Widgets Streamlit (carte IA, devoirs, révision) |
| `tests/test_student_guidance_0020.py` | 43 scénarios ticket + régressions |
| `docs/phase2/LCAI-0020_AI_PROFESSOR_IMPLEMENTATION_REPORT.md` | Ce rapport |

## Fichiers modifiés

| Fichier | Modification |
|---------|--------------|
| `application/experience_factory.py` | `build_student_guidance_service()` |
| `ui/unified_app.py` | Nav « Tableau de bord », carte IA, devoirs, révision |
| `ui/v2_experience.py` | Aide Professeur IA en séance, explication post-séance |
| `tests/test_unified_experience.py` | Assertion navigation |

---

## Flux implémentés

### Connexion / Tableau de bord

- `build_home_guidance()` → carte Professeur IA (IA ou déterministe)
- Catégories de maîtrise via `render_mastery_bands()`
- Navigation invariante : **Tableau de bord** toujours présent

### Devoir — Avant

- `prepare_homework_guidance()` affiché sur devoirs READY / IN_PROGRESS / PAUSED
- Objectif, durée estimée, conseil pédagogique

### Devoir — Pendant

- `guide_current_exercise()` dans `session_screen()` via expander « Demander au Professeur IA »
- Niveaux d'aide 1–6, pas de solution immédiate aux niveaux bas

### Devoir — Après

- `explain_homework_result()` sur devoirs terminés (onglet Terminés)
- `explain_session_result()` à la fin d'une séance COMPLETED

### Révision

- `recommend_revision()` sur la page Révision libre

---

## Comportement IA

| Mode | Comportement |
|------|--------------|
| **ACTIVE** | Orchestrateur appelé pour welcome, aide exercice, explication, révision |
| **INACTIVE** | Fallback déterministe ; message d'activation parent |
| **UNAVAILABLE** | Fallback + notice de dégradation non bloquante |

Les notes et la maîtrise restent calculées par les moteurs métier ; le LLM n'expose que des explications.

---

## Tests (43 scénarios ticket)

| Catégorie | Résultat |
|-----------|----------|
| Navigation (1–5) | PASS |
| Connexion (6–10) | PASS |
| Devoirs (11–16) | PASS |
| Tableau de bord (17–24) | PASS |
| Révision (25–29) | PASS |
| Robustesse (30–38) | PASS |
| Régression (39–43) | PASS |

**Commande :** `pytest tests/test_student_guidance_0020.py tests/test_unified_experience.py`  
**Résultat :** 59 passed

---

## Qualité

| Outil | Résultat |
|-------|----------|
| Ruff (modules LCAI-0020) | PASS |
| Mypy (`services/student_guidance`, DTOs, UI guidance) | PASS |
| compileall | PASS |
| Import Streamlit `run_unified_app` | PASS |

---

## Limites connues

1. **Smoke Streamlit visuel** non exécuté automatiquement — validation manuelle recommandée par Francis.
2. **Suite complète pytest** non lancée (ticket majeur ; tests ciblés + régression navigation OK).
3. **Ruff sur `unified_app.py`** : alertes préexistantes (E402 path bootstrap) hors périmètre ticket.
4. **Explication post-devoir** : s'appuie sur données coach/dashboard ; pas de recalcul score séance dans l'explication homework si séance non liée.

---

## Blocages

Aucun blocage technique identifié.

---

## Prochaine étape suggérée (hors ticket)

Validation fonctionnelle manuelle : connexion élève → Tableau de bord → devoir → séance → explication → révision.
