# LCAI-0032 — Test Report

```text
pytest tests/test_lcai_0032_referential.py -q
→ 8 passed
```

Couverture tests :

- migrations idempotentes  
- curriculum + volume contenu (≥1000 items, ≥70 skills)  
- pas d’orphelin publié (hors OFFICIAL_ARCHIVE)  
- seuils couverture §19  
- `search_exercises` sans filtre difficulté bloquant  
- manifest + ingest local annales  

Date : 2026-09-06
