# LCAI-0022 — Lot 0 : Gap analysis Master Book IA ↔ code

## Statut

**READY FOR REVIEW** — document de cadrage, sans modification runtime.

## Objectif

Comparer le `MASTER BOOK IA .docx` (vision IA-First V2) à l’architecture et au code Learning Coach AI au 2026-07-31, puis proposer un backlog d’implémentation respectueux des couches existantes.

## Sources

| Source | Rôle |
|--------|------|
| `docs/Master/MASTER BOOK IA .docx` | Vision, architecture, règles, vocal, UX, roadmap |
| `docs/Master/LEARNING_COACH_AI_MASTER_BOOK_VOLUME_*.docx` | Volumes 1–5 (complément) |
| `docs/phase3/*` | Livrables Phase 3 (0015–0021) |
| Code `services/`, `application/`, `infrastructure/`, `ui/` | État d’implémentation |

## Verdict exécutif

Le Master Book décrit un **Professeur IA chef d’orchestre**. Le dépôt possède déjà la majorité des **organes** (moteurs déterministes) et une **ébauche du cerveau** (virtual teacher + pedagogical intelligence + student guidance), mais pas encore l’**orchestration unifiée** du cycle Accueil → Diagnostic → Planification → Devoir → Séance → Analyse → Révision.

| Domaine Master Book | Couverture estimée | Commentaire |
|---------------------|--------------------|-------------|
| 7 moteurs pédagogiques | ~80 % | Présents sous d’autres noms / modules |
| Professeur IA (conversation) | ~50 % | LCAI-0017 V1 opérationnel, pas encore orchestrateur de séance |
| Cycle pédagogique 8 étapes | ~35 % | Étapes dispersées, non enchaînées |
| 3 modes (IA / Compagnon / Manuel) | ~20 % | Feature flags et manuel partiels ; modes non formalisés |
| Bandeau UI Professeur IA | ~15 % | Écrans dédiés VT / guidance, pas de bandeau fixe global |
| Mode vocal scolaire sécurisé | ~15 % | TTS partiel ; STT + filtre scolaire + pipeline absents |
| Sécurité mineurs / invariants | ~40 % | Guardrails VT + auth ; filtre scolaire central manquant |
| Journal de décisions IA | ~20 % | Events VT / PI partiels ; pas de decision log unifié |
| IA-Next / IA-Pro / IA-Studio | 0 % | Hors Phase 4 Core |

---

## 1. Cartographie Master Book → code existant

### 1.1 Couches techniques (Chapitre 17)

| Couche Master Book | Emplacement actuel | Écart |
|--------------------|--------------------|-------|
| UI/UX Layer | `ui/unified_app.py`, `ui/v2_experience.py`, `ui/virtual_teacher.py`, `ui/student_guidance.py` | Pas de bandeau Professeur IA fixe sur tous les écrans élève |
| AI Orchestration Layer | `services/virtual_teacher/*`, `services/student_guidance/*`, `services/pedagogical_intelligence/*` | Pas d’orchestrateur unique du workflow 8 étapes |
| Pedagogical Engines Layer | Voir §1.2 | Noms et frontières à documenter, pas à recréer |
| Data & Safety Layer | DuckDB V2, `migrations/v2`, auth, guardrails VT | Filtre scolaire central + journal décisions à renforcer |

### 1.2 Les 7 moteurs (Chapitre 5)

| Moteur Master Book | Module(s) existants | Statut | Action Phase 4 |
|--------------------|---------------------|--------|----------------|
| Curriculum Engine | `services/curriculum`, repositories curriculum, catalog | **Présent** | Réutiliser ; exposer via orchestrateur |
| Content Factory | `services/content/*`, `services/homework/completion.py`, runtime persistence | **Présent** | Réutiliser ; ne pas dupliquer LCAI-0018B |
| Learning Engine (séances) | `services/learning_session/*`, `unified_session_execution.py` | **Présent** | Brancher pause/reprise déjà corrigés |
| Assessment Engine | `services/learning_session/assessment.py` | **Présent** | Conserver déterminisme + format FR décimaux |
| Mastery Engine | `services/learning/learning_engine_service.py` | **Présent** | Réutiliser ; cache idempotent déjà corrigé |
| Recommendation Engine | `services/recommendation/*`, PI `recommendation_service.py`, homework `exercise_selection.py` | **Présent** | Unifier l’appel depuis orchestrateur |
| Dashboard Engine | `services/learning_session/experience.py`, PI `dashboard_service.py`, `student_guidance` | **Partiel** | Fusionner la vue « accueil intelligent » |

### 1.3 Professeur IA (Chapitres 2, 4, 7, 8)

| Capacité Master Book | Code actuel | Statut | Écart |
|----------------------|-------------|--------|-------|
| Accueil personnalisé | `student_guidance` welcome | Partiel | Pas toujours piloté par diagnostic du jour |
| Diagnostic | `AdaptiveDiagnosticService`, PI platform | Présent | Non déclenché systématiquement en entrée de séance |
| Planification (temps, objectifs) | homework form + recommendation | Partiel | Pas d’adaptation « temps disponible » unifiée |
| Création devoir | `HomeworkService`, LCAI-0021 selection, AI completion B7 | Présent | Pas encore « décidé par Professeur IA » de bout en bout |
| Séance (indices, relances) | session execution + VT pendant exercice | Partiel | Relances / adaptation live limitées |
| Analyse post-exercice | assessment + mastery + post_session_refresh | Présent | Explications élève via guidance ; pas de bandeau unifié |
| Révision | mastery + recommendation + guidance revision | Partiel | Cycle révision espacée non orchestré |
| Préparation prochaine séance | PI refresh, recommendation | Partiel | Pas de « programme du lendemain » explicite |
| Conversation / aide | `AITeacherService`, orchestrator, guardrails | Présent (0017) | Mode Compagnon vs Professeur non séparé |
| États (écoute / réflexion / parole) | UI VT partielle | Manquant | Requis pour bandeau + vocal |
| Préférences parent | `AITeacherPreferencesService`, `feature_enabled` | Présent | À étendre aux 3 modes |

### 1.4 Modes de fonctionnement (Chapitre 1.3)

| Mode Master Book | Aujourd’hui | Cible Phase 4 Lot 2 |
|------------------|-------------|---------------------|
| Mode 1 — Professeur IA activé | VT activable + devoirs/séance V2 | Mode par défaut si `feature_enabled` ; orchestre le cycle |
| Mode 2 — Compagnon IA | Non distinct | Conversation / aide sans modifier planning ni notes |
| Mode 3 — Manuel | Devoirs manuels + catalogue | Conservé ; IA ponctuelle optionnelle |

### 1.5 Mode vocal (Chapitres 10, 14–16)

| Élément | Statut | Écart |
|---------|--------|-------|
| TTS | `tts_service.py` (console / disabled / synthèses) | Voix productives à industrialiser |
| STT | Absent | Nouveau composant Phase B |
| Filtre scolaire vocal | Absent (guardrails texte seulement) | Pipeline STT → filtre → IA → TTS |
| Bandeau vocal UX | Absent | Spec Master Book chap. 16 |
| Exercices 100 % vocaux | Absent | IA-Voice+ / hors Core |

### 1.6 Sécurité mineurs & invariants (Chapitres 6, 11)

| Règle Master Book | Couverture | Écart |
|-------------------|------------|-------|
| Aucune invention de note | Assessment déterministe | OK — à verrouiller dans orchestrateur |
| Aucune décision non tracée | Events VT / PI partiels | Decision log unifié manquant |
| Contenu hors curriculum interdit | Curriculum + guardrails | Filtre central à formaliser |
| Contenu généré non auto-approuvé | Draft / approval lifecycle | OK — conserver |
| Parent contrôle IA | `feature_enabled`, locks | OK — étendre aux modes |
| Sujets sensibles / détresse | Guardrails VT | À renforcer et centraliser |

### 1.7 UI/UX (Chapitre 18)

| Écran Master Book | Existe ? | Commentaire |
|-------------------|----------|-------------|
| Accueil + message IA | Partiel | Dashboard élève + guidance |
| Diagnostic | Partiel | PI / diagnostic services, UX à unifier |
| Séance | Oui | `v2_experience.session_screen` |
| Correction | Partiel | Feedback post-réponse |
| Synthèse | Partiel | Summary + guidance result |
| Tableau de bord | Partiel | Dashboard + PI |
| Bandeau fixe Professeur IA | Non | Lot 2 |

---

## 2. Ce qu’il ne faut PAS faire

1. Recréer un Learning Engine, Content Factory ou schéma DuckDB parallèle.
2. Contourner les repositories depuis Streamlit.
3. Auto-approuver du contenu généré.
4. Implémenter IA-Pro / IA-Studio avant IA-First Core.
5. Remplacer Streamlit par une nouvelle UI tant que le runtime V2 n’est pas orchestré.
6. Coder des pourcentages de panachage en dur hors stratégie configurable (déjà traité LCAI-0021).

---

## 3. Backlog Phase 4 — Phase A (IA-First Core)

### Lot 0 — Gap analysis *(ce document)*
- Livrable : mapping + backlog
- Critère : revue humaine OK

### Lot 1 — Orchestrateur Professeur IA Core — **LCAI-0022A** (proposé)
**But :** un service d’application qui enchaîne les moteurs existants.

```text
ProfesseurIAOrchestrator
  → StudentGuidance (accueil)
  → AdaptiveDiagnostic / PI
  → HomeworkExerciseSelection + HomeworkService (+ AI completion si déficit)
  → UnifiedSessionExecution
  → LearningEngine / Assessment
  → PostSessionPedagogicalRefresh
  → Guidance (synthèse / révision)
```

**Fichiers cibles (indicatif) :**
- `services/professor_ai/` (nouveau package orchestration)
- `application/experience_factory.py` (composition)
- tests `tests/test_professor_ai_orchestrator_0022a.py`

**Hors scope Lot 1 :** vocal, bandeau complet, IA-Next.

### Lot 2 — Bandeau + 3 modes — **LCAI-0022B**
- Bandeau supérieur (avatar, état, message, actions)
- Modes Professeur / Compagnon / Manuel (feature flags + préférences parent)
- Pas de modification des notes en mode Compagnon

### Lot 3 — Cycle séance guidée — **LCAI-0022C**
- Parcours UX Accueil → Diagnostic → Devoir proposé → Séance → Synthèse
- Réutiliser écrans existants ; navigation unifiée

### Lot 4 — Invariants + journal de décisions — **LCAI-0022D**
- Table / événements `ai_decision_log` (migration additive)
- Traçabilité : élève, objectif, candidats, exclusions, déficit, justification
- Interdiction explicite de mutation directe des scores

### Lot 5 — Sécurité mineurs renforcée — **LCAI-0022E**
- Filtre scolaire central (texte, puis prêt pour vocal)
- Harmonisation guardrails VT + contenu

### Lot 6 — Mode vocal scolaire sécurisé — **LCAI-0023** (Phase B)
- STT → filtre → Professeur IA → TTS
- Spec UX bandeau vocal
- Après stabilisation Core

---

## 4. Alignement roadmap Master Book

| Phase Master Book | Lots Phase 4 | Priorité |
|-------------------|--------------|----------|
| Phase 1 — IA-First Core | Lots 1–5 | **Immédiat** |
| Phase 2 — IA-Voice | Lot 6 | Après Core |
| Phase 3 — IA-Next | Tickets futurs | Après Voice |
| Phase 4 — IA-Pro | Hors scope court terme | Plus tard |
| Phase 5 — IA-Studio | Hors scope court terme | Plus tard |

---

## 5. Dépendances techniques déjà livrées (ne pas retravailler)

| Ticket | Apport pour Phase 4 |
|--------|---------------------|
| LCAI-0017 | Professeur virtuel V1, préférences, guardrails |
| LCAI-0018 / B5 / B7 | Devoirs + complément IA strict |
| LCAI-0019 | Pedagogical Intelligence |
| LCAI-0020 | Student guidance |
| LCAI-0021 | Sélection devoirs sans filtre bloquant difficulté |
| Fixes session récents | Pause synchronisée, Decimal FR, cache learning |

---

## 6. Risques

| Risque | Mitigation |
|--------|------------|
| Orchestrateur qui duplique les services | Façade mince ; appels uniquement aux services existants |
| UX Streamlit saturée | Bandeau progressif ; un écran = une action |
| Coût LLM | Deterministic fallback déjà présent ; quotas parent |
| Coupures WiFi pendant longs lots | Cloud Agents optionnels ; lots petits |
| Contenu généré non validé exposé | Lifecycle Draft / Approved inchangé |

---

## 7. Critères d’acceptation du Lot 0

1. Répertoire `docs/phase4/` créé avec README.
2. Mapping Master Book ↔ code documenté.
3. Écarts classés (présent / partiel / manquant).
4. Backlog Lots 1–6 proposé avec ordre.
5. Interdits d’implémentation listés.
6. Aucune modification runtime dans ce lot.
7. Prêt pour démarrer Lot 1 après validation humaine.

---

## 8. Prochaine action recommandée

Après validation humaine de ce Lot 0 :

1. Ouvrir le ticket **LCAI-0022A — Orchestrateur Professeur IA Core**.
2. Spécifier l’API publique de l’orchestrateur (entrées / sorties / idempotence).
3. Implémenter avec tests ciblés, sans vocal.

---

## 9. Fichiers de ce lot

| Fichier | Action |
|---------|--------|
| `docs/phase4/README.md` | Créé |
| `docs/phase4/LCAI-0022_LOT0_GAP_ANALYSIS_MASTER_BOOK_IA.md` | Créé |

## Verdict

**READY FOR REVIEW**
