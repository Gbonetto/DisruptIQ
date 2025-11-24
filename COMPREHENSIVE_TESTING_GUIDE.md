# 🧪 GUIDE COMPLET - TESTS EXHAUSTIFS DISRUPTIQ

## 📋 Vue d'Ensemble

Cette suite de tests exhaustifs simule les **conditions réelles d'utilisation** par un syndic de copropriété, en testant:

✅ **TOUS les agents** individuellement et en cascade (10+ agents)
✅ **TOUTES les sources de données** : SQL, RAG, Web, seules et combinées
✅ **TOUS les use cases réels** d'un syndic (20+ scénarios métier)
✅ **Mémoire et conversations longues** (15+ échanges)
✅ **Utilisateurs concurrents** (5+ sessions simultanées)
✅ **UI-API parity** (cohérence endpoints)
✅ **Edge cases et sécurité** (injections, cas limites)
✅ **Performance sous charge** réelle

---

## 🎯 Objectifs des Tests

### Pourquoi ces tests ?

Le problème identifié : **les tests API passent, mais l'UI a des erreurs en production**.

Ces tests garantissent que :
1. ✅ Les agents fonctionnent **comme en production réelle**
2. ✅ Les sources de données sont **accessibles et fiables**
3. ✅ La mémoire contextuelle **fonctionne sur longue durée**
4. ✅ Le système **gère la charge** (utilisateurs concurrents)
5. ✅ **Aucune surprise** au déploiement production

---

## 📁 Structure des Tests

### 1️⃣ Tests Conditions Réelles Syndic
**Fichier:** `test_runner_real_world_exhaustive.py`
**Durée:** ~10 minutes
**Couverture:** 6 scénarios, 60+ tests

#### Scénarios inclus:

**S1 - Tous les Agents Individuellement (14 tests)**
- SQLAgent (3 tests) : résidents, professionnels, statistiques
- RAGService (2 tests) : règlements, contrats
- EmailAgent (2 tests) : urgence, devis
- WorkflowAgentV2 (2 tests) : urgence eau, travaux
- LegalAgent (2 tests) : délais AG, obligations
- WebAgent (2 tests) : actualités, prix marché
- Orchestrator (1 test) : question générale

**S2 - Toutes les Sources de Données (10 tests)**
- SQL only (3 tests)
- RAG only (2 tests)
- Web only (2 tests)
- SQL + RAG combo (1 test)
- SQL + Web combo (1 test)
- All sources (1 test)

**S3 - Use Cases Réels Syndic (5 use cases complets)**
- UC1: Urgence dégât des eaux (6 étapes : workflow → plombiers → emails → mémoire → synthèse)
- UC2: Organisation AG (5 étapes : setup → legal → copros → convocation → modification)
- UC3: Demande devis multiple (4 étapes : recherche → emails → prix marché → synthèse)
- UC4: Incident ascenseur (4 étapes : déclaration → technicien → emails résidents)
- UC5: Analyse contrat syndic (3 étapes : recherche → legal → conformité)

**S4 - UI-API Parity (8 tests comparatifs)**
- Compare `/api/chat/ask` (UI) vs `/api/assistant-v2/chat` (API)
- Vérifie même comportement, mêmes agents, résultats similaires

**S5 - Utilisateurs Concurrents (5 utilisateurs × 3 queries = 15 queries parallèles)**
- Simule 5 syndics utilisant le système simultanément
- Vérifie isolation des sessions
- Mesure throughput (queries/sec)

**S6 - Edge Cases & Robustesse (12 tests)**
- Input vide, ultra-long (5000 chars), caractères spéciaux
- **Sécurité:** SQL injection, XSS, Command injection
- Contradictions, requêtes impossibles, boucles infinies
- Unicode extrême, null bytes, données inexistantes

---

### 2️⃣ Tests Mémoire et Conversations Longues
**Fichier:** `test_long_conversation_memory.py`
**Durée:** ~5 minutes
**Couverture:** 3 scénarios mémoire

#### Scénarios inclus:

**S1 - Conversation Longue 15 Tours**
- Test conversation réaliste préparation AG sur 15 échanges
- **Rappels mémoire distants** : info du tour 1 rappelée au tour 12
- **Basculements contexte** : passage AG → règlement → retour AG
- Synthèse finale complète

**S2 - Context Store TTL**
- Phase 1: Stockage contexte workflow (urgence électrique)
- Phase 2: Rappel immédiat (<1min)
- Phase 3: Rappel après délai (toujours < TTL 30min)
- Vérifie persistance Redis

**S3 - Isolation Contextes Multiples**
- 3 sessions utilisateurs distinctes (Syndic A, B, C)
- Chaque syndic a contexte différent
- Vérifie qu'aucune "fuite" de contexte entre sessions

---

### 3️⃣ Tests API Ultra-Exhaustifs (Legacy)
**Fichier:** `test_runner_ultra_exhaustive.py`
**Durée:** ~5 minutes
**Couverture:** 4 scénarios API

Tests API purs sans simulation UI (déjà existant).

---

### 4️⃣ Script d'Exécution Global
**Fichier:** `run_all_comprehensive_tests.py`
**Durée:** ~20 minutes total

Lance les 3 suites de tests en séquence et génère rapport consolidé.

---

## 🚀 Exécution des Tests

### Prérequis

1. **Backend en cours d'exécution** :
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   # Ou via Docker:
   docker-compose up backend
   ```

2. **Base de données seeded** :
   ```bash
   # Vérifier que les données de test sont présentes
   psql -U postgres -d disruptiq -f seed_all_tables.sql
   ```

3. **Dependencies Python** :
   ```bash
   pip install httpx asyncio
   ```

---

### Option 1 : Exécuter TOUS les tests (Recommandé)

```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC2

python run_all_comprehensive_tests.py
```

**Sortie:**
- Rapport consolidé dans la console
- JSON détaillé : `test_results_comprehensive_all.json`
- Durée : ~20 minutes

---

### Option 2 : Exécuter une suite spécifique

#### Tests Conditions Réelles Syndic
```bash
python test_runner_real_world_exhaustive.py
```
**Rapport JSON:** `test_results_real_world_exhaustive.json`

#### Tests Mémoire
```bash
python test_long_conversation_memory.py
```
**Rapport JSON:** `test_results_long_conversation_memory.json`

#### Tests API Ultra-Exhaustifs
```bash
python test_runner_ultra_exhaustive.py
```
**Rapport JSON:** `test_results_ultra_exhaustive.json`

---

## 📊 Interprétation des Résultats

### Rapport Console

#### Exemple de sortie réussie:
```
📊 RAPPORT FINAL CONSOLIDÉ - TOUS LES TESTS
================================================================================

🎯 RÉSULTATS GLOBAUX:
   Test suites exécutées: 3
   ✅ Réussies: 3
   ❌ Échouées: 0
   Taux succès: 100.0%
   Durée totale: 18.5 minutes

📊 STATISTIQUES AGRÉGÉES:
   Total scénarios: 14
   Scénarios réussis: 14
   Taux succès scénarios: 100.0%
   Total tests individuels: 85
   Tests réussis: 84
   Taux succès tests: 98.8%

🚦 VERDICT FINAL:
   🟢🟢🟢 EXCELLENCE TOTALE
   ✅ Toutes les suites PASS
   ✅ 95%+ scénarios réussis
   🚀 DÉPLOIEMENT PRODUCTION IMMÉDIAT RECOMMANDÉ
```

### Niveaux de Succès

| Niveau | Suite Success | Scenario Success | Verdict |
|--------|--------------|------------------|---------|
| 🟢🟢🟢 Excellence | 100% | ≥95% | **GO Production immédiat** |
| 🟢🟢 Très Bon | ≥90% | ≥90% | GO Production après validation |
| 🟢 Bon | ≥75% | ≥80% | GO Staging |
| 🟡 Acceptable | ≥60% | ≥70% | Corrections avant staging |
| 🔴 Insuffisant | <60% | <70% | **NE PAS DÉPLOYER** |

---

### Rapports JSON Détaillés

Chaque suite génère un fichier JSON détaillé avec:

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "session_id": "real_world_test_1705315800",
  "backend_url": "http://localhost:8000",
  "scenarios": [
    {
      "scenario_id": "S1_ALL_AGENTS_INDIVIDUAL",
      "tests": [
        {
          "test": "sql_residents",
          "success": true,
          "duration": 3.2
        }
      ],
      "success_rate": 0.92,
      "overall_success": true,
      "duration": 45.6
    }
  ]
}
```

**Utilisation:**
```bash
# Voir taux de succès global
cat test_results_real_world_exhaustive.json | jq '.scenarios[].success_rate'

# Compter tests réussis
cat test_results_real_world_exhaustive.json | jq '[.scenarios[].tests[].success] | map(select(. == true)) | length'

# Trouver tests échoués
cat test_results_real_world_exhaustive.json | jq '.scenarios[].tests[] | select(.success == false)'
```

---

## 🔍 Debug et Diagnostics

### Si des tests échouent

#### 1. Vérifier le backend
```bash
curl http://localhost:8000/health
# Doit retourner: {"status": "healthy"}
```

#### 2. Vérifier les logs backend
```bash
# Dans le terminal du backend, chercher:
# - Erreurs 500
# - Timeouts
# - Erreurs de base de données
```

#### 3. Vérifier la base de données
```bash
psql -U postgres -d disruptiq -c "SELECT COUNT(*) FROM coproprietes;"
# Doit retourner: 5

psql -U postgres -d disruptiq -c "SELECT COUNT(*) FROM coproprietaires;"
# Doit retourner: 12

psql -U postgres -d disruptiq -c "SELECT COUNT(*) FROM professionnels;"
# Doit retourner: 67
```

#### 4. Tests spécifiques échoués

**Si "SQL Agent" échoue:**
```bash
# Vérifier que SQLAgent peut accéder à la DB
curl -X POST http://localhost:8000/api/assistant-v2/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Liste copropriétaires", "conversation_history": [], "session_id": "test"}'
```

**Si "RAG Service" échoue:**
```bash
# Vérifier Qdrant
curl http://localhost:6333/collections/disruptiq_documents
```

**Si "Web Agent" échoue:**
```bash
# Vérifier variables d'environnement
echo $BRAVE_SEARCH_API_KEY
echo $SERPER_API_KEY
```

**Si "Memory/Context" échoue:**
```bash
# Vérifier Redis
redis-cli ping
# Doit retourner: PONG

# Vérifier clés de session
redis-cli KEYS "context:*"
```

---

## 📈 Métriques de Performance Attendues

### Latences Typiques

| Agent/Operation | Latence Attendue | Acceptable | Problématique |
|----------------|------------------|------------|---------------|
| SQL Query | 2-5s | <10s | >15s |
| RAG Search | 3-8s | <12s | >20s |
| Email Generation | 5-10s | <15s | >25s |
| Workflow Creation | 4-8s | <12s | >20s |
| Legal Query | 6-12s | <20s | >30s |
| Web Search | 8-15s | <25s | >40s |
| Multi-Agent Cascade (3+ agents) | 12-25s | <40s | >60s |

### Throughput Concurrent Users

| Concurrent Users | Expected Throughput | Status |
|-----------------|---------------------|--------|
| 1 user | 0.2-0.5 req/s | ✅ Normal |
| 5 users | 0.8-1.5 req/s | ✅ Good |
| 10 users | 1.2-2.0 req/s | 🟡 Acceptable |
| 20+ users | <1.0 req/s | 🔴 Bottleneck |

---

## 🎯 Cas d'Usage Couverts

### Urgences (testés)
- ✅ Dégât des eaux avec cascade complète
- ✅ Panne électrique générale
- ✅ Incident ascenseur
- ✅ Fuite gaz (via workflow general)

### Communication (testés)
- ✅ Convocation AG formelle
- ✅ Email urgent professionnels
- ✅ Information résidents travaux
- ✅ Demande devis multiple

### Gestion Administrative (testés)
- ✅ Recherche copropriétaires
- ✅ Recherche professionnels par catégorie
- ✅ Statistiques copropriétés
- ✅ Emails non traités

### Legal & Conformité (testés)
- ✅ Délais convocation AG
- ✅ Obligations rénovation énergétique
- ✅ Analyse contrat syndic
- ✅ Recherche jurisprudence web

### Documents (testés)
- ✅ Recherche règlement copropriété
- ✅ Recherche contrats maintenance
- ✅ Analyse assurance

### Multi-Agent Complex (testés)
- ✅ AG complète (legal → SQL → email → synthèse)
- ✅ Travaux (workflow → pros → devis → web prix)
- ✅ Urgence (workflow → SQL → email × 2 → mémoire)

---

## 🔒 Sécurité Testée

### Injections (toutes testées)
✅ **SQL Injection** : `'; DROP TABLE users; --`
✅ **XSS Injection** : `<script>alert('XSS')</script>`
✅ **Command Injection** : `; rm -rf / #`

**Résultat attendu:** Système **doit bloquer ou gérer gracieusement** sans erreur 500.

### Edge Cases (tous testés)
✅ Input vide
✅ Input ultra-long (5000+ chars)
✅ Caractères spéciaux et emojis
✅ Unicode extrême (chinois, arabe, hébreu)
✅ Null bytes et escape sequences
✅ Contradictions extrêmes
✅ Boucles infinies demandées
✅ Requêtes impossibles

---

## 📝 Checklist Avant Déploiement

### Backend
- [ ] Tous tests `run_all_comprehensive_tests.py` passent à ≥90%
- [ ] UI-API parity à 100%
- [ ] Aucune injection de sécurité non gérée
- [ ] Latences < seuils acceptables
- [ ] Mémoire fonctionne sur 15+ tours
- [ ] Context store Redis fonctionne
- [ ] Isolation sessions utilisateurs OK

### Frontend
- [ ] Tests manuels UI correspondent aux tests API
- [ ] Streaming SSE fonctionne
- [ ] Quick actions testées
- [ ] Timeouts configurés (60s)
- [ ] Error handling robuste

### Infrastructure
- [ ] Health check `/api/health` OK
- [ ] Base de données accessible
- [ ] Qdrant accessible
- [ ] Redis accessible
- [ ] APIs externes (Brave, Serper, Legifrance) fonctionnelles
- [ ] CORS configuré pour production
- [ ] Rate limiting actif

### Monitoring Production (à mettre en place)
- [ ] Logs structurés (structlog JSON)
- [ ] Metrics agents utilisés (Prometheus/Grafana)
- [ ] Alertes latences >30s
- [ ] Alertes erreurs 500
- [ ] Tracking sessions utilisateurs
- [ ] Monitoring Redis (memory usage, hit rate)
- [ ] Monitoring Qdrant (collection size, query latency)

---

## 🎓 Prochaines Étapes

### Si tests passent à >95%
1. ✅ Déploiement staging
2. ✅ Tests acceptance utilisateurs (beta)
3. ✅ Déploiement production progressif (10% → 50% → 100%)

### Si tests passent à 80-95%
1. 🔧 Corrections mineures
2. ✅ Re-test ciblé
3. ✅ Déploiement staging
4. 🎯 Monitoring renforcé production

### Si tests passent à <80%
1. 🛑 **NE PAS DÉPLOYER**
2. 🔍 Analyse détaillée échecs
3. 🔧 Corrections majeures
4. ♻️  Re-test complet

---

## 📞 Support

### Problèmes avec les tests

**Erreur "Backend not healthy"**
→ Vérifier que le backend tourne sur `http://localhost:8000`

**Erreur "Timeout"**
→ Augmenter timeout dans le script (ligne `timeout=120.0`)

**Erreur "Connection refused"**
→ Vérifier firewall, ports, et que tous services (backend, postgres, redis, qdrant) sont démarrés

**Tests passent en local mais échouent en CI/CD**
→ Vérifier variables d'environnement, seeds DB, et accès réseau

### Logs utiles

```bash
# Logs backend
tail -f backend/logs/app.log

# Logs PostgreSQL
docker logs disruptiq_postgres

# Logs Redis
docker logs disruptiq_redis

# Logs Qdrant
docker logs disruptiq_qdrant
```

---

## 🎉 Conclusion

Cette suite de tests garantit que **DisruptIQ fonctionne parfaitement en conditions réelles** avant tout déploiement.

**Objectif atteint si:**
- ✅ 95%+ tests passent
- ✅ UI et API cohérentes
- ✅ Mémoire fonctionne sur longue durée
- ✅ Sécurité validée
- ✅ Performance acceptable sous charge

**→ Confiance totale pour le déploiement production! 🚀**
