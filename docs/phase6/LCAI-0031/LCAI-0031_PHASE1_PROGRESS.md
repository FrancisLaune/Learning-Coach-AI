# LCAI-0031 — Phase 1 Progress Report

**Statut :** PHASE 1 PARTIELLE — modèle cible + UX 3e minimale  
**Date :** 2026-09-06  
**Commit/push :** non (interdit ticket)

---

## Livré

| Élément | Détail |
|---------|--------|
| Config domaine | `domain/dnb/` — matières terminales, EN/ES continuous-only, grade FR-3E |
| Calendrier | `domain/dnb/calendar.py` + migration `026_dnb_exam_calendar.sql` |
| Capabilities | `SubjectCapabilities` / `supports_brevet_exam` |
| Façade | `services/dnb/` — filtres grades / matières Brevet |
| UX grades | `grade_levels()` → **FR-3E uniquement** (admin : `product_facing=False`) |
| UX matières | Devoirs / évaluations / onboarding : hors EN/ES terminal |
| Onboarding | Titre « Objectif Brevet 2027 », objectif examen prioritaire |
| Homework AI | Grades par défaut = `FR-3E` (élargissable via env) |
| Sauvegarde DB | `data/backups/lcai_0031_phase1_20260906_164905/` |
| Tests | `tests/test_dnb_config_0031.py` (+ sélecteurs curriculum adaptés) |

---

## Non livré (phases suivantes)

- Diagnostic initial obligatoire
- Planificateur jusqu’au DNB / Readiness Score produit
- Templates Sujet Brevet / Brevet blanc / Oral
- Navigation complète §33
- Coach Brevet (prompts Professeur IA)
- Migration contenus CM1–4e → prérequis uniquement (données conservées)

---

## Fichiers

**Créés**
- `domain/dnb/*`
- `services/dnb/__init__.py`
- `migrations/v2/026_dnb_exam_calendar.sql`
- `docs/phase6/LCAI-0031/*`
- `tests/test_dnb_config_0031.py`

**Modifiés**
- `infrastructure/repositories/unified_experience.py`
- `services/unified_experience.py` (protocol)
- `services/homework/config.py`
- `services/homework/coverage.py`
- `ui/unified_app.py`
- `tests/test_curriculum_selectors.py`

---

## Validation

```text
pytest tests/test_dnb_config_0031.py tests/test_curriculum_selectors.py tests/test_lcai_0030d_coverage_antirepeat.py
→ 22 passed
```

---

## Verdict Phase 1

```text
PHASE 1 FOUNDATION READY — continue Phase 2 (migration données / curriculum) or Phase 3 (moteur)
```

Pas encore `READY FOR REVIEW` global (scénario recette §60 incomplet).
