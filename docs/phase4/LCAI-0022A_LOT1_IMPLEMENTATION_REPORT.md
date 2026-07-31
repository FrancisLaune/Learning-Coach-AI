# LCAI-0022A — Lot 1 : Orchestrateur Professeur IA Core

## Statut

**READY FOR REVIEW**

## Objectif

Fournir une façade d’orchestration qui enchaîne les moteurs existants sans les dupliquer, conformément au Master Book IA-First (cycle Accueil → Diagnostic → Devoir → Séance → Analyse → Préparation).

## Décisions d’architecture

1. **Façade mince** : `ProfessorAIOrchestrator` appelle uniquement des services déjà livrés (guidance, PI, homework, homework sessions).
2. **Pas de mutation de notes** : aucune écriture de score dans l’orchestrateur.
3. **Mode Compagnon** : interdit la création de devoirs (PermissionError).
4. **Mode Manuel** : planning sans consultation PI ; pas de refresh post-séance.
5. **Decision trace** : breadcrumbs en mémoire (`DecisionTraceEntry`) — persistance DuckDB reportée au Lot 4.
6. **Composition** : `build_professor_ai_orchestrator()` dans `application/experience_factory.py`.

## API publique

| Méthode | Rôle Master Book |
|---------|------------------|
| `resolve_mode` | Modes Professeur / Compagnon / Manuel |
| `plan_session` | Accueil + diagnostic overview |
| `compose_homework` | Création devoir (catalogue ± IA completion) |
| `open_session` | Matérialisation + `ensure_running` |
| `close_session_cycle` | Explication + refresh PI |

## Fichiers

| Fichier | Action |
|---------|--------|
| `services/professor_ai/__init__.py` | Créé |
| `services/professor_ai/models.py` | Créé |
| `services/professor_ai/orchestrator.py` | Créé |
| `application/experience_factory.py` | `build_professor_ai_orchestrator` |
| `tests/test_professor_ai_orchestrator_0022a.py` | Créé |
| `docs/phase4/LCAI-0022A_LOT1_IMPLEMENTATION_REPORT.md` | Créé |

## Tests

```text
pytest tests/test_professor_ai_orchestrator_0022a.py -q
→ 9 passed
```

## Limites résiduelles (Lots suivants)

- Pas encore branché dans l’UI Streamlit (Lot 2/3 — bandeau + cycle UX).
- Pas de journal persisté `ai_decision_log` (Lot 4).
- Pas de mode vocal (Lot 6).
- `compose_homework` réutilise `create_with_diagnostics` existant ; pas de nouveau générateur.

## Verdict

**READY FOR REVIEW**
