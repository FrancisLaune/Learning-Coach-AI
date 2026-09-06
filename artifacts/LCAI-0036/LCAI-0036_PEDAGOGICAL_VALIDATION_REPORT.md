# LCAI-0036 — Pedagogical Validation Report

## Avant / Après

| Indicateur | Avant 0036 | Après |
|---|---:|---:|
| OFFICIAL_ARCHIVE | 1098 | 1098 |
| VALIDATED | 0 | 0 |
| AUTO_CHECKED | 0 | 2 |
| REVIEW | 1098 | 1093 |
| REJECTED | 0 | 3 |
| Compatible 2027 TRUE | 0 | 0 |
| Compatible REVIEW | 1098 | 972 |
| Compatible FALSE | 0 | 126 |
| Jouables certifiées 2027 | 0 | 0 |
| Reliability A | 0 | 0 |
| Reliability B | 0 | 2 |
| Reliability C | 0 | 567 |
| Reliability D | 0 | 529 |

## Principes appliqués

- Aucune validation massive aveugle `REVIEW → VALIDATED`
- Aucun `curriculum_2027_compatible = TRUE` automatique (confirmation humaine requise)
- Les 3 placeholders 2024 (`Question A/B/C`) sont `REJECTED` / `FALSE`
- Les questions incertaines restent `REVIEW`
- `ARCHIVE_DERIVED_WITHOUT_PARENT = 0`

## 3 questions 2024 préexistantes

```json
[
  {
    "content_id": 1979,
    "validation_status": "REJECTED",
    "compat": "FALSE",
    "reason": "INCOMPLETE_CONTEXT",
    "warnings": "PLACEHOLDER_STATEMENT"
  },
  {
    "content_id": 1980,
    "validation_status": "REJECTED",
    "compat": "FALSE",
    "reason": "INCOMPLETE_CONTEXT",
    "warnings": "PLACEHOLDER_STATEMENT"
  },
  {
    "content_id": 1981,
    "validation_status": "REJECTED",
    "compat": "FALSE",
    "reason": "INCOMPLETE_CONTEXT",
    "warnings": "PLACEHOLDER_STATEMENT"
  }
]
```

## Verdicts

OFFICIAL QUESTION AUDIT: PASS
SEGMENTATION VALIDATION: PARTIAL
SUBJECT CLASSIFICATION: PARTIAL
SKILL MAPPING VALIDATION: PARTIAL
DNB 2027 COMPATIBILITY: PARTIAL
ASSET QUALITY: PARTIAL
OFFICIAL CORRECTION COVERAGE: PARTIAL
PEDAGOGICAL RELIABILITY: PASS
CERTIFIED COVERAGE: PARTIAL
ARCHIVE TRACEABILITY: PASS
CANONICAL REPOSITORY: PASS
NON-REGRESSION: PASS
REVIEW PACKAGE: PASS

READY FOR REVIEW
