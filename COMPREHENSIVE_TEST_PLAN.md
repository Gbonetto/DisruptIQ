# 🧪 Plan de Tests Complets - Système Multi-Agent avec Context Store

**Date**: 2025-11-24
**Objectif**: Tester l'intelligence du système avec context_store, dual-intent, et coordination multi-agents
**Cible**: 100% de réussite sur tous les tests

---

## 📋 Structure des Tests

### Niveau 1: Tests Agents Individuels (Single Agent)
### Niveau 2: Tests Multi-Agents (Agent Coordination)
### Niveau 3: Tests Edge Cases (Intelligence Challenge)

---

## ✅ Niveau 1: Tests Agents Individuels

### Test 1.1: TRIGGER_WORKFLOW Seul - Urgence Simple
**Intent Attendu**: TRIGGER_WORKFLOW
**Agents Mobilisés**: WorkflowAgent V2
**Context Store**: Doit stocker workflow_data

**Message UI**:
```
URGENT: Fuite d'eau détectée dans l'appartement 12,
résidence Les Tilleuls, 3ème étage.
Propriétaire: M. Dupont (dupont@example.com, 06 12 34 56 78).
Eau coule du plafond, situation critique.
```

**Critères de Succès**:
- ✅ Intent classifié: TRIGGER_WORKFLOW
- ✅ To-do list générée avec 5-8 étapes
- ✅ Context extrait: building, apartment, owner, urgency
- ✅ Logs montrent: `workflow_context_stored`
- ✅ Message contient tous les détails de l'incident

**Vérification Logs**:
```bash
docker-compose logs -f backend | grep -E "(workflow_context_stored|workflow_agent_v2)"
```

**Score**: __/5

---

### Test 1.2: QUERY_DATA Seul - Recherche Professionnels
**Intent Attendu**: QUERY_DATA
**Agents Mobilisés**: HybridExecutor (SQL)
**Context Store**: Doit stocker sql_results si applicable

**Message UI**:
```
Donne-moi la liste de tous les plombiers avec leurs coordonnées
```

**Critères de Succès**:
- ✅ Intent classifié: QUERY_DATA
- ✅ SQL généré et exécuté
- ✅ Résultats affichés (nom, email, téléphone si disponible)
- ✅ Pas d'hallucination (seulement vraies données DB)
- ✅ Format lisible

**Vérification Logs**:
```bash
docker-compose logs -f backend | grep -E "(sql_query_generated|query_data)"
```

**Score**: __/5

---

### Test 1.3: SEND_EMAIL Seul - Email Contextuel
**Intent Attendu**: SEND_EMAIL
**Agents Mobilisés**: EmailAgent V2
**Context Store**: Doit lire workflow_data depuis previous message

**Setup**: Exécuter d'abord Test 1.1 pour avoir workflow dans context_store

**Message UI** (dans même session après Test 1.1):
```
Envoie un email aux plombiers pour les informer de cette urgence
```

**Critères de Succès**:
- ✅ Intent classifié: SEND_EMAIL
- ✅ Email généré avec contexte riche (pas générique)
- ✅ Objet contient "🚨 URGENT"
- ✅ Corps contient: résidence, appartement, propriétaire, contact
- ✅ Logs montrent: `workflow_context_retrieved_from_store`
- ✅ Email draft affiché pour validation

**Vérification Logs**:
```bash
docker-compose logs -f backend | grep -E "(workflow_context_retrieved|email_content_generated)"
```

**Score**: __/5

---

## ✅ Niveau 2: Tests Multi-Agents (Coordination)

### Test 2.1: WORKFLOW → EMAIL (Séquentiel, même conversation)
**Intent Séquence**: TRIGGER_WORKFLOW puis SEND_EMAIL
**Agents Mobilisés**: WorkflowAgent V2 → EmailAgent V2
**Test**: Context propagation via context_store

**Message 1**:
```
URGENT: Panne électrique totale au bâtiment B, résidence Park Avenue.
Concerne 24 appartements. Contact gardien: Jean Martin (martin@test.com, 06 11 22 33 44).
```

**Attendre réponse...**

**Message 2** (même session):
```
Rédige un email pour les électriciens certifiés
```

**Critères de Succès**:
- ✅ Message 1: Workflow to-do list générée
- ✅ Message 1: workflow_data stocké dans context_store
- ✅ Message 2: Email généré avec contexte du workflow
- ✅ Email contient: bâtiment B, 24 appartements, Park Avenue
- ✅ Email NOT generic ("Demande de devis..." ❌)
- ✅ Session_id transmis correctement

**Vérification Logs**:
```bash
# After message 1:
docker-compose logs backend | grep "workflow_context_stored"

# After message 2:
docker-compose logs backend | grep "workflow_context_retrieved_from_store"
```

**Score**: __/6

---

### Test 2.2: QUERY_DATA → SEND_EMAIL (Multi-étape intelligent)
**Intent Séquence**: QUERY_DATA puis SEND_EMAIL
**Agents Mobilisés**: SQLAgent → EmailAgent
**Test**: Utilisation résultats query pour destinataires email

**Message 1**:
```
Trouve tous les copropriétaires de l'étage 3
```

**Attendre réponse avec liste...**

**Message 2** (même session):
```
Envoie-leur un email pour les prévenir de travaux de plomberie prévus demain
```

**Critères de Succès**:
- ✅ Message 1: SQL exécuté, liste affichée
- ✅ Message 2: Email généré mentionnant travaux plomberie
- ✅ Destinataires pré-remplis depuis query précédente
- ✅ Email professionnel et contextualisé
- ✅ Pas de perte d'information entre les 2 messages

**Score**: __/5

---

### Test 2.3: Coordination Complexe (3 agents)
**Intent Séquence**: SEARCH_DOCUMENTS → QUERY_DATA → SEND_EMAIL
**Agents Mobilisés**: RAG → SQL → Email
**Test**: Multi-agent avec contexte accumulé

**Message 1**:
```
Cherche les documents sur le règlement de copropriété concernant les travaux
```

**Message 2**:
```
Qui sont les membres du conseil syndical?
```

**Message 3**:
```
Envoie-leur un email récapitulatif avec le règlement trouvé
```

**Critères de Succès**:
- ✅ Message 1: Documents trouvés par RAG
- ✅ Message 2: Membres conseil listés via SQL
- ✅ Message 3: Email avec contexte des 2 précédents
- ✅ Email mentionne règlement ET membres conseil
- ✅ Intelligence contextuelle maintenue

**Score**: __/5

---

## ✅ Niveau 3: Edge Cases (Intelligence Challenge)

### Test 3.1: Ambiguïté Intentionnelle
**Test**: Système doit demander clarification

**Message UI**:
```
Les plombiers
```

**Critères de Succès**:
- ✅ Système détecte ambiguïté (confidence < 0.7)
- ✅ Demande clarification: "Souhaitez-vous..."
- ✅ Propose options (liste plombiers vs contacter vs autre)
- ✅ Pas d'exécution hasardeuse

**Score**: __/4

---

### Test 3.2: Contexte Absent (Nouveau Session)
**Test**: Email sans workflow préalable dans nouvelle session

**Setup**: Nouvelle session (clear cookies ou incognito)

**Message UI**:
```
Envoie un email aux plombiers pour intervention urgente
```

**Critères de Succès**:
- ✅ Système détecte absence de contexte
- ✅ Email généré mais plus générique (normal)
- ✅ OU demande clarification sur détails manquants
- ✅ Pas de crash, gestion gracieuse
- ✅ Logs: `workflow_context_retrieved_from_store` absent

**Score**: __/5

---

### Test 3.3: Requête Composite (Dual Intent Implicite)
**Test**: Un seul message avec 2 actions

**Message UI**:
```
Urgence: Incendie détecté bâtiment C.
Crée le workflow ET envoie immédiatement email pompiers.
```

**Critères de Succès**:
- ✅ Workflow créé
- ✅ Email généré automatiquement (sans 2ème message)
- ✅ Email contextuel avec données workflow
- ✅ Ordre logique respecté (workflow before email)
- ✅ Logs montrent séquence coordonnée

**Note**: Ce test peut échouer si dual-intent pas encore activé (OK pour V1)

**Score**: __/5

---

### Test 3.4: Cascade d'Erreurs (Robustesse)
**Test**: Requête avec données manquantes

**Message UI**:
```
URGENT: Problème au bâtiment sans nom, appartement inconnu, propriétaire absent.
```

**Critères de Succès**:
- ✅ Workflow généré malgré données manquantes
- ✅ To-do list indique "À compléter" pour champs manquants
- ✅ Système NE hallucine PAS de fausses données
- ✅ Message d'avertissement sur données manquantes
- ✅ Reste fonctionnel

**Score**: __/5

---

### Test 3.5: Changement de Contexte Rapide
**Test**: Passer d'un workflow à un autre dans même session

**Message 1**:
```
URGENT: Dégât des eaux appartement 5
```

**Message 2** (immédiatement après):
```
URGENT: Incendie appartement 10
```

**Message 3**:
```
Envoie email pour l'incendie
```

**Critères de Succès**:
- ✅ 2 workflows créés séparément
- ✅ context_store mis à jour avec dernier workflow (incendie)
- ✅ Email Message 3 parle de INCENDIE (pas dégât eaux)
- ✅ Pas de confusion entre les 2 contextes
- ✅ Dernier contexte écrase précédent (TTL correct)

**Score**: __/5

---

### Test 3.6: Session Expirée (TTL Context Store)
**Test**: Vérifier TTL de 30min fonctionne

**Setup**: Difficile à tester en temps réel. Alternative: vérifier code

**Message 1**:
```
URGENT: Test workflow
```

**Attendre 31 minutes (ou modifier TTL à 1min pour test)...**

**Message 2**:
```
Envoie email pour cette urgence
```

**Critères de Succès**:
- ✅ Contexte expiré après TTL
- ✅ Email générique (contexte pas retrouvé)
- ✅ Logs montrent contexte expiré
- ✅ Pas de crash
- ✅ Système demande clarification ou génère email générique

**Note**: Test optionnel (nécessite modification TTL)

**Score**: __/5 (optionnel)

---

## 📊 Scoring Final

### Calcul du Score

**Niveau 1 (Single Agent)**: 15 points
- Test 1.1: __/5
- Test 1.2: __/5
- Test 1.3: __/5

**Niveau 2 (Multi-Agent)**: 16 points
- Test 2.1: __/6
- Test 2.2: __/5
- Test 2.3: __/5

**Niveau 3 (Edge Cases)**: 29 points (24 requis, 5 optionnel)
- Test 3.1: __/4
- Test 3.2: __/5
- Test 3.3: __/5
- Test 3.4: __/5
- Test 3.5: __/5
- Test 3.6: __/5 (optionnel)

**TOTAL**: __/60 points (sans 3.6) ou __/65 (avec 3.6)

**Objectif**: 100% = 60/60 (ou 65/65)

---

## 🐛 Template de Bug Report

Pour chaque test échoué, documenter:

```markdown
### Bug #X: [Titre Court]

**Test**: X.Y - [Nom Test]
**Symptôme**: [Ce qui s'est passé]
**Attendu**: [Ce qui devait se passer]
**Logs**:
```
[Logs pertinents]
```

**Root Cause**: [Si identifié]
**Fix**: [Solution appliquée]
**Retest Score**: __/Y
```

---

## 🔧 Commandes de Debug Utiles

### Monitoring en temps réel:
```bash
# Workflow context storage
docker-compose logs -f backend | grep "workflow_context_stored"

# Context retrieval
docker-compose logs -f backend | grep "workflow_context_retrieved"

# Intent classification
docker-compose logs -f backend | grep "intent_classification"

# Email generation
docker-compose logs -f backend | grep "email_content_generated"

# Errors
docker-compose logs -f backend | grep -E "(ERROR|error|failed)"
```

### Reset Context Store (si besoin):
```bash
docker-compose restart backend
```

### Check Health:
```bash
curl http://localhost:8000/health
```

---

## 📝 Instructions d'Exécution

1. **Ouvrir UI**: http://localhost:3000
2. **Nouvelle session** pour chaque groupe de tests (ou noter session_id)
3. **Exécuter tests dans l'ordre** (certains dépendent des précédents)
4. **Noter score immédiatement** après chaque test
5. **Copier logs pertinents** pour debugging
6. **Si test échoue**: Debug → Fix → Redémarrer backend → Retest
7. **Continuer jusqu'à 60/60** (ou 65/65)

---

## ✅ Checklist de Validation Finale

Avant de considérer 100% atteint:

- [ ] Tous les tests Niveau 1 passent (15/15)
- [ ] Tous les tests Niveau 2 passent (16/16)
- [ ] Tous les tests Niveau 3 requis passent (24/24)
- [ ] Context_store fonctionne (logs confirment)
- [ ] Pas de régression sur fonctionnalités existantes
- [ ] Emails générés sont riches et contextuels
- [ ] Workflows contiennent détails complets
- [ ] Aucun crash système observé
- [ ] Performance acceptable (<5s par requête)

---

**Bon courage! Let's get to 100%! 🚀**
