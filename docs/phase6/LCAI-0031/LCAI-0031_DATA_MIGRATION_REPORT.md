# LCAI-0031 — Data Migration Report (Phase 2)

**Statut :** PHASE 2 COMPLETE (classification additive — aucune destruction)  
**Date :** 2026-09-06  
**Backup préalable :** `data/backups/lcai_0031_phase1_20260906_164905/`  
**Migration :** `migrations/v2/027_dnb_product_classification.sql` (appliquée)  
**Inventaire :** `docs/phase6/LCAI-0031/exports/LCAI-0031_PHASE2_CONTENT_INVENTORY.json`

---

## Règles appliquées

| Classification | Signification | Action Phase 2 |
|----------------|---------------|----------------|
| KEEP | Conserver tel quel | Élèves, historiques, EN/ES continuous |
| MIGRATE | Contenu 3e terminal DNB | Marqué + capabilities |
| ARCHIVE | Niveaux antérieurs | `product_role=remediation` — **pas de DELETE** |
| DEPRECATE | Lycée hors produit | `product_role=out_of_scope` |
| DELETE_AFTER_VALIDATION | — | **Non utilisé** |

---

## Volumes (production catalog)

| Classification | Lignes |
|----------------|--------|
| MIGRATE (3e terminal) | **217** |
| KEEP (3e langues continuous) | **12** |
| ARCHIVE (CM1→4e) | **483** |
| **Total classifié** | **712** |

### FR-3E curriculum

| Métrique | Valeur |
|----------|--------|
| Chapitres approuvés | 34 |
| Skills | 196 |
| Production | 229 |
| Curriculum version | `FR_3E_2027_V1` |

### Remédiation (conservée)

| Grade | Chapitres | Production |
|-------|-----------|------------|
| FR-CM1 | 24 | 138 |
| FR-CM2 | 24 | 63 |
| FR-6E | 26 | 45 |
| FR-5E | 28 | 43 |
| FR-4E | 30 | 194 |

---

## Schéma ajouté

- `school_levels.product_role` — terminal / remediation / out_of_scope  
- `subjects.assessment_role` — terminal / continuous  
- `subject_dnb_capabilities` — miroir DB des capacités Python  
- `curriculum_versions` — `FR_3E_2027_V1`  
- `program_product_links` — BREVET/2027 → FR-CYCLE4-3E (`curriculum_source`)  
- `content_migration_classifications` — traçabilité par contenu  

---

## Langues

Anglais / Espagnol : **KEEP**, `assessment_role=continuous`, hors parcours terminal UX (Phase 1). Données et 12 contenus 3e conservés.

---

## Écarts connus (non bloquants Phase 2)

1. **TECHNOLOGY** : 0 chapitre / 0 production FR-3E (dette contenu).  
2. Relations `prior_grade_remediation` / `exam_preparation` encore à 0 — à alimenter Phase 3.  
3. Curriculum auteur sur `FR-CYCLE4-3E` ; programme examen `BREVET/2027` relié (pas de déplacement destructif des chapitres).

---

## Tests

```text
pytest tests/test_lcai_0031_phase2_migration.py tests/test_dnb_config_0031.py tests/test_curriculum_selectors.py
→ 19 passed
```

---

## Fichiers

**Créés**
- `migrations/v2/027_dnb_product_classification.sql`
- `scripts/lcai_0031_phase2_inventory.py`
- `tests/test_lcai_0031_phase2_migration.py`
- `docs/phase6/LCAI-0031/LCAI-0031_DATA_MIGRATION_REPORT.md`
- `docs/phase6/LCAI-0031/exports/LCAI-0031_PHASE2_CONTENT_INVENTORY.json`

**Modifiés**
- `infrastructure/repositories/unified_experience.py` (`grade_levels` via `product_role`)

---

## Verdict Phase 2

```text
PHASE 2 READY — données classifiées, aucune destruction ; enchaîner Phase 3 (moteur pédagogique)
```
