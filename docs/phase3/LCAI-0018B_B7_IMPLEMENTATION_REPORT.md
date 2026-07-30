# LCAI-0018B7 — Rapport d'implémentation

## Statut

**READY FOR REVIEW**

## Cause racine

Lorsque la complétion IA était activée, le pipeline acceptait encore un **mode dégradé** (`allow_degraded_result=True` par défaut) et l'UI affichait des messages du type « seulement X contenu(s) disponibles / devoir limité à ce maximum », laissant croire que le catalogue plafonnait le nombre de questions. Le service tronquait aussi la génération via `generation_cap()` sans lever d'erreur bloquante si le déficit n'était pas comblé.

## Correctifs apportés

| Fichier | Changement |
|---------|------------|
| `services/homework/errors.py` | Nouvelle exception `HomeworkCompletionError` avec messages utilisateur en français |
| `services/homework/completion.py` | Complétion stricte obligatoire, rollback si échec, contrôle `final_count == requested_count` |
| `services/homework/config.py` | `allow_degraded_result=False` par défaut ; `generation_cap()` respecte le déficit exact en mode strict |
| `infrastructure/repositories/unified_experience.py` | `rollback_homework_creation()` supprime devoir READY + exercices runtime |
| `services/unified_experience.py` | Contrat repository étendu pour le rollback |
| `ui/unified_app.py` | Suppression des messages limitants quand l'IA est active ; succès « Le devoir de N questions a été créé » |
| `tests/test_homework_ai_completion_0018b7.py` | 20 scénarios obligatoires + cas strict/rollback |

## Comportement attendu

```text
Questions demandées : N
Catalogue admissible : C
Déficit : N - C

Si déficit > 0 et IA disponible → générer exactement le déficit
Si final ≠ N → HomeworkCompletionError + rollback (aucun devoir laissé en READY)
```

## Tests

Commande :

```bash
python -m pytest tests/test_homework_ai_completion_0018b7.py -q
```

Résultat attendu : **28 passed, 1 skipped** (skip si stock catalogue < 5 pour le scénario catalogue seul).

## Validation runtime

Prérequis `.env` :

- `LCAI_ENABLE_V2_UI=true`
- `HOMEWORK_AI_COMPLETION_ENABLED=true`
- `OPENAI_API_KEY` valide

Cas prioritaire : **Espagnol 4e** — 2 rubriques visibles, 10 questions demandées → 10 exercices finaux jouables.

## Verdict

Le ticket LCAI-0018B7 est **implémenté**. La création de devoirs ne doit plus être limitée par le stock catalogue lorsque la complétion IA est activée ; seule une indisponibilité réelle de l'IA autorise un message d'erreur explicite sans création de devoir.
