# LCAI-0032 — Database Audit

**Date :** 2026-09-06  
**Base cible :** `data/objectif_brevet_2027.duckdb`  
**Backup :** `data/backups/lcai_0032_20260906_175350/`

## État initial (avant ticket)

| Table legacy | Lignes |
|--------------|--------|
| users | 11 |
| exams | 4 |
| exam_questions | 45 |
| practice_attempts | 97 |
| learning_sessions | 0 |

WAL corrompu quarantiné (`objectif_brevet_2027.duckdb.wal.corrupt_backup_*`) pour rouverture.

## Anciennes SQLite

| Fichier | Exercices |
|---------|-----------|
| `revision_3e_enrichie/revision_3e.db` | 9 |
| `revision_3e_enrichie/objectif_brevet_2027.db` | 32 |

## Banques Python (`revision_3e_enrichie/subjects`)

8 matières terminales + chapitres (maths 15, français 11, …) — générateurs `generate_question` / `BANK`.

## État après LCAI-0032

| Entité | Quantité |
|--------|----------|
| curriculum `FR_3E_DNB_2027_V1` | 1 |
| skills actives | 78 |
| content_items | ~1978 |
| exam_archives_ref (manifest) | 64 |
| couverture | COMPLETE 65 / STRONG 13 |

## Sources content_items

- LEGACY_BANK ~1464  
- ARCHIVE_DERIVED ~492  
- CURATED ~22  

PDF officiels Éduscol : **manifestés** (DISCOVERED), import texte local possible via `ingest_dnb_archive(..., local_text=...)` — pas de scraping runtime.
