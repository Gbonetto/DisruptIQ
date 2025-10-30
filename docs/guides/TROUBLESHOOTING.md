# 🔧 Guide de Dépannage - DisruptIQ

Ce guide vous aide à résoudre les problèmes courants rencontrés lors de l'utilisation de DisruptIQ.

---

## 📋 Table des Matières

1. [Problèmes de Démarrage](#problèmes-de-démarrage)
2. [Problèmes Backend](#problèmes-backend)
3. [Problèmes Frontend](#problèmes-frontend)
4. [Problèmes Docker](#problèmes-docker)
5. [Problèmes de Base de Données](#problèmes-de-base-de-données)
6. [Problèmes Qdrant](#problèmes-qdrant)
7. [Problèmes Gmail OAuth](#problèmes-gmail-oauth)
8. [Problèmes d'Indexation](#problèmes-dindexation)
9. [Problèmes de Performance](#problèmes-de-performance)

---

## 🚀 Problèmes de Démarrage

### ❌ "Port already in use"

**Symptôme** : Erreur `Address already in use` lors du lancement

**Solution** :
```bash
# Identifier le processus utilisant le port
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9

# Ou changer le port
uvicorn app.main:app --port 8001
```

### ❌ "Module not found"

**Symptôme** : `ModuleNotFoundError` lors du lancement

**Solution** :
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### ❌ Docker containers won't start

**Symptôme** : `docker-compose up` échoue

**Solution** :
```bash
# Vérifier Docker est lancé
docker --version

# Windows - Lancer Docker Desktop
"C:\Program Files\Docker\Docker\Docker Desktop.exe"

# Nettoyer et redémarrer
docker-compose down
docker-compose up -d

# Vérifier les logs
docker-compose logs -f
```

---

## 🔧 Problèmes Backend

### ❌ "Connection to database failed"

**Symptôme** : Impossible de se connecter à PostgreSQL

**Solution** :
```bash
# 1. Vérifier que PostgreSQL est lancé
docker-compose ps

# 2. Vérifier les variables d'environnement
cat backend/.env | grep DATABASE_URL

# 3. Tester la connexion
docker exec -it disruptiq-postgres psql -U disruptiq -d disruptiq

# 4. Si nécessaire, recréer la base
docker-compose down -v
docker-compose up -d postgres
```

### ❌ "OpenAI API Error"

**Symptôme** : Erreurs lors de l'utilisation de l'assistant ou classification

**Solution** :
```bash
# 1. Vérifier la clé API
echo $OPENAI_API_KEY

# 2. Vérifier le quota
# Aller sur https://platform.openai.com/account/usage

# 3. Tester la clé
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### ❌ "Pydantic ValidationError"

**Symptôme** : Erreur de validation lors de l'import CSV

**Causes courantes** :
- Email invalide (doit avoir un TLD valide : `.com`, `.fr`, etc.)
- Champs manquants
- Format de données incorrect

**Solution** :
```python
# Vérifier le format du CSV
# Colonnes requises : name, email, company_name
# Colonnes optionnelles : phone, category, city, postal_code, etc.

# Exemple de ligne valide :
"Jean Dupont","jean@example.com","Plomberie Dupont","0612345678","Plomberie"
```

### ❌ "Gmail API authentication failed"

**Symptôme** : Impossible de récupérer les emails

**Solution** :
Consultez le guide détaillé : [GMAIL_OAUTH_SETUP.md](../setup/GMAIL_OAUTH_SETUP.md)

```bash
# Vérifier que le fichier token existe
ls backend/credentials/token.json

# Régénérer le token
cd backend/scripts
python gmail_auth.py
```

---

## 🎨 Problèmes Frontend

### ❌ "Failed to fetch"

**Symptôme** : Erreurs réseau lors des appels API

**Solution** :
```bash
# 1. Vérifier que le backend est lancé
curl http://localhost:8000/api/health

# 2. Vérifier CORS
# Dans backend/app/core/config.py
CORS_ORIGINS = ["http://localhost:3000"]

# 3. Vérifier la variable d'environnement
# frontend/.env
VITE_API_URL=http://localhost:8000
```

### ❌ "React Query: Network Error"

**Symptôme** : Les requêtes échouent systématiquement

**Solution** :
```typescript
// Vérifier la configuration de l'API client
// frontend/src/lib/api.ts

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Tester manuellement
const response = await fetch('http://localhost:8000/api/admin/stats')
console.log(await response.json())
```

### ❌ "Blank page / White screen"

**Symptôme** : Page blanche au chargement

**Solution** :
```bash
# 1. Vérifier la console du navigateur (F12)
# Regarder les erreurs JavaScript

# 2. Vérifier que Vite est lancé
npm run dev

# 3. Vider le cache
Ctrl+Shift+R (hard refresh)

# 4. Rebuild
rm -rf node_modules .vite
npm install
npm run dev
```

### ❌ "Vite: Port 3000 unavailable"

**Symptôme** : Le port 3000 est déjà utilisé

**Solution** :
```bash
# Option 1: Tuer le processus
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Option 2: Changer le port
npm run dev -- --port 3001
```

---

## 🐳 Problèmes Docker

### ❌ "Cannot connect to Docker daemon"

**Symptôme** : Docker commands fail

**Solution** :
```bash
# Windows
# Lancer Docker Desktop
"C:\Program Files\Docker\Docker\Docker Desktop.exe"

# Attendre que Docker soit prêt
docker ps

# Linux
sudo systemctl start docker
```

### ❌ "Volume permission denied"

**Symptôme** : Erreurs de permissions sur les volumes

**Solution** :
```bash
# Linux/Mac
sudo chown -R $USER:$USER .

# Windows
# Vérifier les partages de lecteur dans Docker Desktop
```

### ❌ "Image pull failed"

**Symptôme** : Impossible de télécharger une image

**Solution** :
```bash
# Vérifier la connexion internet
ping docker.io

# Nettoyer et réessayer
docker system prune -a
docker-compose pull
docker-compose up -d
```

---

## 🗄️ Problèmes de Base de Données

### ❌ "Table does not exist"

**Symptôme** : Erreur lors de requêtes SQL

**Solution** :
```bash
# Appliquer les migrations
cd backend
alembic upgrade head

# Ou recréer la base
docker exec -it disruptiq-postgres psql -U disruptiq -d disruptiq -f migrations/schema.sql
```

### ❌ "Unique constraint violation"

**Symptôme** : Erreur lors de l'insertion

**Causes** :
- Email en double lors de l'import vendors
- Message ID en double lors de l'import emails

**Solution** :
```python
# Le backend gère déjà les doublons
# Si le problème persiste, vérifier les logs
docker-compose logs -f backend
```

### ❌ "Connection pool exhausted"

**Symptôme** : Trop de connexions simultanées

**Solution** :
```bash
# Augmenter la taille du pool
# backend/app/core/database.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,  # Augmenter
    max_overflow=10
)
```

---

## 🔍 Problèmes Qdrant

### ❌ "Failed to connect to Qdrant"

**Symptôme** : Erreurs lors de l'indexation

**Solution** :
```bash
# 1. Vérifier que Qdrant est lancé
docker-compose ps qdrant

# 2. Vérifier l'URL
# backend/.env
QDRANT_URL=http://localhost:6333

# 3. Tester manuellement
curl http://localhost:6333/collections
```

### ❌ "Collection does not exist"

**Symptôme** : Erreur lors de la recherche RAG

**Solution** :
```bash
# Créer la collection via l'API
curl -X PUT http://localhost:6333/collections/disruptiq_documents \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 1536,
      "distance": "Cosine"
    }
  }'

# Ou via l'interface web
# http://localhost:6333/dashboard
```

### ❌ "Vector dimension mismatch"

**Symptôme** : Erreur lors de l'indexation

**Cause** : Les embeddings OpenAI font 1536 dimensions

**Solution** :
```python
# Vérifier la configuration de la collection
# Dimension doit être 1536 pour OpenAI embeddings
```

---

## 📧 Problèmes Gmail OAuth

### ❌ "invalid_grant"

**Symptôme** : Token invalide ou expiré

**Solution** :
```bash
# Supprimer le token et réauthentifier
rm backend/credentials/token.json
cd backend/scripts
python gmail_auth.py
```

### ❌ "redirect_uri_mismatch"

**Symptôme** : Erreur lors de l'authentification

**Solution** :
```bash
# Vérifier que l'URI de redirection est bien configurée
# Dans Google Cloud Console:
# http://localhost:8080/ ou http://localhost:8080

# Dans backend/scripts/gmail_auth.py
redirect_uri='http://localhost:8080/'
```

### ❌ "Access blocked: DisruptIQ has not completed verification"

**Symptôme** : Google bloque l'accès

**Solution** :
```bash
# Mode développement : Ajouter votre email en test user
# Google Cloud Console > OAuth consent screen > Test users

# Production : Compléter le processus de vérification Google
```

---

## 🔄 Problèmes d'Indexation

### ❌ "Vendors pas indexés après import CSV"

**Symptôme** : `is_indexed = False` même après import

**Solution** :
```bash
# Utiliser le bouton "Réindexer tout" dans l'admin
# Ou via API
curl -X POST http://localhost:8000/api/admin/vendors/reindex
```

### ❌ "Désynchronisation PostgreSQL / Qdrant"

**Symptôme** : Vendors en DB mais pas dans Qdrant

**Solution** :
```bash
# 1. Vérifier le statut d'indexation
# Page Admin > Colonne "Indexé"

# 2. Réindexer les vendors non indexés
curl -X POST http://localhost:8000/api/admin/vendors/reindex

# 3. Si nécessaire, supprimer et réimporter
curl -X DELETE http://localhost:8000/api/admin/vendors/all?confirm=true
# Puis réimporter le CSV
```

### ❌ "Assistant ne trouve pas les vendors"

**Symptôme** : RAG ne retourne aucun résultat

**Solution** :
```bash
# 1. Vérifier que les vendors sont indexés
# Page Admin > Vérifier colonne "Indexé"

# 2. Tester la recherche Qdrant directement
curl http://localhost:6333/collections/disruptiq_documents/points/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.1, 0.2, ...], # 1536 dimensions
    "limit": 5
  }'

# 3. Vérifier les logs du backend
docker-compose logs -f backend | grep -i rag
```

---

## ⚡ Problèmes de Performance

### ❌ "Lenteur lors de l'import CSV"

**Symptôme** : Import de 100 vendors prend > 30s

**Causes** :
- Indexation synchrone dans Qdrant
- Connexion OpenAI lente

**Solution** :
```python
# L'import fait déjà du batch processing
# Si trop lent, désactiver temporairement l'indexation auto

# Ou augmenter le batch size
# backend/app/api/endpoints/admin.py
BATCH_SIZE = 50  # Augmenter
```

### ❌ "RAG queries lentes (> 5s)"

**Symptôme** : Recherche RAG met trop de temps

**Solution** :
```python
# 1. Réduire le nombre de résultats
# backend/app/services/rag_service.py
limit = 3  # Au lieu de 5

# 2. Optimiser les embeddings (cache)
# Utiliser Redis pour cacher les embeddings fréquents

# 3. Augmenter les ressources Qdrant
# docker-compose.yml
services:
  qdrant:
    deploy:
      resources:
        limits:
          memory: 2G
```

### ❌ "Frontend lent / Re-renders excessifs"

**Symptôme** : UI freeze ou lag

**Solution** :
```typescript
// 1. Utiliser React.memo pour les composants lourds
export const VendorCard = React.memo(({ vendor }) => {
  // ...
})

// 2. Optimiser React Query staleTime
const { data } = useQuery({
  queryKey: ['vendors'],
  queryFn: fetchVendors,
  staleTime: 5 * 60 * 1000, // 5 minutes
})

// 3. Utiliser useMemo pour calculs coûteux
const filteredVendors = useMemo(
  () => vendors.filter(v => v.category === category),
  [vendors, category]
)
```

---

## 🔍 Diagnostic Général

### Vérifier l'état du système

```bash
# Backend health check
curl http://localhost:8000/api/health

# Vérifier tous les services Docker
docker-compose ps

# Logs backend
docker-compose logs -f backend

# Logs base de données
docker-compose logs -f postgres

# Logs Qdrant
docker-compose logs -f qdrant
```

### Vérifier les variables d'environnement

```bash
# Backend
cat backend/.env

# Frontend
cat frontend/.env

# Variables requises :
# - OPENAI_API_KEY
# - DATABASE_URL
# - QDRANT_URL
# - VITE_API_URL (frontend)
```

---

## 🆘 Toujours Bloqué ?

Si aucune solution ne fonctionne :

1. **Vérifier les logs** :
   ```bash
   docker-compose logs -f
   ```

2. **Nettoyer complètement** :
   ```bash
   docker-compose down -v
   rm -rf backend/__pycache__ backend/.pytest_cache
   rm -rf frontend/node_modules frontend/.vite
   docker-compose up -d
   ```

3. **Consulter la documentation** :
   - [ARCHITECTURE.md](../development/ARCHITECTURE.md)
   - [QUICK_START.md](./QUICK_START.md)
   - [CONTRIBUTING.md](../development/CONTRIBUTING.md)

4. **Créer une issue GitHub** avec :
   - Description du problème
   - Steps to reproduce
   - Logs d'erreur
   - Environnement (OS, versions)

---

**Dernière mise à jour** : 30 octobre 2025
**Mainteneur** : Équipe DisruptIQ
