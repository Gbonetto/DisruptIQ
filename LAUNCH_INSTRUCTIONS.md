# 🚀 Guide de Lancement - DisruptIQ

## Branche Active
**Nom** : `claude/review-improvements-011CUpYBLnQQ1aDyL444zNjv`

## 📋 Prérequis

1. **Docker & Docker Compose** installés
2. **Node.js 18+** et **npm**
3. **Python 3.11+**
4. **Clés API** (optionnel pour démo) :
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`

---

## 🎯 Lancement Rapide (avec Docker)

### 1️⃣ Démarrer les services

```bash
# Depuis la racine du projet
docker-compose up -d
```

Cela démarre :
- 🐘 PostgreSQL (port 5432)
- 📦 Redis (port 6379)
- 🔍 Qdrant (port 6333)
- 🚀 Backend FastAPI (port 8000)
- ⚛️ Frontend React (port 3000)

### 2️⃣ Vérifier que tout tourne

```bash
docker-compose ps
```

Tous les services doivent être "Up (healthy)" ou "Up".

### 3️⃣ Accéder à l'application

- **Frontend** : http://localhost:3000
- **API Docs** : http://localhost:8000/api/docs
- **API Backend** : http://localhost:8000

---

## 🛠️ Lancement Manuel (Development)

### 1️⃣ Services uniquement (sans backend/frontend)

```bash
# Démarrer seulement les bases de données
docker-compose up -d postgres redis qdrant

# Attendre que les services soient prêts
docker-compose ps
```

### 2️⃣ Backend (dans un terminal)

```bash
cd backend

# Installer les dépendances (première fois)
pip install -r requirements.txt

# Configurer .env (si pas fait)
cp .env.example .env
# Éditer .env avec vos clés API

# Lancer le serveur
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend accessible sur : http://localhost:8000

### 3️⃣ Frontend (dans un autre terminal)

```bash
cd frontend

# Installer les dépendances (première fois)
npm install

# Lancer le serveur de dev
npm run dev
```

Frontend accessible sur : http://localhost:3000

---

## 🔧 Variables d'Environnement

### Backend (.env)

```bash
# Base de données
DATABASE_URL=postgresql+asyncpg://disruptiq:disruptiq_password@localhost:5432/disruptiq
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333

# API Keys (obligatoires pour les fonctions IA)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Sécurité
SECRET_KEY=votre-secret-key-pour-jwt

# N8N Webhooks (optionnel)
N8N_WEBHOOK_BASE_URL=http://localhost:5678
N8N_WEBHOOK_AUTH_TOKEN=token
```

### Frontend (.env)

```bash
VITE_API_URL=http://localhost:8000
```

---

## 📊 Vérification de Santé

### Tester le Backend

```bash
# Health check
curl http://localhost:8000/api/health

# API Documentation
open http://localhost:8000/api/docs
```

### Tester le Frontend

```bash
# Ouvrir dans le navigateur
open http://localhost:3000

# Vérifier la compilation
cd frontend && npm run build
```

---

## 🗄️ Initialisation Base de Données

### Première fois

```bash
cd backend

# Créer les tables
alembic upgrade head

# (Optionnel) Charger des données de test
psql -h localhost -U disruptiq -d disruptiq -f seed_all_tables.sql
```

---

## 🐛 Dépannage

### Port déjà utilisé

```bash
# Trouver le processus sur le port
lsof -i :8000  # Backend
lsof -i :3000  # Frontend

# Tuer le processus
kill -9 <PID>
```

### Services Docker ne démarrent pas

```bash
# Nettoyer et redémarrer
docker-compose down
docker-compose up -d --force-recreate
```

### Problèmes de dépendances

```bash
# Backend
cd backend
pip install --upgrade -r requirements.txt

# Frontend
cd frontend
rm -rf node_modules package-lock.json
npm install
```

---

## 📱 URLs Importantes

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | Interface utilisateur |
| **Backend API** | http://localhost:8000 | API REST |
| **API Docs** | http://localhost:8000/api/docs | Documentation Swagger |
| **PostgreSQL** | localhost:5432 | Base de données |
| **Redis** | localhost:6379 | Cache |
| **Qdrant** | localhost:6333 | Vector DB |

---

## 🎨 Nouvelles Fonctionnalités

### Interface Chat Moderne (MainChatPageV2)

Accessible directement à la racine : http://localhost:3000/

Fonctionnalités :
- ✅ Layout 3 colonnes (Sidebar | Chat | DocumentPanel)
- ✅ Messages user à droite (bulles bleues)
- ✅ Messages assistant à gauche (bulles blanches)
- ✅ Rich Markdown avec syntax highlighting
- ✅ Citations élégantes avec métadonnées
- ✅ Tableaux interactifs (sort/filter/export)
- ✅ Export CSV/Excel/JSON
- ✅ Chain of Thoughts dynamique
- ✅ Streaming SSE en temps réel

---

## 📝 Tests

```bash
# Frontend
cd frontend
npm run build  # Test de compilation
npm run lint   # Analyse de code (nécessite config ESLint)

# Backend
cd backend
pytest tests/  # Tests unitaires
pytest --cov=app tests/  # Avec coverage
```

---

## 🚀 Déploiement Production

Pour production, voir :
- `docker-compose.yml` (profile production avec nginx)
- Configuration SSL/HTTPS dans `nginx/`
- Variables d'environnement de production

---

## 📞 Support

- **Rapport de test complet** : Voir `TEST_REPORT.md`
- **Documentation** : Voir dossier `docs/`
- **Commits récents** : 
  - `9945d2a` - Test report
  - `87c868a` - MainChatPageV2 activation
  - `efaabca` - Premium chat UI

**Status** : ✅ 21/21 tests passed - 0 bugs critiques
