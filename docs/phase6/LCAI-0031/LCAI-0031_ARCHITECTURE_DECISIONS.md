# LCAI-0031 — Architecture Decisions

**Statut :** DRAFT — décisions Phase 0/1  
**Epic :** Recentrage 3e / DNB 2027 (`docs/phase6/LCAI-0031/`)

---

## ADR-0031-001 — ID ticket

Dernier epic livré = **LCAI-0030**. Ce recentrage = **LCAI-0031**.  
L’ancien LCAI-0022 (phase4, Professeur IA) n’est pas renommé ni réutilisé.

## ADR-0031-002 — V2 comme système pédagogique cible

Pas de seconde application. Auth peut rester sur `objectif_brevet_2027.duckdb` ; curriculum, devoirs, séances, readiness évoluent sur `learning_coach_v2.duckdb`.

## ADR-0031-003 — Config DNB hors Streamlit

Calendrier, matières terminales, capabilities : `domain/dnb/*`.  
Interdit de hard-coder les dates DNB dans `ui/*.py`.

## ADR-0031-004 — Codes sujets V2 existants

On conserve `HISTORY` + `GEOGRAPHY` + `EMC` séparés (chapitres).  
Le domaine d’épreuve `HISTORY_GEOGRAPHY` est une agrégation logique (calendrier / coeffs).

## ADR-0031-005 — EN/ES

Données **KEEP**. Capabilities : `supports_brevet_exam=False`, contrôle continu only.

## ADR-0031-006 — `revision_3e_enrichie/`

Référence pédagogique / archive. Pas de runtime parallèle produit.

## ADR-0031-007 — Pas de commit/push dans le ticket

Conformément aux interdictions du ticket source.

## ADR-0031-008 — grade_levels product_facing

`DuckDBUnifiedExperienceRepository.grade_levels(product_facing=True)` (défaut) ne renvoie que `FR-3E`.  
Outils / audits / couverture multi-niveaux : `product_facing=False`. Données CM1–4e non détruites.

## ADR-0031-009 — Homework AI grades défaut

Sans `HOMEWORK_AI_COMPLETION_GRADES`, seule la 3e est autorisée. Les scripts/tests élargissent via l’env.
