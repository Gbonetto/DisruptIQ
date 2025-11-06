# 🏗️ ARCHITECTURE DisruptIQ
## Documentation Technique et Commerciale

**Version**: 3.0
**Date**: Novembre 2025
**Type**: Documentation technique & commerciale

---

## 📋 Table des Matières

1. [Vision & Positionnement](#vision--positionnement)
2. [Architecture Globale](#architecture-globale)
3. [Stack Technique](#stack-technique)
4. [Backend Architecture](#backend-architecture)
5. [Frontend Architecture](#frontend-architecture)
6. [Base de Données](#base-de-données)
7. [Système Multi-Agents](#système-multi-agents)
8. [Fonctionnalités Détaillées](#fonctionnalités-détaillées)
9. [Sécurité & Performance](#sécurité--performance)
10. [Déploiement & Infrastructure](#déploiement--infrastructure)

---

## 🎯 Vision & Positionnement

### Mission
DisruptIQ révolutionne la gestion de copropriétés en automatisant 80% des tâches répétitives grâce à l'intelligence artificielle.

### Proposition de Valeur

**Pour les Syndics**:
- ⏱️ **Gain de temps**: -15h/semaine (tri emails, recherche documents, rédaction)
- 🎯 **Précision**: Zéro oubli d'urgence grâce à la classification IA
- 📊 **Insights**: Analytics prédictifs sur budgets et incidents
- 🤖 **Automatisation**: Workflows N8N pour actions récurrentes

**ROI Client Typique**:
```
Coût solution: 749€/mois
Gain temps: 15h/semaine × 50€/h = 3000€/mois
ROI: 300% (4x retour sur investissement)
Payback: <1 mois
```

### Différenciation Concurrentielle

| Critère | DisruptIQ | Yooz | DocuWare | Logiciels métier |
|---------|-----------|------|----------|------------------|
| **IA Multi-Agents** | ✅ 7 agents | ❌ | ❌ | ❌ |
| **RAG Hybride** | ✅ SQL+Vector | ❌ | ⚠️ Basique | ❌ |
| **Classification Emails** | ✅ 92% précision | ⚠️ 70% | ❌ | ❌ |
| **Génération Emails** | ✅ Contextuels | ❌ | ❌ | ⚠️ Templates |
| **Workflows Automatisés** | ✅ N8N intégré | ❌ | ❌ | ⚠️ Limité |
| **Setup Time** | 🟢 <30min | 🔴 2-3 jours | 🔴 1-2 semaines | 🔴 1+ mois |
| **Prix/mois** | 749€ | 2000€+ | 3000€+ | 1500€+ |

---

## 🏛️ Architecture Globale

### Vue d'Ensemble

```
┌──────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                       │
│                      Neo-Rétro UI ChatGPT-style              │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTPS REST API
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                          │
│                  ┌──────────────────────┐                    │
│                  │  ORCHESTRATOR AGENT  │                    │
│                  │  Intent Classifier v3 │                   │
│                  └──────────┬───────────┘                    │
│                             │                                 │
│        ┌────────────────────┼────────────────────┐          │
│        │                    │                    │          │
│        ▼                    ▼                    ▼          │
│  ┌──────────┐        ┌──────────┐        ┌──────────┐      │
│  │SQL Agent │        │RAG Agent │        │Email Agnt│      │
│  └────┬─────┘        └────┬─────┘        └────┬─────┘      │
└───────┼───────────────────┼───────────────────┼─────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ PostgreSQL   │    │   Qdrant     │    │    Gmail     │
│  (Données)   │    │  (Vectors)   │    │   (SMTP)     │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │
        └───────┬───────────┘
                ▼
        ┌──────────────┐
        │    Redis     │
        │   (Cache)    │
        └──────────────┘
```

### Flux de Données Principal

1. **User Input** → Frontend (React)
2. **API Call** → Backend (FastAPI)
3. **Intent Classification** → Orchestrator Agent (LLM)
4. **Routing** → Agent spécialisé (SQL/RAG/Email/Workflow)
5. **Execution** → Database/Vector DB/External API
6. **Stream Response** → SSE (Server-Sent Events)
7. **Display** → Frontend avec Markdown + Chain of Thoughts

---

## 💻 Stack Technique

### Backend
```yaml
Framework: FastAPI 0.115+ (Python 3.11+)
ORM: SQLAlchemy 2.0 (async)
Database: PostgreSQL 15
Vector DB: Qdrant 1.11+
Cache: Redis 7+
LLM: OpenAI GPT-4 + Anthropic Claude (fallback)
Embeddings: OpenAI text-embedding-3-small
Task Queue: APScheduler (→ Celery v4.0)
Logging: Structlog
Validation: Pydantic 2.8+
```

### Frontend
```yaml
Framework: React 18 + TypeScript 5
Build: Vite 5
UI: Tailwind CSS + Shadcn/UI
State: React Query + Context API
Router: React Router v6
Markdown: react-markdown + remark-gfm
Icons: Lucide React
Animations: Framer Motion (v4.0)
```

### Infrastructure
```yaml
Containers: Docker + Docker Compose
Reverse Proxy: Nginx
Migrations: Alembic
CI/CD: GitHub Actions
Monitoring: Prometheus + Grafana + Sentry
SSL: Let's Encrypt (Certbot)
```

---

## 🔧 Backend Architecture

### Structure Modulaire

```
backend/
├── app/
│   ├── api/
│   │   └── endpoints/          # REST API Controllers
│   │       ├── chat.py         # Assistant chat
│   │       ├── admin.py        # Admin panel
│   │       ├── digest.py       # Email digest
│   │       └── documents.py    # Upload/OCR
│   │
│   ├── core/
│   │   ├── config.py           # Settings (Pydantic)
│   │   ├── database.py         # Async session
│   │   └── security.py         # JWT + Auth
│   │
│   ├── models/                 # SQLAlchemy ORM
│   │   ├── user.py
│   │   ├── conversation.py     # ✅ v3.0
│   │   ├── message.py          # ✅ v3.0
│   │   ├── copropriete.py
│   │   ├── coproprietaire.py
│   │   ├── professionnel.py
│   │   ├── email.py
│   │   └── document.py
│   │
│   ├── schemas/                # Pydantic Validation
│   │   ├── chat.py
│   │   ├── admin.py
│   │   └── ...
│   │
│   ├── services/               # Business Logic
│   │   ├── agents/             # Multi-Agent System
│   │   │   ├── orchestrator_agent.py
│   │   │   ├── intent_classifier_v3.py  # ✅ 92% précision
│   │   │   ├── sql_agent.py
│   │   │   ├── rag_agent.py
│   │   │   ├── email_agent.py
│   │   │   ├── workflow_agent.py
│   │   │   ├── digest_agent.py
│   │   │   └── ocr_agent.py
│   │   │
│   │   ├── rag_service.py      # RAG Hybrid
│   │   ├── email_processor.py  # Classification
│   │   ├── document_service.py # OCR/Extract
│   │   └── state_manager.py    # Conversation state
│   │
│   └── utils/
│       ├── logger.py           # Structlog
│       └── validators.py       # Input validation
│
├── alembic/                    # Database migrations
├── tests/                      # Pytest tests
└── main.py                     # FastAPI app entry
```

### API Endpoints

#### Chat Assistant
```http
POST /api/chat
GET /api/chat/stream          # SSE
GET /api/chat/conversations
GET /api/chat/conversations/{id}
POST /api/chat/conversations/{id}/messages
```

#### Admin Panel
```http
GET /api/admin/coproprietes
POST /api/admin/coproprietes
PUT /api/admin/coproprietes/{id}
DELETE /api/admin/coproprietes/{id}

# Same for: coproprietaires, professionnels, emails, documents
```

#### Digest & Documents
```http
GET /api/digest                # Email classification
POST /api/digest/generate
POST /api/documents/upload
GET /api/documents/{id}
```

#### Health & Monitoring
```http
GET /health
GET /health/db
GET /health/redis
GET /health/qdrant
GET /metrics                   # Prometheus
```

---

## 🎨 Frontend Architecture

### Structure Modulaire

```
frontend/
├── src/
│   ├── pages/                  # Pages principales
│   │   ├── MainChatPage.tsx   # Assistant chat (Neo-Rétro UI)
│   │   ├── AdminDashboard.tsx
│   │   ├── DigestPage.tsx
│   │   └── SettingsPage.tsx
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   └── AppLayout.tsx  # Sidebar navigation
│   │   │
│   │   ├── chat/
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   └── QuickActions.tsx
│   │   │
│   │   ├── ChainOfThought/    # ✅ Temps réel
│   │   │   ├── ProfessionalCoT.tsx
│   │   │   └── SQLExecutionCoT.tsx
│   │   │
│   │   └── ui/                # Shadcn/UI components
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       └── ...
│   │
│   ├── hooks/                  # Custom React hooks
│   │   ├── useChat.ts
│   │   ├── useSSE.ts          # Server-Sent Events
│   │   └── useConversations.ts
│   │
│   ├── lib/
│   │   ├── api.ts             # Axios client
│   │   └── utils.ts           # cn(), formatTimeAgo()
│   │
│   └── types/
│       ├── chat.ts
│       └── admin.ts
│
├── public/
└── index.html
```

### État & Data Fetching

**React Query** pour toutes les API calls:
```typescript
// Exemple: useConversations hook
const { data, isLoading, error } = useQuery({
  queryKey: ['conversations'],
  queryFn: () => api.get('/chat/conversations'),
  staleTime: 5 * 60 * 1000, // 5 min cache
})
```

**Context API** pour état global:
- Auth context (user, token)
- Theme context (dark mode v4.0)

---

## 🗄️ Base de Données

### Schéma PostgreSQL

#### Tables Métier (9 tables)

**1. users** - Authentification
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    full_name VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

**2. conversations** - Historique chat ✅ v3.0
```sql
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    session_id VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**3. messages** - Messages chat ✅ v3.0
```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user' | 'assistant'
    content TEXT NOT NULL,
    thoughts JSON,           -- Chain of Thoughts
    sources JSON,            -- Citations RAG
    suggestions JSON,        -- Actions suggérées
    data JSON,               -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
```

**4. coproprietes** - Immeubles
```sql
CREATE TABLE coproprietes (
    id SERIAL PRIMARY KEY,
    nom VARCHAR NOT NULL,
    adresse TEXT NOT NULL,
    ville VARCHAR NOT NULL,
    code_postal VARCHAR(10),
    nombre_lots INTEGER,
    syndic VARCHAR,
    equipements JSON DEFAULT '[]',
    is_indexed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_coproprietes_ville ON coproprietes(ville);
```

**5. coproprietaires** - Résidents
```sql
CREATE TABLE coproprietaires (
    id SERIAL PRIMARY KEY,
    nom VARCHAR NOT NULL,
    prenom VARCHAR NOT NULL,
    email VARCHAR,
    telephone VARCHAR,
    copropriete_id INTEGER REFERENCES coproprietes(id),
    numero_lot VARCHAR NOT NULL,
    statut VARCHAR DEFAULT 'proprietaire',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(copropriete_id, numero_lot)
);
CREATE INDEX idx_coproprietaires_copropriete ON coproprietaires(copropriete_id);
```

**6. professionnels** - Prestataires (anciennement vendors)
```sql
CREATE TABLE professionnels (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    company_name VARCHAR,
    email VARCHAR UNIQUE NOT NULL,
    phone VARCHAR,
    category VARCHAR,         -- 'plombier', 'electricien'
    rating FLOAT DEFAULT 0.0,
    total_jobs INTEGER DEFAULT 0,
    is_indexed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_professionnels_category ON professionnels(category);
```

**7. emails** - Emails traités
```sql
CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR UNIQUE,
    sender VARCHAR NOT NULL,
    subject VARCHAR NOT NULL,
    body TEXT,
    urgency VARCHAR,          -- 'URGENT' | 'IMPORTANT' | 'ROUTINE'
    category VARCHAR,
    attachments JSON DEFAULT '[]',
    processed BOOLEAN DEFAULT FALSE,
    received_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_emails_urgency ON emails(urgency, received_at);
```

**8. documents** - Documents indexés
```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR NOT NULL,
    file_path VARCHAR,
    file_size BIGINT,
    mime_type VARCHAR,
    document_type VARCHAR,
    extracted_text TEXT,      -- OCR result
    summary TEXT,             -- LLM summary
    qdrant_id VARCHAR,        -- Vector DB reference
    indexed BOOLEAN DEFAULT FALSE,
    uploaded_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_documents_qdrant ON documents(qdrant_id);
```

**9. professionnels_coproprietes** - Junction table
```sql
CREATE TABLE professionnels_coproprietes (
    professionnel_id INTEGER REFERENCES professionnels(id),
    copropriete_id INTEGER REFERENCES coproprietes(id),
    date_debut DATE,
    nombre_interventions INTEGER DEFAULT 0,
    PRIMARY KEY (professionnel_id, copropriete_id)
);
```

### Migrations Alembic ✅

```bash
# Créer migration
alembic revision --autogenerate -m "add_conversations_table"

# Appliquer
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🤖 Système Multi-Agents

### Architecture Agents

**7 Agents Spécialisés** coordonnés par l'Orchestrator:

#### 1. Orchestrator Agent
**Rôle**: Router intelligent basé sur Intent Classifier v3

```python
# Intent classification avec 92% précision
classification = await intent_classifier_v3.classify(
    user_input="liste des plombiers certifiés",
    conversation_history=[...],
    context={...}
)

# Routing vers agent approprié
if classification.intent == IntentType.QUERY_DATA:
    return await sql_agent.execute(user_input)
elif classification.intent == IntentType.SEARCH_DOCUMENTS:
    return await rag_agent.search(user_input)
```

**Features**:
- Quick Rules (100-150ms) pour patterns simples
- Anaphora resolution ("lesquelles", "leur", "ces bâtiments")
- Chain-of-Thought LLM classification
- Confidence scoring (0.0-1.0)

#### 2. SQL Agent
**Rôle**: Text-to-SQL + Execution

```python
# Conversion langage naturel → SQL
user: "liste des plombiers avec rating >4"
→ SELECT * FROM professionnels 
   WHERE category='plombier' AND rating > 4 
   ORDER BY rating DESC
```

**Features**:
- GPT-4 pour génération SQL sécurisée
- Whitelist tables (sécurité)
- Fast formatting (pas d'appel LLM supplémentaire)
- Retry logic si erreur SQL

#### 3. RAG Agent
**Rôle**: Recherche sémantique documents

```python
# Hybrid search: Vector + SQL
results = await rag_agent.search_hybrid(
    query="procédure dégât des eaux",
    top_k=5,
    filters={"document_type": "procedure"}
)
```

**Features**:
- Embeddings OpenAI (text-embedding-3-small)
- Qdrant vector search
- Fallback SQL si pas de match vector
- Citation extraction automatique
- Action lists pour procédures

#### 4. Email Agent
**Rôle**: Génération emails contextuels

```python
# Génération email avec contexte
email = await email_agent.generate(
    context="dégât des eaux chez Mme Durant",
    recipients=["plombier@example.com"],
    tone="professional"
)
```

**Features**:
- Génération GPT-4 personnalisée
- Contexte conversation inclus
- Preview avant envoi
- SMTP Gmail ou N8N webhook

#### 5. Workflow Agent
**Rôle**: Déclenchement N8N workflows

```python
# Déclencher workflow automatisé
await workflow_agent.trigger(
    workflow="notify_neighbors_emergency",
    data={"building_id": 123, "type": "water_leak"}
)
```

**Features**:
- Webhooks N8N configurables
- Confirmation utilisateur (v3.2)
- Dry-run mode
- Retry logic

#### 6. Digest Agent
**Rôle**: Classification emails batch

```python
# Digest quotidien automatique
digest = await digest_agent.generate(
    emails=unprocessed_emails,
    urgency_threshold="IMPORTANT"
)
```

**Features**:
- Batch classification (économie API calls)
- Tri URGENT/IMPORTANT/ROUTINE
- Scheduler automatique (60 min)
- Export PDF/Email

#### 7. OCR Agent
**Rôle**: Extraction texte documents

```python
# OCR document uploadé
text = await ocr_agent.extract(
    file_path="/uploads/facture.pdf",
    lang="fra"
)
```

**Features**:
- Tesseract OCR pour images
- PyPDF2 pour PDFs
- Structuration données (factures)
- Indexation auto Qdrant

---

## 🎯 Fonctionnalités Détaillées

### 1. Assistant Chat Intelligent ✅

**Interface Neo-Rétro**:
- Couleurs flash (cyan, violet, pink, green)
- Pixel art borders et effets CRT
- Markdown rendering (tables, listes, code)
- Chain of Thoughts temps réel (SSE)

**Capabilities**:
```
User: "liste des plombiers de Paris"
→ SQL Agent: SELECT * FROM professionnels WHERE city='Paris' AND category='plombier'
→ Display: Table formatée + 5 résultats

User: "lesquelles sont certifiées?"
→ Intent v3: Anaphora detected → QUERY_DATA (confidence: 0.92)
→ SQL Agent: ... WHERE certification=TRUE
```

### 2. RAG Hybrid Search ✅

**Modes**:
- **Vector Search**: Qdrant (similarité sémantique)
- **SQL Fallback**: PostgreSQL full-text search
- **Hybrid**: Combinaison des deux

**Example**:
```
User: "procédure dégât des eaux"
→ RAG Agent: 
  1. Vector search Qdrant (similarity >0.8)
  2. Extract citations (page, paragraphe)
  3. Generate action list si procédure détectée
  4. Return formatted markdown + sources
```

**Action Lists Automatiques**:
```markdown
## Actions Urgentes
1. ☎️ Contacter plombier d'urgence (+33...)
2. 🚰 Fermer arrivée d'eau générale
3. 📸 Photographier dégâts (assurance)
4. 📧 Informer copropriétaires étage inférieur
```

### 3. Digest Quotidien Automatique ✅

**Classification Tri-Level**:
- 🔴 **URGENT**: Dégâts, pannes, urgences (réponse <2h)
- 🟡 **IMPORTANT**: Devis, réclamations (réponse <24h)
- 🟢 **ROUTINE**: Infos, newsletters (réponse flexible)

**Scheduler**:
```python
# APScheduler - Chaque 60 minutes
@scheduler.scheduled_job('interval', minutes=60)
async def auto_digest():
    unprocessed = await get_unprocessed_emails()
    digest = await digest_agent.generate(unprocessed)
    await notify_syndic(digest)
```

**Performance**: 62s pour 29 emails (vs 21+ min avant v2.0)

### 4. Génération Emails Contextuels ✅

**Contexte Intelligent**:
```python
context = {
    "conversation_history": last_10_messages,
    "related_documents": rag_results,
    "recipient_info": professional_data,
    "building_context": copropriete_info
}

email = await email_agent.generate(
    prompt="génère email pour plombier dégât des eaux",
    context=context
)
```

**Output**:
```
Objet: Urgence - Dégât des eaux Résidence Les Mimosas
Corps: 
Bonjour M. Dupont,

Suite au dégât des eaux survenu ce jour à 14h30 au 
3ème étage (appartement Mme Durant), nous sollicitons 
votre intervention en urgence.

Contexte:
- Fuite canalisation salle de bain
- Dégâts plafond appartement inférieur
- Eau coupée depuis 15h00

Merci de nous confirmer votre disponibilité dans les 2h.

Cordialement,
[Signature syndic]
```

### 5. Workflows N8N Automatisés ✅

**Use Cases**:
- Notification voisins (urgence)
- Devis professionnels automatiques
- Archivage documents
- Alertes SMS copropriétaires

**Example Workflow**:
```yaml
Trigger: Dégât des eaux détecté
Steps:
  1. Récupérer liste copropriétaires étages -1/+1
  2. Générer email notification
  3. Envoyer via SMTP
  4. Logger dans historique
  5. Créer ticket suivi
```

### 6. Admin Panel CRUD ✅

**Gestion Données**:
- ✅ Copropriétés (create, read, update, delete)
- ✅ Copropriétaires
- ✅ Professionnels
- ✅ Emails (view, filter)
- ✅ Documents (view, re-index, delete)

**Bulk Operations** (v3.2):
- CSV import (100+ lignes)
- Delete multiple
- Bulk re-indexing

### 7. Conversation Persistence ✅ v3.0

**Features**:
- Historique complet conversations
- Resume session précédente
- Search in history
- Export conversations (PDF/JSON)

**Storage**:
```
conversations/
├── id: 123
├── title: "Recherche plombiers + Devis"
├── session_id: "sess_abc123"
├── messages: [
│   {role: "user", content: "liste plombiers"},
│   {role: "assistant", content: "...", thoughts: {...}}
│]
```

---

## 🔒 Sécurité & Performance

### Sécurité

#### Authentification
- JWT tokens (HS256)
- Refresh tokens (v4.0)
- 2FA/MFA (v4.5)
- SSO SAML (v4.5)

#### Validations
```python
# SQL Injection Prevention
ALLOWED_TABLES = [
    'coproprietes', 'coproprietaires',
    'professionnels', 'emails', 'documents'
]

# Upload Security
ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.png', '.jpg']
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
```

#### Rate Limiting
```python
# API endpoints
@limiter.limit("100/hour")
async def query_sql(...)

# Upload endpoints
@limiter.limit("10/hour")
async def upload_document(...)
```

### Performance

#### Backend
- Async everywhere (FastAPI + SQLAlchemy)
- Connection pooling (20 connections)
- Redis caching (notifications, stats)
- Query optimization (indexes, EXPLAIN)

#### Frontend
- Code splitting (React.lazy)
- Tree-shaking (lucide-react)
- Bundle <200KB gzipped (target <150KB v4.0)
- Service workers (offline v4.0)

#### Monitoring
```yaml
Metrics:
  - API latency (p50, p95, p99)
  - Database queries (slow query log)
  - Redis cache hit rate
  - LLM API costs

Alerting:
  - Error rate >1%
  - Latency p95 >2s
  - Database connections >80%
  - Disk usage >85%
```

---

## 🚀 Déploiement & Infrastructure

### Docker Compose Production

```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql+asyncpg://...
      - REDIS_URL=redis://redis:6379
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - postgres
      - redis
      - qdrant

  frontend:
    build: ./frontend
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt

  postgres:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  qdrant:
    image: qdrant/qdrant:v1.11.0
    volumes:
      - qdrant_data:/qdrant/storage

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

### VPS Requirements

**Minimum**:
- CPU: 4 cores
- RAM: 8 GB
- Disk: 100 GB SSD
- OS: Ubuntu 22.04 LTS

**Recommended**:
- CPU: 8 cores
- RAM: 16 GB
- Disk: 200 GB SSD

### Backup Strategy

```bash
# Daily automated backups
0 2 * * * /scripts/backup_postgres.sh
0 3 * * * /scripts/backup_qdrant.sh
0 4 * * * /scripts/backup_documents.sh

# 3-2-1 Rule:
# - 3 copies
# - 2 different media (local + cloud)
# - 1 offsite (S3/Backblaze)
```

---

## 📊 Métriques & KPIs

### Métriques Techniques Actuelles (v3.0)

```
Tests Coverage:        60% (target: 80% v3.2)
API p95 Latency:       ~2s (target: <1s v3.2)
Frontend Bundle:       273KB gzipped (target: <150KB v4.0)
Uptime SLA:            99% (target: 99.5% v3.2)
Intent Classification: 92% accuracy
RAG Precision:         85% (with citations)
Digest Speed:          62s for 29 emails
Database Queries:      <100ms avg
```

### Roadmap Performance Targets

| Métrique | v3.0 | v3.2 | v4.0 | v4.5 |
|----------|------|------|------|------|
| Tests Coverage | 60% | 80% | 85% | 90% |
| Uptime SLA | 99% | 99.5% | 99.9% | 99.99% |
| API Latency p95 | 2s | <1s | <500ms | <300ms |
| Frontend Bundle | 273KB | 200KB | 130KB | 120KB |
| Concurrent Users | 10 | 50 | 200 | 500 |

---

## 🎓 Documentation & Support

### Documentation Disponible

- ✅ **ROADMAP.md**: Vision produit 2025-2026
- ✅ **PRD.md**: Product Requirements Document complet
- ✅ **PRODUCTION_CHECKLIST.md**: Checklist déploiement
- ✅ **ARCHITECTURE.md**: Ce document
- ✅ **README.md**: Quick start
- ✅ **INTENT_CLASSIFIER_V3_GUIDE.md**: Guide technique v3
- ✅ API Documentation: OpenAPI/Swagger (à venir v3.2)

### Support & Contact

**Technique**:
- GitHub Issues: Bug reports & feature requests
- Email technique: tech@disruptiq.fr
- Documentation: docs.disruptiq.fr

**Commercial**:
- Demo: demo.disruptiq.fr
- Email commercial: contact@disruptiq.fr
- Calendrier démo: calendly.com/disruptiq

---

## 🔮 Vision Future

### V4.0 - Q1 2026
- Mobile app (React Native)
- Dark mode complet
- API publique + SDK
- 20+ clients actifs

### V4.5 - Q2 2026
- Multi-tenancy enterprise
- OCR factures avancé
- Analytics dashboard
- 50+ clients actifs

### V5.0 - Q4 2026
- Kubernetes deployment
- IA prédictive (ML forecasting)
- Marketplace workflows
- 100+ clients, 1.2M€ ARR

---

*Documentation technique et commerciale - Version 3.0*
*Dernière mise à jour: 6 Novembre 2025*
*Contact: tech@disruptiq.fr*
