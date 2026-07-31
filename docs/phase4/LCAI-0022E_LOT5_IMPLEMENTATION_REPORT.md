# LCAI-0022E — Lot 5 : Filtre scolaire central (sécurité mineurs)

## Statut

**READY FOR REVIEW**

## Objectif

Centraliser et renforcer le filtrage des contenus sensibles / détresse / injection pour les mineurs, en réutilisant le strangler pattern (pas de second stack).

## Décisions

1. **Package** `services/school_safety/` : `classify` + `filter_text` + canaux `user` / `assistant` / `content` / `stt` (prêt Lot 6).
2. **Catalogue élargi** : détresse, contenus adultes/violence/drogues/exploitation, jailbreaks — en plus des patterns VT historiques.
3. **VT** : `PedagogicalGuardrails` délègue la sécurité mineurs au filtre ; anti-triche pédagogique reste local.
4. **Content Factory** : `CandidateValidator` refuse les candidats avec `school_safety_blocked`.
5. **TTS** : synthèse bloquée si texte filtré (`SAFETY_BLOCKED`) — préparation vocale Lot 6.
6. **Pas d’auto-approbation** de contenu ; lifecycle Draft inchangé.

## Fichiers

| Fichier | Action |
|---------|--------|
| `services/school_safety/*` | Créé |
| `services/virtual_teacher/pedagogical_guardrails.py` | Délégation |
| `services/virtual_teacher/ai_teacher_service.py` | Filtre TTS |
| `services/content/factory.py` | Validation scolaire |
| `ui/virtual_teacher.py` | Message `SAFETY_BLOCKED` |
| `tests/test_school_safety_0022e.py` | Créé |
| `docs/phase4/LCAI-0022E_LOT5_IMPLEMENTATION_REPORT.md` | Créé |
| `docs/phase4/README.md` | Lot 5 terminé |

## Tests

```text
pytest tests/test_school_safety_0022e.py tests/test_virtual_teacher_0017.py -q
```

## Limites résiduelles

- Mode vocal STT → filtre → TTS (Lot 6) : canal `stt` prêt, pipeline non branché.
- Pas de ML / modération cloud : filtre déterministe regex uniquement.
- Faux positifs possibles sur certains termes disciplinaires (ex. « arme » en histoire) — affinage futur possible via allowlist curriculum.

## Verdict

**READY FOR REVIEW**
