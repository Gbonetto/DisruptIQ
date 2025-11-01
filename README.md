# 🏢 DisruptIQ

**L'assistant IA qui automatise 80% du travail administratif des syndics de copropriété**

DisruptIQ est un système RAG (Retrieval-Augmented Generation) intelligent conçu pour les syndics de copropriété. Il combine l'intelligence artificielle avec des workflows d'automation pour transformer la gestion quotidienne.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

[![CI](https://github.com/your-org/DisruptIQ_CC/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/DisruptIQ_CC/actions/workflows/ci.yml)
[![CD](https://github.com/your-org/DisruptIQ_CC/actions/workflows/cd.yml/badge.svg)](https://github.com/your-org/DisruptIQ_CC/actions/workflows/cd.yml)
[![Docker](https://github.com/your-org/DisruptIQ_CC/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/your-org/DisruptIQ_CC/actions/workflows/docker-publish.yml)
[![codecov](https://codecov.io/gh/your-org/DisruptIQ_CC/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/DisruptIQ_CC)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=disruptiq_DisruptIQ_CC&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=disruptiq_DisruptIQ_CC)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=disruptiq_DisruptIQ_CC&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=disruptiq_DisruptIQ_CC)

---

## 🎯 Fonctionnalités Principales

### ✅ Implémenté (V0.9)

- **📧 Smart Digest Quotidien** - Classification automatique des emails par urgence avec LLM
  - 🔴 Urgent • 🟠 Important • 🟢 Routine
  - Intégration Gmail API avec OAuth 2.0

- **💬 Assistant RAG Intelligent** - Chat avec accès à vos documents et fournisseurs
  - Recherche sémantique dans Qdrant (vecteurs OpenAI)
  - Indexation automatique des vendors et documents
  - Synchronisation PostgreSQL ↔ Qdrant avec tracking `is_indexed`

- **📝 Générateur d'Emails** - Création assistée par IA
  - Emails professionnels pour fournisseurs
  - Emails en masse personnalisés
  - Templates contextuels

- **👥 Gestion des Fournisseurs** - Base de données indexée
  - Import CSV avec validation Pydantic
  - Indexation automatique pour RAG
  - Réindexation intelligente en cas de désynchronisation

- **🗂️ Upload Documents** - Stockage et indexation
  - Support multi-formats (PDF, DOCX, TXT, images)
  - Extraction de texte automatique
  - Indexation vectorielle pour recherche

- **⚙️ Interface Admin** - Panneau de gestion
  - Statistiques en temps réel
  - Import/export de données
  - Danger Zone avec suppressions confirmées

### 🚧 En Développement

- **📊 Analytics Dashboard** - Phase 1 en cours
  - Toast notifications (Sonner)
  - Recherche et filtres vendors
  - Pagination
  - Auto-refresh
  - Badges de notification

- **🔗 Workflows N8N** - Structure présente
  - Notification voisins
  - Emails batch fournisseurs
  - Archivage documents

---

## 🏗️ Architecture Technique

### Stack Technologique

**Backend**
- **API**: FastAPI 0.115+ (async/await)
- **LLM**: OpenAI GPT-4 + LangChain 0.2+
- **Vector DB**: Qdrant 1.9+ (embeddings 1536D)
- **Database**: PostgreSQL 15 (avec migrations)
- **Cache**: Redis 7+
- **Auth**: JWT (préparé pour OAuth)

**Frontend**
- **Framework**: React 18 + Vite + TypeScript
- **Styling**: Tailwind CSS + Shadcn/ui
- **State**: React Query (cache & mutations)
- **Routing**: React Router v6

**Infrastructure**
- **Containerization**: Docker + Docker Compose
- **Logging**: Structlog (JSON format)
- **Validation**: Pydantic (backend) + Zod (frontend)

### Services Docker

```
┌─────────────┐     ┌─────────────┐
│  Frontend   │────▶│   Backend   │
│  (React)    │     │  (FastAPI)  │
│  :3000      │     │   :8000     │
└─────────────┘     └─────┬───────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
      ┌─────▼─────┐  ┌────▼────┐  ┌──────▼────┐
      │PostgreSQL │  │  Qdrant  │  │   Redis   │
      │   :5432   │  │   :6333  │  │   :6379   │
      └───────────┘  └──────────┘  └───────────┘
```

---

## 🚀 Installation

### Prérequis

- **Docker** 20+ & **Docker Compose** 2+
- **Git**
- **Clé API OpenAI** ([obtenir ici](https://platform.openai.com/api-keys))

### Installation Rapide

#### 1. Cloner le Repository

```bash
git clone https://github.com/your-org/disruptiq.git
cd disruptiq
```

#### 2. Configuration Backend

```bash
cd backend
cp .env.example .env
# Éditez .env et ajoutez votre clé OpenAI
nano .env  # ou vim/code .env
```

**Variables requises** :
```bash
OPENAI_API_KEY=sk-proj-votre-cle-ici
DATABASE_URL=postgresql+asyncpg://disruptiq:disruptiq@postgres:5432/disruptiq
QDRANT_URL=http://qdrant:6333
REDIS_URL=redis://redis:6379/0
SECRET_KEY=votre-cle-secrete-aleatoire
```

> 📖 **Documentation complète** : [docs/setup/ENVIRONMENT.md](docs/setup/ENVIRONMENT.md)

#### 3. Configuration Frontend

```bash
cd ../frontend
cp .env.example .env
# Par défaut, VITE_API_URL=http://localhost:8000 fonctionne
```

#### 4. Lancer les Services

```bash
# Retour à la racine
cd ..

# Lancer tous les services
docker-compose up -d

# Vérifier les logs
docker-compose logs -f backend
```

#### 5. Accéder à l'Application

- **Frontend** : [http://localhost:3000](http://localhost:3000)
- **API Backend** : [http://localhost:8000](http://localhost:8000)
- **API Docs (Swagger)** : [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **Qdrant Dashboard** : [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---

## 📖 Documentation

### 🚀 Démarrage

- [**Quick Start**](docs/guides/QUICK_START.md) - Guide de démarrage rapide
- [**Gmail OAuth Setup**](docs/setup/GMAIL_OAUTH_SETUP.md) - Configuration Gmail API
- [**Environment Variables**](docs/setup/ENVIRONMENT.md) - Variables d'environnement

### 📘 Guides d'Utilisation

- [**Vendor Indexing Guide**](docs/guides/VENDOR_INDEXING_GUIDE.md) - Import et indexation fournisseurs
- [**Testing Guide**](docs/guides/TESTING_GUIDE.md) - Tests manuels et automatisés
- [**Troubleshooting**](docs/guides/TROUBLESHOOTING.md) - Résolution de problèmes

### 🛠️ Développement

- [**Architecture**](docs/development/ARCHITECTURE.md) - Architecture complète du système
- [**Code Audit Report**](docs/development/CODE_AUDIT_REPORT.md) - Rapport d'audit et optimisations
- [**Contributing Guide**](docs/development/CONTRIBUTING.md) - Guide de contribution
- [**PRD**](docs/development/PRD.md) - Product Requirements Document
- [**Phase 1 Implementation**](docs/development/PHASE1_IMPLEMENTATION_GUIDE.md) - Guide Phase 1
- [**N8N Workflows**](docs/development/N8N_WORKFLOWS.md) - Workflows N8N

### 📝 Changelog

- [**Changelog Fixes**](docs/changelog/CHANGELOG_FIXES.md) - Historique des corrections
- [**Tests Manuels**](docs/changelog/TESTS_MANUELS.md) - Tests effectués

> 📚 **Index complet** : [docs/README.md](docs/README.md)

---

## 💡 Cas d'Usage

### 1. Générer le Smart Digest Quotidien

**Interface Web** :
1. Accédez au Dashboard
2. Cliquez sur "Générer le digest"
3. Consultez les emails classés par urgence

**API** :
```bash
curl -X POST http://localhost:8000/api/digest/generate
```

### 2. Poser une Question à l'Assistant

**Interface Web** :
1. Allez sur la page "Assistant"
2. Tapez votre question : "Qui est le plombier habituel ?"
3. Recevez une réponse avec sources

**API** :
```bash
curl -X POST http://localhost:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Quel est le plombier pour le 15 rue Victor Hugo ?"}'
```

### 3. Importer des Fournisseurs

1. Préparez un CSV avec colonnes : `name, email, company_name, phone, category, city`
2. Allez sur la page "Admin"
3. Cliquez sur "Importer CSV"
4. Sélectionnez votre fichier
5. Les vendors sont automatiquement indexés dans Qdrant

**Format CSV** :
```csv
name,email,company_name,phone,category,city
Jean Dupont,jean@plomberie.fr,Plomberie Dupont,0612345678,Plomberie,Paris
Marie Martin,marie@elec.com,Elec Pro,0698765432,Électricité,Lyon
```

---

## 🛠️ Développement

### Structure du Projet

```
DisruptIQ_CC/
├── backend/                    # API FastAPI
│   ├── app/
│   │   ├── api/endpoints/      # Controllers REST
│   │   ├── core/               # Config, DB, Security
│   │   ├── models/             # SQLAlchemy ORM
│   │   ├── schemas/            # Pydantic validation
│   │   ├── services/           # Business logic
│   │   │   ├── rag_service.py          # RAG + Qdrant
│   │   │   ├── email_processor.py      # Gmail + LLM classification
│   │   │   ├── vendor_index_service.py # Indexation vendors
│   │   │   └── llm_service.py          # OpenAI wrapper
│   │   └── utils/              # Helpers
│   ├── migrations/             # SQL migrations
│   ├── scripts/                # Utilitaires (gmail_auth.py, etc.)
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                   # SPA React
│   ├── src/
│   │   ├── components/         # Composants réutilisables
│   │   ├── pages/              # Pages principales
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── ChatPage.tsx
│   │   │   ├── AdminPage.tsx
│   │   │   └── DocumentsPage.tsx
│   │   ├── hooks/              # Custom hooks
│   │   ├── lib/                # API client + utils
│   │   └── styles/             # Tailwind config
│   ├── package.json
│   └── .env.example
│
├── docs/                       # 📚 Documentation organisée
│   ├── setup/                  # Configuration
│   ├── guides/                 # Guides utilisateurs
│   ├── development/            # Documentation développeurs
│   └── changelog/              # Historique
│
├── docker-compose.yml          # Orchestration services
├── .gitignore
└── README.md
```

### Commandes Utiles

**Docker** :
```bash
# Démarrer
docker-compose up -d

# Arrêter
docker-compose down

# Rebuild après modifications
docker-compose up -d --build

# Logs en temps réel
docker-compose logs -f backend
docker-compose logs -f frontend

# Reset complet (⚠️ Supprime les données)
docker-compose down -v
docker-compose up -d
```

**Backend** :
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Run tests
pytest

# Run locally (sans Docker)
uvicorn app.main:app --reload
```

**Frontend** :
```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Run tests
npm test
```

---

## 🧪 Tests

### Backend

```bash
cd backend
pytest                        # Tous les tests
pytest tests/test_rag.py     # Fichier spécifique
pytest --cov=app             # Avec coverage
```

### Frontend

```bash
cd frontend
npm test                      # Mode interactif
npm test -- --coverage        # Avec coverage
```

> 📖 **Guide complet** : [docs/guides/TESTING_GUIDE.md](docs/guides/TESTING_GUIDE.md)

---

## 🔐 Sécurité

### Implémenté

- ✅ CORS configuré
- ✅ Validation Pydantic stricte
- ✅ Confirmation pour opérations destructives
- ✅ Logs de sécurité (structlog)
- ✅ Credentials séparés du code (.env, .gitignore)
- ✅ OAuth 2.0 Gmail
- ✅ Rate Limiting (SlowAPI - 100/min, 1000/hour)
- ✅ SQL Injection protection (validated SQL queries)
- ✅ CI/CD Pipeline (GitHub Actions)
- ✅ Automated security scanning (Trivy)

### À Implémenter (Production)

- 🔄 JWT Authentication complète
- 🔄 HTTPS/SSL
- 🔄 Encrypted secrets (Vault)
- 🔄 Enhanced audit logs
- 🔄 RBAC (Role-Based Access Control)

---

## 📊 Performances

| Opération | Temps Cible | Actuel |
|-----------|-------------|--------|
| GET /api/stats | < 100ms | ~50ms ✅ |
| POST /api/vendors/import (100) | < 10s | ~8s ✅ |
| GET /api/digest/latest | < 500ms | ~300ms ✅ |
| POST /api/chat/ask | < 3s | ~2s ✅ |
| Indexation 1 vendor | < 200ms | ~150ms ✅ |

---

## 🗺️ Roadmap

### ✅ V0.9 (Actuel)
- Smart Digest emails avec classification LLM
- Assistant RAG avec Qdrant
- Gestion vendors avec indexation synchronisée
- Upload & indexation documents
- Interface Admin complète

### 🚧 V1.0 (En cours)
- Toast notifications (Sonner)
- Recherche + filtres vendors
- Pagination optimisée
- Auto-refresh Dashboard
- Badges de notification
- Gmail OAuth production-ready

### 🔮 V1.5 (Prochaine)
- Tests E2E avec Playwright
- N8N workflows opérationnels
- OCR factures avancé
- Analytics dashboard
- Multi-agents spécialisés

### 🌟 V2.0 (Future)
- Multi-tenancy (plusieurs clients)
- Mobile app (React Native)
- Notifications push
- API publique
- Marketplace workflows

---

## 🆘 Support & Contribution

### Besoin d'Aide ?

1. Consultez la [documentation](docs/README.md)
2. Vérifiez le [guide de troubleshooting](docs/guides/TROUBLESHOOTING.md)
3. Ouvrez une [issue GitHub](https://github.com/your-org/disruptiq/issues)

### Contribuer

Consultez le [guide de contribution](docs/development/CONTRIBUTING.md) pour :
- Setup environnement de dev
- Standards de code
- Conventions de commits
- Process de Pull Request

---

## 📄 Licence

[À définir - Propriétaire ou Open Source]

---

## 🙏 Remerciements

DisruptIQ utilise les technologies open-source suivantes :

- **Backend** : FastAPI, LangChain, SQLAlchemy, Pydantic, Structlog
- **Frontend** : React, Vite, Tailwind CSS, Shadcn/ui, React Query
- **Infrastructure** : Docker, PostgreSQL, Redis, Qdrant
- **AI** : OpenAI GPT-4, text-embedding-ada-002

---

<div align="center">

**Développé avec ❤️ pour simplifier la vie des syndics**

🚀 **Prêt à transformer votre gestion quotidienne ?**

`docker-compose up -d`

</div>
