# LCAI-0022C — Lot 3 : Cycle séance guidée

## Statut

**READY FOR REVIEW**

## Objectif

Unifier le parcours élève Accueil → Diagnostic → Devoir → Séance → Synthèse via le bandeau Professeur IA, sans recréer les écrans existants.

## Décisions

1. **Séquenceur soft** : `resolve_guided_cycle` propose l’étape suivante ; la sidebar reste libre.
2. **Réutilisation** : Tableau de bord (accueil + diagnostic PI), Devoirs, Ma séance IA, explication guidance post-séance.
3. **CTA bandeau** : bouton primaire piloté par le cycle (`Étape n/5` + libellé d’action).
4. **Clôture** : à la fin de séance, `close_session_cycle` (Lot 1) est appelé une fois, puis navigation Accueil / Devoirs.
5. **Focus soft** : flags session (`professor_ai_focus_diagnostic`, `professor_ai_focus_homework_id`) pour guider sans bloquer.

## Priorité des étapes

1. Séance active (`READY` / `RUNNING` / `PAUSED` ou session sélectionnée)
2. Synthèse si séance `COMPLETED` non encore clôturée
3. Diagnostic si statut PI hors `COMPLETED`/`PLANNED` (sauf mode Manuel)
4. Devoir en retard puis devoir à faire
5. Accueil

## Fichiers

| Fichier | Action |
|---------|--------|
| `services/professor_ai/guided_cycle.py` | Créé |
| `services/professor_ai/__init__.py` | Exports Lot 3 |
| `ui/professor_ai_guided_cycle.py` | Créé (glue session + CTA) |
| `ui/professor_ai_banner.py` | CTA cycle + progression |
| `ui/v2_experience.py` | Statut séance + `close_session_cycle` + focus diagnostic |
| `ui/unified_app.py` | Focus devoir + mémorisation statut à l’ouverture |
| `tests/test_professor_ai_guided_cycle_0022c.py` | Créé |
| `docs/phase4/LCAI-0022C_LOT3_IMPLEMENTATION_REPORT.md` | Créé |
| `docs/phase4/README.md` | Lot 3 terminé |

## Tests

```text
pytest tests/test_professor_ai_guided_cycle_0022c.py tests/test_professor_ai_orchestrator_0022a.py tests/test_professor_ai_banner_0022b.py -q
```

## Limites résiduelles

- Pas de journal persisté `ai_decision_log` (Lot 4).
- Pas de filtre scolaire central renforcé (Lot 5).
- Pas de mode verbal (Lot 6).
- Le CTA n’ouvre pas automatiquement la séance devoir : navigation vers Devoirs + focus id.

## Verdict

**READY FOR REVIEW**
