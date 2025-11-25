# Guide de Test Multi-Sources - DisruptIQ

## 🎯 Objectif

Valider l'architecture complète du système multi-agents de DisruptIQ avec tous les agents et sources d'information disponibles.

## 📊 Architecture Testée

```
                    ┌─────────────────────┐
                    │   User Interface    │
                    │  (localhost:3000)   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   API Gateway       │
                    │  /api/chat/ask      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Orchestrator      │
                    │  (Multi-Agent)      │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┬──────────────┐
            │                  │                  │              │
    ┌───────▼────────┐ ┌──────▼──────┐ ┌────────▼──────┐ ┌────▼─────────┐
    │   RAG Agent    │ │  SQL Agent  │ │  Web Agent    │ │ Legal Agent  │
    │                │ │             │ │               │ │              │
    │ - Verification │ │ - Database  │ │ - Brave API   │ │ - Analysis   │
    │ - Reflection   │ │ - Queries   │ │ - Web Search  │ │ - Legifrance │
    │ - Qdrant       │ │ - PostgreSQL│ │ - Current     │ │ - Advice     │
    └────────────────┘ └─────────────┘ └───────────────┘ └──────────────┘
```

## 🧪 Suites de Tests

### 1. RAG Agent (Solo) - 3 tests

Tests de l'agent RAG avec l'architecture Agentic à 3 niveaux:
- **Standard RAG** (baseline)
- **+ Verification Agent** (si score < 40%)
- **+ Reflection Agent** (si score < 25%)

**Tests:**
- `R1`: Vocabulary mismatch - "Quelle société gère le contrat de nettoyage ?"
  - Attendu: Verification activé, score final >80%
- `R2`: Information fragmentée - "Règles balcons règlement copropriété"
  - Attendu: Verification activé, score final >40%
- `R3`: Out of scope - "Entretien espaces verts"
  - Attendu: Reflection activé, fallback message, score ~15%

### 2. SQL Agent (Solo) - 2 tests

Tests des requêtes SQL sur la base PostgreSQL:

**Tests:**
- `S1`: Comptage documents - "Combien de documents avons-nous ?"
  - Attendu: Requête SQL correcte, résultat numérique
- `S2`: Recherche par vendor - "Documents liés au vendeur ID 1"
  - Attendu: Filtrage SQL correct, liste documents

### 3. Web/Internet Agent (Solo) - 2 tests

Tests de recherche web via Brave API:

**Tests:**
- `W1`: Actualité législative - "Dernières actualités loi ELAN 2024"
  - Attendu: Sources web récentes, liens valides
- `W2`: Information publique - "Taux légal pénalités retard 2024 France"
  - Attendu: Réponse factuelle avec sources

### 4. Legal Agent (Solo) - 3 tests

Tests de l'agent juridique avec accès LegalFrance API:

**Tests:**
- `L1`: Jurisprudence - "Jurisprudence assemblées générales copropriété"
  - Attendu: Cas de jurisprudence officiels (Legifrance), citations lois
- `L2`: Conseil juridique - "Obligations travaux rénovation énergétique"
  - Attendu: Analyse juridique avec références légales (Loi Climat 2021)
- `L3`: Recherche loi - "Loi Climat 2021 passoires thermiques"
  - Attendu: Contenu loi avec articles pertinents

### 5. Legal Agent (Combiné) - 2 tests

Tests du Legal Agent en combinaison avec d'autres sources:

**Tests:**
- `LC1`: Legal + RAG - "Analyser règlement copropriété conformité loi ELAN"
  - Attendu: Analyse document + vérification conformité légale
- `LC2`: Legal + Web - "Évolutions jurisprudentielles charges copropriété"
  - Attendu: Fusion jurisprudence officielle + actualités web

### 6. Multi-Source Fusion - 2 tests

Tests de fusion de plusieurs sources d'information:

**Tests:**
- `M1`: RAG + SQL + Web - "Résumer documents + obligations syndic"
  - Attendu: 3 agents activés, synthèse cohérente
- `M2`: ALL sources - "Droits et obligations copropriétaire + exemples + lois"
  - Attendu: 4 agents activés, réponse exhaustive avec citations

### 7. Context Awareness - 1 test (3 tours)

Test de la gestion du contexte conversationnel:

**Test `C1`: Conversation multi-tours**
1. "Quelle société gère le contrat de nettoyage ?"
2. "Combien coûte ce contrat ?" ← référence contextuelle
3. "Est-ce conforme avec la loi sur les marchés publics ?" ← contexte + juridique

**Attendu:**
- Référence au contexte ("ce contrat" = contrat NEC)
- Continuité de la conversation
- Agents adaptés à chaque tour

### 8. Baseline (Auto-routing) - 1 test

Test de routing automatique sans sélection de sources:

**Tests:**
- `B1`: Routing automatique - "Différence loi ELAN vs loi Climat"
  - Attendu: Orchestrator choisit Legal + Web automatiquement

## 📋 Validation des Réponses

Chaque test valide automatiquement:

### ✅ Critères généraux
1. **Réponse non vide** (>50 caractères)
2. **Agents attendus utilisés** (routing correct)
3. **Format Markdown** (présence ##, **, -, *)

### ✅ Critères spécifiques RAG
4. **Sources présentes** (si attendu)
5. **Seuil de confidence** (>X% selon test)
6. **Références [1][2]** (citations sources)

### ✅ Critères spécifiques Legal
7. **Citations légales** (loi, article, décret, jurisprudence)
8. **Sources Legifrance** (API officielle)
9. **Disclaimer juridique** (conseil informatif)

### ✅ Critères contexte
10. **Références conversation** (ce, cette, précédemment)
11. **Continuité logique** (réponses cohérentes)

## 🚀 Exécution des Tests

### Via Docker (Recommandé)

```bash
cd backend
docker-compose exec backend python test_multi_source_system.py
```

### Localement

```bash
cd backend
python test_multi_source_system.py
```

### Durée attendue
- **Total**: ~5-10 minutes
- RAG tests: ~1-2 min (Verification/Reflection activés)
- SQL tests: ~30s
- Web tests: ~1 min
- Legal tests (solo): ~2 min (API Legifrance)
- Legal tests (combiné): ~1-2 min
- Multi-source: ~2-3 min (fusion multiple)
- Context: ~2 min (3 tours)

## 📊 Résultats

### Format de sortie

```
================================================================================
TEST [R1]: RAG - Vocabulary Mismatch (Verification should activate)
Query: Quelle société gère le contrat de nettoyage ?
Sources: ['rag']
--------------------------------------------------------------------------------

✅ RESPONSE RECEIVED:
   Agents used: ['rag_agent']
   Sources count: 3
   Confidence: 89.2%
   Response length: 450 chars
   Response preview: La société NEC PLUS gère le contrat de nettoyage...

📊 VALIDATION:
   ✅ Response not empty
   ✅ Expected agents used
   ✅ Has sources
   ✅ Confidence >= 80%
   ✅ Markdown formatted
   ✅ Source references [1][2]

🎉 TEST PASSED
```

### Rapport final

```
################################################################################
                         GLOBAL TEST SUMMARY
################################################################################

📊 RESULTS:
   Total tests: 16
   ✅ Passed: 14 (87.5%)
   ❌ Failed: 2 (12.5%)

❌ FAILED TESTS:
   - [L1] Legal - Jurisprudence search SOLO
     Error: Legifrance API not configured

################################################################################
          🎉 MOST TESTS PASSED - MINOR ISSUES TO ADDRESS
################################################################################
```

### Fichier de résultats

Les résultats détaillés sont sauvegardés dans:
```
backend/test_multi_source_results.json
```

Format JSON avec tous les détails de chaque test.

## 🔍 Monitoring Pendant les Tests

### Logs backend en temps réel

```bash
docker-compose logs -f backend | grep -E "(verification|reflection|legal|orchestrator)"
```

**Logs attendus:**
```
verification_agent_activated reason=low_confidence top_score=0.047
verification_passed final_confidence=89.2%
reflection_agent_activated reason=low_quality_after_verification
failure_diagnosed failure_type=vocabulary_mismatch
strategy_selected strategy=query_expansion
legal_agent_activated query="jurisprudence assemblées générales"
legifrance_api_queried query="assemblées générales copropriété"
```

### Logs Qdrant

```bash
docker-compose logs -f qdrant | tail -20
```

### Logs PostgreSQL

```bash
docker-compose logs -f db | tail -20
```

## 🛠️ Configuration Requise

### Variables d'environnement

```env
# RAG (Qdrant)
QDRANT_HOST=localhost
QDRANT_PORT=6333

# SQL (PostgreSQL)
DATABASE_URL=postgresql://user:pass@db:5432/disruptiq

# Web (Brave API)
BRAVE_API_KEY=your_brave_api_key

# Legal (Legifrance API - optionnel)
LEGIFRANCE_CLIENT_ID=your_client_id
LEGIFRANCE_CLIENT_SECRET=your_client_secret
```

**Note:** Si `LEGIFRANCE_CLIENT_ID` n'est pas configuré, les tests Legal utiliseront uniquement RAG + Web search comme fallback.

## 🐛 Debug des Tests

### Test individuel

Pour tester un seul endpoint:

```bash
curl -X POST http://localhost:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Quelle société gère le contrat de nettoyage ?",
    "selected_sources": ["rag"],
    "conversation_history": []
  }'
```

### Test avec contexte

```bash
curl -X POST http://localhost:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Combien coûte ce contrat ?",
    "selected_sources": ["rag"],
    "session_id": "test_session",
    "conversation_history": [
      {"role": "user", "content": "Quelle société gère le contrat de nettoyage ?"},
      {"role": "assistant", "content": "La société NEC PLUS gère le contrat..."}
    ]
  }'
```

### Vérifier Qdrant

```bash
curl http://localhost:6333/collections
```

### Vérifier PostgreSQL

```bash
docker-compose exec db psql -U disruptiq -d disruptiq -c "SELECT COUNT(*) FROM documents;"
```

## 📈 Métriques de Performance

### Latence attendue (par agent)

| Agent | Solo | Avec agents | Multi-source |
|-------|------|-------------|--------------|
| **RAG** | 2-3s | 5-8s (Verification) | 3-5s |
| **SQL** | 0.5-1s | N/A | 1-2s |
| **Web** | 1-2s | N/A | 2-3s |
| **Legal** | 2-3s | 4-6s (Legifrance) | 3-5s |
| **Multi (3+)** | N/A | N/A | 8-12s |

### Critères de succès

- ✅ **Tests Passed**: ≥80% (12/16 minimum)
- ✅ **RAG avec agents**: Score final ≥40% (vs <15% sans agents)
- ✅ **Legal API**: Connexion Legifrance fonctionnelle (ou fallback graceful)
- ✅ **Context**: Références contextuelles détectées dans conversation
- ✅ **Markdown**: Format structuré avec ## et citations [1]
- ✅ **Latence P90**: <15s pour multi-source fusion

## 🎯 Tests Manuels UI (Post-Automatisation)

Après validation des tests automatisés, tester via l'UI (localhost:3000):

### Test 1: RAG seul
1. Ouvrir http://localhost:3000
2. Cocher uniquement "RAG"
3. Poser: "Quelle société gère le contrat de nettoyage ?"
4. Vérifier: Réponse "NEC PLUS", sources visibles, confidence >80%

### Test 2: Legal seul
1. Cocher uniquement "Legal"
2. Poser: "Trouve-moi la jurisprudence sur les assemblées générales"
3. Vérifier: Cas Legifrance affichés avec citations

### Test 3: Tous activés
1. Cocher RAG + SQL + Web + Legal
2. Poser: "Quels sont mes droits en tant que copropriétaire ? Donne exemples concrets"
3. Vérifier: Fusion des 4 sources, réponse exhaustive

### Test 4: Context
1. Cocher RAG
2. Tour 1: "Quelle société gère le contrat de nettoyage ?"
3. Tour 2 (sans clear): "Combien coûte ce contrat ?"
4. Vérifier: Répond à propos du contrat NEC (contexte maintenu)

### Test 5: Aucune source
1. Décocher toutes les sources
2. Poser: "Quelle est la différence entre loi ELAN et loi Climat ?"
3. Vérifier: Orchestrator route automatiquement vers Legal + Web

## ✅ Checklist de Validation Finale

- [ ] **Tous les tests automatisés passent** (≥80%)
- [ ] **RAG Agents fonctionnent** (Verification + Reflection)
- [ ] **SQL queries retournent résultats**
- [ ] **Web search retourne sources valides**
- [ ] **Legal API accessible** (ou fallback graceful)
- [ ] **Multi-source fusion cohérente**
- [ ] **Context conversationnel maintenu**
- [ ] **Format Markdown structuré**
- [ ] **Citations sources présentes [1][2]**
- [ ] **Latence acceptable** (<15s P90)
- [ ] **Tests UI manuels validés**
- [ ] **Logs backend propres** (pas d'erreurs critiques)
- [ ] **UX fluide et responsive**

## 🚀 Prêt pour Production

Si tous les critères ci-dessus sont validés:

🎉 **Le système multi-sources DisruptIQ est prêt pour production!**

---

**Dernière mise à jour:** 2025-11-25
**Version:** 1.0.0
**Status:** ✅ Tests automatisés implémentés + Guide complet
