# LCAI-0018B6 — Rapport d'implémentation

**Date :** 2026-07-30  
**Statut :** READY FOR REVIEW  
**Verdict :** READY FOR REVIEW  
**Commit / push :** non effectués  

---

## Diagnostic Espagnol 4e — « 2 rubriques »

| Cause | Détail |
|-------|--------|
| **Structure curriculum** | 2 chapitres officiels : Communication + Language (`CH-SPANISH-4E-*`) |
| **Catalogue publié** | ~2 exercices approuvés ; ~24 brouillons non éligibles |
| **UI chapitres** | `chapters()` ne liste que les chapitres avec contenu **publié** → souvent 1 seul visible |
| **Fallback IA** | Désactivé par défaut ; anciennement limité à la 4e uniquement |

**Conclusion :** ce n'est pas un bug UI isolé. Le curriculum existe mais le catalogue publié est insuffisant. Sans complément IA activé, un devoir de 10 exercices est plafonné à ~2.

---

## Implémentation

### Service généralisé

- `HomeworkContentCompletionService` (`services/homework/completion.py`)
- Alias rétrocompatible : `HomeworkAiFallbackOrchestrator`
- Éligibilité multi-niveaux / multi-matières : `services/homework/eligibility.py`
- Cibles curriculum multiples : `resolve_curriculum_targets()` — répartition round-robin entre chapitres/compétences

### Configuration

| Variable | Rôle |
|----------|------|
| `HOMEWORK_AI_COMPLETION_ENABLED` | Active la généralisation |
| `HOMEWORK_AI_COMPLETION_GRADES` | CM1, CM2, 6E, 5E, 4E, 3E → codes `FR-*` |
| `HOMEWORK_AI_COMPLETION_SUBJECTS` | `ALL` ou liste filtrée |
| `HOMEWORK_AI_FALLBACK_4E_ENABLED` | Alias legacy (4e seule si completion OFF) |
| `HOMEWORK_AI_MAX_GENERATED_PER_HOMEWORK` | Plafond génération (20) |

### Flux

1. Sélection catalogue approuvé  
2. Calcul du déficit  
3. Génération IA **uniquement du manquant**  
4. Validation automatique + persistance runtime (`homework_runtime_exercises`)  
5. Devoir jouable immédiatement  

---

## Fichiers

**Créés :** `completion.py`, `eligibility.py`, `tests/test_homework_ai_completion_0018b6.py`, ce rapport  

**Modifiés :** `ai_fallback.py`, `config.py`, `curriculum_target.py`, `factory.py`, `platform_runtime.py`, `unified_experience.py`, `unified_experience` repository, `unified_app.py`, `.env.example`

---

## Tests

```
pytest tests/test_homework_ai_completion_0018b6.py \
       tests/test_homework_ai_fallback_4e.py \
       tests/test_homework_ai_runtime_playability_0018b5.py
→ 19 passed
```

Ruff OK sur modules B6.

---

## Activation (Francis)

Dans `.env` ou variables d'environnement :

```env
LCAI_ENABLE_V2_UI=true
HOMEWORK_AI_COMPLETION_ENABLED=true
OPENAI_API_KEY=...
```

Puis redémarrer Streamlit. Création Espagnol 4e : le moteur complète automatiquement le déficit (ex. 2 catalogue + 4 IA = 6 exercices).

---

## Limites / dette

- Tableau de bord couverture admin (ticket §19) : **non implémenté**
- Persistance catalogue Draft réutilisable : runtime only (B5) — approbation humaine requise pour publication
- Suite pytest complète : non lancée
- 24 brouillons Espagnol 4e : publication séparée (LCAI-0018), non auto-approuvés

---

## Prochaine étape suggérée

Validation manuelle : devoir Espagnol 4e 6–10 exercices avec flag ON + clé OpenAI.
