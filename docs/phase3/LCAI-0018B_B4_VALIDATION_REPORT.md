# LCAI-0018B — Validation B4 (branchement OpenAI UI)

**Date :** 2026-07-29  
**Statut :** ✅ Validé — commit B4

---

## Activation

1. Interface V2 : `LCAI_ENABLE_V2_UI=true`
2. Fallback devoirs 4e : `HOMEWORK_AI_FALLBACK_4E_ENABLED=true`
3. OpenAI : `.streamlit/secrets.toml` (section `[openai]`) **ou** variable `OPENAI_API_KEY`

Exemple `.streamlit/secrets.toml` (déjà utilisé par le professeur virtuel et la Content Factory) :

```toml
[openai]
api_key = "sk-..."
model = "gpt-5-mini"
```

Aucune configuration OpenAI parallèle : le branchement passe par `infrastructure/config/openai_settings.py`.

---

## Câblage livré

| Composant | Rôle |
|-----------|------|
| `services/homework/factory.py` | `build_homework_service()` — lit secrets + flags |
| `services/homework/curriculum_target.py` | Résout chapitre/compétence réels pour OpenAI |
| `ui/unified_app.py` | `_homework_service()` remplace les instanciations directes |
| `ui/parent_learner_sheet.py` | Idem pour listes devoirs parent |

---

## Tests

```bash
pytest tests/test_homework_ai_fallback_4e.py -q
```

| Test | Résultat attendu |
|------|------------------|
| Flag OFF | Comportement legacy |
| Flag ON + stub | Exercices `RUNTIME_ONLY` persistés |
| `resolve_curriculum_target` | Cible ENGLISH / FR-4E valide |
| `build_homework_service` | Fallback actif si flag + clé API |

---

## Dette résiduelle

- Les exercices runtime ne sont pas encore injectés dans `create_homework_proposal` (séance) — le devoir est créé et persisté, la lecture séance reste catalogue-only.
