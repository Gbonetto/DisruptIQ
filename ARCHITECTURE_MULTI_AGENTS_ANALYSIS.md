# Analyse Architecture Multi-Agents - État vs Vision Expert
**Date:** 22 novembre 2025

---

## 🎯 Résumé Exécutif

**Alignement Global:** 70% ✅ | **Gaps Critiques:** 30% ⚠️

**Verdict:** L'architecture actuelle suit les bons principes mais souffre de **confusion dans la séparation des responsabilités** et **d'implémentation incomplète** des 3 couches.

---

## 📊 Les 3 Couches - État Actuel vs Vision

### ✅ CE QUI FONCTIONNE BIEN

#### Couche 1: Classification d'Intention (Orchestrateur)
**Vision Expert:**
```python
task_type   = LEGAL_ANALYSIS
domain      = LEGAL
needs_data  = ["DOCUMENTS"]
confidence  = 0.91
```

**Notre Implémentation:** ✅ **70% Aligné**

**Fichier:** `app/services/agents/intent_classifier_v4.py`

```python
# ✅ Nous avons une taxonomie claire
class IntentType(str, Enum):
    QUERY_DATA = "query_data"           # ✅ Domain: SQL
    SEARCH_DOCUMENTS = "search_documents" # ✅ Domain: RAG
    LEGAL = "legal"                      # ✅ Domain: Legal
    WEB_SEARCH = "web_search"            # ✅ Domain: Web
    SEND_EMAIL = "send_email"            # ✅ Domain: Workflow
    # ... 10 intents au total ✅
```

**✅ Points Forts:**
1. **Quick Rules + LLM Hybridation** - Exactement comme recommandé
   ```python
   # intent_classifier_v4.py:157-189
   def _quick_classification(self, query: str) -> Optional[IntentType]:
       # Règles rapides par mots-clés (70-80% des cas)
       if any(kw in query_lower for kw in ["jurisprudence", "loi", "article"]):
           return IntentType.LEGAL
   ```

2. **Context Boosting** - Scoring intelligent
   ```python
   # intent_classifier_v4.py:286-350
   def _apply_context_boosting(self, scores, context):
       # Boosting basé sur documents uploadés, conversation history
   ```

3. **Confidence Scores** - Chaque classification a un score
   ```python
   return {
       "intent": IntentType.LEGAL,
       "confidence": 0.93,  # ✅
       "reasoning": "..."
   }
   ```

**⚠️ Gaps Identifiés:**

1. **❌ Pas de champ `needs_data`**
   ```python
   # ACTUEL - Manque needs_data
   return {
       "intent": IntentType.LEGAL,
       "confidence": 0.93
   }

   # ATTENDU selon expert
   return {
       "task_type": "LEGAL_ANALYSIS",
       "domain": "LEGAL",
       "needs_data": ["DOCUMENTS", "JURISPRUDENCE"],  # ❌ Manquant!
       "needs_action": ["NONE"],
       "confidence": 0.93
   }
   ```

2. **❌ Mélange task_type et domain**
   - `IntentType.LEGAL` = domain ET task_type en même temps
   - Devrait séparer: `domain=LEGAL` + `task_type=ANALYSIS`

---

### Couche 2: Choix de l'Agent (Orchestrateur)
**Vision Expert:**
```python
primary_agent = "LegalAgent"
support_agents = ["RAGAgent"]
```

**Notre Implémentation:** ⚠️ **40% Aligné - PROBLÈME MAJEUR**

**Fichier:** `app/services/agents/orchestrator_agent.py`

**❌ Problème Critique: Intents Éclatés**

```python
# LIGNE 36 - Enum Principal
class IntentType(str, Enum):
    LEGAL = "legal"  # ✅ Existe

# LIGNE 1909-1912 - Handler Map (INCOHÉRENT!)
handler_map = {
    IntentType.LEGAL_ADVICE: self._handle_legal_advice,      # ❌ N'existe pas dans enum!
    IntentType.LEGAL_ANALYSIS: self._handle_legal_analysis,  # ❌ N'existe pas dans enum!
    IntentType.LEGAL_COMPARISON: self._handle_legal_comparison, # ❌ N'existe pas!
    IntentType.SEARCH_JURISPRUDENCE: self._handle_search_jurisprudence, # ❌ N'existe pas!
}

# LIGNE 464 - Routing Principal
elif intent == IntentType.LEGAL:
    return await self._handle_legal(...)  # ✅ Celui-ci existe
```

**🔴 ERREUR FATALE:**
- **Enum** définit `LEGAL` (générique)
- **Handler Map** attend `LEGAL_ANALYSIS`, `LEGAL_ADVICE` (spécifiques)
- **Routing if/elif** utilise `LEGAL`
- **Résultat:** Code mort + erreurs "LEGAL_ANALYSIS not found"

**Ce que l'expert dirait:**
> "Ton orchestrateur NE DOIT PAS décider entre `LEGAL_ANALYSIS` vs `LEGAL_ADVICE`.
> C'est le boulot du LegalAgent! L'orchestrateur dit juste: 'C'est juridique, j'envoie au LegalAgent'."

**✅ Ce qui marche (partiellement):**

```python
# orchestrator_agent.py:464
elif intent == IntentType.LEGAL:
    return await self._handle_legal(user_input, context, db, thought_stream)
    # ✅ Bonne approche: délégation à un handler unique
```

**❌ Ce qui ne marche pas:**

1. **Pas de structure `primary_agent + support_agents`**
   ```python
   # ACTUEL - Direct call
   elif intent == IntentType.LEGAL:
       return await self._handle_legal(...)

   # ATTENDU selon expert
   agent_plan = {
       "primary_agent": "LegalAgent",
       "support_agents": ["RAGAgent", "WebSearchAgent"],
       "data_needed": ["DOCUMENTS", "JURISPRUDENCE"]
   }
   ```

2. **❌ Agents s'appellent entre eux directement**
   ```python
   # legal_agent.py:671 - MAUVAIS selon expert
   async def search_jurisprudence(self, ...):
       # Legal Agent appelle directement Légifrance
       service = get_legifrance_service()  # ❌ Devrait passer par orchestrateur
       result = await service.search_jurisprudence(...)
   ```

---

### Couche 3: Récupération de Données (Sources)
**Vision Expert:**
```python
data_plan = {
    "use_RAG": true,
    "use_SQL": false,
    "use_Web": false
}
```

**Notre Implémentation:** ⚠️ **50% Aligné - IMPLÉMENTATION PARTIELLE**

**Fichier:** `app/services/agents/orchestrator_agent.py`

**✅ Ce qui existe:**

```python
# orchestrator_agent.py:342-367
selected_sources = self._determine_sources(
    has_active_documents,
    user_controlled_sources
)

# Logique de détermination des sources
if user_controlled_sources:
    # ✅ Respect des checkboxes utilisateur
    if "rag" in user_controlled_sources:
        selected_sources.append("rag")
    if "internet" in user_controlled_sources:
        selected_sources.append("internet")
```

**⚠️ Gaps:**

1. **❌ Pas de structure `data_plan` formelle**
   ```python
   # ACTUEL - Liste simple
   selected_sources = ["rag", "internet"]

   # ATTENDU selon expert
   data_plan = {
       "use_RAG": true,
       "use_SQL": false,
       "use_Web": true,
       "fallback_order": ["RAG", "Web"],
       "merge_strategy": "COMBINED"
   }
   ```

2. **❌ Logique de fallback pas claire**
   - Pas de cascade explicite RAG → SQL → Web
   - Pas de merge strategy documentée

3. **✅ MAIS:** Cases à cocher implémentées correctement
   ```typescript
   // frontend/src/components/chat/SourceSelector.tsx
   <Checkbox>RAG</Checkbox>
   <Checkbox>SQL</Checkbox>
   <Checkbox>Internet</Checkbox>
   <Checkbox>Auto</Checkbox>  // ✅
   ```

---

## 🔍 Exemple Concret - Trace Complète

**Query:** "Analyse ce contrat de syndic et dis-moi les risques principaux"

### Vision Expert (Comment ça DEVRAIT se passer)

```
┌─────────────────────────────────────────────────────────────┐
│ COUCHE 1: Classification (Orchestrateur)                   │
├─────────────────────────────────────────────────────────────┤
│ task_type   = LEGAL_ANALYSIS                                │
│ domain      = LEGAL                                         │
│ needs_data  = ["DOCUMENTS"]                                 │
│ confidence  = 0.93                                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ COUCHE 2: Choix Agent (Orchestrateur)                      │
├─────────────────────────────────────────────────────────────┤
│ primary_agent   = "LegalAgent"                              │
│ support_agents  = ["RAGAgent"]                              │
│ action_decision = delegated_to_primary  # ← CLEF!          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ COUCHE 3: Plan de Données (Sources)                        │
├─────────────────────────────────────────────────────────────┤
│ use_RAG = true  (checkbox cochée)                           │
│ use_SQL = false                                             │
│ use_Web = false                                             │
│                                                             │
│ → RAGAgent.search("contrat syndic")                         │
│ → chunks = [chunk1, chunk2, chunk3]                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ LegalAgent - Décision Métier                               │
├─────────────────────────────────────────────────────────────┤
│ Input:                                                      │
│   - prompt: "analyse risques"                               │
│   - chunks: [RAG data]                                      │
│   - context: {...}                                          │
│                                                             │
│ Décision INTERNE (pas l'orchestrateur!):                   │
│   → action = analyze_document(mode="risk")                  │
│                                                             │
│ Output:                                                     │
│   {                                                         │
│     "summary": "...",                                       │
│     "risks": [...],                                         │
│     "obligations": [...],                                   │
│     "citations": [...]                                      │
│   }                                                         │
└─────────────────────────────────────────────────────────────┘
```

### Implémentation Actuelle (Comment ça SE PASSE vraiment)

```
┌─────────────────────────────────────────────────────────────┐
│ COUCHE 1: Classification                                    │
├─────────────────────────────────────────────────────────────┤
│ intent = IntentType.SEARCH_DOCUMENTS  ← ❌ ERREUR!          │
│ confidence = 0.85                                           │
│                                                             │
│ Problème: Détecte "document" mais pas "legal"              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ COUCHE 2: Routing                                          │
├─────────────────────────────────────────────────────────────┤
│ elif intent == IntentType.SEARCH_DOCUMENTS:                │
│     return await self._handle_search_documents(...)         │
│                                                             │
│ ❌ Va dans RAG générique au lieu de LegalAgent              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Handler: _handle_search_documents                          │
├─────────────────────────────────────────────────────────────┤
│ → RAGAgent.search(...)                                      │
│ → Synthèse générique                                        │
│                                                             │
│ ❌ ÉCHEC: Pas de LegalAgent appelé                          │
│ ❌ Erreur levée: "LEGAL_ANALYSIS" not found                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture Actuelle - Diagramme Réel

```
┌────────────────────────────────────────────────────────────────┐
│                         FRONTEND                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Chat UI      │  │ Checkboxes   │  │ Documents    │         │
│  │              │  │ □ RAG        │  │ Upload       │         │
│  │              │  │ □ SQL        │  │              │         │
│  │              │  │ □ Internet   │  │              │         │
│  │              │  │ ☑ Auto       │  │              │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
└─────────┼──────────────────┼──────────────────┼────────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             ↓
┌────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                          │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  IntentClassifierV4                                      │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │ │
│  │  │Quick Rules │→ │LLM Fallback│→ │Context     │         │ │
│  │  │70% rapide  │  │30% complexe│  │Boosting    │         │ │
│  │  └────────────┘  └────────────┘  └────────────┘         │ │
│  │                                                          │ │
│  │  Output: IntentType (10 types)                          │ │
│  └──────────────────────────────────────────────────────────┘ │
│                             ↓                                  │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Routing (if/elif)                         ❌ PROBLÈME   │ │
│  │                                                          │ │
│  │  if intent == QUERY_DATA:       → SQLAgent             │ │
│  │  elif intent == SEARCH_DOCS:    → RAGAgent             │ │
│  │  elif intent == LEGAL:          → _handle_legal()      │ │
│  │                                    ↓                     │ │
│  │                                    ??? (handler manquant)│ │
│  │  elif intent == WEB_SEARCH:     → WebSearchAgent       │ │
│  │  else:                          → GeneralAgent          │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
                             ↓
         ┌───────────────────┴───────────────────┐
         │                                       │
         ↓                                       ↓
┌──────────────────┐                   ┌──────────────────┐
│   LEGAL AGENT    │                   │   OTHER AGENTS   │
│                  │                   │                  │
│  ❌ S'appelle    │                   │  • RAGAgent      │
│     lui-même     │                   │  • SQLAgent      │
│     les sources  │                   │  • WebSearch     │
│                  │                   │  • N8N           │
│  • Légifrance ←──┼─────────────────→ │  • etc.          │
│  • RAG search    │  ❌ Direct calls  │                  │
│  • Web search    │     (mauvais)     │                  │
└──────────────────┘                   └──────────────────┘
```

---

## 📋 Checklist - Alignement avec Vision Expert

### ✅ Points Alignés (70%)

- [x] **Orchestrateur unique central** - Un seul point d'entrée
- [x] **Taxonomie claire** - 10 intents stables
- [x] **Quick Rules + LLM** - Hybridation fonctionnelle
- [x] **Confidence scores** - Chaque classification a un score
- [x] **Checkboxes sources** - UI ne pilote pas le métier
- [x] **Agents spécialisés** - LegalAgent, SQLAgent, RAGAgent séparés
- [x] **Logging structuré** - Logs JSON avec structlog

### ❌ Gaps Critiques (30%)

- [ ] **Séparation `task_type` vs `domain`** - Actuellement mélangés
- [ ] **Champ `needs_data`** - Pas implémenté dans classification
- [ ] **Structure `primary_agent + support_agents`** - Pas formalisée
- [ ] **Plan de données `data_plan`** - Liste simple vs objet structuré
- [ ] **Agents s'appellent entre eux** - Legal → Légifrance direct (❌)
- [ ] **Intents éclatés** - `LEGAL` vs `LEGAL_ANALYSIS` confusion
- [ ] **Action métier dans orchestrateur** - Handlers trop spécifiques
- [ ] **Fallback cascade** - Pas de stratégie RAG → SQL → Web claire
- [ ] **Observabilité complète** - Logs manquent certains tours

---

## 🎯 Plan de Correction - Roadmap

### Phase 1: Fixes Urgents (2-3 heures) 🔴

**Priorité 1: Harmoniser les IntentTypes**

```python
# ❌ SUPPRIMER de orchestrator_agent.py:1909-1912
handler_map = {
    IntentType.LEGAL_ADVICE: ...,      # ← Supprimer
    IntentType.LEGAL_ANALYSIS: ...,    # ← Supprimer
    IntentType.LEGAL_COMPARISON: ...,  # ← Supprimer
}

# ✅ GARDER SEULEMENT
elif intent == IntentType.LEGAL:
    return await self._handle_legal(...)
```

**Priorité 2: Legal Agent décide en interne**

```python
# legal_agent.py - Ajouter méthode de routage interne
async def process_request(self, user_input, context, thought_stream):
    """Legal Agent décide lui-même de l'action"""

    # Classification interne
    intent = await self._classify_legal_intent(user_input, context)

    if intent["action"] == "analyze":
        return await self.analyze_document(...)
    elif intent["action"] == "jurisprudence":
        return await self.search_jurisprudence(...)
    elif intent["action"] == "compare":
        return await self.compare_multiple_legal_documents(...)
```

**Priorité 3: Corriger le routage actuel**

```python
# orchestrator_agent.py:464
elif intent == IntentType.LEGAL:
    # ✅ Délégation propre au Legal Agent
    legal_agent = LegalAgent()

    # Récupérer les données nécessaires AVANT
    data = await self._gather_data_for_legal(context, selected_sources)

    # Laisser Legal Agent décider
    return await legal_agent.process_request(
        user_input=user_input,
        data=data,  # RAG chunks, SQL results, etc.
        thought_stream=thought_stream
    )
```

---

### Phase 2: Restructuration Architecturale (1-2 jours) ⚠️

**1. Ajouter `needs_data` dans classification**

```python
# intent_classifier_v4.py - Nouvelle structure
class IntentClassification(BaseModel):
    task_type: str          # "ANALYSIS", "COMPARISON", "SEARCH"
    domain: str             # "LEGAL", "FINANCE", "GENERAL"
    needs_data: List[str]   # ["DOCUMENTS", "JURISPRUDENCE", "SQL"]
    needs_action: List[str] # ["NONE", "SEND_EMAIL", "TRIGGER_WORKFLOW"]
    confidence: float

def classify_intent_v5(self, query: str, context: Dict) -> IntentClassification:
    # Logique enrichie
    if "jurisprudence" in query:
        return IntentClassification(
            task_type="SEARCH",
            domain="LEGAL",
            needs_data=["JURISPRUDENCE", "WEB"],
            needs_action=["NONE"],
            confidence=0.95
        )
```

**2. Formaliser `primary_agent + support_agents`**

```python
# orchestrator_agent.py - Nouvelle structure
class AgentPlan(BaseModel):
    primary_agent: str
    support_agents: List[str]
    data_plan: Dict[str, bool]
    confidence: float

def _create_agent_plan(self, classification: IntentClassification) -> AgentPlan:
    if classification.domain == "LEGAL":
        support = []
        if "DOCUMENTS" in classification.needs_data:
            support.append("RAGAgent")
        if "JURISPRUDENCE" in classification.needs_data:
            support.append("LegifanceAgent")

        return AgentPlan(
            primary_agent="LegalAgent",
            support_agents=support,
            data_plan={"use_RAG": True, "use_Web": True},
            confidence=classification.confidence
        )
```

**3. Cascade de Fallback explicite**

```python
# orchestrator_agent.py - Data gathering avec fallback
async def _gather_data_with_fallback(
    self,
    needs_data: List[str],
    query: str,
    context: Dict
) -> Dict[str, Any]:
    """
    Cascade: RAG → SQL → Web
    """
    data = {}

    if "DOCUMENTS" in needs_data:
        # 1. Essayer RAG en premier
        try:
            rag_results = await self.rag_agent.search(query)
            if rag_results["chunks"]:
                data["documents"] = rag_results
                return data  # ✅ Succès RAG
        except Exception as e:
            logger.warning("rag_failed_fallback_to_web", error=str(e))

        # 2. Fallback: Web Search
        try:
            web_results = await self.web_agent.search(query)
            data["web_documents"] = web_results
        except Exception as e:
            logger.error("all_sources_failed", error=str(e))

    return data
```

---

### Phase 3: Observabilité (1 jour) 📊

**Logging complet de chaque tour**

```python
# orchestrator_agent.py - Après chaque requête
logger.info("request_completed",
    user_query=user_input[:100],
    classification={
        "task_type": classification.task_type,
        "domain": classification.domain,
        "confidence": classification.confidence
    },
    agent_plan={
        "primary": agent_plan.primary_agent,
        "support": agent_plan.support_agents
    },
    data_sources_used=list(data.keys()),
    primary_agent_action=result.get("action_taken"),  # Ex: "analyze_document(mode=risk)"
    workflow_triggered=result.get("workflow", "none"),
    execution_time_ms=elapsed_ms
)
```

**Dashboard visuel (optionnel)**
```
User: "Analyse ce contrat et dis-moi les risques"
├─ Intent: LEGAL_ANALYSIS (0.93)
├─ Primary agent: LegalAgent
├─ Sources: RAG (Contrat_Syndic_2024.pdf)
├─ LegalAgent action: analyze_document(mode="risk")
├─ Workflow triggered: none
└─ Response: {"summary": "...", "risks": [...]}
```

---

## 📊 Scorecard Final - Alignement avec Vision Expert

| Dimension | Score | Commentaire |
|-----------|-------|-------------|
| **Orchestrateur Unique** | ✅ 90% | Un seul point d'entrée, bien structuré |
| **Taxonomie Claire (10-20 intents)** | ✅ 85% | 10 intents, mais confusion LEGAL vs LEGAL_ANALYSIS |
| **Quick Rules + LLM** | ✅ 95% | Excellente hybridation |
| **Séparation Couche 1 (Intent)** | ⚠️ 60% | Manque `needs_data`, `task_type` vs `domain` |
| **Séparation Couche 2 (Agent)** | ❌ 40% | Pas de structure `primary + support` formelle |
| **Séparation Couche 3 (Sources)** | ⚠️ 50% | Checkboxes OK, mais pas de `data_plan` structuré |
| **Agents ne s'appellent pas entre eux** | ❌ 30% | Legal → Légifrance direct (violation) |
| **Action métier dans agent, pas orchestrateur** | ⚠️ 50% | Partiellement - handlers trop spécifiques |
| **Observabilité** | ⚠️ 60% | Logs structurés mais incomplets |
| **Fallback cascade documentée** | ❌ 40% | Pas de stratégie claire RAG → SQL → Web |

**Score Global: 60/100** - Architecture sur la bonne voie mais nécessite refactoring

---

## 🎓 Réponse à l'Expert

### "Avons-nous une architecture robuste multi-agents?"

**Réponse courte:** **Partiellement** (60% aligné).

**Réponse détaillée:**

**✅ Ce que nous faisons BIEN:**
1. Orchestrateur unique central ✅
2. Taxonomie claire d'intents (10 types) ✅
3. Hybridation Quick Rules + LLM ✅
4. Séparation UI (checkboxes) vs logique métier ✅
5. Agents spécialisés distincts ✅
6. Logging structuré JSON ✅

**❌ Ce qui DOIT être corrigé:**
1. **Confusion Intents** - `LEGAL` vs `LEGAL_ANALYSIS` éclatés
2. **Agents s'appellent entre eux** - Legal → Légifrance direct
3. **Pas de structure `needs_data`** - Classification incomplète
4. **Pas de `primary + support agents`** - Délégation ad-hoc
5. **Action métier dans orchestrateur** - Handlers trop spécifiques
6. **Fallback cascade implicite** - Pas de stratégie documentée

**Vision Expert vs Notre Réalité:**

| Principe Expert | Notre Implémentation | Gap |
|-----------------|----------------------|-----|
| "Orchestrateur: quoi, qui" | ✅ Fait | - |
| "Agents métier: comment" | ⚠️ Partiellement | Legal décide en interne, mais routing confus |
| "Agents data: où" | ❌ Direct calls | Legal appelle sources directement |
| "UI: contraintes, pas décisions" | ✅ Fait | Checkboxes bien séparées |
| "Taxonomie 10-20 intents max" | ✅ Fait | 10 intents clairs |
| "Observabilité complète" | ⚠️ Partiellement | Logs incomplets |

---

## 🚀 Action Immédiate Recommandée

**Pour débloquer tes tests MAINTENANT:**

1. **Fix Urgent** (30 min): Corriger `LEGAL_ANALYSIS` → `LEGAL`
   ```bash
   # Supprimer les handlers orphelins
   # Tester avec classification corrigée
   ```

2. **Test Direct** (10 min): Créer endpoint de test Legal Agent
   ```python
   # POST /api/legal/test
   # Bypass orchestrator pour valider Legal Agent seul
   ```

**Pour avoir une architecture classe mondiale:**

3. **Refactoring Phase 1** (2-3 jours):
   - Harmoniser IntentTypes
   - Ajouter `needs_data` dans classification
   - Formaliser `AgentPlan` (primary + support)

4. **Refactoring Phase 2** (3-5 jours):
   - Agents ne s'appellent plus entre eux
   - Data gathering centralisé dans orchestrateur
   - Fallback cascade explicite

5. **Observabilité** (1 jour):
   - Logging complet de chaque tour
   - Dashboard de monitoring (optionnel)

---

**Conclusion:** Nous avons les fondations d'une bonne architecture, mais elle souffre de **dette technique** dans la séparation des responsabilités. Avec 3-5 jours de refactoring ciblé, nous pouvons atteindre 90% d'alignement avec la vision expert.

**Veux-tu que je commence par le fix urgent pour débloquer tes tests, ou préfères-tu qu'on attaque directement le refactoring complet?**
