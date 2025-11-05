# 🧪 Plan de Test : Exécution Hybride SQL + RAG

**Date**: 4 Novembre 2025
**Feature**: Intent Classifier v2.0 + Hybrid Executor + Response Fusion
**Status**: PRÊT POUR TESTS

---

## 🎯 OBJECTIFS

Valider que le système :
1. ✅ Classifie correctement les intents (SQL_ONLY, RAG_ONLY, HYBRID, AMBIGUOUS)
2. ✅ Exécute SQL et RAG en parallèle pour HYBRID
3. ✅ Fusionne intelligemment les résultats
4. ✅ Demande clarification pour queries ambiguës
5. ✅ Détecte contradictions SQL vs RAG
6. ✅ Attribution sources correcte : [SQL] et [1], [2]

---

## 📋 TEST SUITE (30 Queries)

### Catégorie 1 : SQL_ONLY (10 queries)

| # | Query | Intent Attendu | Résultat Attendu |
|---|-------|----------------|------------------|
| 1 | "Combien de copropriétaires ?" | SQL_ONLY | COUNT(*) avec [SQL] |
| 2 | "Liste des plombiers" | SQL_ONLY | Liste noms + [SQL] |
| 3 | "Moyenne des budgets" | SQL_ONLY | AVG() + [SQL] |
| 4 | "Tous les professionnels chauffagistes" | SQL_ONLY | WHERE category + [SQL] |
| 5 | "Nombre total de copropriétés" | SQL_ONLY | COUNT(*) + [SQL] |
| 6 | "Statistiques des fournisseurs" | SQL_ONLY | Agrégations + [SQL] |
| 7 | "Filtrer les copropriétaires par immeuble" | SQL_ONLY | WHERE + [SQL] |
| 8 | "Compare budgets Mimosas vs Palmiers" | SQL_ONLY | Comparison + [SQL] |
| 9 | "Liste complète des emails" | SQL_ONLY | SELECT emails + [SQL] |
| 10 | "Quel est le budget total ?" | SQL_ONLY | SUM() + [SQL] |

**Validation** :
- ✅ `agents_used` contient `["intent_classifier_v2", "sql_agent"]`
- ✅ Réponse contient `[SQL]`
- ✅ Pas de `[1]`, `[2]` (RAG)
- ✅ Confidence ~1.0

---

### Catégorie 2 : RAG_ONLY (10 queries)

| # | Query | Intent Attendu | Résultat Attendu |
|---|-------|----------------|------------------|
| 11 | "Que contient le règlement ?" | RAG_ONLY | Résumé + [1], [2] |
| 12 | "Procédure dégât des eaux" | RAG_ONLY | Steps + citations |
| 13 | "Résume le contrat plombier" | RAG_ONLY | Synthèse + [1] |
| 14 | "Que dit le document sur les délais ?" | RAG_ONLY | Extract + [1], [2] |
| 15 | "Comment faire pour une AG ?" | RAG_ONLY | Procédure + [1] |
| 16 | "Quelles sont les étapes d'un sinistre ?" | RAG_ONLY | Steps + citations |
| 17 | "Explique le règlement article 5" | RAG_ONLY | Explication + [1] |
| 18 | "Détaille la charte des mariages" | RAG_ONLY | Détails + [1], [2] |
| 19 | "Que mentionne le contrat sur les tarifs ?" | RAG_ONLY | Extract tarifs + [1] |
| 20 | "Procédure d'urgence copropriété" | RAG_ONLY | Procédure + [1], [2] |

**Validation** :
- ✅ `agents_used` contient `["rag_agent", "synthesis_agent"]`
- ✅ Réponse contient citations `[1]`, `[2]`, `[3]`
- ✅ Footer "📚 **Sources** :"
- ✅ Pas de `[SQL]`
- ✅ Confidence >0.7

---

### Catégorie 3 : HYBRID ⭐ (8 queries)

| # | Query | Intent Attendu | Résultat Attendu | Fusion Strategy |
|---|-------|----------------|------------------|-----------------|
| 21 | "Quel est le tarif du plombier ?" | HYBRID | SQL: 80€ + RAG: conditions [1] | ENRICHMENT |
| 22 | "Contact du plombier" | HYBRID | SQL: email + RAG: validation [1] | VALIDATION |
| 23 | "Budget Les Mimosas" | HYBRID | SQL: montant + RAG: détails PDF [1] | COMPLEMENTARY |
| 24 | "Procédure dégât eaux Immeuble A" | HYBRID | RAG: procédure + SQL: contacts | COMPLEMENTARY |
| 25 | "Tarifs et conditions plombier" | HYBRID | SQL: tarif + RAG: clauses [1] | ENRICHMENT |
| 26 | "Email du syndic" | HYBRID | SQL: email + RAG: contrat [1] | VALIDATION |
| 27 | "Coût intervention chauffagiste" | HYBRID | SQL: tarif + RAG: détails [1] | ENRICHMENT |
| 28 | "Procédure urgence + contacts" | HYBRID | RAG: steps + SQL: téléphones | COMPLEMENTARY |

**Validation** :
- ✅ `agents_used` contient `["sql_agent", "rag_agent", "fusion_agent"]`
- ✅ Réponse contient BOTH `[SQL]` ET `[1]`, `[2]`
- ✅ `data.fusion_strategy` = "enrichment" | "validation" | "complementary"
- ✅ Sources footer liste SQL + RAG
- ✅ Si contradictions → `has_contradictions: true` + warning ⚠️

**Exemple attendu (Query 21)** :
```markdown
Le tarif horaire du plombier est de **80€/h en semaine**[SQL].

**Informations complémentaires du contrat**[1] :
- Tarif majoré à **120€/h les week-ends et jours fériés**[1]
- Facturation **minimum 2 heures** pour toute intervention[1]
- **Frais de déplacement** : 25€ si hors périmètre[1]

---
📚 **Sources** :
[1] **Contrat_plombier_2025** (page 1) - 98%
[SQL] **Base de données DisruptIQ** - 100%
```

---

### Catégorie 4 : AMBIGUOUS (2 queries)

| # | Query | Intent Attendu | Résultat Attendu |
|---|-------|----------------|------------------|
| 29 | "Plombier" | AMBIGUOUS | Clarification avec 3 options |
| 30 | "Copropriétaires" | AMBIGUOUS | Clarification avec options |

**Validation** :
- ✅ `data.clarification_needed: true`
- ✅ `suggestions` contient options
- ✅ Message liste 3 choix :
  1. Consulter la base de données
  2. Chercher dans les documents
  3. Les deux

**Exemple attendu (Query 29)** :
```
Je peux vous aider de plusieurs façons avec : « Plombier »

**Choisissez une option** :
1. Consulter la base de données (listes, statistiques)
2. Chercher dans les documents uploadés (contrats, règlements)
3. Les deux : combiner base de données et documents

Que souhaitez-vous ?
```

---

## 🚀 PROCÉDURE DE TEST

### Prérequis
1. Backend démarré : `docker-compose up -d`
2. Base de données peuplée (copropriétaires, professionnels)
3. Documents uploadés (contrats, règlements)

### Méthode de test

#### Option A : Interface Web (Recommandé)
```bash
# 1. Ouvrir interface
http://localhost:3000

# 2. Tester chaque query une par une
# 3. Noter résultats dans tableau ci-dessous
```

#### Option B : API directe (cURL)
```bash
# Template
curl -X POST http://localhost:8000/api/assistant-v2/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "QUERY_ICI"}' | jq '.response, .data.agents_used, .data.fusion_strategy'

# Exemple
curl -X POST http://localhost:8000/api/assistant-v2/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Quel est le tarif du plombier ?"}' | jq
```

---

## 📊 GRILLE DE RÉSULTATS

### SQL_ONLY (Target: 10/10)

| Query | Intent OK | Agents OK | [SQL] présent | Confidence | ✅/❌ |
|-------|-----------|-----------|---------------|------------|------|
| 1. Combien de copropriétaires ? | | | | | |
| 2. Liste des plombiers | | | | | |
| 3. Moyenne des budgets | | | | | |
| ... | | | | | |

### RAG_ONLY (Target: 10/10)

| Query | Intent OK | Agents OK | [1],[2] présent | Confidence | ✅/❌ |
|-------|-----------|-----------|-----------------|------------|------|
| 11. Que contient le règlement ? | | | | | |
| 12. Procédure dégât des eaux | | | | | |
| ... | | | | | |

### HYBRID (Target: 8/8) ⭐

| Query | Intent OK | Both SQL+RAG | Fusion OK | Strategy | ✅/❌ |
|-------|-----------|--------------|-----------|----------|------|
| 21. Tarif du plombier ? | | | | enrichment | |
| 22. Contact du plombier | | | | validation | |
| 23. Budget Les Mimosas | | | | complementary | |
| ... | | | | | |

### AMBIGUOUS (Target: 2/2)

| Query | Intent OK | Clarification | 3 options | ✅/❌ |
|-------|-----------|---------------|-----------|------|
| 29. Plombier | | | | |
| 30. Copropriétaires | | | | |

---

## ✅ CRITÈRES DE SUCCÈS

### Globaux
- [ ] **Classification accuracy** : >90% (27/30 queries correctes)
- [ ] **Hybrid detection** : 8/8 queries HYBRID détectées
- [ ] **No false positives** : <10% (max 3 erreurs)
- [ ] **Latency** : <3s par query (p95)

### Par Intent
- [ ] **SQL_ONLY** : 10/10 queries avec [SQL] uniquement
- [ ] **RAG_ONLY** : 10/10 queries avec citations [1], [2]
- [ ] **HYBRID** : 8/8 queries avec BOTH [SQL] + [1], [2]
- [ ] **AMBIGUOUS** : 2/2 queries avec clarification

### Fusion Quality
- [ ] **Enrichment** : SQL facts + RAG context fusionnés
- [ ] **Validation** : Contradictions détectées et signalées
- [ ] **Complementary** : Aspects différents combinés
- [ ] **Sources** : Attribution correcte [SQL] et [N]

---

## 🐛 TROUBLESHOOTING

### Problème : Mauvaise classification

**Symptôme** : Query HYBRID classée comme SQL_ONLY

**Debug** :
```bash
# Check logs
docker-compose logs backend | grep "intent_classification_v2"

# Voir scores
# sql_score, rag_score, confidence
```

**Solution** : Ajuster thresholds dans `intent_classifier_v2.py`

---

### Problème : Fusion échoue

**Symptôme** : Erreur lors fusion SQL + RAG

**Debug** :
```bash
docker-compose logs backend | grep "fusion"
```

**Solution** : Check que SQL et RAG retournent bien des résultats

---

### Problème : Pas de [SQL] dans réponse

**Symptôme** : Hybrid mais seulement citations RAG

**Cause** : SQL query n'a retourné aucun résultat

**Fix** : Vérifier que base de données est peuplée

---

## 📈 MÉTRIQUES ATTENDUES

| Métrique | Cible | Mesure |
|----------|-------|--------|
| **Classification accuracy** | >90% | __/30 |
| **SQL_ONLY precision** | 100% | __/10 |
| **RAG_ONLY precision** | 100% | __/10 |
| **HYBRID precision** | 100% | __/8 |
| **AMBIGUOUS precision** | 100% | __/2 |
| **Fusion quality** | >95% | __/8 |
| **Latency p95** | <3s | __ s |
| **User satisfaction** | >4.5/5 | __ /5 |

---

## 🎯 NEXT STEPS APRÈS TESTS

### Si succès (>90% accuracy)
1. ✅ Valider en production
2. ✅ Monitoring + alerting
3. ✅ Passer aux Phases RAG 2-3 (retrieval + reranking)

### Si échecs (< 90%)
1. Analyser queries échouées
2. Ajuster thresholds classifier
3. Améliorer prompts fusion
4. Re-tester

---

**🚀 Ready to test the best hybrid RAG+SQL system ever built!**

---

*Plan de test créé le 4 Novembre 2025*
*System: Intent Classifier v2.0 + Hybrid Executor + Response Fusion Agent*
*Target: >90% accuracy, <3s latency*
