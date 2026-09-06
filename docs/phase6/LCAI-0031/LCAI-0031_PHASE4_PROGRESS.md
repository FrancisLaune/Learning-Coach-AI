# LCAI-0031 — Phase 4 Progress Report (Brevet)

**Statut :** PHASE 4 COMPLETE (fondation formats / annales / blancs / oral)  
**Date :** 2026-09-06  
**Commit/push :** non (interdit ticket)

---

## Livré

| Brique | Détail |
|--------|--------|
| Templates | Maths (automatismes sans calc + raisonnement), Français, HG-EMC, Sciences 2/3, Oral |
| `build_brevet_exam` | Modes `OFFICIAL_ARCHIVE`, `BREVET_STYLE`, `ADAPTIVE_BREVET`, `MOCK_EXAM` |
| Brevet blanc global | 4 écrits ± oral |
| Annales | Métadonnées de provenance (`OFFICIAL_*` ≠ `GENERATED_MOCK`) + seeds 2026 |
| Garde-fou IA | Impossible de marquer un contenu IA comme officiel |
| Oral | Parcours étapes + questions jury (5 types) |
| Migration 029 | `brevet_exam_templates`, `exam_archives*`, `brevet_mock_exams`, `oral_projects`, `oral_simulations` |
| Façade | `services.dnb.brevet_exam` / `mock_brevet_session` / `oral_project` |

---

## Distinction produit

- **Devoir personnalisé** ≠ **Sujet Brevet** (format d'épreuve, pas d'indices live).  
- **Annale officielle** ≠ **sujet généré / blanc**.  
- Sciences : les 3 disciplines restent préparées ; l'épreuve en tire **2**.

---

## Non livré (suite)

- Ingestion PDF/questions d'annales (pipeline séparé, pas de scraping runtime)  
- Exécution Streamlit complète Sujet/Blanc/Oral  
- Correction rédaction / oral par critères détaillés en séance  
- Contenu Technologie 3e toujours manquant (dette curriculum)

---

## Tests

```text
pytest tests/test_lcai_0031_phase4_brevet.py tests/test_lcai_0031_phase3_engine.py
→ 17 passed
```

---

## Verdict Phase 4

```text
PHASE 4 READY — enchaîner Phase 5 (Professeur IA Coach Brevet)
```
