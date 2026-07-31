# LCAI-0022B — Lot 2 : Bandeau Professeur IA + modes

## Statut

**READY FOR REVIEW**

## Objectif

Exposer le Professeur IA comme bandeau fixe côté élève, avec les trois modes Master Book (Professeur / Compagnon / Manuel), persistés et contrôlés par le parent.

## Décisions

1. **Migration additive** `024_professor_ai_operating_mode.sql` : colonne `operating_mode` sur `virtual_teacher_preferences`.
2. **Bandeau** `ui/professor_ai_banner.py` affiché en tête de tous les écrans élève (`run_student`).
3. **États de présence** : IDLE / LISTENING / THINKING / SPEAKING (Lot 2 utilise IDLE/SPEAKING).
4. **Mode Compagnon** : déjà interdit pour `compose_homework` (Lot 1) — rappel UX parent.
5. **Édition élève** : possible si `feature_enabled` et non `parent_locked`.
6. **Parent** : selectbox « Mode d'accompagnement » dans les réglages VT.

## Fichiers

| Fichier | Action |
|---------|--------|
| `migrations/v2/024_professor_ai_operating_mode.sql` | Créé |
| `domain/virtual_teacher/models.py` | `operating_mode` |
| `infrastructure/repositories/virtual_teacher.py` | Lecture / écriture |
| `services/virtual_teacher/ai_teacher_preferences_service.py` | Validation mode |
| `services/professor_ai/banner.py` | Créé |
| `services/professor_ai/orchestrator.py` | Lecture du mode stocké |
| `ui/professor_ai_banner.py` | Créé |
| `ui/unified_app.py` | Branchement bandeau |
| `ui/virtual_teacher.py` | Réglage parent |
| `tests/test_professor_ai_banner_0022b.py` | Créé |

## Tests

```text
pytest tests/test_professor_ai_banner_0022b.py tests/test_professor_ai_orchestrator_0022a.py -q
→ 16 passed
```

## Limites résiduelles

- Pas encore de cycle UX complet Accueil → Diagnostic → Devoir (Lot 3).
- Présence LISTENING/THINKING non pilotée par STT/TTS (Lot 6).
- Le bandeau appelle `plan_session` à chaque rerun : acceptable pour V1 ; cache UI possible plus tard.

## Verdict

**READY FOR REVIEW**
