# 🏗️ Architecture DisruptIQ

## 📋 Vue d'Ensemble

DisruptIQ est une application full-stack construite avec une architecture moderne et scalable :
- **Backend** : FastAPI (Python) - API REST asynchrone
- **Frontend** : React + Vite + TypeScript - SPA moderne
- **Base de données** : PostgreSQL - Données structurées
- **Vector DB** : Qdrant - Recherche sémantique RAG
- **Cache** : Redis - Sessions et cache
- **AI/LLM** : OpenAI + LangChain - Classification et génération

---

## 🎯 Principes Architecturaux

### 1. **Separation of Concerns**
Chaque composant a une responsabilité claire et définie.

### 2. **Asynchronous First**
Utilisation d'async/await partout pour les performances.

### 3. **Type Safety**
- Python : Pydantic pour validation
- TypeScript : Typage strict frontend

### 4. **Idempotence**
Les opérations peuvent être rejouées sans effet de bord.

### 5. **Fail-Safe**
Gestion robuste des erreurs avec rollback automatique.

---

## 🔧 Backend Architecture

### Structure des Dossiers

```
backend/
├── app/
│   ├── api/
│   │   └── endpoints/      # Controllers REST
│   │       ├── admin.py    # Gestion admin
│   │       ├── chat.py     # Assistant RAG
│   │       ├── digest.py   # Email digest
│   │       └── documents.py
│   ├── core/
│   │   ├── config.py       # Configuration centralisée
│   │   ├── database.py     # Session DB
│   │   └── security.py     # Auth & JWT
│   ├── models/             # SQLAlchemy ORM
│   │   ├── user.py
│   │   ├── email.py
│   │   ├── vendor.py
│   │   └── document.py
│   ├── schemas/            # Pydantic Validation
│   │   ├── email.py
│   │   ├── vendor.py
│   │   └── ...
│   ├── services/           # Business Logic
│   │   ├── email_processor.py     # Classification emails
│   │   ├── rag_service.py         # RAG avec Qdrant
│   │   ├── vendor_index_service.py # Indexation vendors
│   │   └── document_service.py    # Extraction documents
│   └── utils/              # Helpers
│       ├── logger.py
│       └── validators.py
├── migrations/             # SQL migrations
├── scripts/                # Utilitaires
│   └── gmail_auth.py
└── main.py                 # Entry point
```

### Flux de Données

```
┌─────────────┐
│   Client    │
│  (Frontend) │
└──────┬──────┘
       │ HTTP/REST
       ▼
┌─────────────────────┐
│  FastAPI Router     │
│  (Endpoints)        │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Pydantic Schema    │
│  (Validation)       │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Business Service   │
│  (Logic métier)     │
└──────┬──────────────┘
       │
       ▼
┌──────────────────────────────┐
│  Data Layer                  │
│  ├── PostgreSQL (CRUD)       │
│  ├── Qdrant (Vectors)        │
│  └── Redis (Cache)           │
└──────────────────────────────┘
```

### Services Critiques

#### 1. **Email Processor** (`email_processor.py`)
```python
Responsabilités:
- Connexion Gmail API
- Récupération emails non lus
- Classification par urgence (LLM)
- Génération digest HTML
- Persistence en base

Pattern: Service Layer
Dépendances: OpenAI, Gmail API, PostgreSQL
```

#### 2. **RAG Service** (`rag_service.py`)
```python
Responsabilités:
- Embedding de texte (OpenAI)
- Stockage vecteurs (Qdrant)
- Recherche sémantique
- Retrieval augmented generation

Pattern: Repository Pattern
Dépendances: OpenAI, Qdrant, LangChain
```

#### 3. **Vendor Index Service** (`vendor_index_service.py`)
```python
Responsabilités:
- Conversion vendor → texte
- Indexation dans Qdrant
- Synchronisation PostgreSQL/Qdrant
- Gestion statut is_indexed

Pattern: Service Layer + Repository
Dépendances: Qdrant, PostgreSQL
Innovation: IDs négatifs pour vendors dans Qdrant
```

### Gestion des Erreurs

```python
try:
    # Business logic
    result = await service.do_something()
    await db.commit()
    return result
except ValidationError as e:
    # Données invalides
    raise HTTPException(400, detail=str(e))
except NotFoundError as e:
    # Ressource introuvable
    raise HTTPException(404, detail=str(e))
except Exception as e:
    # Erreur inattendue
    await db.rollback()
    logger.error("operation_failed", error=str(e))
    raise HTTPException(500, detail="Internal error")
```

---

## 🎨 Frontend Architecture

### Structure des Dossiers

```
frontend/src/
├── components/
│   ├── ui/              # Shadcn/ui components
│   ├── Dashboard.tsx    # Dashboard digest
│   ├── EmailCard.tsx    # Card d'email
│   └── Layout.tsx       # Layout principal
├── pages/
│   ├── DashboardPage.tsx
│   ├── ChatPage.tsx
│   ├── AdminPage.tsx
│   └── DocumentsPage.tsx
├── hooks/
│   ├── useApi.ts        # React Query hooks
│   └── useUrgentCount.ts # Custom hooks
├── lib/
│   ├── api.ts           # API client (axios)
│   └── utils.ts         # Utilitaires
├── styles/
│   └── globals.css
└── App.tsx              # Routes & config
```

### Flux de Données Frontend

```
┌──────────────┐
│  User Action │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Component   │
│  (onClick)   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  API Hook    │
│  (React Query)
└──────┬───────┘
       │ HTTP Request
       ▼
┌──────────────┐
│  Backend API │
└──────┬───────┘
       │ Response
       ▼
┌──────────────┐
│  Cache Update│
│  (React Query)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Re-render   │
│  Component   │
└──────────────┘
```

### State Management

**React Query** pour les données serveur :
- Cache automatique
- Invalidation smart
- Retry logic
- Loading states

**React State** pour l'UI locale :
- Forms
- Modal states
- UI toggles

### Performance Optimizations

1. **Code Splitting**
   ```typescript
   const AdminPage = lazy(() => import('./pages/AdminPage'))
   ```

2. **Memoization**
   ```typescript
   const filteredVendors = useMemo(() =>
     vendors.filter(v => v.name.includes(search)),
     [vendors, search]
   )
   ```

3. **Virtualization** (Pour longues listes)
   ```typescript
   <VirtualList items={vendors} renderItem={VendorCard} />
   ```

---

## 🗄️ Base de Données

### PostgreSQL Schema

```sql
-- Users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Emails
CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR UNIQUE NOT NULL,
    sender VARCHAR NOT NULL,
    subject TEXT,
    body TEXT,
    urgency VARCHAR CHECK (urgency IN ('urgent', 'important', 'routine')),
    received_at TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vendors
CREATE TABLE vendors (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    company_name VARCHAR,
    email VARCHAR UNIQUE NOT NULL,
    phone VARCHAR,
    category VARCHAR,
    specialties JSONB DEFAULT '[]',
    address TEXT,
    city VARCHAR,
    postal_code VARCHAR,
    rating FLOAT DEFAULT 0.0,
    total_jobs INT DEFAULT 0,
    is_indexed BOOLEAN DEFAULT FALSE,
    last_indexed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

-- Documents
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    mime_type VARCHAR,
    size_bytes INT,
    uploaded_by INT REFERENCES users(id),
    indexed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Indexes Critiques

```sql
-- Performance indexes
CREATE INDEX idx_emails_urgency ON emails(urgency);
CREATE INDEX idx_emails_received_at ON emails(received_at DESC);
CREATE INDEX idx_vendors_category ON vendors(category);
CREATE INDEX idx_vendors_city ON vendors(city);
CREATE INDEX idx_vendors_is_indexed ON vendors(is_indexed);
CREATE INDEX idx_vendors_email ON vendors(email);
```

---

## 🔍 Qdrant Vector Database

### Collection Schema

```python
{
    "name": "disruptiq_documents",
    "vectors": {
        "size": 1536,  # OpenAI embedding dimension
        "distance": "Cosine"
    }
}
```

### Document IDs Convention

```
Positive IDs (1, 2, 3, ...)  → Real documents
Negative IDs (-1, -2, -3, ...) → Vendors
```

**Pourquoi?** Éviter les conflits entre documents et vendors.

### Metadata Structure

```python
# Document
{
    "source": "document",
    "document_id": 123,
    "filename": "rapport.pdf",
    "page": 5
}

# Vendor
{
    "source": "vendor",
    "vendor_id": 45,
    "vendor_name": "Jean Dupont",
    "vendor_email": "jean@example.fr",
    "category": "Plomberie",
    "city": "Paris"
}
```

---

## 🔄 Synchronisation PostgreSQL ↔ Qdrant

### Le Problème

PostgreSQL et Qdrant peuvent se désynchroniser si :
- Qdrant est vidé manuellement
- Erreur lors de l'indexation
- Migration de données

### La Solution

**Champ de tracking** : `is_indexed` dans la table vendors

```python
class Vendor:
    is_indexed = Boolean(default=False)
    last_indexed_at = DateTime(nullable=True)
```

**Workflow d'indexation** :
1. Créer vendor en PostgreSQL
2. Indexer dans Qdrant
3. Si succès : `is_indexed = True`
4. Si échec : `is_indexed = False`

**Réindexation automatique** :
```python
# Lors de l'upload CSV
if vendor_exists and not vendor.is_indexed:
    await index_service.index_vendor(vendor, db=db)
    # Met à jour is_indexed automatiquement
```

---

## 🚀 Scalability Considerations

### Actuellement (Monolithique)

```
┌──────────────────┐
│  Single Server   │
│  ├─ FastAPI      │
│  ├─ PostgreSQL   │
│  ├─ Qdrant       │
│  └─ Redis        │
└──────────────────┘
```

### Future (Microservices - si nécessaire)

```
┌─────────────┐
│  API Gateway │
└─────┬───────┘
      │
      ├──→ ┌──────────────┐
      │    │ Email Service│
      │    └──────────────┘
      │
      ├──→ ┌──────────────┐
      │    │  RAG Service │
      │    └──────────────┘
      │
      └──→ ┌──────────────┐
           │ Vendor Service│
           └──────────────┘
```

### Points d'Extension

1. **Queue système** (Celery/RabbitMQ)
   - Indexation asynchrone
   - Digest planifié
   - Webhooks N8N

2. **CDN pour assets**
   - Images uploads
   - Documents statiques

3. **Load Balancer**
   - Multiple instances FastAPI
   - Round-robin

---

## 🔐 Sécurité

### Actuellement Implémenté

- ✅ CORS configuré
- ✅ Validation Pydantic stricte
- ✅ Confirmation pour opérations destructives
- ✅ Logs de sécurité (WARNING/CRITICAL)
- ✅ Credentials séparés du code

### À Implémenter (Production)

- 🔄 JWT Authentication
- 🔄 Rate Limiting
- 🔄 HTTPS/SSL
- 🔄 Encrypted secrets (Vault)
- 🔄 Audit logs
- 🔄 RBAC (Role-Based Access Control)

---

## 📊 Monitoring & Observability

### Logs Structure (structlog)

```python
logger.info("operation_success",
    entity="vendor",
    operation="index",
    vendor_id=123,
    duration_ms=45
)
```

### Métriques Clés à Surveiller

1. **Performance**
   - Temps de réponse API
   - Temps d'indexation Qdrant
   - Temps de classification LLM

2. **Business**
   - Nombre d'emails traités/jour
   - Vendors indexés vs total
   - Taux de réindexation

3. **Erreurs**
   - Taux d'échec indexation
   - Erreurs Gmail API
   - Timeouts OpenAI

### Outils Recommandés

- **Sentry** : Error tracking
- **Prometheus** : Métriques
- **Grafana** : Dashboards
- **ELK Stack** : Logs centralisés

---

## 🧪 Testing Strategy

### Pyramide de Tests

```
      /\
     /E2E\          ← Peu, critiques
    /──────\
   /  API   \       ← Modéré, endpoints
  /──────────\
 / Unit Tests \     ← Beaucoup, services
/──────────────\
```

### Coverage Targets

- Unit tests : 80%+
- Integration tests : 60%+
- E2E tests : Critical paths

---

## 📈 Performance Benchmarks

### Objectifs V1

| Opération | Temps Cible | Actuel |
|-----------|-------------|--------|
| GET /api/stats | < 100ms | ~50ms ✅ |
| POST /api/vendors/import | < 10s pour 100 | ~8s ✅ |
| GET /api/digest/latest | < 500ms | ~300ms ✅ |
| POST /api/chat/ask | < 3s | ~2s ✅ |
| Indexation 1 vendor | < 200ms | ~150ms ✅ |

---

## 🔮 Future Improvements

### V1.5
- [ ] Gmail OAuth complètement intégré
- [ ] N8N workflows opérationnels
- [ ] Tests E2E avec Playwright

### V2.0
- [ ] Multi-tenancy (plusieurs clients)
- [ ] Mobile app (React Native)
- [ ] Notifications push
- [ ] Analytics dashboard avancé

### V3.0
- [ ] Microservices architecture
- [ ] ML personnalisé (fine-tuning)
- [ ] Intégration WhatsApp/SMS

---

## 📚 Références

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Qdrant Docs](https://qdrant.tech/documentation/)
- [LangChain Docs](https://python.langchain.com/)
- [React Query Docs](https://tanstack.com/query/latest)

---

**Dernière mise à jour** : 30 octobre 2025
**Mainteneur** : Équipe DisruptIQ
