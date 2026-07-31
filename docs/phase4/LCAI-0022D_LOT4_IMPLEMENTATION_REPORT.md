# LCAI-0022D — Lot 4 : Invariants IA + journal de décisions

## Statut

**READY FOR REVIEW**

## Objectif

Persister les décisions du Professeur IA (traçabilité Master Book) et formaliser l’interdiction de mutation directe des scores.

## Décisions

1. **Table additive** `ai_decision_log` (migration `025_professor_ai_decision_log.sql`).
2. **Enrichissement** de `DecisionTraceEntry` : objectif, candidats, exclusions, déficit.
3. **Service** `ProfessorAIDecisionLogService` + repository DuckDB.
4. **Orchestrateur** : chaque `plan_session` / `compose_homework` / `open_session` / `close_session_cycle` écrit le journal (si branché).
5. **Invariant** `forbid_direct_score_mutation` / rejet des payloads `mastery_score` etc. dans le journal.
6. **Pas d’UI parent** dans ce lot — lecture via repository / tests ; éventuel écran audit Lot suivant ou outil admin.

## Schéma (champs clés)

| Champ | Rôle |
|-------|------|
| `learner_id` | Élève |
| `correlation_id` | Lien des étapes d’une action |
| `operating_mode` | PROFESSOR / COMPANION / MANUAL |
| `cycle_step` | ACCUEIL, DIAGNOSTIC, CREATION_DEVOIR, … |
| `objective` | Objectif / mission |
| `candidates_json` | Contenus / skills retenus |
| `exclusions_json` | Ex. `catalog_shortfall:N` |
| `deficit_json` | Compteurs catalogue / IA / dégradé |
| `justification` | Texte de décision |
| `homework_id` / `session_id` | Liens runtime |

## Fichiers

| Fichier | Action |
|---------|--------|
| `migrations/v2/025_professor_ai_decision_log.sql` | Créé |
| `infrastructure/repositories/professor_ai_decision_log.py` | Créé |
| `services/professor_ai/decision_log.py` | Créé |
| `services/professor_ai/invariants.py` | Créé |
| `services/professor_ai/models.py` | Enrichi |
| `services/professor_ai/orchestrator.py` | Persistance |
| `services/professor_ai/__init__.py` | Exports |
| `application/experience_factory.py` | Branchement decision_log |
| `tests/test_professor_ai_decision_log_0022d.py` | Créé |
| `docs/phase4/LCAI-0022D_LOT4_IMPLEMENTATION_REPORT.md` | Créé |
| `docs/phase4/README.md` | Lot 4 terminé |

## Tests

```text
pytest tests/test_professor_ai_decision_log_0022d.py tests/test_professor_ai_orchestrator_0022a.py tests/test_professor_ai_guided_cycle_0022c.py tests/test_professor_ai_banner_0022b.py -q
```

## Limites résiduelles

- Filtre scolaire central (Lot 5).
- Mode verbal (Lot 6).
- Pas d’écran parent de consultation du journal dans ce lot.
- Le journal n’empêche pas techniquement un autre service d’écrire des scores ; l’invariant porte sur le périmètre Professeur IA.

## Verdict

**READY FOR REVIEW**
