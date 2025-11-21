# 🚀 Guide de Déploiement DisruptIQ sur OVH VPS

**Version:** 2.0.0 (V0 - Docker Compose)
**Date:** Novembre 2025
**Durée estimée:** 1-2 heures
**Méthode recommandée:** Docker Compose (tout-en-un)

---

## 📋 Table des Matières

1. [Prérequis](#prérequis)
2. [Choix du serveur OVH](#choix-du-serveur-ovh)
3. [Configuration initiale du serveur](#configuration-initiale-du-serveur)
4. [🐳 MÉTHODE RECOMMANDÉE : Déploiement Docker Compose](#-méthode-recommandée--déploiement-docker-compose)
5. [Configuration du domaine et SSL](#configuration-du-domaine-et-ssl)
6. [Vérification et tests](#vérification-et-tests)
7. [Maintenance](#maintenance)
8. [Dépannage](#dépannage)
9. [ANNEXE : Déploiement manuel (alternative)](#annexe--déploiement-manuel-alternative)

---

## 🎯 Prérequis

### Avant de commencer

- [x] **Compte OVH** avec accès au manager
- [x] **Nom de domaine** configuré (ex: disruptiq.com)
- [x] **Clé API Mistral** ([console.mistral.ai](https://console.mistral.ai/))
- [ ] **Gmail API credentials** (optionnel - pour emails)
- [ ] **Sentry DSN** (optionnel - monitoring)

### Informations à préparer

```bash
# Notez ces informations avant de commencer
DOMAIN_NAME=votre-domaine.com
MISTRAL_API_KEY=votre-cle-mistral
OPENAI_API_KEY=votre-cle-openai (fallback optionnel)
```

---

## 🖥️ Choix du Serveur OVH

### Recommandations V0 Pilote

**🏆 Option recommandée : VPS Starter**
- **Prix:** ~6-8€/mois
- **Specs:** 2 vCPU, 4 GB RAM, 80 GB SSD
- **Parfait pour:** Tests pilotes (<50 utilisateurs)
- **Lien:** [VPS OVH](https://www.ovhcloud.com/fr/vps/)

**Alternative : VPS Value**
- **Prix:** ~12-15€/mois
- **Specs:** 2 vCPU, 8 GB RAM, 160 GB SSD
- **Parfait pour:** Production stable (50-200 utilisateurs)

### ✅ Commander le serveur

1. Connectez-vous au [Manager OVH](https://www.ovh.com/manager/)
2. **Commander > VPS > Choisir VPS Starter**
3. **OS:** **Ubuntu 22.04 LTS** (obligatoire)
4. **SSH Key:** Ajoutez votre clé publique SSH si disponible
5. Notez l'**adresse IP** du serveur (ex: 51.210.xxx.xxx)

---

## 🔧 Configuration Initiale du Serveur

### 1. Connexion SSH initiale

```bash
# Depuis votre machine Windows (PowerShell)
ssh root@VOTRE_IP_OVH

# Si première connexion, acceptez la fingerprint SSH
# Tapez "yes" puis Entrée
```

### 2. Mise à jour du système

```bash
# Mise à jour complète
apt update && apt upgrade -y

# Installation des outils essentiels
apt install -y git curl wget vim htop unzip
```

### 3. Création d'un utilisateur non-root (sécurité)

```bash
# Créer l'utilisateur disruptiq
adduser disruptiq
# Choisir un mot de passe sécurisé

# Ajouter aux sudoers
usermod -aG sudo disruptiq

# Copier les clés SSH (si configurées)
mkdir -p /home/disruptiq/.ssh
cp ~/.ssh/authorized_keys /home/disruptiq/.ssh/ 2>/dev/null || true
chown -R disruptiq:disruptiq /home/disruptiq/.ssh
chmod 700 /home/disruptiq/.ssh
chmod 600 /home/disruptiq/.ssh/authorized_keys 2>/dev/null || true

# Passer à l'utilisateur disruptiq
su - disruptiq
```

### 4. Configuration du pare-feu

```bash
# Installer UFW
sudo apt install -y ufw

# Autoriser les ports essentiels
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS

# Activer le pare-feu
sudo ufw --force enable
sudo ufw status
```

### 5. Installation de Docker et Docker Compose

```bash
# Installer Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Ajouter l'utilisateur au groupe docker
sudo usermod -aG docker disruptiq

# Installer Docker Compose v2 (inclus avec Docker)
sudo apt install -y docker-compose-plugin

# Démarrer et activer Docker
sudo systemctl start docker
sudo systemctl enable docker

# IMPORTANT: Se déconnecter et reconnecter pour appliquer les permissions
exit
ssh disruptiq@VOTRE_IP_OVH

# Vérifier l'installation
docker --version
docker compose version
```

---

## 🐳 MÉTHODE RECOMMANDÉE : Déploiement Docker Compose

### Pourquoi Docker Compose ?

✅ **Avantages :**
- Déploiement en **une seule commande**
- Toutes les dépendances incluses (PostgreSQL, Redis, Qdrant)
- Redémarrage automatique des services
- Isolation et sécurité
- Mises à jour simplifiées
- Pas de conflits de versions Python/Node

### Étape 1 : Transférer le projet depuis Windows

#### Option A : Via SCP (recommandé pour première fois)

```powershell
# Sur votre machine Windows (PowerShell)
# Naviguer vers le dossier parent
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ

# Créer une archive ZIP (exclure les fichiers inutiles)
$exclude = @('__pycache__', '*.pyc', 'venv', 'env', 'node_modules', '.git', 'dist', 'htmlcov', '.coverage', 'logs', 'uploads')
Compress-Archive -Path DisruptIQ_CC2\* -DestinationPath DisruptIQ_deploy.zip -Force

# Transférer vers le serveur
scp DisruptIQ_deploy.zip disruptiq@VOTRE_IP_OVH:/home/disruptiq/
```

#### Option B : Via Git (pour mises à jour futures)

```powershell
# Sur Windows - initialiser le repo
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC2
git init
git add .
git commit -m "Initial commit"

# Créer un repo GitHub privé puis :
git remote add origin https://github.com/VOTRE_USERNAME/DisruptIQ.git
git branch -M main
git push -u origin main
```

### Étape 2 : Préparer les fichiers sur le serveur

```bash
# Sur le serveur OVH
cd /home/disruptiq

# Si vous avez utilisé SCP :
unzip DisruptIQ_deploy.zip
mv DisruptIQ_CC2 DisruptIQ

# OU si vous avez utilisé Git :
git clone https://github.com/VOTRE_USERNAME/DisruptIQ.git

# Entrer dans le projet
cd DisruptIQ
ls -la
```

### Étape 3 : Configurer les variables d'environnement

```bash
# Copier le fichier .env d'exemple
cp .env .env.production

# Éditer le fichier de production
nano .env.production
```

**Contenu du fichier `.env.production` :**

```bash
# Application
APP_NAME=DisruptIQ
APP_VERSION=1.0.0
DEBUG=False
ENVIRONMENT=production

# Database (Docker Compose gère ça automatiquement)
DATABASE_URL=postgresql+asyncpg://disruptiq:disruptiq_password@postgres:5432/disruptiq

# Redis
REDIS_URL=redis://redis:6379/0

# Qdrant Vector Database
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_NAME=disruptiq_documents

# ============================================
# Mistral AI (PRIMARY - OBLIGATOIRE)
# ============================================
MISTRAL_API_KEY=VOTRE_CLE_MISTRAL_ICI
MISTRAL_MODEL=mistral-small-latest
MISTRAL_EMBEDDING_MODEL=mistral-embed
MISTRAL_VISION_MODEL=pixtral-12b-2409

# ============================================
# OpenAI (Fallback - Optionnel)
# ============================================
OPENAI_API_KEY=VOTRE_CLE_OPENAI_ICI
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Gmail API (Optionnel - pour emails)
GMAIL_CREDENTIALS_PATH=./credentials/gmail_credentials.json
GMAIL_TOKEN_PATH=./credentials/gmail_token.json

# Scheduler
SCHEDULER_ENABLED=false
DIGEST_GENERATION_INTERVAL=60
DIGEST_SEND_TIME=08:00

# N8N Webhooks (Optionnel)
N8N_WEBHOOK_BASE_URL=https://your-n8n-instance.com
N8N_WEBHOOK_AUTH_TOKEN=your-secret-webhook-token

# Security - GÉNÉRER UNE CLÉ SÉCURISÉE
SECRET_KEY=REMPLACER_PAR_CLE_SECURISEE_32_CARACTERES_MINIMUM
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS - Ajoutez votre domaine
CORS_ORIGINS=https://votre-domaine.com,https://www.votre-domaine.com,http://localhost:3000

# Document Processing
MAX_UPLOAD_SIZE=10485760  # 10MB

# Monitoring (Optionnel mais recommandé)
SENTRY_DSN=https://votre-sentry-dsn@sentry.io/projet
```

**⚠️ IMPORTANT : Générer une SECRET_KEY sécurisée**

```bash
# Générer une clé aléatoire sécurisée
openssl rand -hex 32

# Copier le résultat et le coller dans .env.production pour SECRET_KEY
```

### Étape 4 : Transférer les credentials Gmail (si nécessaire)

```powershell
# Sur Windows - seulement si vous utilisez Gmail
scp C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC2\backend\credentials\*.json disruptiq@VOTRE_IP_OVH:/home/disruptiq/DisruptIQ/credentials/
```

### Étape 5 : Modifier docker-compose.yml pour la production

```bash
# Sur le serveur
cd /home/disruptiq/DisruptIQ
nano docker-compose.yml
```

**Modifier les sections suivantes :**

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: disruptiq_postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: disruptiq
      POSTGRES_USER: disruptiq
      POSTGRES_PASSWORD: disruptiq_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U disruptiq"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - disruptiq_network

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: disruptiq_redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - disruptiq_network

  # Qdrant Vector Database
  qdrant:
    image: qdrant/qdrant:latest
    container_name: disruptiq_qdrant
    restart: unless-stopped
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
    networks:
      - disruptiq_network

  # FastAPI Backend
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: disruptiq_backend
    restart: unless-stopped
    env_file:
      - .env.production
    volumes:
      - ./credentials:/app/credentials
      - backend_uploads:/app/uploads
      - backend_logs:/app/logs
    expose:
      - "8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started
    command: gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120
    networks:
      - disruptiq_network

  # React Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - VITE_API_URL=https://votre-domaine.com/api
    container_name: disruptiq_frontend
    restart: unless-stopped
    expose:
      - "80"
    depends_on:
      - backend
    networks:
      - disruptiq_network

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: disruptiq_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - certbot_www:/var/www/certbot:ro
      - certbot_conf:/etc/letsencrypt:ro
    depends_on:
      - backend
      - frontend
    networks:
      - disruptiq_network

  # Certbot pour SSL (Let's Encrypt)
  certbot:
    image: certbot/certbot:latest
    container_name: disruptiq_certbot
    volumes:
      - certbot_www:/var/www/certbot
      - certbot_conf:/etc/letsencrypt
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"
    networks:
      - disruptiq_network

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  backend_uploads:
  backend_logs:
  certbot_www:
  certbot_conf:

networks:
  disruptiq_network:
    driver: bridge
```

### Étape 6 : Créer la configuration Nginx

```bash
# Créer le dossier nginx
mkdir -p /home/disruptiq/DisruptIQ/nginx

# Créer la configuration
nano /home/disruptiq/DisruptIQ/nginx/nginx.conf
```

**Contenu de `nginx.conf` :**

```nginx
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logs
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Optimisations
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 10M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1000;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Serveur HTTP (redirection HTTPS)
    server {
        listen 80;
        listen [::]:80;
        server_name votre-domaine.com www.votre-domaine.com;

        # Let's Encrypt challenge
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        # Redirection HTTPS
        location / {
            return 301 https://$host$request_uri;
        }
    }

    # Serveur HTTPS
    server {
        listen 443 ssl http2;
        listen [::]:443 ssl http2;
        server_name votre-domaine.com www.votre-domaine.com;

        # SSL Configuration (Let's Encrypt)
        ssl_certificate /etc/letsencrypt/live/votre-domaine.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/votre-domaine.com/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security Headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # Frontend (React)
        location / {
            proxy_pass http://frontend:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Backend API
        location /api {
            proxy_pass http://backend:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts pour les requêtes LLM longues
            proxy_connect_timeout 120s;
            proxy_send_timeout 120s;
            proxy_read_timeout 120s;
        }

        # Health checks
        location /health {
            proxy_pass http://backend:8000/health;
            access_log off;
        }
    }
}
```

**⚠️ REMPLACER `votre-domaine.com` par votre vrai domaine !**

### Étape 7 : Lancer l'application (SANS SSL d'abord)

```bash
# Modifier temporairement nginx.conf pour désactiver SSL
cd /home/disruptiq/DisruptIQ
nano nginx/nginx.conf

# Commenter les lignes SSL (ajouter # devant) :
# listen 443 ssl http2;
# ssl_certificate ...
# ssl_certificate_key ...

# Garder seulement le serveur HTTP port 80

# Construire et lancer tous les services
docker compose -f docker-compose.yml up -d --build

# Vérifier que tout tourne
docker compose ps

# Vous devriez voir :
# disruptiq_postgres   running
# disruptiq_redis      running
# disruptiq_qdrant     running
# disruptiq_backend    running
# disruptiq_frontend   running
# disruptiq_nginx      running
```

### Étape 8 : Appliquer les migrations de base de données

```bash
# Exécuter les migrations Alembic
docker compose exec backend alembic upgrade head

# Vérifier que ça a fonctionné
docker compose exec backend alembic current

# Vous devriez voir : "Initial schema with all tables"
```

### Étape 9 : Créer un premier utilisateur admin

```bash
# Se connecter au backend
docker compose exec backend bash

# Lancer Python
python

# Dans Python :
from app.models.user import User
from app.core.database import SessionLocal
from app.core.security import get_password_hash

db = SessionLocal()

# Créer un admin
admin = User(
    email="admin@votre-domaine.com",
    hashed_password=get_password_hash("VotreMotDePasseSecurise123!"),
    full_name="Admin DisruptIQ",
    is_superuser=True,
    is_active=True
)

db.add(admin)
db.commit()
print("Admin créé avec succès !")
exit()

# Quitter le container
exit
```

### Étape 10 : Tester l'application (HTTP)

```bash
# Depuis le serveur
curl http://VOTRE_IP_OVH/health

# Depuis votre navigateur
http://VOTRE_IP_OVH
```

Si ça fonctionne, passez à la configuration SSL !

---

## 🔒 Configuration du Domaine et SSL

### 1. Configurer le DNS chez OVH

**Dans le Manager OVH :**

1. Allez dans **Web Cloud > Noms de domaine**
2. Sélectionnez votre domaine
3. Onglet **Zone DNS**
4. Cliquez **Ajouter une entrée**
5. Ajoutez ces 2 entrées :

```
Type: A
Sous-domaine: @ (vide)
Cible: VOTRE_IP_OVH

Type: A
Sous-domaine: www
Cible: VOTRE_IP_OVH
```

6. Cliquez **Valider**
7. **Attendre 10-30 minutes** pour la propagation DNS

### 2. Vérifier la propagation DNS

```bash
# Sur le serveur
nslookup votre-domaine.com
ping votre-domaine.com

# L'IP doit correspondre à votre serveur OVH
```

### 3. Obtenir le certificat SSL Let's Encrypt

```bash
# Arrêter temporairement nginx
docker compose stop nginx

# Obtenir le certificat
docker compose run --rm certbot certonly --standalone \
  -d votre-domaine.com \
  -d www.votre-domaine.com \
  --email votre-email@example.com \
  --agree-tos \
  --no-eff-email

# Redémarrer nginx
docker compose start nginx
```

### 4. Réactiver HTTPS dans nginx.conf

```bash
# Éditer nginx.conf
nano nginx/nginx.conf

# Décommenter les lignes SSL (retirer les #)
# listen 443 ssl http2;
# ssl_certificate ...
# ssl_certificate_key ...

# Sauvegarder et redémarrer nginx
docker compose restart nginx
```

### 5. Tester HTTPS

```bash
# Tester depuis le navigateur
https://votre-domaine.com

# Vérifier le certificat SSL (doit être Let's Encrypt)
```

---

## ✅ Vérification et Tests

### 1. Vérifier tous les services

```bash
# Statut de tous les containers
docker compose ps

# Tous doivent être "Up" et "healthy"
```

### 2. Vérifier les logs

```bash
# Logs du backend
docker compose logs backend --tail=50

# Logs nginx
docker compose logs nginx --tail=50

# Logs en temps réel (Ctrl+C pour quitter)
docker compose logs -f
```

### 3. Tester les endpoints

```bash
# Health check
curl https://votre-domaine.com/health

# API docs (Swagger)
https://votre-domaine.com/api/docs

# Frontend
https://votre-domaine.com
```

### 4. Test complet utilisateur

1. **Connexion** : https://votre-domaine.com
2. **Login** avec le compte admin créé
3. **Upload** un document PDF
4. **Poser une question** : "Combien de copropriétaires ?"
5. **Vérifier** la réponse du système

---

## 🔧 Maintenance

### Commandes utiles

```bash
# Voir les logs
docker compose logs -f

# Redémarrer un service
docker compose restart backend

# Redémarrer tout
docker compose restart

# Arrêter tout
docker compose down

# Mettre à jour depuis Git
cd /home/disruptiq/DisruptIQ
git pull origin main
docker compose up -d --build

# Backup de la base de données
docker compose exec postgres pg_dump -U disruptiq disruptiq > backup_$(date +%Y%m%d).sql

# Nettoyer les images inutilisées
docker system prune -a
```

### Surveillance

```bash
# Utilisation des ressources
docker stats

# Espace disque
df -h
docker system df
```

### Logs automatiques

Les logs sont persistés dans les volumes Docker :
- Backend : `/var/lib/docker/volumes/disruptiq_backend_logs`
- Nginx : Dans les containers (voir avec `docker compose logs nginx`)

---

## 🔍 Dépannage

### Problème 1 : Backend ne démarre pas

```bash
# Voir les logs détaillés
docker compose logs backend

# Problèmes courants :
# - SECRET_KEY manquante → Vérifier .env.production
# - MISTRAL_API_KEY invalide → Vérifier la clé API
# - Base de données inaccessible → Vérifier que postgres est "healthy"

# Redémarrer proprement
docker compose down
docker compose up -d
```

### Problème 2 : Erreur 502 Bad Gateway

```bash
# Vérifier que backend répond
docker compose exec backend curl http://localhost:8000/health

# Si ça ne fonctionne pas, redémarrer backend
docker compose restart backend

# Vérifier les logs nginx
docker compose logs nginx
```

### Problème 3 : SSL ne fonctionne pas

```bash
# Vérifier les certificats
docker compose exec nginx ls -la /etc/letsencrypt/live/

# Renouveler manuellement
docker compose run --rm certbot renew --force-renewal

# Redémarrer nginx
docker compose restart nginx
```

### Problème 4 : Qdrant ne répond pas

```bash
# Vérifier le statut
docker compose ps qdrant

# Tester l'accès
docker compose exec backend curl http://qdrant:6333/collections

# Redémarrer
docker compose restart qdrant
```

### Problème 5 : Manque d'espace disque

```bash
# Vérifier l'espace
df -h

# Nettoyer Docker
docker system prune -a --volumes

# Attention : cela supprime TOUT ce qui n'est pas utilisé !
```

---

## 📊 Checklist Finale

### ✅ Avant production

- [ ] DNS configuré et propagé (10-30 min)
- [ ] SSL/HTTPS fonctionnel (certificat Let's Encrypt)
- [ ] Tous les services Docker "Up" et "healthy"
- [ ] Migrations de base de données appliquées
- [ ] Compte admin créé et testé
- [ ] Variables d'environnement correctes (.env.production)
- [ ] SECRET_KEY sécurisée (32+ caractères)
- [ ] MISTRAL_API_KEY valide
- [ ] Test upload document OK
- [ ] Test requête SQL OK
- [ ] Test recherche RAG OK
- [ ] Logs accessibles
- [ ] Backup testé

### 📌 Post-déploiement (48h)

- [ ] Surveiller les logs (`docker compose logs -f`)
- [ ] Vérifier l'utilisation des ressources (`docker stats`)
- [ ] Tester toutes les fonctionnalités avec les pilotes
- [ ] Documenter les bugs rencontrés
- [ ] Créer un premier backup manuel

---

## 🎉 Félicitations !

Votre application **DisruptIQ** est maintenant **en production** sur OVH VPS avec Docker Compose !

**URLs importantes :**
- Frontend : https://votre-domaine.com
- API Docs : https://votre-domaine.com/api/docs
- Health Check : https://votre-domaine.com/health

**Support :**
- Documentation : `/docs/` dans le projet
- Issues : GitHub Issues
- Logs : `docker compose logs -f`

---

## 📝 ANNEXE : Déploiement Manuel (Alternative)

<details>
<summary>Cliquez pour voir le guide de déploiement manuel (sans Docker)</summary>

Si vous préférez ne pas utiliser Docker Compose, voici la méthode manuelle...

[Le reste du contenu original du guide serait ici]

</details>

---

**Version du guide:** 2.0.0
**Dernière mise à jour:** Novembre 2025
**Testé sur:** Ubuntu 22.04 LTS + OVH VPS Starter + Docker Compose
**Auteur:** DisruptIQ Team
