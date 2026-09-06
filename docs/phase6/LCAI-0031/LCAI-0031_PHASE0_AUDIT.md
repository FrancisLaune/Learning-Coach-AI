# LCAI-0031 — Phase 0 Audit (Recentrage 3e / DNB 2027)

**Statut :** PHASE 0 COMPLETE — prêt pour Phase 1  
**Date :** 2026-09-06  
**Ticket :** LCAI-0031 (ex-fichier source mal étiqueté LCAI-0022)  
**Source :** `LCAI-0031_Recentrage_3e_Preparation_DNB_2027.md`  
**Périmètre :** audit lecture seule (aucune migration destructive)

---

## Numérotation

| ID | Contenu |
|----|---------|
| LCAI-0022 (phase4) | Professeur IA — **hors périmètre**, inchangé |
| LCAI-0030 (phase5) | Dernier epic produit livré |
| **LCAI-0031** (phase6) | **Ce ticket** — recentrage 3e / DNB 2027 |

---

## Architecture

| Couche | Emplacement | Label |
|--------|-------------|-------|
| Shell produit | `ui/unified_app.py` / `ui/streamlit_app.py` | **KEEP** |
| Auth legacy | `data/objectif_brevet_2027.duckdb` | **KEEP** (strangler) |
| Pédagogie V2 | `data/learning_coach_v2.duckdb` | **KEEP** — cible recentrage |
| Snapshot Objectif Brevet | `revision_3e_enrichie/` | **ARCHIVE** / référence |
| Professeur IA | `services/professor_ai/*` | **KEEP** → futur Coach Brevet |

---

## Constats clés

1. Le produit V2 est encore **multi-niveaux** (CM1→3e) côté UX/onboarding/homework.
2. Le curriculum **FR-3E / BREVET 2027** existe déjà en V2 (seeds, tests 0018G, bias homework).
3. Anglais / Espagnol sont des matières à part entière — à déclasser du parcours terminal.
4. Pas de calendrier DNB versionné, templates d’épreuve, annales structurées, oral, Brevet blanc, Readiness produit, planificateur jusqu’au DNB.
5. `exam_readiness_current` existe en schéma mais n’égale pas le Readiness Score du ticket.

---

## KEEP / MIGRATE / GAP

| Élément | Label |
|---------|-------|
| V2 + shell unifié + Professor AI | KEEP |
| Curriculum FR-3E, homework AI, difficulté non bloquante | KEEP → approfondir |
| Sélecteurs CM1–4e, politiques multi-niveaux | MIGRATE (UX 3e only) |
| EN/ES en préparation Brevet | MIGRATE (contrôle continu only) |
| Inventaires LCAI-0013 annales | KEEP docs → MIGRATE schéma |
| `revision_3e_enrichie` | ARCHIVE référence |
| Calendrier, capabilities, templates, mocks, oral, planner | GAP |

---

## Phase 1 — démarrage

1. Config DNB versionnée (`domain/dnb/*`).
2. `SubjectCapabilities` (terminal vs continuous).
3. Niveau utilisateur canonique = `FR-3E`.
4. Tests unitaires config.
5. Sauvegarde DB avant migrations additives.

**Interdit :** commit, push, destruction CM1–4e, hard-code dates dans Streamlit, app V2 parallèle.
