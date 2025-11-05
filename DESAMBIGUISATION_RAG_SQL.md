# 🧠 Désambiguïsation Intelligente : RAG vs SQL

**Date**: 4 Novembre 2025
**Objectif**: Assurer une cohabitation harmonieuse entre RAG Agent et SQL Agent
**Status**: SPECIFICATION

---

## 🎯 PROBLÉMATIQUE

### Questions Ambiguës (peuvent être RAG OU SQL)

| Question | RAG (Documents) | SQL (Base de données) |
|----------|-----------------|----------------------|
| "Quel est le tarif du plombier ?" | Contrat PDF uploadé | Table `professionnels.tarif_horaire` |
| "Combien de copropriétaires ?" | Règlement PDF | Table `coproprietaires` COUNT(*) |
| "Procédure dégât des eaux" | Document procédure | Historique incidents table |
| "Contact du plombier" | Contrat uploadé | Table `professionnels.email` |
| "Budget Immeuble A" | PDF budget uploadé | Table `coproprietes.budget` |

**Risque actuel** :
- ❌ Confusion entre les deux sources
- ❌ Réponse partielle (seulement RAG ou seulement SQL)
- ❌ Frustration utilisateur ("pourquoi tu ne cherches pas dans la BDD ?")

---

## 🏗️ ARCHITECTURE PROPOSÉE

### Approche 1 : **Hybrid Intent Classifier** ⭐ RECOMMANDÉ

```
USER QUERY
    │
    ▼
┌─────────────────────────────────────┐
│   INTENT CLASSIFIER v2.0            │
│   - Analyse sémantique              │
│   - Détection keywords              │
│   - Contextual scoring              │
└─────────┬───────────────────────────┘
          │
          ├─→ SQL_ONLY (95% confidence)
          ├─→ RAG_ONLY (95% confidence)
          ├─→ HYBRID (50-95% → utilise LES DEUX)
          └─→ AMBIGUOUS (< 50% → demande clarification)

┌─────────▼─────────────────────────────┐
│   EXECUTION STRATEGY                  │
│                                       │
│   SQL_ONLY:    SQL Agent seul         │
│   RAG_ONLY:    RAG Agent seul         │
│   HYBRID:      SQL + RAG → Fusion     │
│   AMBIGUOUS:   User clarification     │
└───────────────────────────────────────┘
```

---

## 📊 RÈGLES DE CLASSIFICATION

### Signal Patterns (Priorité décroissante)

#### 1. **Signaux FORTS SQL** (95%+ confidence → SQL_ONLY)

**Keywords** :
- Quantitatifs : `combien`, `nombre`, `total`, `count`, `liste complète`
- Agrégations : `moyenne`, `somme`, `maximum`, `minimum`, `statistiques`
- Filtres : `tous les`, `filtrer par`, `dont`, `avec profession`, `par catégorie`
- Comparaisons : `compare`, `différence`, `écart`

**Patterns** :
```
"Combien de [entité] ?"              → SQL
"Liste des [entité] [filtre]"        → SQL
"Tous les [entité] avec [critère]"   → SQL
"Quel est le budget de [copro] ?"    → SQL (si table existe)
"Moyenne des [metric]"               → SQL
```

**Exemples** :
```
✅ SQL: "Combien de copropriétaires dans Les Mimosas ?"
✅ SQL: "Liste des plombiers avec tarif < 100€"
✅ SQL: "Moyenne des budgets par copropriété"
✅ SQL: "Tous les professionnels de catégorie chauffagiste"
```

---

#### 2. **Signaux FORTS RAG** (95%+ confidence → RAG_ONLY)

**Keywords** :
- Documents : `document`, `fichier`, `PDF`, `contrat`, `règlement`, `procédure`
- Contenu : `que dit`, `contenu`, `résume`, `détaille`, `explique`
- Recherche sémantique : `parle de`, `mentionne`, `traite de`
- Contextuel : `selon le document`, `dans le fichier`

**Patterns** :
```
"Que contient [document] ?"                → RAG
"Quelle est la procédure pour [action] ?"  → RAG
"Que dit le [doc] sur [sujet] ?"           → RAG
"Résume le [document]"                     → RAG
"Comment faire pour [action] ?"            → RAG (procédural)
```

**Exemples** :
```
✅ RAG: "Que contient le règlement de copropriété ?"
✅ RAG: "Quelle est la procédure en cas de dégât des eaux ?"
✅ RAG: "Résume le contrat du plombier"
✅ RAG: "Comment procéder pour une AG ?"
```

---

#### 3. **Signaux HYBRID** (50-95% confidence → SQL + RAG)

**Scénarios nécessitant les DEUX sources** :

**A. Enrichissement SQL avec RAG**
```
Query: "Quel est le tarif du plombier ?"

Strategy:
1. SQL: Cherche dans table `professionnels` → tarif_horaire: 80€
2. RAG: Cherche dans contrats uploadés → conditions spéciales, weekend, etc.
3. Fusion: Combine les deux sources

Response:
"D'après la base de données, le tarif horaire du plombier est de 80€[SQL].
Selon le contrat uploadé, ce tarif passe à 120€ les week-ends et jours fériés[1]."
```

**B. Validation croisée**
```
Query: "Contact du plombier"

Strategy:
1. SQL: Table `professionnels.email` → jean.durand@plomberie.fr
2. RAG: Contrat uploadé → peut contenir email différent ou confirmé
3. Compare: Si différence → signale contradiction

Response:
"Email du plombier : jean.durand@plomberie.fr[SQL]
⚠️ Note : Le contrat uploadé mentionne contact@plomberie-cannes.fr[1].
Vérifiez lequel est à jour."
```

**C. Contextualisation**
```
Query: "Procédure dégât des eaux pour Les Mimosas"

Strategy:
1. SQL: Récupère infos copropriété (contacts, assurance, etc.)
2. RAG: Récupère procédure générale
3. Fusion: Personnalise la procédure avec données SQL

Response:
"Voici la procédure pour Les Mimosas[SQL] :
1. Couper l'arrivée d'eau[1]
2. Contacter le syndic : 01 44 12 33 01[SQL]
3. Prévenir l'assurance Allianz : 0825 825 000[SQL]
4. Établir constat amiable[1]
..."
```

**Exemples HYBRID** :
```
🔀 "Tarif du plombier ?"           → SQL (tarif DB) + RAG (conditions contrat)
🔀 "Contact du plombier"           → SQL (email DB) + RAG (contrat uploadé)
🔀 "Budget Les Mimosas"            → SQL (montant) + RAG (détails PDF)
🔀 "Procédure urgence Immeuble A"  → RAG (procédure) + SQL (contacts spécifiques)
```

---

#### 4. **Signaux AMBIGUOUS** (<50% confidence → Clarification)

**Scénarios nécessitant clarification** :

```
Query: "Plombier"

Ambiguïté:
- SQL: Liste des plombiers ?
- RAG: Info sur contrat plombier ?
- Email: Contacter le plombier ?

Clarification:
"Je peux vous aider avec plusieurs choses concernant le plombier :
1. 📋 Voir la liste des plombiers enregistrés
2. 📄 Consulter le contrat du plombier
3. 📞 Obtenir ses coordonnées de contact
4. 💰 Connaître ses tarifs

Que souhaitez-vous ?"
```

```
Query: "Copropriétaires"

Clarification:
"Souhaitez-vous :
1. 📊 Le nombre total de copropriétaires (base de données)
2. 📋 La liste complète des copropriétaires
3. 📄 Les informations dans le règlement de copropriété
4. 📧 Envoyer un email aux copropriétaires"
```

---

## 🧪 ALGORITHME DE CLASSIFICATION

### Pseudo-code

```python
class IntentClassifierV2:

    async def classify_with_confidence(
        self,
        query: str,
        context: Dict
    ) -> ClassificationResult:
        """
        Classify query intent with confidence scoring

        Returns:
            {
                "intent": "SQL_ONLY" | "RAG_ONLY" | "HYBRID" | "AMBIGUOUS",
                "confidence": 0.0-1.0,
                "reasoning": "SQL keywords detected...",
                "suggested_action": "execute_sql" | "execute_rag" | "execute_both" | "ask_clarification"
            }
        """

        # Step 1: Keyword scoring
        sql_score = self._compute_sql_score(query)
        rag_score = self._compute_rag_score(query)

        # Step 2: Contextual boosting
        if context.get("has_uploaded_documents"):
            rag_score *= 1.2
        if context.get("last_query_was_sql"):
            sql_score *= 1.1

        # Step 3: LLM-based semantic analysis
        llm_scores = await self._llm_classify(query)

        # Step 4: Weighted fusion
        final_sql = (0.4 * sql_score) + (0.6 * llm_scores["sql"])
        final_rag = (0.4 * rag_score) + (0.6 * llm_scores["rag"])

        # Step 5: Decision logic
        if final_sql > 0.95 and final_rag < 0.3:
            return ClassificationResult(
                intent="SQL_ONLY",
                confidence=final_sql,
                reasoning="Strong SQL indicators: quantitative query"
            )

        elif final_rag > 0.95 and final_sql < 0.3:
            return ClassificationResult(
                intent="RAG_ONLY",
                confidence=final_rag,
                reasoning="Strong RAG indicators: document-centric query"
            )

        elif final_sql > 0.5 and final_rag > 0.5:
            return ClassificationResult(
                intent="HYBRID",
                confidence=(final_sql + final_rag) / 2,
                reasoning="Both SQL and RAG applicable, using hybrid approach"
            )

        else:
            return ClassificationResult(
                intent="AMBIGUOUS",
                confidence=max(final_sql, final_rag),
                reasoning="Unclear intent, requesting clarification",
                clarification_options=[
                    "Consulter la base de données",
                    "Chercher dans les documents",
                    "Les deux"
                ]
            )

    def _compute_sql_score(self, query: str) -> float:
        """Compute SQL likelihood based on keywords"""
        sql_keywords = {
            "combien": 0.8,
            "nombre": 0.8,
            "liste": 0.7,
            "tous les": 0.75,
            "total": 0.8,
            "moyenne": 0.9,
            "statistique": 0.9,
            "filtrer": 0.85,
            "avec profession": 0.9,
            "budget": 0.6,  # Peut être SQL ou RAG
        }

        score = 0.0
        query_lower = query.lower()

        for keyword, weight in sql_keywords.items():
            if keyword in query_lower:
                score += weight

        # Normalize to 0-1
        return min(score / len(sql_keywords), 1.0)

    def _compute_rag_score(self, query: str) -> float:
        """Compute RAG likelihood based on keywords"""
        rag_keywords = {
            "document": 0.9,
            "fichier": 0.9,
            "contrat": 0.85,
            "règlement": 0.85,
            "procédure": 0.9,
            "que dit": 0.95,
            "contenu": 0.8,
            "résume": 0.95,
            "comment faire": 0.9,
            "explique": 0.85,
        }

        score = 0.0
        query_lower = query.lower()

        for keyword, weight in rag_keywords.items():
            if keyword in query_lower:
                score += weight

        return min(score / len(rag_keywords), 1.0)
```

---

## 🎯 EXEMPLES DE CLASSIFICATION

### Test Suite

| Query | Intent | Confidence | Reasoning |
|-------|--------|------------|-----------|
| "Combien de copropriétaires ?" | SQL_ONLY | 98% | Quantitatif pur |
| "Résume le règlement" | RAG_ONLY | 99% | Document-centric |
| "Tarif du plombier ?" | HYBRID | 75% | SQL (DB) + RAG (contrat) |
| "Plombier" | AMBIGUOUS | 40% | Trop vague |
| "Liste des chauffagistes" | SQL_ONLY | 95% | Énumération BDD |
| "Procédure dégât des eaux" | RAG_ONLY | 97% | Procédure = document |
| "Contact du plombier" | HYBRID | 70% | SQL (DB) + RAG (validation) |
| "Budget Les Mimosas" | HYBRID | 80% | SQL (montant) + RAG (PDF détails) |
| "Copropriétaires" | AMBIGUOUS | 35% | Contexte manquant |
| "Que dit le contrat sur les tarifs ?" | RAG_ONLY | 98% | "Que dit" + "contrat" |

---

## 🔀 STRATÉGIE D'EXÉCUTION HYBRID

### Workflow

```
HYBRID Intent détecté
    │
    ├─→ Parallel Execution
    │   ├─→ SQL Agent: Execute query
    │   └─→ RAG Agent: Search documents
    │
    ▼
Fusion des résultats
    │
    ├─→ Si SQL vide et RAG non-vide → Return RAG
    ├─→ Si RAG vide et SQL non-vide → Return SQL
    ├─→ Si les deux non-vides → Synthesize
    └─→ Si les deux vides → "Aucune info"

Synthesis Strategy:
    │
    ├─→ Détection contradictions (SQL ≠ RAG)
    ├─→ Enrichissement (SQL = faits, RAG = contexte)
    └─→ Validation croisée (coherence check)
```

---

## 📝 FORMAT DE RÉPONSE HYBRID

### Template

```markdown
[Réponse synthétisée combinant SQL et RAG]

**Source base de données**[SQL] :
- [Fait 1 depuis SQL]
- [Fait 2 depuis SQL]

**Source documents**[1] :
- [Info 1 depuis RAG avec citation]
- [Info 2 depuis RAG avec citation]

⚠️ [Contradictions si détectées]

---
📚 Sources :
[1] Nom_document.pdf - 87%
[SQL] Base de données DisruptIQ
```

### Exemple concret

```
Query: "Quel est le tarif du plombier ?"

Response:
Le tarif horaire du plombier Jean Durand est de **80€/h en semaine**[SQL].

**Informations complémentaires du contrat**[1] :
- Tarif majoré à **120€/h les week-ends et jours fériés**[1]
- Facturation **minimum 2 heures** pour toute intervention[1]
- **Frais de déplacement** : 25€ si hors périmètre Cannes[1]

---
📚 Sources :
[1] **Contrat_plombier_2025** (page 1) - 98%
[SQL] Base de données `professionnels` - 100%
```

---

## 🧪 IMPLÉMENTATION

### Fichiers à créer

```
backend/app/services/agents/
├── intent_classifier_v2.py         ⭐ NOUVEAU (classification avancée)
├── hybrid_executor.py              ⭐ NOUVEAU (exécution SQL + RAG)
└── response_fusion_agent.py        ⭐ NOUVEAU (fusion intelligente)
```

### Modifications

```
backend/app/services/agents/orchestrator_agent.py
- Remplacer classify_intention() simple
- Par classify_with_confidence() avancée
- Ajouter logic HYBRID execution
```

---

## 🎯 PLAN D'IMPLÉMENTATION

### Phase 1 : Intent Classifier v2.0 (3h)
- [ ] Créer `intent_classifier_v2.py`
- [ ] Keyword scoring (SQL vs RAG)
- [ ] LLM semantic analysis
- [ ] Confidence scoring
- [ ] Tests unitaires (30 queries)

### Phase 2 : Hybrid Executor (2h)
- [ ] Créer `hybrid_executor.py`
- [ ] Parallel SQL + RAG execution
- [ ] Result aggregation
- [ ] Error handling

### Phase 3 : Response Fusion (2h)
- [ ] Créer `response_fusion_agent.py`
- [ ] Detect contradictions
- [ ] Synthesize responses
- [ ] Format with sources [SQL] + [1]

### Phase 4 : Integration (1h)
- [ ] Modifier orchestrator_agent.py
- [ ] Wire up new components
- [ ] End-to-end testing

### Phase 5 : Testing & Tuning (2h)
- [ ] Test 50 queries ambiguës
- [ ] Ajuster thresholds
- [ ] Mesurer accuracy
- [ ] Documentation

**Total : 10 heures**

---

## ✅ SUCCESS CRITERIA

### Metrics

| Métrique | Cible |
|----------|-------|
| **Classification accuracy** | >90% |
| **False positives SQL** | <5% |
| **False positives RAG** | <5% |
| **Hybrid detection** | >80% des cas ambigus |
| **User clarification rate** | <10% des queries |
| **Response coherence** | >95% (pas de contradictions non signalées) |

### Test Cases

```
✅ "Combien de copropriétaires ?" → SQL_ONLY
✅ "Résume le règlement" → RAG_ONLY
✅ "Tarif du plombier ?" → HYBRID
✅ "Plombier" → AMBIGUOUS → Clarification
✅ HYBRID execution fusionne SQL + RAG correctement
✅ Contradictions détectées et signalées
```

---

## 🚀 NEXT STEPS

1. **Valider l'approche** : Ce plan te convient ?
2. **Implémenter Phase 1** : Intent Classifier v2.0 (3h)
3. **Tester avec queries réelles**
4. **Itérer selon feedbacks**

---

**Tu veux qu'on commence l'implémentation ? 🚀**
