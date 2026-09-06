# LCAI-0033 — DATABASE STATE

Generated: 2026-09-06T16:58:41Z

## A. Executive facts

| Indicateur | Valeur |
|---|---:|
| Exercices/contenus totaux | 1981 |
| Contenus jouables | 1981 |
| Matières DNB couvertes | 9 |
| Compétences 3e totales | 78 |
| Compétences sans exercice | 0 |
| Compétences avec >=20 exercices | 78 |
| Compétences avec >=40 exercices | 13 |
| Annales officielles enregistrées | 64 |
| Questions officielles | 3 |
| Exercices dérivés d'annales | 492 |
| Exercices IA | 0 |
| Provenance inconnue | 0 |
| Doublons exacts | 0 |
| Quasi-doublons | 361 |
| Contenus non jouables | 0 |
| Supports manquants | 0 |
| Références Éduscol traçables | 64 |

## B. Bases trouvées

- Inventory rows: see `LCAI-0033_DATA_SOURCE_INVENTORY.csv`
- Note: LCAI-0032 referential already present in `objectif_brevet_2027.duckdb` (audit after 0031+0032).

## C. Base runtime

Proven chain:
1. `ui/unified_app.py` / `core/database.py` → `core.config.get_database_path()` → `data/objectif_brevet_2027.duckdb` (auth + brevet content)
2. V2 pedagogy → `core.config.get_v2_database_path()` → `data/learning_coach_v2.duckdb`
3. Env overrides: LCAI_DATABASE_PATH=None, LCAI_V2_DATABASE_PATH=None
4. Resolved OB: `C:\Users\Utilisateur\Documents\App_AILearning\Learning-Coach-AI\data\objectif_brevet_2027.duckdb`
5. Resolved V2: `C:\Users\Utilisateur\Documents\App_AILearning\Learning-Coach-AI\data\learning_coach_v2.duckdb`

### Audit copies

```json
{
  "objectif_brevet": {
    "source": "data/objectif_brevet_2027.duckdb",
    "copy": "artifacts/LCAI-0033/objectif_brevet_2027_AUDIT_COPY.duckdb",
    "source_sha256": "1d68e49907ac30ddf6a9e18429297c961d90f2ca9857bbdab77d75b45b05fd20",
    "copy_sha256": "1d68e49907ac30ddf6a9e18429297c961d90f2ca9857bbdab77d75b45b05fd20",
    "source_size": 29110272,
    "copy_size": 29110272,
    "sha_match": true
  },
  "learning_coach_v2": {
    "source": "data/learning_coach_v2.duckdb",
    "copy": "artifacts/LCAI-0033/learning_coach_v2_AUDIT_COPY.duckdb",
    "source_sha256": "e2b9826fab629c4094d27b8cf4168a6a88a361bfc183df5d832e4cc5f731724d",
    "copy_sha256": "e2b9826fab629c4094d27b8cf4168a6a88a361bfc183df5d832e4cc5f731724d",
    "source_size": 241184768,
    "copy_size": 241184768,
    "sha_match": true
  },
  "anonymized_sha256": "5da12fe50c6a8ac44ac96d8a605da590d7a46c67b661ea31bbc3e1610c3c9fa1",
  "anonymized_size": 29110272
}
```

## D. Schéma
See `LCAI-0033_DATABASE_SCHEMA.md`, CSV inventories, `LCAI-0033_SCHEMA_DUMP.sql`.

## E. Volume

- OB content_items: 1981
- OB skills/chapters/archives: 78/78/64
- OB users/practice_attempts: 11/97
- V2 exercises/questions/skills/learners/attempts: 3202/3202/1227/7/77

## F. Couverture matière

- EMC: total=122 playable=122 official=0 derived=30 ai=0 legacy=92
- FRENCH: total=313 playable=313 official=0 derived=79 ai=0 legacy=234
- GEOGRAPHY: total=180 playable=180 official=0 derived=45 ai=0 legacy=135
- HISTORY: total=262 playable=262 official=0 derived=65 ai=0 legacy=197
- MATHEMATICS: total=485 playable=485 official=3 derived=117 ai=0 legacy=365
- ORAL: total=30 playable=30 official=0 derived=8 ai=0 legacy=0
- PHYSICS_CHEMISTRY: total=232 playable=232 official=0 derived=59 ai=0 legacy=173
- SVT: total=233 playable=233 official=0 derived=59 ai=0 legacy=174
- TECHNOLOGY: total=124 playable=124 official=0 derived=30 ai=0 legacy=94

## G. Couverture compétence

Histogram playable per skill (global): {'20-29': 51, '40+': 13, '30-39': 14}

## H. Annales

Registered archives: 64; parsed/linked questions: 3

## I. Éduscol
See `LCAI-0033_EDUSCOL_SOURCE_AUDIT.md`.

## J. Exercices fondés sur annales

OFFICIAL_ARCHIVE=3 ARCHIVE_DERIVED=492 (derivations table rows=0)

## K. IA

AI_GENERATED in OB catalog: 0. Runtime homework AI fill persists to V2 with source ai_runtime_fallback (not AI_GENERATED enum).

## L. Legacy

LEGACY_BANK dominates OB catalog; Python banks under subjects/ and revision_3e_enrichie/subjects/.

## M. Doublons

Exact fingerprint groups: 0; near semantic groups: 361

## N. Non jouables

Flagged rows: 0

## O. Supports

content_assets rows: 0 (missing asset files: N/A if zero assets required)

## P. Capacité devoirs
See `LCAI-0033_HOMEWORK_CAPACITY.csv`.

## Q. Capacité révisions
Skill coverage_status via §26 thresholds in CONTENT_BY_SKILL.

## R. Compatibilité 2027

Distribution curriculum_2027_compatible: {'TRUE': 1950, 'REVIEW': 31}

## S. Risques

- Annales DISCOVERED without bulk PDF parse → official question count near-zero
- Dual catalog (V2 exercises vs OB content_items) not fully unified in homework
- content_derivations empty despite ARCHIVE_DERIVED labels (label without parent FK)

## T. Gaps pour LCAI-0032

Note: LCAI-0032 already executed. Remaining gaps = PDF ingest, derivation links, Technologie depth, V2↔OB homework wiring, AI_GENERATED tagging.

## Verdicts

```text
DATABASE STRUCTURE:
PASS

3E CURRICULUM COVERAGE:
PARTIAL

DNB ARCHIVE GROUNDING:
PARTIAL

REVISION CONTENT CAPACITY:
PASS

AUDIT PACKAGE:
PASS
```

`READY FOR EXTERNAL REVIEW`


Cursor verdict: **READY FOR REVIEW**
