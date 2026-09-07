# LCAI-0038 Test Report

Suite: `tests/test_lcai_0038_curriculum_tree.py`

| Test | Intent |
|---|---|
| `test_normalize_and_overlap` | Normalisation / overlap sémantique |
| `test_extraction_layers` | Extraction matières/domaines/chapitres/compétences |
| `test_orphan_and_duplicate_detection_run` | Orphelins + doublons |
| `test_content_and_official_coverage_fields` | Compteurs contenu / archive |
| `test_tree_ordering_stable` | Ordre déterministe |
| `test_read_only_hash_unchanged` | Aucune mutation DB |
| `test_math_verdict_not_complete_with_known_gaps` | Maths INCOMPLETE + gap Trigonométrie |

Commande: `python -m pytest tests/test_lcai_0038_curriculum_tree.py -q`
Résultat attendu: **7 passed**
