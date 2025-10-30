# 🔐 Variables d'Environnement - DisruptIQ

Ce document liste toutes les variables d'environnement nécessaires pour faire fonctionner DisruptIQ.

---

## 📋 Table des Matières

1. [Backend Environment Variables](#backend-environment-variables)
2. [Frontend Environment Variables](#frontend-environment-variables)
3. [Configuration Docker](#configuration-docker)
4. [Exemples de Configuration](#exemples-de-configuration)

---

## 🔧 Backend Environment Variables

Fichier : `backend/.env`

### Obligatoires

#### OpenAI API

```bash
# Clé API OpenAI pour embeddings et LLM
OPENAI_API_KEY=sk-...votre-clé-ici...

# Optionnel : Modèle à utiliser (défaut: gpt-4)
OPENAI_MODEL=gpt-4
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002
```

**Où obtenir** : https://platform.openai.com/api-keys

---

#### Base de Données PostgreSQL

```bash
# URL de connexion PostgreSQL
DATABASE_URL=postgresql+asyncpg://disruptiq:your_password@localhost:5432/disruptiq
```

**Format** : `postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE`

**Docker** : Si vous utilisez Docker Compose, utilisez :
```bash
DATABASE_URL=postgresql+asyncpg://disruptiq:disruptiq@postgres:5432/disruptiq
```

---

#### Qdrant Vector Database

```bash
# URL de Qdrant pour RAG
QDRANT_URL=http://localhost:6333

# Optionnel : Clé API si Qdrant Cloud
QDRANT_API_KEY=
```

**Docker** : Si vous utilisez Docker Compose :
```bash
QDRANT_URL=http://qdrant:6333
```

---

#### Redis (Optionnel)

```bash
# URL de Redis pour le cache
REDIS_URL=redis://localhost:6379/0
```

**Docker** : Si vous utilisez Docker Compose :
```bash
REDIS_URL=redis://redis:6379/0
```

---

### Optionnelles

#### Sécurité & JWT

```bash
# Clé secrète pour JWT (générer une chaîne aléatoire)
SECRET_KEY=votre-cle-secrete-tres-longue-et-aleatoire

# Algorithme JWT (défaut: HS256)
ALGORITHM=HS256

# Durée de validité du token en minutes (défaut: 30)
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**Générer une clé** :
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

#### Gmail API (Pour Email Digest)

```bash
# Chemin vers le fichier credentials.json
GMAIL_CREDENTIALS_PATH=credentials/credentials.json

# Chemin vers le fichier token.json
GMAIL_TOKEN_PATH=credentials/token.json
```

**Note** : Ces fichiers sont générés en suivant le guide [GMAIL_OAUTH_SETUP.md](./GMAIL_OAUTH_SETUP.md)

---

#### CORS

```bash
# Liste des origines autorisées (séparées par des virgules)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Autoriser tous les domaines (⚠️ NE PAS utiliser en production)
CORS_ORIGINS=*
```

---

#### Logging

```bash
# Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Format des logs (json ou text)
LOG_FORMAT=json
```

---

#### N8N Webhooks (Optionnel)

```bash
# URL de base pour les webhooks N8N
N8N_BASE_URL=http://localhost:5678

# Endpoints spécifiques
N8N_NOTIFY_NEIGHBORS_WEBHOOK=/webhook/notify-neighbors
N8N_SEND_VENDOR_EMAILS_WEBHOOK=/webhook/send-vendor-emails
N8N_ARCHIVE_DOCUMENT_WEBHOOK=/webhook/archive-document
```

---

### Exemple Complet Backend `.env`

```bash
# ========================================
# OPENAI
# ========================================
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002

# ========================================
# DATABASE
# ========================================
DATABASE_URL=postgresql+asyncpg://disruptiq:disruptiq@postgres:5432/disruptiq

# ========================================
# QDRANT
# ========================================
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=

# ========================================
# REDIS
# ========================================
REDIS_URL=redis://redis:6379/0

# ========================================
# SECURITY
# ========================================
SECRET_KEY=super-secret-key-change-this-in-production-12345678
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ========================================
# GMAIL (Optionnel)
# ========================================
GMAIL_CREDENTIALS_PATH=credentials/credentials.json
GMAIL_TOKEN_PATH=credentials/token.json

# ========================================
# CORS
# ========================================
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ========================================
# LOGGING
# ========================================
LOG_LEVEL=INFO
LOG_FORMAT=json

# ========================================
# N8N (Optionnel)
# ========================================
N8N_BASE_URL=http://n8n:5678
N8N_NOTIFY_NEIGHBORS_WEBHOOK=/webhook/notify-neighbors
N8N_SEND_VENDOR_EMAILS_WEBHOOK=/webhook/send-vendor-emails
N8N_ARCHIVE_DOCUMENT_WEBHOOK=/webhook/archive-document
```

---

## 🎨 Frontend Environment Variables

Fichier : `frontend/.env`

### Obligatoires

```bash
# URL de l'API Backend
VITE_API_URL=http://localhost:8000
```

**Note** : En production, changez pour l'URL de production de votre API.

---

### Optionnelles

```bash
# Mode de développement (development, production)
VITE_MODE=development

# Activer les logs de debug
VITE_DEBUG=true

# Timeout des requêtes API (en ms)
VITE_API_TIMEOUT=30000
```

---

### Exemple Complet Frontend `.env`

```bash
# ========================================
# API
# ========================================
VITE_API_URL=http://localhost:8000

# ========================================
# DÉVELOPPEMENT
# ========================================
VITE_MODE=development
VITE_DEBUG=true
VITE_API_TIMEOUT=30000
```

---

## 🐳 Configuration Docker

### docker-compose.yml Environment

Le fichier `docker-compose.yml` contient également des variables d'environnement pour les services.

#### PostgreSQL

```yaml
environment:
  POSTGRES_USER: disruptiq
  POSTGRES_PASSWORD: disruptiq
  POSTGRES_DB: disruptiq
```

#### Qdrant

```yaml
# Qdrant n'a généralement pas besoin de variables d'environnement
# Toute la configuration se fait via l'API
```

#### Redis

```yaml
# Redis n'a généralement pas besoin de variables d'environnement
# Configuration par défaut suffit
```

---

## 📝 Exemples de Configuration

### Développement Local (Sans Docker)

**Backend `.env`** :
```bash
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://disruptiq:password@localhost:5432/disruptiq
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
SECRET_KEY=dev-secret-key-not-for-production
LOG_LEVEL=DEBUG
```

**Frontend `.env`** :
```bash
VITE_API_URL=http://localhost:8000
VITE_DEBUG=true
```

---

### Développement avec Docker

**Backend `.env`** :
```bash
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://disruptiq:disruptiq@postgres:5432/disruptiq
QDRANT_URL=http://qdrant:6333
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=http://localhost:3000
SECRET_KEY=dev-secret-key-not-for-production
LOG_LEVEL=INFO
```

**Frontend `.env`** :
```bash
VITE_API_URL=http://localhost:8000
```

---

### Production

**Backend `.env`** :
```bash
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://user:strong_password@db.production.com:5432/disruptiq
QDRANT_URL=https://qdrant.production.com:6333
QDRANT_API_KEY=your-qdrant-cloud-api-key
REDIS_URL=redis://redis.production.com:6379/0
CORS_ORIGINS=https://app.disruptiq.com
SECRET_KEY=very-long-random-secure-key-generated-securely
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
LOG_LEVEL=WARNING
LOG_FORMAT=json

# Gmail OAuth
GMAIL_CREDENTIALS_PATH=/app/credentials/credentials.json
GMAIL_TOKEN_PATH=/app/credentials/token.json
```

**Frontend `.env`** :
```bash
VITE_API_URL=https://api.disruptiq.com
VITE_MODE=production
VITE_DEBUG=false
```

---

## 🔐 Sécurité

### ⚠️ IMPORTANT

1. **Ne jamais committer les fichiers `.env`** dans Git
2. Ajouter `.env` au `.gitignore`
3. Créer des fichiers `.env.example` sans valeurs sensibles
4. Utiliser des secrets managers en production (AWS Secrets Manager, HashiCorp Vault, etc.)
5. Rotation régulière des clés API

### Générer des Clés Sécurisées

```bash
# Clé SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# UUID aléatoire
python -c "import uuid; print(uuid.uuid4())"

# Chaîne hexadécimale
openssl rand -hex 32
```

---

## ✅ Vérification de la Configuration

### Script de Vérification Backend

```python
# backend/scripts/check_env.py
import os
from dotenv import load_dotenv

load_dotenv()

required_vars = [
    "OPENAI_API_KEY",
    "DATABASE_URL",
    "QDRANT_URL",
    "SECRET_KEY",
]

missing = []
for var in required_vars:
    if not os.getenv(var):
        missing.append(var)

if missing:
    print(f"❌ Variables manquantes: {', '.join(missing)}")
else:
    print("✅ Toutes les variables requises sont définies")
```

### Lancer la Vérification

```bash
cd backend
python scripts/check_env.py
```

---

## 📚 Ressources

- [OpenAI API Keys](https://platform.openai.com/api-keys)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [PostgreSQL Environment Variables](https://www.postgresql.org/docs/current/libpq-envars.html)
- [Vite Environment Variables](https://vitejs.dev/guide/env-and-mode.html)

---

**Dernière mise à jour** : 30 octobre 2025
**Mainteneur** : Équipe DisruptIQ
