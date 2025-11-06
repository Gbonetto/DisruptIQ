# 🚀 Checklist Mise en Production DisruptIQ

**Date création**: 6 Novembre 2025
**Version cible**: v3.2
**Score actuel**: 6.25/10
**Objectif**: Production-ready deployment sur VPS

---

## 📊 Statut Global

| Catégorie | Score | Statut | Priorité |
|-----------|-------|--------|----------|
| **Sécurité** | 6/10 | 🟠 À compléter | P0 - Critique |
| **Base de données** | 7/10 | 🟢 Alembic OK | P1 - Important |
| **Tests** | 5/10 | 🟡 Insuffisant | P1 - Important |
| **Frontend** | 8/10 | 🟢 Build OK | P2 - Mineur |
| **Monitoring** | 5/10 | 🟡 À compléter | P1 - Important |
| **Infrastructure** | 7/10 | 🟢 Docker OK | P2 - Mineur |

**Verdict**: ✅ GO avec corrections Week 1-2

---

## ✅ Semaine 1: Sécurité Critique (P0)

### 🔒 Validations & Hardening

#### SQL Injection Prevention
- [ ] **Whitelist tables** dans orchestrator_agent.py
  ```python
  ALLOWED_TABLES = ['coproprietes', 'coproprietaires', 
                    'professionnels', 'emails', 'documents']
  ```
- [ ] **Validation paramètres** utilisateur (Pydantic schemas)
- [ ] **Rate limiting** SQL queries (100 req/hour/user)
- [ ] **Sanitization** inputs avant SQL execution

#### Upload Security
- [ ] **File type whitelist**: PDF, DOCX, TXT, PNG, JPG uniquement
- [ ] **File size limit**: 25 MB maximum
- [ ] **Filename sanitization**: alphanum + underscore only
- [ ] **Rate limiting** upload (10 fichiers/hour/user)
- [ ] **Antivirus scan** (ClamAV) optionnel

#### Production Hardening
- [ ] **SECRET_KEY validation**: 50+ chars random en .env.production
- [ ] **CORS whitelist**: Domaines autorisés uniquement
  ```python
  CORS_ORIGINS = ["https://app.disruptiq.fr"]
  ```
- [ ] **Error masking**: Pas de stack traces en production
- [ ] **HTTPS enforcement**: nginx redirect HTTP → HTTPS
- [ ] **CSP headers**: Content Security Policy
- [ ] **Environment variables**: Vérifier .env.production complet

**Livrable**: ✅ 0 vulnérabilités critiques (npm audit, safety, bandit)

---

## 🧪 Semaine 2: Tests & Qualité (P1)

### Backend Tests (Target: 80% coverage)

#### Tests Unitaires
- [ ] **Intent Classifier v3**: 15 tests
  - Classification SQL queries
  - Classification RAG queries
  - Classification emails
  - Anaphora resolution
  - Confidence scoring
  
- [ ] **RAG Hybrid**: 10 tests
  - Vector search
  - SQL fallback
  - Hybrid mode
  - Citation extraction

- [ ] **Conversation Persistence**: 8 tests
  - Create conversation
  - Add messages
  - Retrieve history
  - Update metadata

- [ ] **API Endpoints**: 20 tests d'intégration
  - /api/chat endpoints
  - /api/admin endpoints
  - /api/digest endpoints
  - Error handling

#### Tests Frontend (Target: 60% coverage)

- [ ] **Tests Composants** (Vitest)
  - MainChatPage
  - ChainOfThoughts
  - EmailCard
  - ProfessionalCoT

- [ ] **Tests E2E** (Playwright)
  - Upload document → Query RAG
  - SQL query natural language → Display results
  - Generate email → Preview → Send
  - Generate digest → Filter by urgency

**Livrable**: ✅ Coverage backend >80%, frontend >60%

---

## 📊 Semaine 3: Monitoring & Performance (P1)

### Monitoring Production

#### Error Tracking
- [ ] **Sentry** configuration
  - DSN dans .env.production
  - Source maps upload
  - Release tracking
  - User context

#### Metrics & Alerting
- [ ] **Prometheus** + **Grafana** setup
  - Backend metrics (requests, latency, errors)
  - Database metrics (connections, queries, slow queries)
  - Redis metrics (cache hit rate, memory)
  - System metrics (CPU, RAM, disk)

- [ ] **AlertManager** configuration
  - API p95 latency >2s
  - Error rate >1%
  - Database connections >80%
  - Disk usage >85%

#### Logging
- [ ] **Structured logging** partout (structlog)
- [ ] **Log aggregation** (Loki ou CloudWatch)
- [ ] **Log rotation** (7 jours retention)
- [ ] **Health checks** détaillés:
  - /health/db
  - /health/redis
  - /health/qdrant
  - /health/gmail

### Performance Optimization

- [ ] **Query optimization**: EXPLAIN ANALYZE sur requêtes lentes
- [ ] **Database indexing**: Vérifier indexes sur FK
- [ ] **Cache Redis**: Notifications, stats dashboard
- [ ] **Connection pooling**: asyncpg pool size 20
- [ ] **Frontend bundle**: <200KB gzipped (actuellement 273KB)

**Livrable**: ✅ Monitoring opérationnel + Alerting configuré

---

## 📚 Semaine 4: Documentation & Deployment (P2)

### Documentation

#### Documentation Utilisateur
- [ ] **Quick Start Guide** (5 minutes)
- [ ] **FAQ** (20+ questions fréquentes)
- [ ] **Troubleshooting Guide** (10+ problèmes communs)
- [ ] **Video Tutorials** (3-5 use cases):
  - Recherche documents RAG
  - Génération emails
  - Utilisation digest quotidien

#### Documentation Technique
- [ ] **API Documentation** (OpenAPI/Swagger)
- [ ] **Architecture Decision Records** (ADRs)
- [ ] **Deployment Guide** (step-by-step VPS)
- [ ] **Contributing Guide** (dev onboarding)
- [ ] **Changelog** maintenu (CHANGELOG.md)

### VPS Deployment

#### Infrastructure VPS

- [ ] **Serveur provisionné**:
  - OS: Ubuntu 22.04 LTS
  - RAM: 8GB minimum
  - CPU: 4 cores minimum
  - Disk: 100GB SSD

- [ ] **Docker & Docker Compose** installés (version >20)
- [ ] **Nginx** configuré:
  - Reverse proxy
  - SSL/TLS (Let's Encrypt)
  - Rate limiting
  - Gzip compression

- [ ] **Firewall** (ufw):
  - Port 80 (HTTP redirect)
  - Port 443 (HTTPS)
  - Port 22 (SSH, IP restreint)
  - Tous autres ports fermés

#### Deployment Steps

- [ ] **Clone repository**: `git clone`
- [ ] **Environment variables**: Copier .env.example → .env.production
- [ ] **Generate secrets**: SECRET_KEY, DB passwords
- [ ] **Build images**: `docker-compose build`
- [ ] **Start services**: `docker-compose up -d`
- [ ] **Run migrations**: `docker exec -it backend alembic upgrade head`
- [ ] **Verify services**: Check /health endpoints
- [ ] **SSL certificates**: `certbot --nginx`
- [ ] **Backup setup**: Automated daily backups (PostgreSQL + documents)

#### Post-Deployment

- [ ] **Smoke tests**:
  - Frontend accessible (HTTPS)
  - Login fonctionnel
  - Chat assistant operational
  - Admin panel accessible
  - Digest generation works

- [ ] **Monitoring dashboards**: Grafana configuré
- [ ] **Alerting**: Tester notifications (email/Slack)
- [ ] **Backup restore**: Tester une fois
- [ ] **Documentation déploiement**: Finaliser

**Livrable**: ✅ DisruptIQ déployé en production sur VPS

---

## 🎯 Critères de Validation Production

### Critères GO/NO-GO

#### ✅ GO si:
- ✅ 0 vulnérabilités critiques
- ✅ Tests coverage backend >75%
- ✅ Frontend build sans erreurs
- ✅ Alembic migrations fonctionnelles
- ✅ Monitoring configuré
- ✅ Documentation complète
- ✅ Smoke tests passent

#### ❌ NO-GO si:
- ❌ Vulnérabilités critiques présentes
- ❌ Tests coverage <70%
- ❌ Build errors frontend
- ❌ Pas de monitoring
- ❌ Migrations DB manquantes

---

## 📈 Post-Production (Semaines 5-8)

### Week 5-6: Stabilisation

- [ ] **Monitoring actif** 24/7
- [ ] **Hotfixes** si bugs critiques
- [ ] **Performance tuning** basé sur métriques réelles
- [ ] **User feedback** collection
- [ ] **NPS tracking** démarré

### Week 7-8: Optimisations

- [ ] **Load testing** (k6, locust)
- [ ] **Database optimization** (slow query log)
- [ ] **Cache strategy** refinement
- [ ] **Bundle optimization** (<150KB target)
- [ ] **Feature requests** priorisées

---

## 🔧 Outils & Commandes Utiles

### Alembic Migrations
```bash
# Créer une migration
alembic revision --autogenerate -m "description"

# Appliquer migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Tests
```bash
# Backend tests
pytest tests/ -v --cov=app --cov-report=html

# Frontend tests
npm run test
npm run test:e2e
```

### Docker Deployment
```bash
# Build production
docker-compose -f docker-compose.prod.yml build

# Start production
docker-compose -f docker-compose.prod.yml up -d

# Logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Health check
curl https://app.disruptiq.fr/health
```

### Monitoring
```bash
# Prometheus metrics
curl http://localhost:9090/metrics

# Grafana dashboards
http://grafana.disruptiq.fr

# Sentry errors
https://sentry.io/organizations/disruptiq
```

---

## 📋 Checklist Rapide

```
Week 1 - Sécurité:
[ ] SQL whitelist
[ ] Upload validation
[ ] Rate limiting
[ ] CORS config
[ ] Error masking
[ ] SECRET_KEY validation

Week 2 - Tests:
[ ] Tests Intent Classifier v3
[ ] Tests RAG Hybrid
[ ] Tests Conversation
[ ] Tests E2E Playwright
[ ] Coverage >75%

Week 3 - Monitoring:
[ ] Sentry setup
[ ] Prometheus + Grafana
[ ] AlertManager
[ ] Structured logging
[ ] Health checks

Week 4 - Deployment:
[ ] VPS provisioning
[ ] Docker deployment
[ ] SSL certificates
[ ] Smoke tests
[ ] Backup setup
[ ] Documentation
```

---

## 🎯 Objectifs Post-Production

**Objectif 1 mois**:
- ✅ 1-3 clients actifs
- ✅ Uptime >99%
- ✅ NPS >8/10
- ✅ 0 incidents critiques

**Objectif 3 mois**:
- ✅ 5-10 clients actifs
- ✅ MRR 5k€+
- ✅ Uptime >99.5%
- ✅ Features v4.0 planifiées

---

*Document vivant - Dernière mise à jour: 6 Novembre 2025*
*Prochaine révision: Post-deployment Week 4*
