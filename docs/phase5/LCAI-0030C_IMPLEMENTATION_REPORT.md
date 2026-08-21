# LCAI-0030-C — Rapport d’implémentation (Lot 3)

**Date :** 2026-08-21  
**Statut technique :** OK (validation ciblée)  
**Spec :** [LCAI-0030_PRODUCT_REORIENTATION.md](LCAI-0030_PRODUCT_REORIENTATION.md)

## Objectif livré

- Plus de choix obligatoire **Facile / Moyen / Difficile** à la création de devoir.  
- Sélection d’exercices **adaptée aux résultats** (renforcement après échecs, stretch après réussites).  
- Aides **progressives et utiles** (indice → notion → démarche), sans spoiler immédiat.

## Changements

| Zone | Détail |
|------|--------|
| UI devoirs | Selectbox difficulté retirée → mode **ADAPTIVE** implicite + légende |
| Sélection | `LearnerOutcomeSignals` + `strategy_from_outcomes` / `target_difficulty_from_outcomes` |
| Aides | `homework_during` enrichi (consigne, hint contenu) ; UI radio progressive 1–5 |
| Messages | Fin du branding « Professeur IA » sur les notices d’aide dégradée |

## Fichiers

**Créés**
- `tests/test_lcai_0030c_adaptation_aids.py`
- `docs/phase5/LCAI-0030C_IMPLEMENTATION_REPORT.md`

**Modifiés**
- `services/homework/exercise_selection.py`
- `infrastructure/repositories/unified_experience.py`
- `services/student_guidance/deterministic.py`
- `services/student_guidance/service.py`
- `ui/student_guidance.py`
- `ui/unified_app.py`
- `ui/v2_experience.py`

## Validation technique (ciblée)

- `pytest` Lot 3 + sélection 0021 + hints 0020 : **18 passed**
- `ruff check` sur modules métier Lot 3 : OK (hors bruits préexistants `unified_app` E402)

## Limites restantes

- Anti-répétition longue durée et couverture CM1–3ᵉ = Lot 4.  
- ChatGPT Voice = Lot 5.  
- Les hints catalogue avec pénalité restent disponibles en complément.

## Validation humaine attendue

1. Créer un devoir : plus de liste Facile/Moyen/Difficile.  
2. Après plusieurs échecs, le mix penche vers le renforcement (message « adaptés à ton profil »).  
3. En séance, ouvrir **Demander une aide** → conseils progressifs utiles liés à la consigne.
