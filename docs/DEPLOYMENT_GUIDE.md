# 🚀 Guide de Déploiement Production - DisruptIQ V0

**Date:** Novembre 2025
**Version:** V0.9 → V0 Production
**Environnement:** VPS Ubuntu 22.04 LTS

---

## 📋 Prérequis

### Serveur VPS

- **OS:** Ubuntu 22.04 LTS (recommandé)
- **RAM:** 8 GB minimum
- **CPU:** 4 cores minimum
- **Disk:** 100 GB SSD
- **Accès:** SSH avec clé publique (pas de mot de passe)

### Logiciels Requis

- Docker 20+
- Docker Compose 2+
- Git
- Certbot (Let's Encrypt)

---

## 🔐 ÉTAPE 1 : Préparation Serveur (30 min)

### 1.1 Connexion SSH

```bash
# Depuis votre machine locale
ssh root@votre-ip-vps
```

### 1.2 Mise à Jour Système

```bash
# Update packages
sudo apt-get update
sudo apt-get upgrade -y

# Install essentials
sudo apt-get install -y curl wget git ufw fail2ban
```

### 1.3 Créer Utilisateur Non-Root

```bash
# Create user
adduser disruptiq
usermod -aG sudo disruptiq

# Setup SSH key
mkdir -p /home/disruptiq/.ssh
cp ~/.ssh/authorized_keys /home/disruptiq/.ssh/
chown -R disruptiq:disruptiq /home/disruptiq/.ssh
chmod 700 /home/disruptiq/.ssh
chmod 600 /home/disruptiq/.ssh/authorized_keys

# Switch to new user
su - disruptiq
```

### 1.4 Configurer Firewall

```bash
# Enable UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (IMPORTANT: do this first!)
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
sudo ufw status
```

### 1.5 Installer Docker & Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# Log out and log back in for group changes to take effect
exit
ssh disruptiq@votre-ip-vps
```

---

## 🔑 ÉTAPE 2 : Secrets & Configuration (20 min)

### 2.1 Générer Secrets Sécurisés

```bash
# Generate SECRET_KEY (50+ characters)
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Generate PostgreSQL password
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate Redis password (optional)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**⚠️ IMPORTANT:** Sauvegardez ces valeurs dans un gestionnaire de mots de passe sécurisé !

### 2.2 Cloner Repository

```bash
# Create app directory
mkdir -p ~/apps
cd ~/apps

# Clone project
git clone https://github.com/your-org/DisruptIQ.git
cd DisruptIQ
```

### 2.3 Configuration .env.production

```bash
cd backend
cp .env.production.example .env.production
nano .env.production
```

**Variables CRITIQUES à modifier:**

```bash
# CRITICAL: Change these values!
SECRET_KEY=<votre-secret-key-50-chars>
DATABASE_URL=postgresql+asyncpg://disruptiq:<votre-db-password>@postgres:5432/disruptiq
CORS_ORIGINS=https://votre-domaine.com
MISTRAL_API_KEY=<votre-mistral-key>

# Optional but recommended
REDIS_PASSWORD=<votre-redis-password>
POSTGRES_PASSWORD=<votre-db-password>
```

### 2.4 Configurer Docker Compose

```bash
cd ~/apps/DisruptIQ

# Create .env file for docker-compose
cat > .env << EOF
POSTGRES_PASSWORD=<votre-db-password>
REDIS_PASSWORD=<votre-redis-password>
EOF

# Secure permissions
chmod 600 .env backend/.env.production
```

---

## 🔒 ÉTAPE 3 : SSL/TLS Certificates (15 min)

### 3.1 Installer Certbot

```bash
sudo apt-get install -y certbot
```

### 3.2 Générer Certificats Let's Encrypt

**Option A: Certbot Standalone (serveur arrêté)**

```bash
# Stop nginx if running
docker-compose -f docker-compose.prod.yml down nginx

# Generate certificates
sudo certbot certonly --standalone \
  -d votre-domaine.com \
  -d www.votre-domaine.com \
  --email votre-email@example.com \
  --agree-tos \
  --no-eff-email
```

**Option B: Certbot Webroot (serveur running)**

```bash
# Create webroot directory
sudo mkdir -p /var/www/certbot

# Generate certificates
sudo certbot certonly --webroot \
  -w /var/www/certbot \
  -d votre-domaine.com \
  -d www.votre-domaine.com \
  --email votre-email@example.com \
  --agree-tos \
  --no-eff-email
```

### 3.3 Copier Certificats

```bash
# Create SSL directory
mkdir -p ~/apps/DisruptIQ/nginx/ssl

# Copy certificates
sudo cp /etc/letsencrypt/live/votre-domaine.com/fullchain.pem ~/apps/DisruptIQ/nginx/ssl/
sudo cp /etc/letsencrypt/live/votre-domaine.com/privkey.pem ~/apps/DisruptIQ/nginx/ssl/
sudo cp /etc/letsencrypt/live/votre-domaine.com/chain.pem ~/apps/DisruptIQ/nginx/ssl/

# Set permissions
sudo chown -R $USER:$USER ~/apps/DisruptIQ/nginx/ssl
chmod 600 ~/apps/DisruptIQ/nginx/ssl/*.pem
```

### 3.4 Auto-Renewal Setup

```bash
# Test renewal
sudo certbot renew --dry-run

# Add cron job for auto-renewal
sudo crontab -e

# Add this line (runs twice daily):
0 0,12 * * * certbot renew --quiet --post-hook "cd ~/apps/DisruptIQ && docker-compose -f docker-compose.prod.yml restart nginx"
```

### 3.5 Mettre à Jour Nginx Config

```bash
cd ~/apps/DisruptIQ
nano nginx/nginx.prod.conf

# Change server_name to your domain:
server_name votre-domaine.com www.votre-domaine.com;
```

---

## 🚀 ÉTAPE 4 : Déploiement (15 min)

### 4.1 Build Images

```bash
cd ~/apps/DisruptIQ

# Build production images
docker-compose -f docker-compose.prod.yml build
```

### 4.2 Start Services

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps
```

### 4.3 Run Database Migrations

```bash
# Wait for services to be healthy (30-60 seconds)
sleep 60

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### 4.4 Verify Services

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs frontend
docker-compose -f docker-compose.prod.yml logs nginx

# Test health endpoints
curl http://localhost:8000/health
curl https://votre-domaine.com/health
```

---

## ✅ ÉTAPE 5 : Smoke Tests (10 min)

### 5.1 Tests Manuels

1. **Frontend accessible:**
   - Ouvrir `https://votre-domaine.com`
   - Vérifier HTTPS (cadenas vert)
   - Vérifier redirection HTTP → HTTPS

2. **API Backend:**
   - Ouvrir `https://votre-domaine.com/api/docs`
   - Tester endpoint `/health`

3. **Login/Authentication:**
   - Tester login utilisateur
   - Vérifier session persistence

4. **Core Features:**
   - Upload document
   - Chat assistant
   - Generate email

### 5.2 Security Headers Check

```bash
# Check security headers
curl -I https://votre-domaine.com | grep -E "Strict-Transport|X-Frame|X-Content|Content-Security"
```

Attendu:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Content-Security-Policy: ...
```

### 5.3 Rate Limiting Test

```bash
# Test API rate limiting (should fail after 100 req/min)
for i in {1..105}; do curl -s -o /dev/null -w "%{http_code}\n" https://votre-domaine.com/api/health; done
```

Attendu: Code 429 (Too Many Requests) après ~100 requêtes

---

## 📊 ÉTAPE 6 : Monitoring & Backup (20 min)

### 6.1 Setup Logs

```bash
# Create log directory
mkdir -p ~/apps/DisruptIQ/logs

# View real-time logs
docker-compose -f docker-compose.prod.yml logs -f --tail=100
```

### 6.2 Automated Backups

```bash
# Create backup script
cat > ~/apps/DisruptIQ/scripts/backup.sh << 'EOF'
#!/bin/bash
# DisruptIQ Automated Backup Script

BACKUP_DIR="/home/disruptiq/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker-compose -f ~/apps/DisruptIQ/docker-compose.prod.yml exec -T postgres \
  pg_dump -U disruptiq disruptiq | gzip > $BACKUP_DIR/postgres_$DATE.sql.gz

# Backup Qdrant
docker-compose -f ~/apps/DisruptIQ/docker-compose.prod.yml exec -T qdrant \
  tar czf - /qdrant/storage > $BACKUP_DIR/qdrant_$DATE.tar.gz

# Backup uploads
tar czf $BACKUP_DIR/uploads_$DATE.tar.gz ~/apps/DisruptIQ/uploads

# Delete backups older than 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
EOF

# Make executable
chmod +x ~/apps/DisruptIQ/scripts/backup.sh

# Test backup
~/apps/DisruptIQ/scripts/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e

# Add line:
0 2 * * * /home/disruptiq/apps/DisruptIQ/scripts/backup.sh >> /home/disruptiq/apps/DisruptIQ/logs/backup.log 2>&1
```

### 6.3 Monitoring Setup (Optionnel)

**Option A: Sentry (Error Tracking)**

```bash
# Add to .env.production
SENTRY_DSN=your-sentry-dsn-here
SENTRY_ENVIRONMENT=production
```

**Option B: Prometheus + Grafana (Métriques)**

(Voir documentation Prometheus/Grafana)

---

## 🔄 ÉTAPE 7 : Maintenance

### Update Application

```bash
cd ~/apps/DisruptIQ

# Pull latest code
git pull origin main

# Rebuild images
docker-compose -f docker-compose.prod.yml build

# Stop services
docker-compose -f docker-compose.prod.yml down

# Start with new images
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100 backend
```

### Restart Services

```bash
# Restart all
docker-compose -f docker-compose.prod.yml restart

# Restart specific service
docker-compose -f docker-compose.prod.yml restart backend
```

### Database Backup/Restore

**Backup:**
```bash
docker-compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U disruptiq disruptiq > backup.sql
```

**Restore:**
```bash
cat backup.sql | docker-compose -f docker-compose.prod.yml exec -T postgres \
  psql -U disruptiq disruptiq
```

---

## 🚨 Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs

# Check disk space
df -h

# Check Docker status
sudo systemctl status docker
```

### Database Connection Errors

```bash
# Check PostgreSQL logs
docker-compose -f docker-compose.prod.yml logs postgres

# Verify database is healthy
docker-compose -f docker-compose.prod.yml ps postgres

# Test connection
docker-compose -f docker-compose.prod.yml exec postgres psql -U disruptiq -d disruptiq -c "SELECT 1"
```

### SSL Certificate Issues

```bash
# Check certificate expiry
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal

# Check nginx config
docker-compose -f docker-compose.prod.yml exec nginx nginx -t
```

### High Memory Usage

```bash
# Check container stats
docker stats

# Restart heavy services
docker-compose -f docker-compose.prod.yml restart backend
```

---

## ✅ Checklist GO/NO-GO Production

### Pré-Déploiement

- [ ] SECRET_KEY est généré et sécurisé (50+ caractères)
- [ ] CORS_ORIGINS contient uniquement votre domaine (pas de *)
- [ ] DATABASE_URL password changé du défaut
- [ ] MISTRAL_API_KEY configuré
- [ ] Certificats SSL générés et copiés
- [ ] Nginx server_name configuré avec votre domaine
- [ ] Firewall UFW configuré
- [ ] Backups automatiques configurés

### Post-Déploiement

- [ ] HTTPS fonctionne (cadenas vert)
- [ ] HTTP redirige vers HTTPS
- [ ] Headers de sécurité présents
- [ ] API /health retourne 200
- [ ] Frontend accessible
- [ ] Login fonctionne
- [ ] Rate limiting actif (test 429)
- [ ] Logs accessibles
- [ ] Backup script testé

---

## 📞 Support

En cas de problème:

1. Consulter les logs: `docker-compose -f docker-compose.prod.yml logs`
2. Vérifier PRODUCTION_CHECKLIST.md
3. Consulter la documentation technique
4. Ouvrir une issue sur GitHub

---

**Félicitations ! DisruptIQ est déployé en production. 🎉**

*Dernière mise à jour: Novembre 2025*
