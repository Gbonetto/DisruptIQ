# DisruptIQ - Architecture Multi-Agent Complete

> **Version**: Decembre 2025
> **Stack LLM**: Mistral Large 3 / Ministral 8B / Pixtral 12B

---

## Vue d'Ensemble

```
                                    DISRUPTIQ MULTI-AGENT SYSTEM
                                    ============================

    [UTILISATEUR]
         |
         v
    +--------------------+
    |   FRONTEND REACT   |
    |  - Chat Interface  |
    |  - Document Upload |
    |  - Action Buttons  |
    +--------------------+
              |
              | HTTP/WebSocket
              v
+==============================================================================+
|                              BACKEND FASTAPI                                  |
|                                                                               |
|  +------------------------------------------------------------------------+  |
|  |                         API ENDPOINTS                                   |  |
|  |  POST /api/assistant/chat      - Chat principal                        |  |
|  |  POST /api/assistant/action    - Actions follow-up (Legal, Web)        |  |
|  |  POST /api/email-generator/*   - Generation d'emails                   |  |
|  |  POST /api/emergency-workflows - Workflows urgence                     |  |
|  |  POST /api/digest/*            - Digests emails                        |  |
|  +------------------------------------------------------------------------+  |
|              |                                                               |
|              v                                                               |
|  +------------------------------------------------------------------------+  |
|  |                      ORCHESTRATOR (Singleton)                           |  |
|  |                                                                         |  |
|  |   +-----------------+        +---------------------+                    |  |
|  |   | OrchestratorV2  |   OR   | CoreFirstOrchest.  |                    |  |
|  |   | (Legacy, full)  |        | (Simplified SQL+RAG)|                    |  |
|  |   +-----------------+        +---------------------+                    |  |
|  +------------------------------------------------------------------------+  |
|              |                                                               |
|              v                                                               |
|  +------------------------------------------------------------------------+  |
|  |                    CLASSIFICATION PIPELINE                              |  |
|  |                                                                         |  |
|  |  1. Template Filter     - Greetings/thanks (0ms)                       |  |
|  |  2. UI Context Bypass   - Action buttons (0ms)                         |  |
|  |  3. LLM Intent Class.   - Mistral semantic (10-50ms)                   |  |
|  |  4. IntentClassifierV5  - Keyword fallback (1ms)                       |  |
|  +------------------------------------------------------------------------+  |
|              |                                                               |
|              v                                                               |
|  +------------------------------------------------------------------------+  |
|  |                    MODEL ROUTER (NEW Dec 2025)                          |  |
|  |                                                                         |  |
|  |     +------------------+     +-------------------+                      |  |
|  |     |  FAST TIER       |     |   LARGE TIER      |                      |  |
|  |     | ministral-8b     |     | mistral-large     |                      |  |
|  |     |                  |     |                   |                      |  |
|  |     | - Classification |     | - Legal Analysis  |                      |  |
|  |     | - Simple Q&A     |     | - Critical Emails |                      |  |
|  |     | - Post-OCR       |     | - Multi-doc Synth |                      |  |
|  |     | - Email Routine  |     | - Complex Reason. |                      |  |
|  |     |                  |     |                   |                      |  |
|  |     | 200-500ms        |     | 1-30s             |                      |  |
|  |     | ~$0.10/M tokens  |     | ~$0.50-1.50/M     |                      |  |
|  |     +------------------+     +-------------------+                      |  |
|  +------------------------------------------------------------------------+  |
|              |                                                               |
|              v                                                               |
|  +------------------------------------------------------------------------+  |
|  |                    PARALLEL SOURCE EXECUTION                            |  |
|  |                                                                         |  |
|  |  +-------------+  +-------------+  +-------------+  +-------------+    |  |
|  |  | SQL AGENT   |  | RAG SERVICE |  | LEGAL AGENT |  | WEB AGENT   |    |  |
|  |  |             |  |             |  |             |  |             |    |  |
|  |  | Text-to-SQL |  | Qdrant Vec  |  | Legifrance  |  | DuckDuckGo  |    |  |
|  |  | PostgreSQL  |  | BM25 Hybrid |  | Contract    |  | Web Search  |    |  |
|  |  | Whitelisted |  | Reranking   |  | Analysis    |  | Extraction  |    |  |
|  |  +-------------+  +-------------+  +-------------+  +-------------+    |  |
|  |         |               |               |               |              |  |
|  |         +-------+-------+-------+-------+               |              |  |
|  |                 |                                       |              |  |
|  |                 v                                       |              |  |
|  |  +---------------------------+                          |              |  |
|  |  |    RESPONSE FUSION        |<-------------------------+              |  |
|  |  |                           |                                         |  |
|  |  | - Merge SQL + RAG         |                                         |  |
|  |  | - Detect contradictions   |                                         |  |
|  |  | - Cross-validate data     |                                         |  |
|  |  +---------------------------+                                         |  |
|  +------------------------------------------------------------------------+  |
|              |                                                               |
|              v                                                               |
|  +------------------------------------------------------------------------+  |
|  |                    SYNTHESIS AGENT                                      |  |
|  |                                                                         |  |
|  |  - Generate natural language response                                  |  |
|  |  - Add inline citations [1], [2], [3]                                  |  |
|  |  - Format source list with metadata                                    |  |
|  |  - Calculate confidence score                                          |  |
|  +------------------------------------------------------------------------+  |
|              |                                                               |
|              v                                                               |
|  +------------------------------------------------------------------------+  |
|  |                    RESPONSE + SUGGESTIONS                               |  |
|  |                                                                         |  |
|  |  {                                                                     |  |
|  |    "message": "Response avec [1] citations...",                        |  |
|  |    "agents_used": ["sql_agent", "rag_service"],                        |  |
|  |    "confidence": 0.87,                                                 |  |
|  |    "structured_suggestions": [                                         |  |
|  |      {"label": "Consulter la loi", "action": "legal_lookup"},          |  |
|  |      {"label": "Rechercher prix", "action": "web_search"}              |  |
|  |    ]                                                                   |  |
|  |  }                                                                     |  |
|  +------------------------------------------------------------------------+  |
+==============================================================================+
```

---

## Inventaire des Agents

### Agents Principaux (Core)

| Agent | Fichier | Role | Modele |
|-------|---------|------|--------|
| **SQL Agent** | `sql_agent.py` | NL to SQL, requetes PostgreSQL | FAST |
| **RAG Service** | `rag_service.py` | Recherche semantique Qdrant | FAST/LARGE |
| **Synthesis Agent** | `synthesis_agent.py` | Generation reponse + citations | LARGE |
| **Response Fusion** | `response_fusion_agent.py` | Fusion SQL + RAG | FAST |

### Agents Specialises

| Agent | Fichier | Role | Modele |
|-------|---------|------|--------|
| **Legal Agent** | `legal_agent_v2.py` | Analyse juridique, Legifrance | LARGE |
| **Email Agent** | `email_agent.py` | Generation emails types | FAST/LARGE |
| **Workflow Agent** | `workflow_agent_v2.py` | Workflows urgence, to-do | LARGE |
| **Digest Agent** | `digest_agent.py` | Synthese emails, rapports | LARGE |
| **Web Agent** | `web_agent.py` | Recherche web, extraction | FAST |
| **OCR Agent** | `ocr_agent.py` | Extraction texte images | Pixtral 12B |

### Agents World-Class (Phase 3)

| Agent | Fichier | Role | Declencheur |
|-------|---------|------|-------------|
| **Verification Agent** | `verification_agent.py` | Valide si chunks repondent | confidence < 0.40 |
| **Reflection Agent** | `reflection_agent.py` | Diagnostique echecs RAG | confidence < 0.30 |
| **Query Planning** | `query_planning_agent.py` | Decompose requetes complexes | Multi-hop queries |
| **Entity Extractor** | `entity_extractor.py` | Extrait entites metier | Enrichissement contexte |

---

## Flux de Classification des Intentions

```
                            REQUETE UTILISATEUR
                                    |
                                    v
                    +-------------------------------+
                    |      TEMPLATE FILTER          |
                    |   "Bonjour", "Merci", etc.    |
                    +-------------------------------+
                           |              |
                    Match  |              | No Match
                           v              v
                    +-------------+  +---------------------------+
                    | Reponse     |  |   LLM INTENT CLASSIFIER   |
                    | Template    |  |   (Mistral Large)         |
                    | (0ms)       |  |   Few-shot examples       |
                    +-------------+  +---------------------------+
                                              |
                                     confidence > 0.7?
                                       |          |
                                      Yes        No
                                       |          |
                                       v          v
                                  +--------+  +-----------------------+
                                  | Route  |  | INTENT CLASSIFIER V5  |
                                  | Agent  |  | (Keyword fallback)    |
                                  +--------+  +-----------------------+
                                                     |
                                                     v
                                              +-------------+
                                              | Route Agent |
                                              +-------------+
```

### Mapping Intention -> Agent

| Intention | Sources | Agent(s) Declenche(s) |
|-----------|---------|----------------------|
| `QUERY_DATA` | SQL | SQL Agent |
| `SEARCH_DOCUMENTS` | RAG | RAG Service + Synthesis |
| `LEGAL` | RAG + Legal | Legal Agent + RAG |
| `WEB_SEARCH` | Web | Web Agent |
| `SEND_EMAIL` | - | Email Agent |
| `TRIGGER_WORKFLOW` | - | Workflow Agent |
| `GENERAL_QUESTION` | SQL + RAG | Hybrid Executor |
| `GENERATE_DIGEST` | - | Digest Agent |

---

## Flux Email/Workflow Urgence

```
DETECTION URGENCE: "Degat des eaux au 3eme"
          |
          v
+-------------------+
| Intent: WORKFLOW  |
| Domain: EMERGENCY |
+-------------------+
          |
          v
+-----------------------------------+
|     WORKFLOW AGENT V2             |
|                                   |
| 1. classify_workflow() -> URGENCE |
| 2. Extract context:               |
|    - Lot: 3eme etage              |
|    - Type: Degat des eaux         |
|    - Severity: HIGH               |
+-----------------------------------+
          |
          v
+-----------------------------------+
|     CONTEXT ENRICHMENT            |
|                                   |
| SQL: Fetch owner, contacts        |
| RAG: Emergency procedures         |
+-----------------------------------+
          |
          v
+-----------------------------------+
|     TODO LIST GENERATION          |
|                                   |
| 1. [ ] Notifier proprietaire      |
| 2. [ ] Contacter plombier         |
| 3. [ ] Couper arrivee eau         |
| 4. [ ] Informer voisins           |
+-----------------------------------+
          |
          v
+-----------------------------------+
|     PREVIEW TO USER               |
| requires_confirmation: true       |
+-----------------------------------+
          |
    User: "Execute"
          |
          v
+-----------------------------------+
|     N8N WORKFLOW EXECUTION        |
|                                   |
| Step 1: Send email owner    [OK]  |
| Step 2: Send email plumber  [OK]  |
| Step 3: Log intervention    [OK]  |
+-----------------------------------+
          |
          v
+-----------------------------------+
|     CALLBACK & COMPLETION         |
| ThoughtStream: WORKFLOW_SUCCESS   |
+-----------------------------------+
```

---

## Integration Model Router

```
                         REQUETE ENTRANTE
                                |
                                v
                    +------------------------+
                    |     MODEL ROUTER       |
                    |     (Dec 2025)         |
                    +------------------------+
                                |
              +-----------------+-----------------+
              |                                   |
              v                                   v
    +-------------------+               +-------------------+
    |    FAST TIER      |               |    LARGE TIER     |
    |  ministral-8b     |               |  mistral-large    |
    +-------------------+               +-------------------+
              |                                   |
              |  Criteres:                        |  Criteres:
              |  - prompt < 50 chars              |  - mots-cles juridiques
              |  - classification                 |  - prompt > 2000 chars
              |  - post-OCR extraction            |  - multi-documents
              |  - email routine                  |  - urgence/critique
              |  - Q&A simple                     |  - analyse complexe
              |                                   |
              v                                   v
    +-------------------+               +-------------------+
    |  Latence: 200ms   |               |  Latence: 1-30s   |
    |  Cost: $0.10/M    |               |  Cost: $0.50-1.50 |
    +-------------------+               +-------------------+


                    VISION / OCR PIPELINE
                    =====================

                         Document PDF/Image
                                |
                                v
                    +------------------------+
                    |   PIXTRAL 12B          |
                    |   (Seul model vision)  |
                    +------------------------+
                                |
                                v
                    +------------------------+
                    |   Texte Extrait        |
                    |   (Structure conservee)|
                    +------------------------+
                                |
                                v
                    +------------------------+
                    |   Post-Processing      |
                    |   -> FAST model        |
                    |   (Extraction entites) |
                    +------------------------+
```

---

## Metriques et Observabilite

### LLM Metrics Logger

```python
# Chaque appel LLM est trace
{
    "call_id": "llm_1701234567_42",
    "model_tier": "fast",          # ou "large"
    "model_name": "ministral-8b-latest",
    "task_type": "classification",
    "latency_ms": 234.5,
    "tokens_in": 150,
    "tokens_out": 50,
    "estimated_cost_usd": 0.00002,
    "routing_reasoning": "simple task detected"
}
```

### Rapport de Couts

```python
metrics_logger.get_cost_report(hours=24)

# Output:
{
    "period_hours": 24,
    "actual_cost_usd": 0.45,
    "projected_monthly_usd": 13.50,
    "tier_breakdown": {
        "fast": {"cost_usd": 0.12, "percentage": 26.7},
        "large": {"cost_usd": 0.33, "percentage": 73.3}
    },
    "optimization_hints": [
        "Task 'simple_qa' uses LARGE predominantly - consider FAST"
    ]
}
```

---

## Points Cles Architecture

### Forces

1. **Execution Parallele** - SQL + RAG simultanement
2. **Routing Intelligent** - LLM + fallback keyword
3. **Fusion Multi-Source** - SQL facts + RAG context
4. **World-Class RAG** - Verification, Reflection, Reranking
5. **Cost-Optimized** - FAST/LARGE routing (~65% economies)
6. **Resilience** - Graceful degradation, timeouts
7. **Observabilite** - Metrics structurees, ThoughtStream

### Points d'Attention

1. **Pixtral 12B** seul model vision (Ministral 8B n'a PAS vision)
2. **Legal Agent** necessite LARGE pour precision juridique
3. **Timeouts** : 30s/agent, 60s/requete
4. **Classification fallback** si LLM incertain

---

## Fichiers Cles

| Fichier | Taille | Role |
|---------|--------|------|
| `orchestrator_agent.py` | 230KB | Orchestrateur principal |
| `legal_agent.py` | 104KB | Analyse juridique |
| `email_agent.py` | 78KB | Generation emails |
| `model_router.py` | 15KB | Routing FAST/LARGE |
| `llm_metrics_logger.py` | 10KB | Metriques LLM |
| `synthesis_agent.py` | 25KB | Generation + citations |
| `world_class_router.py` | 35KB | Pipeline RAG avance |

---

*Document genere le 3 Decembre 2025*
