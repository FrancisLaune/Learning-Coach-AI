# LCAI-0000A — AI-Driven Validation Framework

**Statut :** ✅ ADOPTÉ (2026-07-30)  
**Portée :** Tous les tickets Learning Coach AI, en particulier la série curriculums LCAI-0018

---

## 1. Objectif

Mettre en place un processus de validation où l'IA réalise automatiquement la majorité des contrôles techniques avant de soumettre une fonctionnalité à validation humaine.

Le développeur humain ne doit intervenir que pour :

- les tests fonctionnels finaux ;
- l'expérience utilisateur ;
- les décisions métier ;
- les arbitrages produit.

## 2. Cycle par ticket

```text
Analyse → Implémentation → Auto-revue IA → Correction → Re-revue IA
    → Validation technique IA → Commit → Push → Validation fonctionnelle humaine
```

## 3. Contrôles IA obligatoires

| Domaine | Contrôles |
|---------|-----------|
| Architecture | couches, patterns, duplication, conventions |
| Base de données | migrations, index, clés, intégrité (si applicable) |
| Code | Ruff, Mypy, compileall, imports |
| Tests | unitaires, intégration, régression périmètre ticket |
| Sécurité | auth, isolation, secrets |
| Documentation | cohérence spec/code, rapport, liste fichiers |
| Runtime | smoke démarrage si touché |

## 4. Script de validation

```powershell
python scripts/lcai_0000a_technical_validation.py --ticket LCAI-0018E
python scripts/lcai_0000a_technical_validation.py --curriculum-all
python scripts/lcai_0000a_global_curriculum_inventory.py
```

Rapports générés dans `docs/phase3/exports/lcai_0000a_<ticket>_validation_report.json` et `.md`.

## 5. Rapport attendu en fin de ticket

- État général : Implémentation / Auto-revue / Validation technique (OK/NOK)
- Résultats par contrôle (Architecture, DB, Tests, Ruff, Mypy, compileall, démarrage)
- Corrections automatiques réalisées
- Régressions : aucune ou liste
- Limites restantes : **uniquement** blocages non résolvables par l'IA

## 6. Validation humaine

- Lancer l'application
- Parcourir les écrans concernés
- Vérifier comportement métier et UX
- Signaler ajustements fonctionnels si besoin

**Aucune** revue manuelle du code, migrations ou tests n'est attendue sauf demande explicite.

## 7. Instruction permanente (EN)

```text
Cursor is responsible for the complete technical validation of its own implementation.

Before requesting user review, Cursor must:
- review the architecture;
- review the implementation;
- execute all applicable tests;
- execute static analysis;
- validate migrations;
- validate security rules;
- validate authorization;
- validate documentation consistency;
- automatically correct every issue it can resolve.

Only unresolved issues requiring a functional or product decision may be escalated.

The user is responsible only for functional validation and user experience testing,
not for technical code review.
```

## 8. Application curriculums LCAI-0018

| Ticket | Niveau | Validation technique IA | Validation humaine fonctionnelle |
|--------|--------|-------------------------|----------------------------------|
| LCAI-0018C | CM1 | via `--curriculum-all` | Homework CM1 en UI |
| LCAI-0018D | CM2 | via `--curriculum-all` | Homework CM2 en UI |
| LCAI-0018E | 6e | via `--curriculum-all` | Homework 6e en UI |
| LCAI-0018F | 5e | à exécuter après implémentation | Homework 5e en UI |
| LCAI-0018H | Global | audit certification | Parcours multi-niveaux |

Voir aussi : [LCAI-0000A_CURRICULUM_VALIDATION_STATUS.md](LCAI-0000A_CURRICULUM_VALIDATION_STATUS.md)
