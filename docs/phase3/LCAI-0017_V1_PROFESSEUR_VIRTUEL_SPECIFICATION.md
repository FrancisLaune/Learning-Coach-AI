# LCAI-0017 — Professeur virtuel V1

**Spécification fonctionnelle et technique unifiée**  
**Version du document :** 1.1 — Phase 3 (alignement LCAI-0015A)  
**Statut :** Référence officielle pour implémentation — documentation uniquement

---

## Journal des modifications

### LCAI-0015A ALIGNMENT UPDATE (2026-07-28)

- `child_id` remplacé par `learner_id` (identité pédagogique V2 `learners.id`)
- Table typée `virtual_teacher_preferences` confirmée (pas de store key/value générique)
- Champ `feature_enabled` ajouté (activation Parent sans suppression des préférences)
- Noms de services IA standardisés (`AITeacherService`, `AITeacherPreferencesService`, `AIConversationOrchestrator`)
- AI Teacher confirmé comme **service applicatif**, jamais comme rôle d'authentification
- Exigence d'un `learner_id` V2 résolu — pas de contournement legacy
- Autorisation au niveau service clarifiée (`AuthRole`, `parent_owns_learner`, gardes)
- Propriété Parent/Élève des préférences et comportement `parent_locked` documentés
- `teacher_name` clarifié (affichage uniquement, pas identité)
- Critères d'acceptation et plan de tests étendus
- Dépendance LCAI-0015A formalisée
- Périmètre V1 préservé (hors périmètre inchangé)

---

## Prérequis — Dépendance LCAI-0015A

LCAI-0017 **dépend de** :

- LCAI-0015A Authentication (Parent/Student login, PBKDF2, recovery)
- Routage des rôles Parent / Student (`AuthRole`)
- Validation de session contre la base (`session_user_still_valid`)
- Autorisation `parent_owns_learner`
- Liens tuteur V2 (`learner_guardian_links`)
- Isolation inter-familles
- Contenus pédagogiques publiés
- Identités apprenant V2 (`learners`)

**Règle explicite :** LCAI-0017 doit **réutiliser** le système d'authentification et d'autorisation existant. Il ne doit **pas** introduire un second système d'identité.

---

## 1. Vision et objectifs

Le Professeur virtuel V1 est un **assistant pédagogique** intégré à Learning Coach AI. Il aide l'élève à comprendre une notion, à progresser dans un exercice et à recevoir une explication adaptée à son niveau. Il ne remplace pas un enseignant humain et ne devient pas un chatbot généraliste.

### 1.1 Objectifs prioritaires

- Explications simples, structurées, adaptées au niveau scolaire
- Aide sans réponse finale immédiate
- Réutilisation du référentiel de compétences et contenus publiés
- Choix professeur homme/femme et voix masculine/féminine
- Personnalité modérée et bienveillante
- Cadre pédagogique strict et protection des mineurs
- Livraison rapide, extensible (V2/V3)

### 1.2 Principes de conception

| Principe | Application |
|---|---|
| Simple | Un écran de conversation, peu de réglages |
| Pédagogique | Indice puis explication |
| Personnalisé | Niveau, matière, prénom, ton, voix, profil |
| Sécurisé | Filtrage, contrôle Parent, pas de données sensibles |
| Traçable | Conversations et événements à rétention maîtrisée |
| Réutilisable | Services découplés de Streamlit |

---

## 2. Périmètre V1 et hors périmètre

### 2.1 Inclus V1

- Accès depuis le tableau de bord Élève (Student Dashboard)
- Profil professeur statique homme/femme
- Prénom (`teacher_name`) depuis liste validée
- Voix masculine/féminine chaleureuse (TTS à la demande)
- Ton : calme, encourageant, scolaire
- Chat textuel contextualisé (matière, chapitre, compétence, exercice)
- Aide graduée (guidage, indice, explication, exemple)
- Modération et sécurité enfant
- Préférences typées par `learner_id` (`virtual_teacher_preferences`)
- Contrôle Parent : `feature_enabled`, verrouillage, niveau d'aide
- Historique court de séance + résumé pédagogique

### 2.2 Hors périmètre V1 (confirmé)

Sauf approbation explicite ultérieure, **restent hors V1** :

- Rôle d'authentification AI Teacher
- Avatar 3D animé / synchronisation labiale temps réel
- Mémoire conversationnelle longue illimitée
- Actions autonomes en arrière-plan
- Équipe multi-agents enseignants
- Rôles humains école/enseignant (login)
- Framework de préférences générique key/value
- Reconnaissance vocale (STT) — **V2**
- Profilage émotionnel avancé — **V3**
- Remplacement du moteur adaptatif existant
- Orchestration multi-LLM automatique
- Paiement / abonnement / boutique de voix

**V2 prévu :** STT, avatar animé, mémoire, personnalité adaptive  
**V3 prévu :** plusieurs enseignants, multi-agent, adaptation émotionnelle, mémoire pédagogique longue

---

## 3. Expérience utilisateur

### 3.1 Parcours Élève (Student)

1. Connexion compte enfant (`AuthRole.STUDENT`)
2. Résolution obligatoire de `learner_id` V2 via `users.learner_external_ref`
3. Redirection tableau de bord Élève
4. Ouverture « Mon professeur virtuel » (si `feature_enabled = true`)
5. Choix professeur/voix/ton si autorisé (`parent_locked = false`)
6. Conversation + audio optionnel
7. Résumé pédagogique de fin de séance

Si `learner_id` non résolu → message clair non technique, pas d'accès au professeur.

### 3.2 Parcours Parent

- Activer/désactiver via `feature_enabled` pour chaque `learner_id` lié
- Verrouiller préférences (`parent_locked`)
- Configurer niveau d'aide, longueur des réponses
- Consulter indicateurs synthétiques
- Réinitialiser préférences
- Demander suppression historique conversationnel

---

## 4. Personnalisation du professeur

### 4.1 Profils (`teacher_profile`)

| Code | Présentation | Ton défaut | Avatar |
|---|---|---|---|
| `TEACHER_FEMALE_01` | Professeure chaleureuse | Encourageant | Illustration féminine statique |
| `TEACHER_MALE_01` | Professeur calme | Calme | Illustration masculine statique |

### 4.2 Paramètres V1

| Paramètre | Valeurs | Contrôle |
|---|---|---|
| `teacher_profile` | `TEACHER_FEMALE_01`, `TEACHER_MALE_01` | Parent ; Élève si déverrouillé |
| `teacher_name` | Liste validée (Emma, Léa, Lucas, Hugo…) | Parent ; Élève si déverrouillé |
| `voice_id` | `warm_female`, `warm_male` | Parent ; Élève si déverrouillé |
| `tone` | `calm`, `encouraging`, `academic` | Parent ; Élève si déverrouillé |
| `response_length` | `short`, `normal`, `detailed` | Parent ; Élève si déverrouillé |
| `help_level` | `light`, `normal`, `reinforced` (ou entier 1–3) | Parent |
| `audio_enabled` | booléen | Parent ; Élève si déverrouillé |
| `feature_enabled` | booléen | **Parent uniquement** |
| `parent_locked` | booléen | **Parent uniquement** |

### 4.3 `teacher_name`

- Nom d'affichage convivial, **séparé** de `teacher_profile`
- Optionnel ou valeur par défaut
- Sanitisé, longueur bornée
- **Aucun effet** sur authentification ou autorisation
- **Ne remplace pas** `teacher_profile` et n'est pas une identité base de données

---

## 5. AUTHENTICATION AND ROLE ARCHITECTURE

Le Professeur virtuel est un **service applicatif**. Il ne doit **jamais** être implémenté comme un rôle d'authentification.

### 5.1 Rôles d'authentification actuels

Définis dans `services/auth/roles.py` (`AuthRole`) :

- `parent`
- `student`

**Ne pas créer :**

- `ai_teacher` dans `AuthRole`
- Compte utilisateur AI Teacher (`users`)
- Login / mot de passe AI Teacher
- Session autonome AI possédant des données apprenant
- Données apprenant « possédées » par l'IA

### 5.2 Comportement Student

- Utilise le professeur virtuel **uniquement** pour son propre `learner_id` résolu
- Lit/modifie uniquement les préférences autorisées
- Ne peut pas contourner `parent_locked`
- Accès refusé si `feature_enabled = false`
- Ne peut pas accéder à un autre `learner_id`

### 5.3 Comportement Parent

- Configure le professeur **uniquement** pour les `learner_id` liés (`parent_owns_learner`)
- Peut activer/désactiver `feature_enabled`
- Peut verrouiller les préférences protégées
- Ne peut pas accéder aux apprenants hors périmètre familial

### 5.4 Mécanismes d'autorisation réutilisés

- `AuthRole` + session authentifiée (`st.session_state.user`)
- `session_user_still_valid()` (rôle revalidé en base)
- `users.learner_external_ref` → résolution `learner_id` V2
- `parent_owns_learner()` + `learner_guardian_links`
- `require_parent_role()` / `require_student_role()`
- Gardes au **niveau service** (pas seulement UI Streamlit)
- Isolation inter-familles

### 5.5 Exigence `learner_id` V2 résolu

**Prérequis obligatoire :** le Professeur virtuel V1 exige un `learner_id` V2 valide et résolu.

| Situation | Comportement |
|---|---|
| Student login sans `learner_external_ref` / sans enregistrement V2 | Erreur contrôlée, message UI clair |
| Parent cible un `learner_id` non lié | Refus autorisation |
| Tentative création préférence sans `learner_id` | Refus |
| Legacy sans contournement | **Pas de fallback** non sécurisé |

**Tests négatifs requis :** identité non résolue → erreur contrôlée.

### 5.6 Propriété des préférences

**Contrôlés par le Parent (toujours) :**

- `feature_enabled`
- `parent_locked`
- Tous les champs ci-dessus lorsque `parent_locked = true`

**Modifiables par l'Élève uniquement si `parent_locked = false` :**

- `teacher_profile`, `teacher_name`, `voice_id`, `tone`, `response_length`, `help_level`, `audio_enabled`

La couche service (`AITeacherPreferencesService`) détermine les permissions d'édition. Ne pas s'appuyer uniquement sur des champs Streamlit désactivés.

### 5.7 `feature_enabled`

- Permet au Parent d'activer/désactiver le professeur pour un apprenant lié
- **Défaut V1 recommandé :** `false` (activation explicite Parent) ou `true` selon politique produit — **à figer en implémentation**
- Student : accès refusé si `false`
- Désactivation **ne supprime pas** préférences ni historique
- **Ne remplace pas** l'autorisation (double vérification service + rôle)

---

## 6. Architecture fonctionnelle

| Composant | Responsabilité |
|---|---|
| Virtual Teacher UI | Avatar statique, chat, audio, actions rapides |
| **AITeacherPreferencesService** | Préférences typées par `learner_id`, verrouillages |
| **AIConversationOrchestrator** | Contexte pédagogique + appel LLM |
| **PedagogicalGuardrails** | Indice d'abord, modération, sécurité |
| **TTSService** | Synthèse vocale à la demande |
| VirtualTeacherRepository | Sessions, messages, résumés, événements |

### 6.1 Flux principal

1. UI transmet question + `learner_id` + contexte
2. **Autorisation service** (rôle, ownership, `feature_enabled`, `learner_id` résolu)
3. Si échec → **aucun** appel LLM ni TTS
4. `AIConversationOrchestrator` charge préférences + contexte
5. `PedagogicalGuardrails` prépare et valide
6. LLM → réponse structurée → validation → affichage
7. TTS optionnel si autorisé
8. Persistance session / événements

---

## 7. Architecture technique

### 7.1 Organisation recommandée

```
services/virtual_teacher/
  ai_teacher_service.py              # AITeacherService
  ai_teacher_preferences_service.py  # AITeacherPreferencesService
  ai_conversation_orchestrator.py    # AIConversationOrchestrator
  pedagogical_guardrails.py          # PedagogicalGuardrails
  tts_service.py                     # TTSService
  schemas.py
infrastructure/repositories/
  virtual_teacher_repository.py
ui/
  pages/virtual_teacher_page.py
  components/teacher_avatar.py
  components/teacher_chat.py
prompts/
  virtual_teacher_system.md
tests/
  test_ai_teacher_service.py
  test_ai_teacher_preferences_service.py
  test_ai_conversation_orchestrator.py
  test_pedagogical_guardrails.py
  test_virtual_teacher_authorization.py
  test_virtual_teacher_ui.py
```

### 7.2 Interfaces principales

| Service | Méthodes V1 |
|---|---|
| **AITeacherService** | `start_session()`, `answer()`, `end_session()` |
| **AITeacherPreferencesService** | `get_preferences()`, `save_preferences()`, `enforce_parent_lock()`, `can_student_edit()` |
| **AIConversationOrchestrator** | `build_context()`, `generate_answer()` |
| **PedagogicalGuardrails** | `classify_request()`, `apply_help_policy()`, `validate_response()` |
| **TTSService** | `synthesize()`, `list_available_voices()` |
| **VirtualTeacherRepository** | `create_session()`, `append_message()`, `save_summary()` |

**Note de nommage :** les noms `AITeacherService`, `AITeacherPreferencesService`, `AIConversationOrchestrator` rendent explicite la frontière IA. Aucun conflit avec une convention existante du projet.

### 7.3 Réponse structurée

```json
{
  "message": "Texte principal",
  "response_type": "HINT | EXPLANATION | EXAMPLE | REDIRECTION | SAFETY",
  "suggested_actions": ["Donne-moi un indice"],
  "skill_code": "optionnel",
  "confidence": 0.0,
  "audio_allowed": true
}
```

---

## 8. Modèle de données

Le modèle réutilise les tables existantes (utilisateurs V1, `learners` V2, compétences, exercices, sessions). Convention du projet : **tables typées par domaine**, pas de store key/value générique.

### 8.1 Table `virtual_teacher_preferences`

**Une ligne active par apprenant en V1** (`UNIQUE (learner_id)`).

| Champ | Type (indicatif) | Description |
|---|---|---|
| `id` | BIGINT PK | Séquence V2 (`global_entity_id_seq`) |
| `learner_id` | BIGINT NOT NULL FK → `learners(id)` | Identité pédagogique canonique |
| `teacher_profile` | VARCHAR NOT NULL | Profil validé (`TEACHER_FEMALE_01`, …) |
| `teacher_name` | VARCHAR | Nom d'affichage (sanitisé) |
| `voice_id` | VARCHAR NOT NULL | `warm_female`, `warm_male` |
| `tone` | VARCHAR NOT NULL | Enum contrôlé |
| `response_length` | VARCHAR NOT NULL | Enum contrôlé |
| `help_level` | INTEGER NOT NULL | Plage validée (ex. 1–3) |
| `audio_enabled` | BOOLEAN NOT NULL | Lecture audio |
| `feature_enabled` | BOOLEAN NOT NULL | Activation Parent |
| `parent_locked` | BOOLEAN NOT NULL | Verrouillage Parent |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | |

**Contraintes :**

- FK `learner_id` → `learners(id)` — pas de préférence orpheline
- Pas de référence à un compte AI Teacher
- Pas de FK directe vers `users.id` (sauf métadonnées d'audit optionnelles ailleurs)
- Valeurs par défaut sensées à définir en migration
- Enums / CHECK pour `tone`, `response_length`, `teacher_profile`, `voice_id`

### 8.2 Exemple SQL (architectural — adapter en implémentation)

```sql
CREATE TABLE virtual_teacher_preferences (
    id BIGINT PRIMARY KEY DEFAULT nextval('global_entity_id_seq'),
    learner_id BIGINT NOT NULL,
    teacher_profile VARCHAR NOT NULL,
    teacher_name VARCHAR,
    voice_id VARCHAR NOT NULL,
    tone VARCHAR NOT NULL,
    response_length VARCHAR NOT NULL,
    help_level INTEGER NOT NULL CHECK (help_level BETWEEN 1 AND 3),
    audio_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    feature_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    parent_locked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_virtual_teacher_preferences_learner
        FOREIGN KEY (learner_id) REFERENCES learners(id),

    CONSTRAINT uq_virtual_teacher_preferences_learner
        UNIQUE (learner_id)
);
```

**Ne pas créer cette migration lors de la mise à jour documentaire.**

### 8.3 Tables complémentaires V1

| Table | Clé apprenant | Rôle |
|---|---|---|
| `virtual_teacher_sessions` | `learner_id` | Séance pédagogique |
| `virtual_teacher_messages` | via `session_id` | Historique court |
| `virtual_teacher_summaries` | via `session_id` | Résumé fin de séance |
| `virtual_teacher_events` | `learner_id` | Audit / métriques |

Remplacer toute occurrence historique de `child_id` par `learner_id` dans schémas, repositories, services, tests et critères d'acceptation.

### 8.4 Règles de conservation

- Échanges minimaux nécessaires à la séance et au suivi
- Rétention configurable
- Suppression demandée par le Parent
- Jamais de mot de passe, jeton ou secret dans les messages
- Résumé pédagogique privilégié vs verbatim long

---

## 9. Intégration authentification (résumé)

| Rôle auth | Droits Virtual Teacher |
|---|---|
| `student` | Utiliser pour son `learner_id` ; éditer préférences non verrouillées |
| `parent` | Configurer apprenants liés ; `feature_enabled` ; verrouillage |
| Non connecté | Aucun accès |
| Autre famille | Aucun accès |

---

## 10. Critères d'acceptation

### 10.1 Fonctionnels (existants + alignés)

| ID | Critère |
|---|---|
| AC-01 | Élève authentifié ouvre le professeur depuis son tableau de bord |
| AC-02 | Profil et voix conservés entre sessions |
| AC-03 | Parent peut verrouiller les préférences |
| AC-04 | Réponse adaptée au niveau |
| AC-05 | Depuis exercice : pas de réponse finale immédiate |
| AC-06 | Audio avec voix choisie |
| AC-07 | Panne TTS n'empêche pas le texte |
| AC-08 | Hors périmètre redirigé |
| AC-09 | Isolation inter-familles |
| AC-10 | Parent peut désactiver (`feature_enabled`) |
| AC-11 | Résumé pédagogique de séance |
| AC-12 | Pas de régression tableaux de bord |

### 10.2 Authentification

- AI Teacher **absent** de `AuthRole`
- Pas de login, mot de passe ou ligne `users` AI Teacher
- Actions Student limitées à son `learner_id` résolu
- Actions Parent limitées aux `learner_id` liés
- Accès inter-familles rejeté
- Identité apprenant inconnue/non résolue → rejet sécurisé

### 10.3 Préférences

- Stockage dans `virtual_teacher_preferences`
- Clé : `learner_id`
- Une ligne V1 par apprenant
- `feature_enabled = false` → accès refusé, préférences conservées
- `parent_locked` appliqué en service
- Student ne modifie pas les champs verrouillés
- Parent ne modifie pas un apprenant non lié

### 10.4 Services

- Service principal : **AITeacherService**
- Préférences : **AITeacherPreferencesService**
- Orchestration : **AIConversationOrchestrator**
- Autorisation évaluée **avant** tout appel LLM ou TTS

### 10.5 Sécurité

- Échec autorisation → **aucun** prompt LLM
- Échec autorisation → **aucune** requête TTS
- Pas de conversation persistée sans `learner_id` valide
- Pas de contournement legacy des gardes V2

---

## 11. Plan de tests (aligné LCAI-0015A)

| Test | Résultat attendu |
|---|---|
| Student accède avec son `learner_id` | PASS |
| Student tente un autre `learner_id` | DENIED |
| Parent configure apprenant lié | PASS |
| Parent configure apprenant non lié | DENIED |
| Student sans `learner_id` résolu | CONTROLLED ERROR |
| `feature_enabled = false` | Accès refusé |
| `feature_enabled = true` | Accès autorisé (si autres gardes OK) |
| `parent_locked = true` | Mise à jour Student refusée |
| `parent_locked = false` | Mise à jour Student permise acceptée |
| AI Teacher absent de `AuthRole` | PASS |
| Aucun compte user AI Teacher créé | PASS |
| Préférence avec `learner_id` invalide | Refus |
| Échec autorisation | Pas d'appel LLM |
| Échec autorisation | Pas d'appel TTS |
| Désactivation/réactivation `feature_enabled` | Préférences préservées |

---

## 12. Ticket exécutable Cursor (extrait aligné)

**LCAI-0017 — VIRTUAL TEACHER V1**

1. Auditer LCAI-0015A finalisé — ne pas dupliquer identité/session/LLM
2. Préférences typées par `learner_id` — champs complets incluant `feature_enabled`
3. Migration minimale : tables listées §8 — **FK `learners(id)`**
4. Services : `AITeacherService`, `AITeacherPreferencesService`, `AIConversationOrchestrator`, `PedagogicalGuardrails`, `TTSService`
5. Autorisation service : `AuthRole`, `parent_owns_learner`, `feature_enabled`, `learner_id` obligatoire
6. UI Streamlit tableau de bord Élève + contrôles Parent existants
7. Tests : voir §11
8. Rapport : `docs/phase3/LCAI-0017_VIRTUAL_TEACHER_V1_IMPLEMENTATION_REPORT.md`

**Ne pas implémenter avant validation de cette spécification alignée.**

---

## 13. Définition de terminé V1

La V1 est terminée lorsque tous les critères §10 sont validés, l'isolation familiale prouvée, les voix masculine/féminine fonctionnent, le Parent contrôle `feature_enabled` et les verrouillages, et la suite de tests du projet ne régresse pas.
