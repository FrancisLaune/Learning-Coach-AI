# LCAI-0015B — Phase 0 Audit (factuel)

**Date:** 2026-07-28  
**Branche:** develop  
**Commande de test:** `python -m streamlit run app.py`

---

## 4.1 Interface réellement exécutée

| Point | Constat |
|---|---|
| Point d'entrée | `app.py` → `ui.streamlit_app.run_app()` |
| Interface active | **`ui/unified_app.run_unified_app`** lorsque `LCAI_ENABLE_LEGACY_UI` est absent/false (défaut) |
| Legacy masquée | `parent_app()` / `student_app()` dans `streamlit_app.py` ne s'exécutent que si legacy opt-in |
| Professeur IA (LCAI-0017) | Présent dans **`unified_app.run_student`** — page **Mon professeur** |
| Config Parent IA | Accessible via **Mes enfants → Profil IA** (`render_parent_virtual_teacher_settings`) |

**Écart spec / UI:** le menu élève affiche « Mon professeur » et non « Mon professeur IA ».

---

## 4.2 Bases DuckDB réellement utilisées

| Base | Rôle runtime |
|---|---|
| `data/objectif_brevet_2027.duckdb` | Auth V1 (users, passwords, student accounts) |
| `data/learning_coach_v2.duckdb` | Learners, liens familiaux, onboarding, Virtual Teacher |

| Point | Constat |
|---|---|
| Chemin V2 | `core.config.DEFAULT_V2_DATABASE_PATH` ou `LCAI_V2_DATABASE_PATH` |
| Migration 018 | Appliquée sur l'environnement local de review (niveau 18) |
| Tables VT | `virtual_teacher_*` présentes après migration 018 |

---

## 4.3 Liens Parent–Élève

| Point | Constat |
|---|---|
| Clé parent | `parent_ref = str(user["id"])` |
| Table lien | `learner_guardian_links.guardian_external_ref` |
| Création | `LearnerProfileManagementService.create()` → `link_parent()` |
| Filtrage | `ParentExperienceController.learners()` filtre via `parent_authorized()` |
| Risque identifié | `_learner_id()` met en cache `unified_learner_id` sans revalider le compte courant |

---

## 4.4 Professeur IA

| Point | Constat |
|---|---|
| Migration | 018 — OK |
| Menu élève | Présent mais libellé « Mon professeur » |
| Activation | `feature_enabled` default **false** — Parent doit activer |
| État sur fiche enfant | **Non affiché** sur la liste « Mes enfants » |
| Création élève | **Pas d'étape Professeur IA** dans le formulaire actuel (monolithique) |

---

## Synthèse des écarts à corriger (LCAI-0015B)

1. Renommer le menu élève en **Mon professeur IA**
2. Afficher le statut Professeur IA sur chaque carte enfant
3. Masquer la création derrière **+ Ajouter un enfant** quand des élèves existent
4. Assistant création en **5 étapes** avec atomicité conservée
5. Revalidation du cache `learner_id` élève à la connexion
6. Accueil Parent centré sur **Mes enfants** (déjà 1er item navigation)

**Verdict Phase 0:** développement autorisé sur les écarts ci-dessus, sans recréer LCAI-0015A / LCAI-0017.
