# LCAI-0032 — Archive Import Report

**Manifest :** `data/dnb_archive_manifest.json`  
**Autorité :** Éduscol — hub DNB  

## Découverte

| Années | Zones | Matières clés | Entrées |
|--------|-------|---------------|---------|
| 2018,2019,2021–2026 | métropole, centres_étrangers | Maths, Français, HG-EMC, Sciences | 64 |

Statut initial des entrées : **DISCOVERED** (URLs hub, PDF à télécharger hors runtime).

## Import

- Pipeline : `ingest_dnb_archive` — **pas de scraping Streamlit**  
- Avec `local_text` : segmentation paragraphes → `OFFICIAL_ARCHIVE` + `RESERVED_FOR_MOCK` + compat `REVIEW`  
- Dedup logique : `year+session+zone+series+subject+base_exam_identifier`  
- Variantes accessibles PDF : non comptées comme sujets distincts (même `base_exam_identifier`)

## Limites restantes

- Téléchargement / parsing PDF Éduscol non automatisé dans ce ticket (offline manuel puis `local_text`)  
- Mapping compétence fin des annales officielles : à enrichir lors de l’ingestion PDF  
- Session 2020 absente volontairement
