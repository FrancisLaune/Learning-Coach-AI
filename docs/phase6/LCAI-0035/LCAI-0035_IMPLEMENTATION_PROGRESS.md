# LCAI-0035 — Ingestion massive annales officielles DNB Éduscol 2018–2026

## État

**READY FOR REVIEW** (données produites ; compatibilité 2027 reste `REVIEW` humaine)

## Baseline → Après

| Indicateur | Avant (0034) | Après (0035) |
|---|---:|---:|
| Questions `OFFICIAL_ARCHIVE` | 3 | **1098** |
| Documents PDF enregistrés | 0 | **97** |
| Documents parsés/importés | 0 | **97** |
| `ARCHIVE_DERIVED_WITHOUT_PARENT` | 0 | **0** |
| Ingestion PDF Éduscol | PARTIAL | **exécutée offline** |

## Pipeline

```bash
python scripts/ingest_dnb_archives.py --years 2018:2026
```

Options : `--download-only`, `--parse-only`, `--map-only`, `--validate-only`, `--resume`, `--force`, `--dry-run`, `--report`, `--include-accessibility`, `--rebuild-catalog`.

Runtime Streamlit : **jamais** d'ingestion réseau.

## Artifacts

- `data/dnb_eduscol_document_catalog.json`
- `data/dnb_archive_manifest.json` (V2)
- `artifacts/LCAI-0035/pdfs/`
- `artifacts/LCAI-0035/LCAI-0035_INGEST_SUMMARY.json`
- `artifacts/LCAI-0035/LCAI-0035_ARCHIVE_COVERAGE_BY_*.csv`
- Backup OB : `artifacts/LCAI-0035/backups/`

## Migrations

- `012_lcai_0035_ingestion.sql`
- `013_lcai_0035_indexes.sql`
- `014_lcai_0035_coverage_views.sql`

## Limites restantes (validation humaine / métier)

1. **Compatibilité DNB 2027** : toutes les questions officielles restent `REVIEW` (pas d'auto-APPROVED).
2. **Couverture sciences / HG** plus faible que français/maths selon les PDF STANDARD trouvés.
3. **2018–2022** : corpus enrichi mais non exhaustif (hub Éduscol HTML bloqué Cloudflare ; découverte via `/document/<id>/download` + inventaires locaux).
4. **Segmentation** heuristique (Exercice/Question) — QCM maths parfois regroupés ; revue humaine souhaitable.
5. **Corrigés officiels** : non massivement liés (`correction_source=NONE` par défaut).
6. **Variantes accessibilité** téléchargeables avec `--include-accessibility` mais dédupliquées hors run STANDARD.
7. Pas de génération massive de dérivés IA (interdit avant corpus officiel — respecté).

## Verdict technique

- `official_question_count > 3` : **PASS**
- invariant orphelins 0034 : **PASS**
- provenance inventée : **NON** (URL officielles + hash SHA-256)
- DoD produit de données : **PASS partiel** (corpus exploitable ; validation pédagogique humaine ouverte)
