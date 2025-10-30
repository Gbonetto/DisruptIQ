# Guide de Démarrage Rapide - DisruptIQ avec Claude Code

## 📍 Statut Actuel du Projet

### ✅ Fonctionnalités Complétées

**Backend (FastAPI)**
- ✅ Structure complète avec modèles SQLAlchemy (User, Email, Document, Vendor)
- ✅ Service Email avec classification par urgence (digest.py)
- ✅ Service RAG complet avec Qdrant (rag_service.py)
- ✅ Service d'extraction de documents (document_service.py) - PDF, DOCX, TXT
- ✅ Service d'indexation des fournisseurs (vendor_index_service.py) - **NOUVEAU**
- ✅ API Admin avec gestion des fournisseurs
- ✅ Import CSV automatique avec détection de délimiteur (`,` et `;`)
- ✅ Validation Pydantic stricte des emails
- ✅ Prévention des doublons de fournisseurs
- ✅ Indexation automatique des vendors dans Qdrant pour l'assistant RAG
- ✅ Endpoint de réindexation manuelle (`/api/admin/vendors/reindex`)
- ✅ Gestion d'erreurs robuste avec logs structurés (structlog)

**Frontend (React + Vite + TypeScript)**
- ✅ Configuration Tailwind CSS + Shadcn/ui
- ✅ Layout responsive avec navigation
- ✅ Page Dashboard avec statistiques
- ✅ Page Admin avec upload CSV et liste des vendors
- ✅ Interface Chat pour l'assistant RAG
- ✅ Gestion d'erreurs améliorée avec affichage utilisateur
- ✅ Messages d'import détaillés (création, doublons, indexation)
- ✅ États de chargement pour meilleure UX

**Infrastructure**
- ✅ Docker Compose complet (PostgreSQL, Qdrant, Redis, Backend, Frontend)
- ✅ Base de données PostgreSQL avec migrations
- ✅ Qdrant vectoriel pour RAG (port 6333)
- ✅ Configuration CORS fonctionnelle
- ✅ Tests automatisés (voir TESTING_GUIDE.md)

**Documentation**
- ✅ TESTING_GUIDE.md - Guide complet de tests
- ✅ CHANGELOG_FIXES.md - Historique des corrections
- ✅ VENDOR_INDEXING_GUIDE.md - Documentation système d'indexation vendors
- ✅ N8N_WORKFLOWS.md - Workflows N8N
- ✅ PRD.md - Product Requirements Document

### 🚧 En Attente / Non Implémenté

- ⏳ Configuration Gmail OAuth (optionnel, pas bloquant)
- ⏳ Intégration N8N webhooks (structure présente, non testée)
- ⏳ Workflow complet d'envoi d'emails via N8N
- ⏳ Tests E2E avec Playwright
- ⏳ Déploiement production avec Nginx + SSL
- ⏳ Monitoring et alertes

### 🎯 Dernières Améliorations (Session Actuelle)

1. **Système d'Indexation des Fournisseurs** ⭐
   - Les vendors sont maintenant automatiquement indexés dans Qdrant
   - L'assistant RAG peut rechercher et répondre aux questions sur les fournisseurs
   - Format structuré: nom, catégorie, email, téléphone, ville, spécialités
   - IDs négatifs pour distinguer vendors (-1, -2...) des documents (1, 2...)

2. **Corrections de Bugs**
   - Emails persistés en base après classification
   - Validation stricte des emails avant insertion
   - Détection automatique du délimiteur CSV
   - Contrainte unique sur vendor.email
   - Gestion des erreurs d'indexation sans bloquer l'import

3. **Améliorations Frontend**
   - Messages d'import avec détails d'indexation
   - Affichage des erreurs réseau et de validation
   - Configuration Vite avec --host 0.0.0.0 pour accès localhost

---

## 🚀 Démarrage Rapide (Pour Tester Maintenant)

### Option 1: Démarrage Complet avec Docker (Recommandé)

```bash
# 1. Assurez-vous que Docker Desktop est lancé

# 2. Démarrez tous les services
docker-compose up -d

# 3. Attendez 30 secondes que tous les services démarrent

# 4. Accédez à l'application
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/api/docs
# Qdrant: http://localhost:6333/dashboard
```

### Option 2: Démarrage Frontend/Backend Séparé

```bash
# Terminal 1 - Backend (Docker)
docker-compose up backend postgres qdrant redis

# Terminal 2 - Frontend (Local)
cd frontend
npm install
npm run dev -- --host 0.0.0.0

# Accédez à http://localhost:3000
```

### Premier Test - Import de Fournisseurs

1. Ouvrez http://localhost:3000/admin
2. Cliquez sur "Importer CSV"
3. Utilisez un fichier CSV avec le format:
   ```csv
   name,company_name,email,phone,category,specialties,address,city,postal_code
   Jean Dupont,Plomberie Dupont,jean@example.fr,0601020304,Plomberie,"Dépannage|Rénovation",12 rue de Paris,Paris,75001
   ```
4. Vérifiez les statistiques et la liste des vendors
5. Testez l'assistant dans l'onglet Chat: "Qui est le plombier ?"

### Vérification du Système

```bash
# Statut des services
docker-compose ps

# Logs en temps réel
docker-compose logs -f backend

# Test API direct
curl http://localhost:8000/api/health

# Nombre de vendors indexés
curl http://localhost:8000/api/admin/stats
```

---

## 📖 Instructions Détaillées pour Claude Code

### Étape 1: Initialisation du Projet
```bash
# Dans Claude Code, commencez par cette commande:
claude "Créez le projet DisruptIQ selon le PRD fourni, en commençant par la structure de base et le backend FastAPI avec les endpoints essentiels pour le Smart Digest et le générateur d'emails"
```

### Étape 2: Prompts Séquentiels Recommandés

#### 2.1 Backend Core (Jour 1-2)
```bash
# Prompt 1 - Structure et configuration
"Créez la structure backend FastAPI avec:
- Configuration Docker pour PostgreSQL, Redis, Qdrant
- Modèles SQLAlchemy pour users, emails, vendors, documents
- Service d'authentification basique JWT
- Endpoints health check et configuration
- Variables d'environnement dans .env.example"

# Prompt 2 - Email Service
"Implémentez le service de traitement des emails:
- Connexion IMAP/Gmail API
- Classification urgence avec LangChain et GPT-4
- Extraction des pièces jointes
- Génération du digest HTML quotidien
- Tests unitaires pour le classifier"

# Prompt 3 - RAG System
"Créez le système RAG avec:
- Ingestion documents PDF/DOCX via LangChain
- Vectorisation avec OpenAI embeddings
- Stockage dans Qdrant avec métadonnées
- Endpoint de recherche sémantique
- Gestion de la session de chat"

# Prompt 4 - N8N Integration
"Ajoutez l'intégration N8N:
- Service webhook avec signature HMAC
- Endpoints pour déclencher workflows
- Retry logic et gestion erreurs
- Logging des actions N8N
- 3 workflows JSON d'exemple"
```

#### 2.2 Frontend React (Jour 3-4)
```bash
# Prompt 5 - Setup UI
"Créez le frontend React avec:
- Vite + TypeScript + Tailwind CSS
- Installation et configuration Shadcn/ui
- Layout responsive avec sidebar mobile
- Thème avec les couleurs du design system
- Composants Card, Button, Badge de base"

# Prompt 6 - Dashboard
"Implémentez la page Dashboard:
- Affichage du Smart Digest avec cards par urgence
- Actions N8N intégrées dans chaque card
- Skeleton loading pendant chargement
- Version mobile avec swipe actions
- Connexion API backend avec React Query"

# Prompt 7 - Chat Interface
"Créez l'interface de chat pour générer des emails:
- Chat UI avec historique des messages
- Affichage du brouillon d'email généré
- Liste des destinataires avec badges
- Boutons pour copier et envoyer via N8N
- Suggestions de prompts contextuels"

# Prompt 8 - Admin Panel
"Ajoutez le panneau d'administration:
- Upload CSV des fournisseurs par drag & drop
- Table éditable avec recherche et filtres
- Configuration des webhooks N8N
- Formulaire de connexion Gmail OAuth
- Dashboard statistiques basiques"
```

#### 2.3 Intégration & Déploiement (Jour 5)
```bash
# Prompt 9 - Docker & Tests
"Finalisez avec:
- Docker Compose complet multi-services
- Nginx configuration avec SSL
- Script d'installation bash one-click
- Tests E2E critiques avec Playwright
- Documentation API Swagger auto-générée"

# Prompt 10 - Production Ready
"Optimisez pour la production:
- Variables d'environnement sécurisées
- Gestion des erreurs et logs structurés
- Rate limiting sur les endpoints
- Health checks pour monitoring
- Backup automatique PostgreSQL"
```

### 📋 Checklist Avant Chaque Prompt

Avant chaque nouveau prompt, vérifiez:
- [ ] Le code précédent compile et fonctionne
- [ ] Les tests passent (si applicables)
- [ ] Les dépendances sont à jour
- [ ] Le .env.example est documenté
- [ ] Les erreurs sont gérées proprement

### 🔧 Commandes Utiles

```bash
# Démarrage complet (recommandé)
docker-compose up -d

# Backend (via Docker - recommandé sur Windows)
docker-compose up -d backend
docker-compose logs -f backend

# Backend (local - nécessite Python 3.11+)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev -- --host 0.0.0.0  # IMPORTANT: --host 0.0.0.0 pour accès localhost

# Docker - Commandes utiles
docker-compose up -d                    # Démarrer tous les services
docker-compose down                     # Arrêter tous les services
docker-compose logs -f backend          # Logs backend en temps réel
docker-compose logs -f frontend         # Logs frontend en temps réel
docker-compose ps                       # Statut des services
docker-compose restart backend          # Redémarrer le backend

# Base de données
docker-compose exec backend alembic upgrade head  # Migrations
docker-compose exec postgres psql -U disruptiq    # Console PostgreSQL

# Tests
pytest backend/tests                    # Tests unitaires backend
npm run test --prefix frontend          # Tests frontend (si configurés)
python test_api.py                      # Tests API manuels

# Vendor Indexing
curl -X POST http://localhost:8000/api/admin/vendors/reindex  # Réindexer tous les vendors

# Qdrant Dashboard
# Accédez à http://localhost:6333/dashboard pour voir les vecteurs indexés
```

### 🐛 Résolution de Problèmes Courants

**Problème**: Frontend inaccessible via localhost (ERR_CONNECTION_REFUSED)
```bash
# Solution: Utiliser --host 0.0.0.0
cd frontend
npm run dev -- --host 0.0.0.0

# Le frontend écoute maintenant sur http://localhost:3000
# Au lieu de seulement [::1]:3000 (IPv6)
```

**Problème**: Network Error après upload CSV
```bash
# Cause: Vendor avec email invalide dans la base
# Solution 1: Supprimer les vendors avec emails invalides
docker-compose exec postgres psql -U disruptiq -c "DELETE FROM vendors WHERE email NOT LIKE '%@%.%';"

# Solution 2: Réindexer après nettoyage
curl -X POST http://localhost:8000/api/admin/vendors/reindex
```

**Problème**: L'assistant ne trouve pas les vendors fraîchement importés
```bash
# Solution: Réindexer manuellement
curl -X POST http://localhost:8000/api/admin/vendors/reindex

# Vérification dans Qdrant Dashboard:
# http://localhost:6333/dashboard
# Collection: disruptiq_documents
# Points avec IDs négatifs = vendors
```

**Problème**: Erreur psycopg2-binary sur Windows Python 3.13
```bash
# Solution: Utiliser le backend via Docker au lieu de local
docker-compose up -d backend

# Alternative: Installer Visual C++ Build Tools
# https://visualstudio.microsoft.com/downloads/
```

**Problème**: tailwind.config.js - "require is not defined"
```bash
# Solution: Renommer en .cjs et utiliser module.exports
mv frontend/tailwind.config.js frontend/tailwind.config.cjs

# Dans le fichier, remplacer:
# export default { ... }
# Par:
# module.exports = { ... }
```

**Problème**: Erreur de connexion PostgreSQL
```bash
# Solution
docker-compose down -v
docker-compose up -d postgres
# Attendre 30 secondes
docker-compose up -d
```

**Problème**: Erreur CORS Frontend-Backend
```python
# Dans backend/app/main.py, vérifiez:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Problème**: Qdrant ne démarre pas
```yaml
# Vérifiez dans docker-compose.yml:
qdrant:
  image: qdrant/qdrant:v1.9.0  # Version spécifique
  restart: always
  ports:
    - "6333:6333"
```

**Problème**: Import CSV échoue sur les spécialités
```bash
# Solution: Utiliser le format avec pipes et guillemets
# Format correct dans le CSV:
# name,company_name,email,phone,category,specialties,address,city,postal_code
# Jean Dupont,Plomberie Dupont,jean@example.fr,0601020304,Plomberie,"Dépannage|Rénovation",12 rue...,Paris,75001

# Le parser gère automatiquement les deux formats:
# - Séparateur pipe: "Dépannage|Rénovation"
# - Séparateur point-virgule: "Dépannage;Rénovation"
```

### 💡 Tips d'Optimisation

1. **Commencez simple**: Focus sur 2 use cases d'abord
2. **Testez tôt**: Validez chaque service individuellement
3. **Documentez**: Commentez les fonctions complexes
4. **Versionnez**: Commit après chaque fonctionnalité
5. **Itérez**: Améliorez basé sur les retours

### 📊 Métriques de Progression

| Phase | Durée Estimée | Statut | Validation |
|-------|--------------|--------|------------|
| Backend Core | 2 jours | ✅ **Complété** | API responds, DB connected, RAG service |
| Frontend MVP | 2 jours | ✅ **Complété** | UI displays, vendor management works |
| Vendor Indexing | 0.5 jour | ✅ **Complété** | Assistant finds vendors, auto-indexing |
| Integration | 1 jour | 🟡 **Partiel** | Vendor flow complete, N8N pending |
| Deployment | 0.5 jour | ✅ **Complété** | Docker runs, services accessible |
| Testing | 0.5 jour | ✅ **Complété** | Tests documented, manual validation done |
| Gmail OAuth | 0.5 jour | ⏳ **En attente** | Optional feature |
| N8N Workflows | 1 jour | ⏳ **En attente** | Structure present, needs testing |

### 🎯 Critères de Succès V1

**Implémenté:**
- ✅ Smart Digest génère et classe les emails par urgence
- ✅ Interface responsive mobile fonctionnelle
- ✅ Déploiement Docker en 1 commande (`docker-compose up -d`)
- ✅ Upload et gestion des fournisseurs avec CSV
- ✅ Assistant RAG répond aux questions sur les vendors
- ✅ Import robuste avec validation et gestion des doublons
- ✅ Indexation automatique dans Qdrant

**En attente:**
- ⏳ Smart Digest s'envoie automatiquement (nécessite Gmail OAuth)
- ⏳ Actions N8N se déclenchent (structure présente)
- ⏳ Génération d'emails < 5 secondes (workflow N8N à tester)

---

## 🌐 Accès aux Services

Une fois Docker Compose lancé, accédez aux services:

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | Interface utilisateur React |
| **Backend API** | http://localhost:8000 | API FastAPI |
| **API Docs (Swagger)** | http://localhost:8000/api/docs | Documentation interactive de l'API |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | Interface Qdrant pour voir les vecteurs |
| **PostgreSQL** | localhost:5432 | Base de données (user: disruptiq, db: disruptiq) |

### 📚 Documentation Supplémentaire

- **VENDOR_INDEXING_GUIDE.md** - Guide complet du système d'indexation des fournisseurs
  - Architecture technique
  - Exemples de questions pour l'assistant
  - Vérification de l'indexation
  - Dépannage spécifique vendors

- **TESTING_GUIDE.md** - Guide de tests
  - Tests API manuels et automatisés
  - Scénarios de tests complets
  - Résolution de problèmes

- **CHANGELOG_FIXES.md** - Historique détaillé des corrections
  - Liste complète des bugs corrigés
  - Modifications techniques
  - Tests de validation

- **N8N_WORKFLOWS.md** - Documentation des workflows N8N (à venir)

---

## 🚨 COMMANDE DE DÉMARRAGE IMMÉDIAT

Copiez-collez ceci dans Claude Code pour commencer:

```
Bonjour Claude Code ! Je veux créer DisruptIQ, un système RAG pour syndics. 

Commencez par créer la structure complète du projet avec:
- Backend FastAPI dans /backend
- Frontend React dans /frontend  
- Docker Compose à la racine
- README avec instructions

Puis implémentez le backend avec:
1. Modèles de base de données (users, emails, vendors)
2. Service de connexion Gmail API
3. Endpoint POST /api/digest/generate qui classe des emails par urgence
4. Configuration complète dans .env.example

Le tout doit être production-ready avec gestion d'erreurs et logs.
```

---

## 📈 Résumé de l'État Actuel

### ✅ Ce qui Fonctionne Maintenant

1. **Gestion Complète des Fournisseurs**
   - Import CSV avec validation automatique des emails
   - Détection automatique du délimiteur (`,` ou `;`)
   - Prévention des doublons par email
   - Affichage dans l'interface admin
   - Statistiques en temps réel

2. **Assistant RAG Fonctionnel**
   - Recherche sémantique dans Qdrant
   - Indexation automatique des vendors à l'import
   - Réponses précises avec coordonnées complètes
   - Support des questions naturelles en français
   - Endpoint de réindexation manuelle disponible

3. **Infrastructure Stable**
   - Docker Compose avec tous les services
   - Base de données PostgreSQL avec contraintes
   - Qdrant vectoriel opérationnel
   - Frontend accessible via localhost
   - API documentée avec Swagger

4. **Gestion d'Erreurs Robuste**
   - Validation Pydantic des données
   - Messages d'erreur clairs dans l'interface
   - Logs structurés avec structlog
   - Rollback automatique en cas d'échec
   - Gestion des erreurs d'indexation

### 🎯 Prochaines Étapes Recommandées

1. **Tests Utilisateur** (Maintenant)
   - Tester l'import de différents CSV
   - Vérifier les réponses de l'assistant
   - Valider l'expérience utilisateur

2. **Configuration Gmail** (Optionnel)
   - Activer Gmail OAuth
   - Tester le Smart Digest automatique
   - Vérifier la classification des emails

3. **Intégration N8N** (Priorité Moyenne)
   - Tester les webhooks existants
   - Créer les workflows d'envoi d'emails
   - Intégrer avec les actions dans le frontend

4. **Optimisations** (Selon Retours)
   - Améliorer les performances de recherche
   - Ajouter plus de filtres dans l'admin
   - Enrichir les réponses de l'assistant

### 📞 Support

Pour tout problème:
1. Consultez d'abord la section "Résolution de Problèmes Courants" ci-dessus
2. Vérifiez les logs: `docker-compose logs -f backend`
3. Référez-vous aux guides spécifiques:
   - VENDOR_INDEXING_GUIDE.md pour problèmes d'indexation
   - TESTING_GUIDE.md pour validation des fonctionnalités
   - CHANGELOG_FIXES.md pour historique des corrections

---

**Dernière mise à jour:** Session de développement actuelle
**Statut global:** ✅ Système stable et fonctionnel pour tests utilisateur

Bonne chance ! 🚀
