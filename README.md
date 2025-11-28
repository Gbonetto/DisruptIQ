# DisruptIQ - Assistant IA pour Syndics de Copropriété

**Version**: 3.2 World-Class
**Status**: Production Ready

DisruptIQ est un assistant IA multi-agents conçu pour automatiser et optimiser le travail des syndics de copropriété.

## Architecture World-Class

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React 18)                           │
│                    Neo-Retro UI + Chain of Thoughts                     │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ WebSocket + REST API
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR AGENT                                  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │          LLM INTENT CLASSIFIER (World-Class)                       │ │
│  │                                                                     │ │
│  │  Primary: Groq/Llama-3.1-8B (~800ms, 100% accuracy)               │ │
│  │  Fallback: Mistral/small-latest                                    │ │
│  │                                                                     │ │
│  │  8 Intent Types:                                                   │ │
│  │  • query_data → SQL Agent                                          │ │
│  │  • search_documents → RAG Agent                                    │ │
│  │  • legal → Legal Agent (Légifrance)                               │ │
│  │  • send_email → Email Agent                                        │ │
│  │  • web_search → Web Agent (Brave/DuckDuckGo)                      │ │
│  │  • trigger_workflow → Workflow Agent (N8N)                         │ │
│  │  • generate_digest → Digest Agent                                  │ │
│  │  • general_question → General Agent                                │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SQL Agent     │    │   RAG Agent     │    │  Legal Agent    │
│   PostgreSQL    │    │   Qdrant        │    │   Légifrance    │
│   Entity Graph  │    │   ColBERT FR    │    │   API PISTE     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- Node.js 18+
- API Keys: Groq, Mistral, Brave Search (optional)

### 2. Configuration

```bash
# Clone & setup
cd DisruptIQ_CC2
cp backend/.env.example backend/.env

# Configure API keys in backend/.env
GROQ_API_KEY=gsk_xxxxxxxxxxxx          # Primary - ultra-fast
MISTRAL_API_KEY=xxxxxxxxxxxx            # Fallback
BRAVE_SEARCH_API_KEY=xxxxxxxxxxxx       # Optional - web search
```

### 3. Launch

```bash
# Start all services
docker-compose up -d

# Rebuild backend with latest code
docker-compose build backend --no-cache
docker-compose restart backend

# Check logs
docker logs disruptiq_backend -f
```

### 4. Access

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **N8N Workflows**: http://localhost:5678

## LLM Configuration

### Groq (Primary - Ultra Fast)

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxx
GROQ_MODEL=llama-3.1-8b-instant        # ~800ms latency
GROQ_MODEL_FALLBACK=llama-3.3-70b-versatile
```

**Performance**:
- Latency: ~800ms (34% faster than Mistral)
- Accuracy: 100% (23/23 tests)
- Cost: ~$0.05/M tokens

### Mistral (Fallback)

```env
MISTRAL_API_KEY=xxxxxxxxxxxx
MISTRAL_MODEL=mistral-small-latest
```

## Multi-Agent System

| Agent | Intent | Description |
|-------|--------|-------------|
| **SQL Agent** | `query_data` | Requêtes BDD (copropriétaires, lots, charges) |
| **RAG Agent** | `search_documents` | Recherche documents (factures, contrats, PV) |
| **Legal Agent** | `legal` | Recherche juridique (Légifrance API) |
| **Email Agent** | `send_email` | Rédaction & envoi emails |
| **Web Agent** | `web_search` | Recherche internet (Brave/DuckDuckGo) |
| **Workflow Agent** | `trigger_workflow` | Automation N8N (urgences, processus) |
| **Digest Agent** | `generate_digest` | Résumés emails & activité |

## Key Features

### Chain of Thoughts (CoT)

Transparence totale du raisonnement IA en temps réel via SSE:

```
🔍 Analyse de la requête...
📊 Classification: query_data (100%)
🗃️ Génération SQL: SELECT COUNT(*) FROM copropriétaires...
✅ Résultat: 45 copropriétaires
```

### Intent Classifier World-Class

- **100% accuracy** sur 23 types de requêtes
- **Cascading prompts** supportés (follow-up questions)
- **Context-aware** (historique conversation)
- **Fallback cascade**: Groq fast → Groq accurate → Mistral → Keywords

### RAG Hybride

- **Vector Search**: Qdrant + Mistral Embeddings (1024 dims)
- **Reranking**: ColBERT français (antoinelouis/colbert-xm-v1)
- **Tokenization**: spaCy français (fr_core_news_md)

## API Endpoints

```
POST /api/assistant-v2/chat          # Chat avec streaming
GET  /api/assistant-v2/stream/{id}   # SSE Chain of Thoughts
GET  /api/coproprietes               # Liste copropriétés
GET  /api/copropriétaires            # Liste copropriétaires
POST /api/documents/upload           # Upload document
GET  /api/documents/{id}/search      # RAG search
```

## Development

### Run Tests

```bash
cd backend

# Basic classifier tests (23 queries)
python test_llm_classifier.py

# Context & cascading tests
python test_classifier_context.py

# Groq vs Mistral benchmark
python test_groq_vs_mistral.py
```

### Project Structure

```
DisruptIQ_CC2/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI routes
│   │   ├── core/                   # Config, security
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── services/
│   │   │   └── agents/             # Multi-agent system
│   │   │       ├── orchestrator_agent.py
│   │   │       ├── llm_intent_classifier.py  # Groq/Mistral
│   │   │       ├── sql_agent.py
│   │   │       ├── rag_agent.py
│   │   │       └── ...
│   │   └── main.py
│   └── requirements.txt
├── frontend/                       # React 18 + TypeScript
├── n8n/workflows/                  # N8N automation
└── docker-compose.yml
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, TypeScript, Tailwind CSS |
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic |
| **LLM** | Groq (Llama 3.1 8B), Mistral |
| **Vector DB** | Qdrant |
| **Database** | PostgreSQL |
| **Cache** | Redis |
| **Automation** | N8N |
| **Container** | Docker Compose |

## License

Proprietary - DisruptIQ 2025

---

**Last Updated**: November 28, 2025
**Version**: 3.2 World-Class
